"""본인 페이지 API: 불러오기 → 고치기 → 조정 완료, 마감 반영. DB 가 없으면 건너뛴다.

테스트용 방을 따로 만들고 끝나면 지운다 (데모 방은 건드리지 않는다).
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import db
from app.expenses.mockbank import router as mockbank
from app.main import app

client = TestClient(app)
pytestmark = pytest.mark.skipif(not db.ping(), reason="DATABASE_URL 로 DB 에 접속할 수 없음")

A = "BTG00000000000000000000A"
CODE = "zzexpensetest"


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
    for nickname, budget, account in [("발표자", 100000, A), ("예시", 50000, None)]:
        ids[nickname] = db.fetch_one(
            "insert into members (room_code, nickname, budget, fintech_use_num) values (%s, %s, %s, %s) returning id",
            (CODE, nickname, budget, account),
        )["id"]
    yield ids
    db.execute("delete from rooms where code = %s", (CODE,))


def load(member_id):
    return client.post("/api/expenses/import", json={"member_id": member_id}).json()


def me(member_id):
    return client.get("/api/expenses/me", params={"member_id": member_id}).json()


def item(summary, merchant, nth=0):
    return [i for i in summary["items"] if i["merchant"] == merchant][nth]


def patch(member_id, expense_id, **fields):
    return client.patch(f"/api/expenses/{expense_id}", json={"member_id": member_id, **fields})


def test_presenter_demo_flow(room, monkeypatch):
    me_id = room["발표자"]

    # 1~6일째 불러오기 (전날)
    first = load(me_id)
    assert first["added"] == 10 and first["summary"]["status"] == "미확인"
    assert load(me_id)["added"] == 0  # 다시 눌러도 두 번 저장되지 않음

    s = me(me_id)
    taxis = {i["amount"]: i for i in s["items"] if i["merchant"] == "택시"}
    assert taxis[20000]["badges"] == ["자동 제외 · 가승인"] and taxis[20000]["excluded"]
    assert taxis[9800]["badges"] == [] and not taxis[9800]["excluded"]
    assert item(s, "식당")["badges"] == ["자동 제외 · 기간 밖"]
    assert item(s, "간편결제충전")["badges"] == ["제외 후보 · 충전"]
    assert item(s, "이예시")["badges"] == ["제외 후보 · 내 계좌 이체"]
    assert item(s, "편의점")["badges"] == ["중복?"]

    # 발표 전 정리: 통신비 제외, 편의점 한 건 제외, 조정 완료
    patch(me_id, item(s, "통신비")["id"], excluded=True)
    patch(me_id, item(s, "편의점", 1)["id"], excluded=True)
    s = client.post("/api/expenses/confirm", json={"member_id": me_id}).json()
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
    s = client.post("/api/expenses/confirm", json={"member_id": me_id}).json()
    assert s["status"] == "조정 완료"


def test_cannot_touch_someone_elses_item(room):
    load(room["발표자"])
    target = me(room["발표자"])["items"][0]["id"]
    assert patch(room["예시"], target, people=2).status_code == 404


def test_member_without_account_cannot_import(room):
    res = client.post("/api/expenses/import", json={"member_id": room["예시"]})
    assert res.status_code == 409


def test_gave_up_member_cannot_change(room):
    load(room["발표자"])
    db.execute("update members set gave_up_at = now() where id = %s", (room["발표자"],))
    target = me(room["발표자"])["items"][0]["id"]
    assert patch(room["발표자"], target, people=2).status_code == 409
    assert me(room["발표자"])["status"] == "항복"


def test_settle_fills_members_with_accounts_and_skips_others(room):
    res = client.post(f"/api/expenses/rooms/{CODE}/settle").json()
    by_name = {m["nickname"]: m for m in res["members"]}
    assert by_name["발표자"]["added"] == 10
    assert by_name["예시"]["skipped"] == "계좌 없음"
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


def test_spent_rounds_once_like_the_formula(room):
    me_id = room["발표자"]
    db.execute(
        "insert into expenses (member_id, spent_on, merchant, amount, people, excluded, source) values "
        "(%s, date '2026-10-03', '모임', 10000, 3, false, 'manual'), (%s, date '2026-10-03', '모임2', 10000, 3, false, 'manual')",
        (me_id, me_id),
    )
    s = me(me_id)
    assert [i["my_share"] for i in s["items"]] == [3333, 3333]
    assert s["spent"] == 6667  # 10000/3 + 10000/3 = 6666.67 → 6667 (계산식 그대로 더한 뒤 반올림)
