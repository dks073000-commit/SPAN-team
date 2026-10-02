"""방 레인: /, /r/{code}, /api/rooms/..."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.db import fetch_all, fetch_one

STATIC = Path(__file__).resolve().parents[2] / "static" / "rooms"

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
