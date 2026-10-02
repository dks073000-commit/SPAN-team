"""DB 연결 (공용 파일).

DATABASE_URL 환경변수로 외부 Postgres 에 연결한다. 로컬에서는 .env 에서 읽는다.

테이블과 데모 방 넣기 (프로젝트 폴더에서 한 줄):
    python -m app.db init

레인에서 쓰는 법:
    from app.db import fetch_all, fetch_one, execute
    rows = fetch_all("select * from members where room_code = %s", (code,))
"""

import os
import sys
from contextlib import contextmanager
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL 이 비어 있습니다. .env 를 확인하세요.")
    return url


@contextmanager
def connect():
    """연결을 열고, 블록이 끝나면 커밋하고 닫는다. 에러가 나면 되돌린다."""
    # prepare_threshold=None: Supabase pooler(6543 포트)에서도 동작하게 한다
    with psycopg.connect(database_url(), row_factory=dict_row, prepare_threshold=None, connect_timeout=10) as conn:
        yield conn


def fetch_all(sql: str, params=None) -> list[dict]:
    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def fetch_one(sql: str, params=None) -> dict | None:
    with connect() as conn:
        return conn.execute(sql, params).fetchone()


def execute(sql: str, params=None) -> int:
    """insert / update / delete. 바뀐 행 수를 돌려준다."""
    with connect() as conn:
        return conn.execute(sql, params).rowcount


def ping() -> bool:
    try:
        fetch_one("select 1")
        return True
    except Exception:
        return False


def init() -> None:
    """db/schema.sql 과 db/seed.sql 을 차례로 실행한다."""
    with connect() as conn:
        for name in ("schema.sql", "seed.sql"):
            conn.execute((ROOT / "db" / name).read_text(encoding="utf-8"))
            print(f"{name} 완료")


if __name__ == "__main__":
    if sys.argv[1:] == ["init"]:
        init()
    else:
        print("사용법: python -m app.db init")
