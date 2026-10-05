"""방 레인: /, /r/{code}, /api/rooms/..."""

import secrets
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from app.db import connect, fetch_all, fetch_one
from app.rooms.pin import check_pin, hash_pin

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
# 가짜 은행 계좌 연결에서 돌려받은 핀테크이용번호. 연결 없이는 참여할 수 없다 (미제출을 없애기 위해, 10/3)
FINTECH_USE_NUM = Field(pattern=r"^[A-Za-z0-9]{1,40}$")


class MemberIn(BaseModel):
    nickname: str = Field(min_length=1, max_length=20)
    budget: int = Field(gt=0, le=100_000_000)                # 원
    pin: str = PIN
    fintech_use_num: str = FINTECH_USE_NUM

    @field_validator("nickname")
    @classmethod
    def strip_nickname(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("닉네임을 넣어 주세요")
        return v


@router.post("/api/rooms/{code}/members", status_code=201)
def join_room(code: str, member: MemberIn):
    """닉네임 · 예산 · 숫자 4자리 · 연결한 가상 계좌로 참여한다. 돌려준 id 를 브라우저가 member_id:{code} 로 저장한다.

    계좌는 가짜 은행 화면(/api/expenses/mockbank/oauth/2.0/authorize)에서 고르고, 돌아온 fintech_use_num 을 받는다.
    """
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
            insert into members (room_code, nickname, budget, pin_hash, fintech_use_num) values (%s, %s, %s, %s, %s)
            returning id, nickname, budget
            """,
            (code, member.nickname, member.budget, hash_pin(member.pin), member.fintech_use_num),
        ).fetchone()


class RejoinIn(BaseModel):
    pin: str = PIN


@router.post("/api/rooms/{code}/members/{member_id}/rejoin")
def rejoin_room(code: str, member_id: int, body: RejoinIn):
    """다른 브라우저에서 다시 들어오기: 방 홈에서 내 이름을 누르고 4자리를 넣는다.

    맞으면 멤버를 돌려주고 브라우저가 member_id:{code} 로 저장한다 (참여와 같다).
    """
    m = fetch_one(
        "select id, nickname, budget, pin_hash from members where room_code = %s and id = %s",
        (code, member_id),
    )
    if m is None:
        raise HTTPException(404, "이 방에 없는 멤버입니다")
    if m["pin_hash"] is None:
        raise HTTPException(403, "4자리를 정하지 않은 멤버라 다시 들어올 수 없습니다")
    if not check_pin(body.pin, m["pin_hash"]):
        raise HTTPException(401, "4자리가 맞지 않아요")
    return {"id": m["id"], "nickname": m["nickname"], "budget": m["budget"]}


@router.post("/api/rooms/{code}/members/{member_id}/give-up")
def give_up(code: str, member_id: int):
    """항복(중도포기): 본인 페이지의 [항복하기] 버튼이 부른다. 되돌릴 수 없다.

    처음 누른 시각만 남긴다. 이미 항복했으면 그 시각 그대로 성공으로 돌려준다 (두 번 눌러도 같은 결과).
    """
    row = fetch_one(
        """
        update members set gave_up_at = coalesce(gave_up_at, now())
        where room_code = %s and id = %s
        returning id, gave_up_at
        """,
        (code, member_id),
    )
    if row is None:
        raise HTTPException(404, "이 방에 없는 멤버입니다")
    return {"member_id": row["id"], "gave_up_at": row["gave_up_at"]}
