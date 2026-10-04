"""지출 레인: /r/{code}/add (본인 페이지), /api/expenses/...

본인 페이지 흐름: 불러오기(바로 저장) → 몇 명이서 · 제외 고치기 → 조정 완료.
남의 지출 상세(상호 · 금액)는 어떤 API 로도 내보내지 않는다. 내 member_id 의 것만 돌려준다.
"""

from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.db import connect, fetch_all, fetch_one
from app.expenses import bank, classify
from app.expenses.mockbank.router import router as mockbank_router

STATIC = Path(__file__).resolve().parents[2] / "static" / "expenses"
LOOKBACK_DAYS = 7  # 방 시작 며칠 전부터 은행에 묻는다 (기간 밖 거래를 보여주려고)

router = APIRouter()
router.include_router(mockbank_router)  # 가짜 은행: /api/expenses/mockbank/...


@router.get("/r/{code}/add", include_in_schema=False)
def add_page(code: str):
    return FileResponse(STATIC / "add.html")


@router.get("/api/expenses")
def lane_status():
    """레인 확인용. 방 전체 지출 목록은 내보내지 않는다 (다른 사람 상세 숨김, 10/3)."""
    return {"lane": "expenses", "ok": True}


# ---------------------------------------------------------------------------
# 도우미
# ---------------------------------------------------------------------------

def _member(member_id: int) -> dict:
    row = fetch_one(
        """
        select m.id, m.room_code, m.nickname, m.budget, m.fintech_use_num, m.confirmed_at, m.gave_up_at,
               r.name as room_name, r.start_date, r.end_date
        from members m join rooms r on r.code = m.room_code
        where m.id = %s
        """,
        (member_id,),
    )
    if row is None:
        raise HTTPException(404, "멤버를 찾을 수 없어요")
    return row


def _bank_items(member: dict) -> list[dict]:
    """은행 내역을 받아 분류한 결과. 계좌가 없으면 빈 목록."""
    num = member["fintech_use_num"]
    if not num:
        return []
    try:
        rows = bank.fetch_transactions(num, member["start_date"] - timedelta(days=LOOKBACK_DAYS), member["end_date"])
    except bank.BankError as e:
        raise HTTPException(502, f"은행 응답 오류: {e}")
    return classify.classify(num, rows, bank.holder_name(num), member["start_date"], member["end_date"])


def _import(member: dict) -> int:
    """처음 보는 거래만 저장한다. 저장한 건수를 돌려준다."""
    items = _bank_items(member)
    added = 0
    with connect() as conn:
        for item in items:
            added += conn.execute(
                """
                insert into expenses (member_id, spent_on, merchant, amount, people, excluded, source, ref)
                values (%s, %s, %s, %s, 1, %s, 'virtual', %s)
                on conflict (member_id, ref) do nothing
                """,
                (member["id"], item["spent_on"], item["merchant"], item["amount"], item["excluded"], item["ref"]),
            ).rowcount
    return added


def _share(amount: int, people: int) -> int:
    """내 몫 = amount ÷ people, 원 단위 반올림(0.5 는 올림). 보드 레인 app/board/calc.py 의 my_share 와 같은 식이다.
    결과 카드와 본인 페이지 금액이 1원도 어긋나지 않게 정수로만 계산한다."""
    return (2 * amount + people) // (2 * people)


def _badge(reason: str | None, excluded: bool) -> str | None:
    """자동 제외 사유인데 지금 포함돼 있으면 (사용자가 다시 넣었거나, 가승인 취소가 나중에 들어온 경우)
    "자동 제외"라고 쓰지 않고 제외를 권하는 문구로 보여준다."""
    if reason and reason.startswith("자동 제외") and not excluded:
        return reason.removeprefix("자동 제외 · ") + " · 제외 권장"
    return reason


def _summary(member: dict) -> dict:
    """본인 페이지가 그리는 데 쓰는 전부."""
    rows = fetch_all(
        """
        select id, spent_on, merchant, amount, people, excluded, source, ref, created_at
        from expenses where member_id = %s
        order by spent_on desc, id desc
        """,
        (member["id"],),
    )
    reasons = {item["ref"]: item["reason"] for item in _bank_items(member)}  # 배지는 볼 때마다 다시 판정
    duplicates = classify.duplicate_ids(rows)
    confirmed_at = member["confirmed_at"]

    items = []
    for r in rows:
        badges = []
        if badge := _badge(reasons.get(r["ref"]), r["excluded"]):
            badges.append(badge)
        if r["id"] in duplicates:
            badges.append(classify.REASON_DUPLICATE)
        if confirmed_at and r["created_at"] > confirmed_at:
            badges.append("새로 들어옴")  # 조정 완료 뒤에 들어온 것
        items.append({
            "id": r["id"],
            "date": r["spent_on"].isoformat(),
            "merchant": r["merchant"],
            "amount": r["amount"],
            "people": r["people"],
            "my_share": 0 if r["excluded"] else _share(r["amount"], r["people"]),
            "excluded": r["excluded"],
            "badges": badges,
        })

    # 쓴 돈 = 항목마다 반올림한 내 몫의 합 (보드 레인 calc.py 와 같은 규칙)
    spent = sum(i["my_share"] for i in items)
    if member["gave_up_at"]:
        status = "항복"
    elif confirmed_at is None or any(r["created_at"] > confirmed_at for r in rows):
        status = "미확인"
    else:
        status = "조정 완료"

    return {
        "member_id": member["id"],
        "nickname": member["nickname"],
        "room_name": member["room_name"],
        "start_date": member["start_date"].isoformat(),
        "end_date": member["end_date"].isoformat(),
        "account": bank.account_alias(member["fintech_use_num"]) if member["fintech_use_num"] else None,
        "budget": member["budget"],
        "spent": spent,
        "remaining": member["budget"] - spent,
        "status": status,
        "confirmed_at": confirmed_at.isoformat() if confirmed_at else None,
        "items": items,
    }


def _not_gave_up(member: dict) -> None:
    if member["gave_up_at"]:
        raise HTTPException(409, "항복한 뒤에는 바꿀 수 없어요")


# ---------------------------------------------------------------------------
# 본인 페이지 API
# ---------------------------------------------------------------------------

class MemberIn(BaseModel):
    member_id: int


class ExpenseUpdate(BaseModel):
    member_id: int
    people: int | None = Field(None, ge=1, le=99)
    excluded: bool | None = None


@router.get("/api/expenses/me")
def my_expenses(member_id: int):
    """내 목표 · 쓴 돈 · 남은 금액 · 상태 · 내 항목 목록."""
    return _summary(_member(member_id))


@router.post("/api/expenses/import")
def import_expenses(body: MemberIn):
    """불러오기: 내 계좌의 새 거래를 바로 저장한다 (1명 · 포함, 자동 제외 대상은 제외로)."""
    member = _member(body.member_id)
    _not_gave_up(member)
    if not member["fintech_use_num"]:
        raise HTTPException(409, "계좌가 연결되지 않은 멤버예요")
    added = _import(member)
    message = f"새로 {added}건 들어왔어요" if added else "새로 들어온 거래가 없어요"
    return {"added": added, "message": message, "summary": _summary(_member(body.member_id))}


@router.patch("/api/expenses/{expense_id}")
def update_expense(expense_id: int, body: ExpenseUpdate):
    """몇 명이서 · 제외를 고친다. 바로 저장되고 바뀐 요약을 돌려준다."""
    member = _member(body.member_id)
    _not_gave_up(member)
    row = fetch_one("select member_id from expenses where id = %s", (expense_id,))
    if row is None or row["member_id"] != member["id"]:
        raise HTTPException(404, "내 지출 항목이 아니에요")
    with connect() as conn:
        if body.people is not None:
            conn.execute("update expenses set people = %s where id = %s", (body.people, expense_id))
        if body.excluded is not None:
            conn.execute("update expenses set excluded = %s where id = %s", (body.excluded, expense_id))
    return _summary(_member(body.member_id))


@router.post("/api/expenses/confirm")
def confirm(body: MemberIn):
    """조정 완료. 이 시각 뒤에 새 지출이 저장되면 다시 미확인이 된다."""
    member = _member(body.member_id)
    _not_gave_up(member)
    with connect() as conn:
        conn.execute("update members set confirmed_at = now() where id = %s", (member["id"],))
    return _summary(_member(body.member_id))


# ---------------------------------------------------------------------------
# 마감 자동 반영 (보드 레인이 결과 카드를 열기 전에 부른다)
# ---------------------------------------------------------------------------

@router.post("/api/expenses/rooms/{code}/settle")
def settle_room(code: str):
    """방 멤버 중 계좌가 있는 사람 전원의 새 거래를 대신 불러와 저장한다. 여러 번 불러도 결과는 같다.
    계좌가 없는 멤버(데모 방의 예시 데이터)는 건너뛴다. 금액이나 상세는 돌려주지 않는다."""
    room = fetch_one("select code from rooms where code = %s", (code,))
    if room is None:
        raise HTTPException(404, "방을 찾을 수 없어요")
    ids = fetch_all("select id from members where room_code = %s order by id", (code,))
    result = []
    for row in ids:
        member = _member(row["id"])
        if not member["fintech_use_num"]:
            result.append({"member_id": member["id"], "nickname": member["nickname"], "skipped": "계좌 없음"})
            continue
        result.append({"member_id": member["id"], "nickname": member["nickname"], "added": _import(member)})
    return {"room": code, "today": date.today().isoformat(), "members": result}
