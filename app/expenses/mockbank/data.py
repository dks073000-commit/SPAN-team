"""가짜 은행의 가상 계좌와 거래내역 (시연용 예시 데이터, 실제 계좌가 아니다).

- 날짜는 "며칠째"로 적는다. 1일째 = START_DATE. 방 기간(1주일) 밖 거래는 두지 않는다 (10/6 회의).
- START_DATE 는 시연 주(10/2 금 ~ 10/8 목)의 첫날이다.
  다른 날짜로 시험하려면 환경변수 MOCKBANK_START_DATE=YYYY-MM-DD 로 바꾼다.
- 거래 후 잔액은 은행 응답 모양을 맞추려고 계산만 한다. 우리 앱은 저장하거나 보여주지 않는다.
- 번호(A-02 등)는 우리끼리 부르는 이름이다. 은행 응답에는 나가지 않는다.
"""

import os
from datetime import date, datetime, timedelta

START_DATE = date.fromisoformat(os.environ.get("MOCKBANK_START_DATE", "2026-10-02"))

BANK_NAME = "가상은행"  # /flow 시안(store.js)과 같은 이름 (10/6)

# (번호, 며칠째, 시간 HH:MM, 통장 표시, 금액, 입출금, 거래구분)
# 발표자(가상 주인 이예시)의 계좌 두 개. 계좌 연결 화면에서 이 중 하나를 고른다 (10/5)
# - A: 입출금 통장(생활비 통장). 시연 거래가 모두 여기 있다 (데모 방 seed 의 발표자가 A 를 연결한 채 이미 참여해 있다)
# - S: 적금. 출금이 없어서 골라도 불러올 지출이 없다 (A 에서 보낸 "내 계좌 이체"가 들어온다)
# 다른 참여자는 예시 데이터(목표 예산 · 총액)만 쓴다
ACCOUNTS = {
    "BTG00000000000000000000A": {
        "label": "가상 계좌 A",
        "product_name": "생활비 통장",
        "account_type": "1",  # 오픈뱅킹 명세: 1 수시입출금, 2 예적금, 6 수익증권
        "masked": "123-****-1234",
        "issue_date": date(2026, 3, 2),
        "maturity_date": None,
        "owner": "이예시",
        "opening_balance": 500_000,
        "transactions": [
            ("A-02", 1, "10:30", "카페", 4_800, "출금", "대체"),
            ("A-03", 2, "09:00", "통신비", 55_000, "출금", "대체"),  # 사용자가 제외
            ("A-04", 3, "09:30", "간편결제충전", 20_000, "출금", "대체"),  # 충전 → 제외 후보
            ("A-05", 3, "20:00", "이예시", 100_000, "출금", "타행환"),  # 내 계좌 이체 → 제외 후보
            ("A-06", 4, "18:20", "편의점", 6_300, "출금", "대체"),  # 중복 경고
            ("A-07", 4, "18:21", "편의점", 6_300, "출금", "대체"),  # 중복 경고
            ("A-08", 5, "12:10", "학생식당", 5_500, "출금", "대체"),
            ("A-09", 6, "23:10", "택시", 20_000, "출금", "대체"),  # 가승인 (A-10 과 짝)
            ("A-10", 6, "23:40", "택시", 20_000, "입금", "대체"),  # 가승인 취소
            ("A-11", 6, "23:40", "택시", 9_800, "출금", "대체"),  # 실제 요금
            ("A-12", 7, "16:30", "치킨집", 48_000, "출금", "대체"),  # 시연: 4명. 발표(10/8 17:00~) 전에 결제
            ("A-13", 7, "16:50", "친구정산", 36_000, "입금", "타행환"),
        ],
    },
    "BTG00000000000000000000S": {
        "label": "가상 적금",
        "product_name": "자유적금",
        "account_type": "2",
        "masked": "123-****-5678",
        "issue_date": date(2026, 3, 2),
        "maturity_date": date(2027, 3, 2),
        "owner": "이예시",
        "opening_balance": 1_200_000,
        "transactions": [
            ("S-01", 3, "20:00", "이예시", 100_000, "입금", "타행환"),  # A-05 내 계좌 이체가 들어온 것
        ],
    },
}

# 다른 참여자 예시 (거래내역 없이 목표 예산 · 총 지출만, 10/5)
# 중간 결과 페이지가 없어서 다른 사람은 결과 카드에 총액만 보인다. 그래서 거래 시나리오는 두지 않고 금액만 남긴다.
# 총 지출은 1/N · 제외를 마친 뒤의 금액이다. 데모 방에 넣으려면 db/seed.sql(공용, 안정훈)에 이 값을 쓰면 된다.
EXAMPLE_MEMBERS = [
    {"name": "보통", "budget": 50_000, "spent": 31_000, "status": "조정 완료"},  # 62.0%
    {"name": "많이 쓰는 사람", "budget": 120_000, "spent": 129_400, "status": "조정 완료"},  # 107.8%, 초과
    {"name": "중도포기", "budget": 50_000, "spent": 133_400, "status": "항복 (3일째 밤)"},  # 금액은 결과에서 숨김
]


def transactions(fintech_use_num: str) -> list[dict]:
    """그 계좌의 전체 거래를 시간순으로, 실제 날짜와 거래 후 잔액을 붙여 돌려준다."""
    account = ACCOUNTS[fintech_use_num]
    rows = []
    for _, day, hhmm, content, amount, inout, tran_type in account["transactions"]:
        hour, minute = map(int, hhmm.split(":"))
        when = datetime.combine(START_DATE + timedelta(days=day - 1), datetime.min.time()).replace(
            hour=hour, minute=minute
        )
        rows.append({"when": when, "content": content, "amount": amount, "inout": inout, "tran_type": tran_type})

    rows.sort(key=lambda r: r["when"])
    balance = account["opening_balance"]
    for row in rows:
        balance += row["amount"] if row["inout"] == "입금" else -row["amount"]
        row["after_balance"] = balance
    return rows
