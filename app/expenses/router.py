"""지출 레인: /r/{code}/add, /api/expenses/..."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.db import fetch_all

STATIC = Path(__file__).resolve().parents[2] / "static" / "expenses"

router = APIRouter()


@router.get("/r/{code}/add", include_in_schema=False)
def add_page(code: str):
    return FileResponse(STATIC / "add.html")


@router.get("/api/expenses")
def list_expenses(room_code: str | None = None):
    """room_code 를 주면 그 방에 저장된 지출을 돌려준다 (뼈대 확인용)."""
    if room_code is None:
        return {"lane": "expenses", "ok": True}
    return fetch_all(
        """
        select e.id, e.member_id, e.spent_on, e.merchant, e.amount, e.people, e.excluded, e.source, e.ref
        from expenses e join members m on m.id = e.member_id
        where m.room_code = %s
        order by e.spent_on, e.id
        """,
        (room_code,),
    )
