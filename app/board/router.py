"""보드 레인: /r/{code}/board (마감일 결과 카드), /api/board/..."""

from datetime import date
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.board.calc import build_board
from app.db import connect

STATIC = Path(__file__).resolve().parents[2] / "static" / "board"

router = APIRouter()


@router.get("/r/{code}/board", include_in_schema=False)
def board_page(code: str):
    return FileResponse(STATIC / "board.html")


# 발표용 입구 /flow: 이 브라우저에 "발표 모드"를 켜고 실제 방 만들기(/)로 보낸다.
# 화면 · 기능은 전부 실제 서비스 것이고, 발표하는 브라우저에서만 위에 시연 막대가 뜬다 (static/board/flow/demo-bar.js).
# 그래서 시연 중 만든 방 링크는 진짜 링크다 (다른 폰에서 열면 막대 없이 같은 방).
FLOW = STATIC / "flow"

ROOMS_INDEX = STATIC.parent / "rooms" / "index.html"   # 실제 방 만들기 화면 (방 레인 파일, 읽기만)
DEMO_ON = '<script>try { localStorage.setItem("flow:demo", "1"); } catch (e) {}</script>'


@router.get("/flow", include_in_schema=False)
def flow_start():
    # 중간 화면 없이 바로 실제 방 만들기를 보여 주고, 같은 자리에서 발표 모드를 켠다 (시연 막대가 바로 뜬다)
    page = ROOMS_INDEX.read_text(encoding="utf-8").replace("<head>", "<head>" + DEMO_ON, 1)
    return HTMLResponse(page)


@router.get("/flow/privacy", include_in_schema=False)
def flow_privacy():
    # 개인정보 처리방침 (모든 화면 바닥글에서 연결). 공용 주소 /privacy 는 방 + 공용 레인이 정한다
    return FileResponse(FLOW / "privacy.html")


# 예전 가짜 시연 주소(/flow/r/...)로 공유된 링크는 실제 주소로 넘긴다
@router.get("/flow/r/{code}", include_in_schema=False)
def flow_room(code: str):
    return RedirectResponse(f"/r/{quote(code)}", status_code=307)


@router.get("/flow/r/{code}/me", include_in_schema=False)
def flow_me(code: str):
    return RedirectResponse(f"/r/{quote(code)}/add", status_code=307)


@router.get("/flow/r/{code}/board", include_in_schema=False)
def flow_board(code: str):
    return RedirectResponse(f"/r/{quote(code)}/board", status_code=307)


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
    # 마감 자동 반영은 결과 카드 화면(board.js)이 이 API 를 부르기 전에
    # 지출 레인의 POST /api/expenses/rooms/{code}/settle 을 부른다 (레인끼리 import 하지 않기 위해 화면에서).
    rows = load_board_rows(code)
    if rows is None:
        raise HTTPException(404, "없는 방입니다")
    room, members, expenses = rows
    # 서버와 DB 는 한국 시간이다 (render.yaml 의 TZ, app/db.py). 오늘은 한국 날짜
    return build_board(room, members, expenses, date.today(), preview=preview)
