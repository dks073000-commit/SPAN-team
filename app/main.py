"""앱 시작 (공용 파일). 레인별 라우터를 붙이고 static 을 서빙한다.

화면과 API 는 각 레인 폴더의 router.py 에서 만든다. 이 파일은 고치지 않는다.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import db
from app.board.router import router as board_router
from app.expenses.router import router as expenses_router
from app.rooms.router import router as rooms_router

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="버티기")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(rooms_router)
app.include_router(expenses_router)
app.include_router(board_router)


@app.get("/api/health")
def health():
    """Render 상태 확인용. DB 는 보지 않는다."""
    return {"ok": True}


@app.get("/api/health/db")
def health_db():
    """db 가 false 면 DATABASE_URL 이나 DB 접속을 확인한다."""
    return {"ok": True, "db": db.ping()}
