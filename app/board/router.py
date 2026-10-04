"""보드 레인: /r/{code}/board (마감일 결과 카드), /api/board/..."""

from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.board.calc import build_board
from app.db import connect

STATIC = Path(__file__).resolve().parents[2] / "static" / "board"

router = APIRouter()


@router.get("/r/{code}/board", include_in_schema=False)
def board_page(code: str):
    return FileResponse(STATIC / "board.html")


# 시연용 전체 흐름: 방 만들기 → 참여 → 내 페이지 → 결과 카드를 보드 레인 UI로 끊김 없이 보여 준다.
# 데이터는 브라우저에만 저장하는 가짜 데이터다 (static/board/flow/store.js). 실제 화면은 각 레인의 주소에 있다.
FLOW = STATIC / "flow"


@router.get("/flow", include_in_schema=False)
def flow_create():
    return FileResponse(FLOW / "index.html")


@router.get("/flow/r/{code}", include_in_schema=False)
def flow_room(code: str):
    return FileResponse(FLOW / "room.html")


@router.get("/flow/r/{code}/me", include_in_schema=False)
def flow_me(code: str):
    return FileResponse(FLOW / "me.html")


@router.get("/flow/r/{code}/board", include_in_schema=False)
def flow_board(code: str):
    return FileResponse(STATIC / "board.html")


@router.get("/api/board")
def board_status():
    return {"lane": "board", "ok": True}


def load_board_rows(code: str):
    """방, 멤버, 지출을 읽는다. 없는 방이면 None.

    지출은 합계 계산에 필요한 칸만 읽는다. 상호(merchant)는 읽지 않는다.
    """
    with connect() as conn:
        room = conn.execute(
            "select code, name, start_date, end_date from rooms where code = %s",
            (code,),
        ).fetchone()
        if room is None:
            return None
        members = conn.execute(
            "select id, nickname, budget, confirmed_at, gave_up_at from members where room_code = %s order by id",
            (code,),
        ).fetchall()
        expenses = conn.execute(
            """
            select e.member_id, e.amount, e.people, e.excluded, e.created_at
            from expenses e join members m on m.id = e.member_id
            where m.room_code = %s
            """,
            (code,),
        ).fetchall()
    return room, members, expenses


@router.get("/api/board/{code}")
def get_board(code: str, preview: bool = False):
    """마감일 결과 카드 데이터. 칸 이름은 단톡방에 공유한 약속이다. 바꾸기 전에 팀에 먼저 말한다.

    마감일 전에는 순위를 내보내지 않는다 (members 가 빈 목록). preview=1 은 시연용 미리 보기다.
    거래 항목(상호, 개별 금액)은 내보내지 않는다. 합계만 돌려준다.
    """
    # TODO(지출 레인 API 이름이 정해지면): 마감일에는 결과를 만들기 전에
    # 아직 안 불러온 멤버의 내역을 지출 레인의 마감 자동 반영 API로 채운다 (BUILD_ORDER "마감 자동 반영").
    rows = load_board_rows(code)
    if rows is None:
        raise HTTPException(404, "없는 방입니다")
    room, members, expenses = rows
    # 서버와 DB 는 한국 시간이다 (render.yaml 의 TZ, app/db.py). 오늘은 한국 날짜
    return build_board(room, members, expenses, date.today(), preview=preview)
