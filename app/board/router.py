"""보드 레인: /r/{code}/board, /api/board/..."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

STATIC = Path(__file__).resolve().parents[2] / "static" / "board"

router = APIRouter()


@router.get("/r/{code}/board", include_in_schema=False)
def board_page(code: str):
    return FileResponse(STATIC / "board.html")


@router.get("/api/board")
def board_status():
    return {"lane": "board", "ok": True}
