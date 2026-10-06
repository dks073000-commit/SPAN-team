"""본인 페이지 API: 불러오기 → 고치기 → 조정 완료, 마감 반영. DB 가 없으면 건너뛴다.

테스트용 방을 따로 만들고 끝나면 지운다 (데모 방은 건드리지 않는다).
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import db
from app.expenses.mockbank import router as mockbank
from app.main import app
from app.rooms.pin import hash_pin

client = TestClient(app)
pytestmark = pytest.mark.skipif(not db.ping(), reason="DATABASE_URL 로 DB 에 접속할 수 없음")

A = "BTG00000000000000000000A"
CODE = "zzexpensetest"
PIN = "1234"


def set_now(monkeypatch, when):
    monkeypatch.setattr(mockbank, "now_kst", lambda: when)


@pytest.fixture
def room(monkeypatch):
    set_now(monkeypatch, datetime(2026, 10, 7, 23, 59))  # 발표 전날 밤: 택시까지 일어났고 치킨은 아직
    db.execute("delete from rooms where code = %s", (CODE,))
    db.execute(
        "insert into rooms (code, name, start_date, end_date) values (%s, '지출 테스트', date '2026-10-02', date '2026-10-08')",
        (CODE,),
    )
    ids = {}
    for nickname, budget, account, pin in [("발표자", 100000, A, PIN), ("예시", 50000, None, "5678"), ("4자리없음", 50000, A, None)]:
        ids[nickname] = db.fetch_one(
            "insert into members (room_code, nickname, budget, fintech_use_num, pin_hash) values (%s, %s, %s, %s, %s) returning id",
            (CODE, nickname, budget, account, hash_pin(pin) if pin else None),
        )["id"]
    yield ids
    db.execute("delete from rooms where code = %s", (CODE,))


def auth(pin=PIN):
    return {"X-Member-Pin": pin}


def load(member_id, pin=PIN):
    return client.post("/api/expenses/import", json={"member_id": member_id}, headers=auth(pin)).json()


def me(member_id, pin=PIN):
    return client.get("/api/expenses/me", params={"member_id": member_id}, headers=auth(pin)).json()


def confirm(member_id):
    return client.post("/api/expenses/confirm", json={"member_id": member_id}, headers=auth()).json()


def item(summary, merchant, nth=0):
    return [i for i in summary["items"] if i["merchant"] == merchant][nth]


def patch(member_id, expense_id, pin=PIN, **fields):
    return client.patch(f"/api/expenses/{expense_id}", json={"member_id": member_id, **fields}, headers=auth(pin))


def test_presenter_demo_flow(room, monkeypatch):
    me_id = room["발표자"]

    # 1~6일째 불러오기 (전날). 방 기간 안 출금만
    first = load(me_id)
    assert first["added"] == 9 and first["summary"]["status"] == "미확인"
    assert load(me_id)["added"] == 0  # 다시 눌러도 두 번 저장되지 않음

    # 결제 시간: 시간 칸이 비어 있던 예전 행도 다시 불러오면 채워진다
    db.execute("update expenses set spent_time = null where member_id = %s", (me_id,))
    assert load(me_id)["added"] == 0
    assert all(len(i["time"]) == 5 and i["time"][2] == ":" for i in me(me_id)["items"])

    s = me(me_id)
    taxis = {i["amount"]: i for i in s["items"] if i["merchant"] == "택시"}
    assert taxis[20000]["badges"] == ["자동 제외 · 가승인"] and taxis[20000]["excluded"] and taxis[20000]["auto"]
    assert taxis[9800]["badges"] == [] and not taxis[9800]["excluded"]
    assert all(i["date"] >= "2026-10-02" for i in s["items"])  # 기간 밖은 저장하지 않음
    for name in ["간편결제충전", "이예시"]:  # 꼬리표만 달고 포함 (본인이 제외를 고른다, /flow 와 같다)
        assert (item(s, name)["badges"], item(s, name)["excluded"]) == (["충전·내 계좌 이체일 수 있어요"], False)
    assert item(s, "편의점")["badges"] == ["중복일 수 있어요"]

    # 발표 전 정리: 통신비 · 충전 · 내 계좌 이체 · 편의점 한 건 제외, 조정 완료
    for name, nth in [("통신비", 0), ("간편결제충전", 0), ("이예시", 0), ("편의점", 1)]:
        patch(me_id, item(s, name, nth)["id"], excluded=True)
    s = confirm(me_id)
    assert (s["spent"], s["status"]) == (26400, "조정 완료")

    # 발표 당일: 치킨이 1명으로 들어오면 다시 미확인
    set_now(monkeypatch, datetime(2026, 10, 8, 17, 0))
    res = load(me_id)
    assert res["added"] == 1 and res["message"] == "새로 1건 들어왔어요"
    s = res["summary"]
    chicken = item(s, "치킨집")
    assert (chicken["my_share"], chicken["badges"], s["status"], s["spent"]) == (48000, ["새로 들어옴"], "미확인", 74400)

    # 4명으로 고치고 조정 완료
    s = patch(me_id, chicken["id"], people=4).json()
    assert (item(s, "치킨집")["my_share"], s["spent"], s["remaining"]) == (12000, 38400, 61600)
    s = confirm(me_id)
    assert s["status"] == "조정 완료"


def test_cannot_touch_someone_elses_item(room):
    load(room["발표자"])
    target = me(room["발표자"])["items"][0]["id"]
    assert patch(room["예시"], target, pin="5678", people=2).status_code == 404


def test_member_without_account_cannot_import(room):
    res = client.post("/api/expenses/import", json={"member_id": room["예시"]}, headers=auth("5678"))
    assert res.status_code == 409


def test_member_id_alone_is_not_enough(room):
    """주소의 member_id 만 바꿔서는 남의 상세를 보거나 고칠 수 없다 (10/6)."""
    me_id = room["발표자"]
    load(me_id)
    target = me(me_id)["items"][0]["id"]
    assert client.get("/api/expenses/me", params={"member_id": me_id}).status_code == 401
    assert client.get("/api/expenses/me", params={"member_id": me_id}, headers=auth("0000")).status_code == 401
    assert client.post("/api/expenses/import", json={"member_id": me_id}).status_code == 401
    assert client.post("/api/expenses/confirm", json={"member_id": me_id}).status_code == 401
    assert patch(me_id, target, pin="5678", people=2).status_code == 401  # 다른 사람의 4자리


def test_member_without_pin_cannot_open(room):
    assert client.get("/api/expenses/me", params={"member_id": room["4자리없음"]}, headers=auth()).status_code == 403


def test_gave_up_member_cannot_change(room):
    load(room["발표자"])
    db.execute("update members set gave_up_at = now() where id = %s", (room["발표자"],))
    target = me(room["발표자"])["items"][0]["id"]
    assert patch(room["발표자"], target, people=2).status_code == 409
    assert me(room["발표자"])["status"] == "항복"


def test_settle_fills_members_with_accounts_and_skips_others(room):
    res = client.post(f"/api/expenses/rooms/{CODE}/settle").json()
    by_name = {m["nickname"]: m for m in res["members"]}
    assert by_name["발표자"]["added"] == 9
    assert by_name["예시"]["skipped"] == "계좌 없음"
    assert set(res) == {"room", "today", "members"}  # 응답 모양은 그대로 (결과 카드 board.js 가 부른다)
    again = client.post(f"/api/expenses/rooms/{CODE}/settle").json()
    assert {m["nickname"]: m.get("added") for m in again["members"]}["발표자"] == 0
    assert "items" not in str(res)  # 상세는 돌려주지 않음


def test_settle_unknown_room():
    assert client.post("/api/expenses/rooms/nope-nope/settle").status_code == 404


def test_badge_says_recommended_when_user_puts_auto_excluded_back(room):
    me_id = room["발표자"]
    load(me_id)
    taxi = next(i for i in me(me_id)["items"] if i["merchant"] == "택시" and i["amount"] == 20000)
    s = patch(me_id, taxi["id"], excluded=False).json()
    taxi = next(i for i in s["items"] if i["id"] == taxi["id"])
    assert taxi["badges"] == ["가승인 · 제외 권장"] and taxi["my_share"] == 20000


def test_spent_matches_board_rounding(room):
    me_id = room["발표자"]
    db.execute(
        "insert into expenses (member_id, spent_on, merchant, amount, people, excluded, source) values "
        "(%s, date '2026-10-03', '모임', 10000, 3, false, 'manual'), (%s, date '2026-10-03', '모임2', 10000, 3, false, 'manual')",
        (me_id, me_id),
    )
    s = me(me_id)
    assert [i["my_share"] for i in s["items"]] == [3333, 3333]
    assert s["spent"] == 6666  # 항목마다 반올림한 3,333 + 3,333 (보드 calc.py 와 같은 규칙)
    db.execute(
        "insert into expenses (member_id, spent_on, merchant, amount, people, excluded, source) values "
        "(%s, date '2026-10-03', '반올림', 5, 2, false, 'manual')",
        (me_id,),
    )
    assert me(me_id)["spent"] == 6666 + 3  # 2.5 → 3 (0.5 는 올림)


def test_editing_after_confirm_needs_confirm_again(room):
    me_id = room["발표자"]
    load(me_id)
    assert confirm(me_id)["status"] == "조정 완료"
    target = me(me_id)["items"][0]["id"]
    assert patch(me_id, target, people=2).json()["status"] == "미확인"
