"""방 레인: /, /r/{code}, /api/rooms/..."""

import secrets
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from app.db import connect, fetch_all, fetch_one

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
    room["members"] = fetch_all(
        "select id, nickname, budget from members where room_code = %s order by id",
        (code,),
    )
    return room


class MemberIn(BaseModel):
    nickname: str = Field(min_length=1, max_length=20)
    budget: int = Field(gt=0, le=100_000_000)                # 원

    @field_validator("nickname")
    @classmethod
    def strip_nickname(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("닉네임을 넣어 주세요")
        return v


@router.post("/api/rooms/{code}/members", status_code=201)
def join_room(code: str, member: MemberIn):
    """닉네임과 예산으로 참여한다. 돌려준 id 를 브라우저가 member_id:{code} 로 저장한다."""
    with connect() as conn:
        if conn.execute("select 1 from rooms where code = %s", (code,)).fetchone() is None:
            raise HTTPException(404, "없는 방입니다")
        taken = conn.execute(
            "select 1 from members where room_code = %s and nickname = %s", (code, member.nickname)
        ).fetchone()
        if taken:
            raise HTTPException(409, "이미 있는 닉네임입니다")
        return conn.execute(
            "insert into members (room_code, nickname, budget) values (%s, %s, %s) returning id, nickname, budget",
            (code, member.nickname, member.budget),
        ).fetchone()
