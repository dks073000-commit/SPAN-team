"""방 만들기와 참여. DB 가 없으면 DB 가 필요한 테스트는 건너뛴다."""

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.rooms.pin import check_pin, hash_pin

client = TestClient(app)

needs_db = pytest.mark.skipif(not db.ping(), reason="DATABASE_URL 로 DB 에 접속할 수 없음")

ACCOUNT = "BTG00000000000000000000A"  # 가짜 은행 계좌 A

ROOM = {"name": "테스트 방", "start_date": "2026-10-02", "end_date": "2026-10-08"}


@pytest.fixture
def room_code():
    code = client.post("/api/rooms", json=ROOM).json()["code"]
    yield code
    db.execute("delete from rooms where code = %s", (code,))


def test_rejects_end_before_start():
    res = client.post("/api/rooms", json={**ROOM, "start_date": "2026-10-08", "end_date": "2026-10-02"})
    assert res.status_code == 422


def test_rejects_blank_name():
    assert client.post("/api/rooms", json={**ROOM, "name": "   "}).status_code == 422


def test_rejects_bad_budget():
    res = client.post("/api/rooms/demo/members", json={"nickname": "a", "budget": 0, "pin": "1234", "fintech_use_num": ACCOUNT})
    assert res.status_code == 422


@needs_db
def test_create_room_has_defaults(room_code):
    room = client.get(f"/api/rooms/{room_code}").json()
    assert room["name"] == "테스트 방"
    assert room["upload_cycle"] == 7
    assert room["deadline_weekday"] == 6
    assert room["members"] == []


@needs_db
def test_join_room(room_code):
    res = client.post(f"/api/rooms/{room_code}/members", json={"nickname": " 지수 ", "budget": 80000, "pin": "1234", "fintech_use_num": ACCOUNT})
    assert res.status_code == 201
    member = res.json()
    assert member["nickname"] == "지수"
    members = client.get(f"/api/rooms/{room_code}").json()["members"]
    assert [m["id"] for m in members] == [member["id"]]


@needs_db
def test_duplicate_nickname(room_code):
    client.post(f"/api/rooms/{room_code}/members", json={"nickname": "지수", "budget": 80000, "pin": "1234", "fintech_use_num": ACCOUNT})
    res = client.post(f"/api/rooms/{room_code}/members", json={"nickname": "지수", "budget": 50000, "pin": "1234", "fintech_use_num": ACCOUNT})
    assert res.status_code == 409


@needs_db
def test_unknown_room():
    assert client.get("/api/rooms/nope99").status_code == 404
    res = client.post("/api/rooms/nope99/members", json={"nickname": "a", "budget": 1000, "pin": "1234", "fintech_use_num": ACCOUNT})
    assert res.status_code == 404


# 다시 들어오기 (닉네임 + 숫자 4자리, 10/4)


def test_pin_hash_roundtrip():
    stored = hash_pin("0420")
    assert "0420" not in stored
    assert check_pin("0420", stored)
    assert not check_pin("0421", stored)
    assert hash_pin("0420") != stored          # 멤버마다 salt 가 달라 같은 숫자도 해시가 다르다
    assert not check_pin("0420", "망가진 값")


@pytest.mark.parametrize("pin", ["123", "12345", "abcd", "", "12 4"])
def test_rejects_bad_pin(pin):
    res = client.post("/api/rooms/demo/members", json={"nickname": "a", "budget": 1000, "pin": pin, "fintech_use_num": ACCOUNT})
    assert res.status_code == 422


def test_join_requires_pin():
    res = client.post("/api/rooms/demo/members", json={"nickname": "a", "budget": 1000, "fintech_use_num": ACCOUNT})
    assert res.status_code == 422


def join(code, nickname="지수", pin="1234"):
    return client.post(f"/api/rooms/{code}/members", json={"nickname": nickname, "budget": 80000, "pin": pin, "fintech_use_num": ACCOUNT}).json()


def rejoin(code, member_id, pin):
    return client.post(f"/api/rooms/{code}/members/{member_id}/rejoin", json={"pin": pin})


@needs_db
def test_rejoin_with_pin(room_code):
    me = join(room_code)
    res = rejoin(room_code, me["id"], "1234")
    assert res.status_code == 200
    assert res.json() == {"id": me["id"], "nickname": "지수", "budget": 80000}


@needs_db
def test_room_shows_has_pin_but_not_hash(room_code):
    join(room_code)
    member = client.get(f"/api/rooms/{room_code}").json()["members"][0]
    assert member["has_pin"] is True
    assert "pin_hash" not in member


@needs_db
def test_wrong_pin(room_code):
    me = join(room_code)
    assert rejoin(room_code, me["id"], "9999").status_code == 401
    assert rejoin(room_code, me["id"], "1234").status_code == 200


@needs_db
def test_rejoin_other_room_or_unknown_member(room_code):
    me = join(room_code)
    assert rejoin("demo", me["id"], "1234").status_code == 404   # 다른 방의 멤버 id
    assert rejoin(room_code, 999999999, "1234").status_code == 404


@needs_db
def test_member_without_pin_cannot_rejoin(room_code):
    me = join(room_code)
    db.execute("update members set pin_hash = null where id = %s", (me["id"],))
    assert rejoin(room_code, me["id"], "1234").status_code == 403


# 가상 계좌 연결 (10/5): 참여할 때 은행 연결 → 내 계좌 선택이 필수다


@pytest.mark.parametrize("account", [None, "", "BTG-0001", "a" * 41])
def test_join_requires_account(account):
    body = {"nickname": "a", "budget": 1000, "pin": "1234"}
    if account is not None:
        body["fintech_use_num"] = account
    assert client.post("/api/rooms/demo/members", json=body).status_code == 422


@needs_db
def test_join_saves_account(room_code):
    me = join(room_code)
    row = db.fetch_one("select fintech_use_num from members where id = %s", (me["id"],))
    assert row["fintech_use_num"] == ACCOUNT


# 항복 (10/3): gave_up_at 을 처음 누른 시각으로 기록한다. 되돌리기는 없다


def give_up(code, member_id):
    return client.post(f"/api/rooms/{code}/members/{member_id}/give-up")


@needs_db
def test_give_up_sets_time(room_code):
    me = join(room_code)
    res = give_up(room_code, me["id"])
    assert res.status_code == 200
    assert res.json()["member_id"] == me["id"]
    assert res.json()["gave_up_at"]
    row = db.fetch_one("select gave_up_at from members where id = %s", (me["id"],))
    assert row["gave_up_at"] is not None


@needs_db
def test_give_up_twice_keeps_first_time(room_code):
    me = join(room_code)
    first = give_up(room_code, me["id"]).json()["gave_up_at"]
    second = give_up(room_code, me["id"])
    assert second.status_code == 200
    assert second.json()["gave_up_at"] == first


@needs_db
def test_give_up_other_room_or_unknown_member(room_code):
    me = join(room_code)
    assert give_up("demo", me["id"]).status_code == 404   # 다른 방의 멤버 id
    assert give_up(room_code, 999999999).status_code == 404
    row = db.fetch_one("select gave_up_at from members where id = %s", (me["id"],))
    assert row["gave_up_at"] is None
