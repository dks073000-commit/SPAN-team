"""30일 자동 삭제 (app/rooms/cleanup.py). DB 가 없으면 건너뛴다.

날짜는 오늘(DB 의 current_date)에서 거꾸로 센다: 마감 + 30일이 오늘이면 아직 보관, 마감 + 31일이 오늘이면 지운다.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.rooms.cleanup import purge_expired_rooms

client = TestClient(app)

needs_db = pytest.mark.skipif(not db.ping(), reason="DATABASE_URL 로 DB 에 접속할 수 없음")

ACCOUNT = "BTG00000000000000000000A"


def today():
    return db.fetch_one("select current_date as d")["d"]


def make_room(days_after_end):
    """마감일이 오늘보다 days_after_end 일 앞인 방을 만들고, 멤버 1명 · 지출 1건을 넣는다."""
    end = today() - timedelta(days=days_after_end)
    room = {"name": "지난 방", "start_date": str(end - timedelta(days=6)), "end_date": str(end)}
    code = client.post("/api/rooms", json=room).json()["code"]
    member = db.fetch_one(
        "insert into members (room_code, nickname, budget, fintech_use_num) values (%s, '지수', 50000, %s) returning id",
        (code, ACCOUNT),
    )
    db.execute(
        "insert into expenses (member_id, spent_on, merchant, amount, source) values (%s, %s, '편의점', 3000, 'manual')",
        (member["id"], end),
    )
    return code, member["id"]


def exists(code):
    return db.fetch_one("select 1 from rooms where code = %s", (code,)) is not None


def purge():
    with db.connect() as conn:
        return purge_expired_rooms(conn)


@pytest.fixture
def rooms():
    made = []
    yield made
    for code in made:
        db.execute("delete from rooms where code = %s", (code,))


@needs_db
def test_keeps_room_until_30_days_after_end(rooms):
    code, _ = make_room(30)              # 마감 다음 날부터 30일째 = 오늘. 아직 보관
    rooms.append(code)
    assert code not in purge()
    assert exists(code)


@needs_db
def test_deletes_room_with_members_and_expenses(rooms):
    code, member_id = make_room(31)      # 30일이 지났다
    rooms.append(code)
    assert code in purge()
    assert not exists(code)
    # on delete cascade: 멤버와 지출도 같이 지워진다
    assert db.fetch_one("select 1 from members where id = %s", (member_id,)) is None
    assert db.fetch_one("select 1 from expenses where member_id = %s", (member_id,)) is None


@needs_db
def test_opening_expired_room_is_404(rooms):
    code, _ = make_room(31)
    rooms.append(code)
    assert client.get(f"/api/rooms/{code}").status_code == 404
    assert not exists(code)              # 404 를 내도 지운 것은 되돌리지 않는다


@needs_db
def test_creating_room_deletes_expired_rooms(rooms):
    old, _ = make_room(40)
    rooms.append(old)
    rooms.append(client.post("/api/rooms", json={"name": "새 방", "start_date": str(today()), "end_date": str(today())}).json()["code"])
    assert not exists(old)


@needs_db
def test_ongoing_room_is_kept(rooms):
    code, _ = make_room(-3)              # 아직 진행 중 (마감이 3일 뒤)
    rooms.append(code)
    purge()
    assert client.get(f"/api/rooms/{code}").status_code == 200


@needs_db
def test_demo_room_is_never_deleted():
    # 데모 방은 seed.sql 의 가짜 데이터라 기간이 지나도 남긴다
    end = db.fetch_one("select end_date from rooms where code = 'demo'")
    if end is None:
        pytest.skip("데모 방이 없음 (python -m app.db init)")
    db.execute("update rooms set end_date = current_date - 100, start_date = current_date - 106 where code = 'demo'")
    try:
        assert "demo" not in purge()
        assert exists("demo")
    finally:
        db.execute("update rooms set start_date = date '2026-10-02', end_date = %s where code = 'demo'", (end["end_date"],))


def test_server_start_runs_cleanup_without_db(monkeypatch):
    # DB 가 안 닿아도 서버는 떠야 한다 (지우기 실패는 기록만)
    import app.rooms.router as rooms_router

    def broken():
        raise RuntimeError("DB 없음")

    monkeypatch.setattr(rooms_router, "connect", broken)
    with TestClient(app) as c:
        assert c.get("/api/health").json() == {"ok": True}

