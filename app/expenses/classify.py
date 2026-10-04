"""은행 거래내역(오픈뱅킹 res_list 모양)을 우리 지출 항목으로 바꾸고 자동 분류한다. DB 를 쓰지 않는다.

규칙 (BUILD_ORDER "S1-지출의 확인 화면"):
- 입금은 저장하지 않는다. 가승인 짝을 찾는 데만 쓴다
- 같은 상호 · 같은 금액이 나갔다가 7일 안에 다시 들어오면 가승인(또는 환불) → 자동 제외
- 방 기간 밖 날짜 → 자동 제외
- 받는 쪽 이름이 계좌 주인 이름이면 내 계좌 이체 → 제외 후보 (기본 제외)
- 내용에 "충전" → 제외 후보 (기본 제외)
- 같은 날 · 같은 상호 · 같은 금액 출금이 2건 이상이면 중복 경고 (저장은 둘 다 포함)
"""

import hashlib
from datetime import date, datetime, timedelta

PAIR_DAYS = 7  # 가승인이 풀리기까지 기다리는 날 수

REASON_PREAUTH = "자동 제외 · 가승인"
REASON_OUT_OF_PERIOD = "자동 제외 · 기간 밖"
REASON_OWN_TRANSFER = "제외 후보 · 내 계좌 이체"
REASON_CHARGE = "제외 후보 · 충전"
REASON_DUPLICATE = "중복?"


def make_ref(fintech_use_num: str, row: dict) -> str:
    """같은 거래는 언제 불러와도 같은 번호가 나온다. 잔액은 넣지 않는다 (개인정보, 10/3)."""
    key = "|".join([
        fintech_use_num, row["tran_date"], row["tran_time"], row["print_content"], row["tran_amt"], row["inout_type"],
    ])
    return "mb-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]


def _when(row: dict) -> datetime:
    return datetime.strptime(row["tran_date"] + row["tran_time"], "%Y%m%d%H%M%S")


def classify(
    fintech_use_num: str, rows: list[dict], holder_name: str, start: date, end: date
) -> list[dict]:
    """출금만 골라 저장할 모양으로 돌려준다. 시간순."""
    rows = sorted(rows, key=_when)
    deposits = [r for r in rows if r["inout_type"] == "입금"]
    used_deposits: set[int] = set()

    items = []
    for row in rows:
        if row["inout_type"] != "출금":
            continue
        when = _when(row)
        amount = int(row["tran_amt"])
        content = row["print_content"]

        reason = None
        # 가승인: 같은 상호 · 같은 금액 입금이 7일 안에 들어왔는가 (입금 한 건은 한 번만 짝이 된다)
        for i, dep in enumerate(deposits):
            if (
                i not in used_deposits
                and dep["print_content"] == content
                and int(dep["tran_amt"]) == amount
                and when <= _when(dep) <= when + timedelta(days=PAIR_DAYS)
            ):
                used_deposits.add(i)
                reason = REASON_PREAUTH
                break
        if reason is None and not (start <= when.date() <= end):
            reason = REASON_OUT_OF_PERIOD
        if reason is None and holder_name and content == holder_name:
            reason = REASON_OWN_TRANSFER
        if reason is None and "충전" in content:
            reason = REASON_CHARGE

        items.append({
            "ref": make_ref(fintech_use_num, row),
            "spent_on": when.date(),
            "merchant": content,
            "amount": amount,
            "excluded": reason is not None,
            "reason": reason,
        })
    return items


def duplicate_ids(expenses: list[dict]) -> set[int]:
    """저장된 지출 중 같은 날 · 같은 상호 · 같은 금액이 2건 이상인 것의 id."""
    groups: dict[tuple, list[int]] = {}
    for e in expenses:
        groups.setdefault((e["spent_on"], e["merchant"], e["amount"]), []).append(e["id"])
    return {i for ids in groups.values() if len(ids) > 1 for i in ids}
