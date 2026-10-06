"""30일 자동 삭제: 마감일 다음 날부터 30일이 지난 방을 지운다 (개인정보 처리방침 3번 · 참여 동의 ①).

방을 지우면 members · expenses 는 on delete cascade 로 같이 지워진다 (db/schema.sql).

언제 부르나: Render 무료 서버는 쓰는 사람이 없으면 잠들어서 "매일 새벽 3시" 같은 정해진 시각 실행을 믿을 수 없다.
그래서 서버가 깨어날 때(시작)와 사람이 방을 만들거나 열 때 함께 지운다. 아무도 안 쓰는 동안은 지워지지 않지만,
그동안은 누구도 그 정보를 볼 수 없고, 다음에 누가 들어오는 순간 먼저 지워진다.
"""

# 마감일 다음 날을 1일째로 세어 30일이 지나면 지운다. 마감 10/8 → 11/7 까지 보관, 11/8 에 지운다
KEEP_DAYS = 30

# 데모 방은 발표 자료에 링크가 실려 있고 seed.sql 의 가짜 데이터라 지우지 않는다
KEEP_CODES = ("demo",)


def purge_expired_rooms(conn) -> list[str]:
    """지운 방 코드 목록을 돌려준다. 날짜는 DB 의 current_date (app/db.py 가 한국 시간으로 맞춤)."""
    rows = conn.execute(
        "delete from rooms where end_date + %s < current_date and code <> all(%s) returning code",
        (KEEP_DAYS, list(KEEP_CODES)),
    ).fetchall()
    return [r["code"] for r in rows]
