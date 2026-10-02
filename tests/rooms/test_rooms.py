"""방 만들기와 참여. DB 가 없으면 DB 가 필요한 테스트는 건너뛴다."""

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app

client = TestClient(app)

needs_db = pytest.mark.skipif(not db.ping(), reason="DATABASE_URL 로 DB 에 접속할 수 없음")

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
    res = client.post("/api/rooms/demo/members", json={"nickname": "a", "budget": 0})
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
    res = client.post(f"/api/rooms/{room_code}/members", json={"nickname": " 지수 ", "budget": 80000})
    assert res.status_code == 201
    member = res.json()
    assert member["nickname"] == "지수"
    members = client.get(f"/api/rooms/{room_code}").json()["members"]
    assert [m["id"] for m in members] == [member["id"]]


@needs_db
def test_duplicate_nickname(room_code):
    client.post(f"/api/rooms/{room_code}/members", json={"nickname": "지수", "budget": 80000})
    res = client.post(f"/api/rooms/{room_code}/members", json={"nickname": "지수", "budget": 50000})
    assert res.status_code == 409


@needs_db
def test_unknown_room():
    assert client.get("/api/rooms/nope99").status_code == 404
    res = client.post("/api/rooms/nope99/members", json={"nickname": "a", "budget": 1000})
    assert res.status_code == 404
