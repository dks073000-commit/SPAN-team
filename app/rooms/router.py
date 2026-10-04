"""방 레인: /, /r/{code}, /api/rooms/..."""

import secrets
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from app.db import connect, fetch_all, fetch_one
from app.rooms.pin import LOCK_MINUTES, MAX_FAILS, check_pin, hash_pin

STATIC = Path(__file__).resolve().parents[2] / "static" / "rooms"

# 헷갈리는 글자(0, o, 1, l, i)를 뺀 방 코드 글자
CODE_CHARS = "abcdefghjkmnpqrstuvwxyz23456789"
CODE_LENGTH = 6

router = APIRouter()


@router.get("/", include_in_schema=False)
def create_page():
    return FileResponse(STATIC / "index.html")


@router.get("/r/{code}", include_in_schema=False)
def room_page(code: str):
    return FileResponse(STATIC / "room.html")


@router.get("/api/rooms")
def rooms_status():
    return {"lane": "rooms", "ok": True}


class RoomIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    start_date: date
    end_date: date
    upload_cycle: int = Field(default=7, ge=1, le=31)        # 일. 기본 주 1회
    deadline_weekday: int = Field(default=6, ge=0, le=6)     # 0=월 ... 6=일

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("방 이름을 넣어 주세요")
        return v


@router.post("/api/rooms", status_code=201)
def create_room(room: RoomIn):
    """방을 만들고 코드를 돌려준다. 공유 링크는 /r/{code}."""
    if room.end_date < room.start_date:
        raise HTTPException(422, "종료일이 시작일보다 빠릅니다")
    with connect() as conn:
        for _ in range(5):
            code = "".join(secrets.choice(CODE_CHARS) for _ in range(CODE_LENGTH))
            row = conn.execute(
                """
                insert into rooms (code, name, start_date, end_date, upload_cycle, deadline_weekday)
                values (%s, %s, %s, %s, %s, %s)
                on conflict (code) do nothing
                returning code
                """,
                (code, room.name, room.start_date, room.end_date, room.upload_cycle, room.deadline_weekday),
            ).fetchone()
            if row:
                return {"code": row["code"], "path": f"/r/{row['code']}"}
    raise HTTPException(500, "방 코드를 만들지 못했습니다. 다시 시도해 주세요")


@router.get("/api/rooms/{code}")
def get_room(code: str):
    """방 정보와 멤버 목록."""
    room = fetch_one(
        "select code, name, start_date, end_date, upload_cycle, deadline_weekday from rooms where code = %s",
        (code,),
    )
    if room is None:
        raise HTTPException(404, "없는 방입니다")
    # has_pin: 이름을 눌러 4자리로 다시 들어올 수 있는지. 해시는 내보내지 않는다
    room["members"] = fetch_all(
        "select id, nickname, budget, pin_hash is not null as has_pin from members where room_code = %s order by id",
        (code,),
    )
    return room


PIN = Field(pattern=r"^[0-9]{4}$")                         # 숫자 4자리 (다시 들어오기용)


class MemberIn(BaseModel):
    nickname: str = Field(min_length=1, max_length=20)
    budget: int = Field(gt=0, le=100_000_000)                # 원
    pin: str = PIN

    @field_validator("nickname")
    @classmethod
    def strip_nickname(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("닉네임을 넣어 주세요")
        return v


@router.post("/api/rooms/{code}/members", status_code=201)
def join_room(code: str, member: MemberIn):
    """닉네임 · 예산 · 숫자 4자리로 참여한다. 돌려준 id 를 브라우저가 member_id:{code} 로 저장한다."""
    with connect() as conn:
        if conn.execute("select 1 from rooms where code = %s", (code,)).fetchone() is None:
            raise HTTPException(404, "없는 방입니다")
        taken = conn.execute(
            "select 1 from members where room_code = %s and nickname = %s", (code, member.nickname)
        ).fetchone()
        if taken:
            raise HTTPException(409, "이미 있는 닉네임입니다")
        return conn.execute(
            """
            insert into members (room_code, nickname, budget, pin_hash) values (%s, %s, %s, %s)
            returning id, nickname, budget
            """,
            (code, member.nickname, member.budget, hash_pin(member.pin)),
        ).fetchone()


class RejoinIn(BaseModel):
    pin: str = PIN


@router.post("/api/rooms/{code}/members/{member_id}/rejoin")
def rejoin_room(code: str, member_id: int, body: RejoinIn):
    """다른 브라우저에서 다시 들어오기: 방 홈에서 내 이름을 누르고 4자리를 넣는다.

    맞으면 멤버를 돌려주고 브라우저가 member_id:{code} 로 저장한다 (참여와 같다).
    5번 연속 틀리면 10분 동안 맞는 4자리도 받지 않는다 (429).
    """
    with connect() as conn:
        # for update: 동시에 여러 번 눌러도 틀린 횟수가 정확히 쌓이게 한다
        m = conn.execute(
            """
            select id, nickname, budget, pin_hash, pin_fails, pin_locked_until > now() as locked
            from members where room_code = %s and id = %s for update
            """,
            (code, member_id),
        ).fetchone()
        if m is None:
            raise HTTPException(404, "이 방에 없는 멤버입니다")
        if m["pin_hash"] is None:
            raise HTTPException(403, "4자리를 정하지 않은 멤버라 다시 들어올 수 없습니다")
        if m["locked"]:
            raise HTTPException(429, f"여러 번 틀려서 잠겼어요. {LOCK_MINUTES}분 뒤에 다시 해 주세요")
        if check_pin(body.pin, m["pin_hash"]):
            conn.execute("update members set pin_fails = 0, pin_locked_until = null where id = %s", (m["id"],))
            return {"id": m["id"], "nickname": m["nickname"], "budget": m["budget"]}
        fails = m["pin_fails"] + 1
        if fails >= MAX_FAILS:
            conn.execute(
                "update members set pin_fails = 0, pin_locked_until = now() + make_interval(mins => %s) where id = %s",
                (LOCK_MINUTES, m["id"]),
            )
        else:
            conn.execute("update members set pin_fails = %s where id = %s", (fails, m["id"]))
    # 틀린 횟수는 위 블록이 끝날 때 저장된다 (블록 안에서 에러를 내면 되돌려진다)
    if fails >= MAX_FAILS:
        raise HTTPException(429, f"여러 번 틀려서 잠겼어요. {LOCK_MINUTES}분 뒤에 다시 해 주세요")
    raise HTTPException(401, f"4자리가 맞지 않아요 (남은 기회 {MAX_FAILS - fails}번)")
