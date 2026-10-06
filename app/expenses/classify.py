"""은행 거래내역(오픈뱅킹 res_list 모양)을 우리 지출 항목으로 바꾸고 자동 분류한다. DB 를 쓰지 않는다.

규칙 (BUILD_ORDER "S1-지출의 확인 화면", 10/6 회의로 바뀜. /flow 시안 store.js importTx 와 같다):
- 방 기간(시작일 ~ 마감일, 1주일) 안의 출금만 불러온다. 기간 밖은 아예 저장하지 않는다
- 예외: 새벽(0시 ~ 6시 전) 결제는 전날 밤 활동일 수 있다
  - 시작일 새벽 → 포함 + "시작 전날 밤 결제일 수도 있어요"
  - 마감 다음 날 새벽 → 불러오되 제외 + "마감 날 밤 결제일 수도 있어요"
- 입금은 저장하지 않는다. 가승인 짝을 찾는 데만 쓴다
- 같은 상호 · 같은 금액이 나갔다가 7일 안에 다시 들어오면 가승인(또는 환불) → 자동 제외
- 받는 쪽 이름이 계좌 주인 이름(내 계좌 이체)이거나 내용에 "충전" → 포함 + 꼬리표 (본인이 제외를 고른다)
- 같은 날 · 같은 상호 · 같은 금액 출금이 2건 이상이면 중복 꼬리표 (저장은 둘 다 포함)
"""

import hashlib
from datetime import date, datetime, time, timedelta

PAIR_DAYS = 7  # 가승인이 풀리기까지 기다리는 날 수

DAWN_END = time(6, 0)  # 이 시각 전 결제는 "새벽"

REASON_PREAUTH = "자동 제외 · 가승인"
REASON_START_DAWN = "시작 전날 밤 결제일 수도 있어요"
REASON_END_DAWN = "마감 날 밤 결제일 수도 있어요"
REASON_TRANSFER = "충전·내 계좌 이체일 수 있어요"
REASON_DUPLICATE = "중복일 수 있어요"


def make_ref(fintech_use_num: str, row: dict) -> str:
    """같은 거래는 언제 불러와도 같은 번호가 나온다. 잔액은 넣지 않는다 (개인정보, 10/3)."""
    key = "|".join([
        fintech_use_num, row["tran_date"], row["tran_time"], row["print_content"], row["tran_amt"], row["inout_type"],
    ])
    return "mb-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]


def _when(row: dict) -> datetime:
    return datetime.strptime(row["tran_date"] + row["tran_time"], "%Y%m%d%H%M%S")


def fetch_range(start: date, end: date) -> tuple[date, date]:
    """은행에 물어볼 날짜 범위. 마감 다음 날 새벽까지 본다."""
    return start, end + timedelta(days=1)


def classify(
    fintech_use_num: str, rows: list[dict], holder_name: str, start: date, end: date
) -> list[dict]:
    """방 기간 안의 출금(+ 마감 다음 날 새벽)만 골라 저장할 모양으로 돌려준다. 시간순."""
    rows = sorted(rows, key=_when)
    deposits = [r for r in rows if r["inout_type"] == "입금"]
    used_deposits: set[int] = set()

    items = []
    for row in rows:
        if row["inout_type"] != "출금":
            continue
        when = _when(row)
        dawn = when.time() < DAWN_END
        late_night = when.date() == end + timedelta(days=1) and dawn
        if not (start <= when.date() <= end) and not late_night:
            continue  # 기간 밖은 저장하지 않는다 (10/6)
        amount = int(row["tran_amt"])
        content = row["print_content"]

        reason = None
        excluded = False
        # 가승인: 같은 상호 · 같은 금액 입금이 7일 안에 들어왔는가 (입금 한 건은 한 번만 짝이 된다)
        for i, dep in enumerate(deposits):
            if (
                i not in used_deposits
                and dep["print_content"] == content
                and int(dep["tran_amt"]) == amount
                and when <= _when(dep) <= when + timedelta(days=PAIR_DAYS)
            ):
                used_deposits.add(i)
                reason, excluded = REASON_PREAUTH, True
                break
        if reason is None and late_night:
            reason, excluded = REASON_END_DAWN, True
        elif reason is None and when.date() == start and dawn:
            reason = REASON_START_DAWN
        elif reason is None and ("충전" in content or (holder_name and content == holder_name)):
            reason = REASON_TRANSFER

        items.append({
            "ref": make_ref(fintech_use_num, row),
            "spent_on": when.date(),
            "spent_time": when.time(),
            "merchant": content,
            "amount": amount,
            "excluded": excluded,
            "reason": reason,
        })
    return items


def duplicate_ids(expenses: list[dict]) -> set[int]:
    """저장된 지출 중 같은 날 · 같은 상호 · 같은 금액이 2건 이상인 것의 id."""
    groups: dict[tuple, list[int]] = {}
    for e in expenses:
        groups.setdefault((e["spent_on"], e["merchant"], e["amount"]), []).append(e["id"])
    return {i for ids in groups.values() if len(ids) > 1 for i in ids}
