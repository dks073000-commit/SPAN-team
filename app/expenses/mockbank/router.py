"""가짜 은행: 금융결제원 오픈뱅킹 "거래내역조회" 명세 모양으로 가상 계좌의 거래를 돌려준다.

명세 주소  GET /v2.0/account/transaction_list/fin_num
여기 주소  GET /api/expenses/mockbank/v2.0/account/transaction_list/fin_num

명세와 다른 점 (시연용이라 일부러 단순하게 한 것):
- 사용자 인증과 토큰을 쓰지 않는다. Authorization 헤더는 없어도, 아무 값이어도 통과한다.
- 오늘(한국 시간) 이후의 거래는 아직 일어나지 않은 것으로 보고 돌려주지 않는다.
- 오류 응답코드 M로 시작하는 값은 이 가짜 은행이 정한 것이다 (명세의 응답코드 목록이 아니다).
- 아무것도 저장하지 않는다. 같은 요청에는 언제나 같은 거래가 나온다.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from app.expenses.mockbank import data

KST = timezone(timedelta(hours=9))  # 한국은 서머타임이 없다. Windows 에서도 tzdata 없이 돈다
PAGE_SIZE = 25  # 명세: 한 페이지는 최대 25건
BANK_CODE = "999"  # 가짜 은행 코드

router = APIRouter(prefix="/api/expenses/mockbank")


def now_kst() -> datetime:
    """테스트에서 시각을 바꿔 끼울 수 있게 함수로 둔다."""
    return datetime.now(KST).replace(tzinfo=None)


def _base(now: datetime, bank_tran_id: str) -> dict:
    return {
        "api_tran_id": str(uuid.uuid4()),
        "api_tran_dtm": now.strftime("%Y%m%d%H%M%S%f")[:17],
        "rsp_code": "A0000",
        "rsp_message": "",
        "bank_tran_id": bank_tran_id,
        "bank_tran_date": now.strftime("%Y%m%d"),
        "bank_code_tran": BANK_CODE,
        "bank_rsp_code": "000",
        "bank_rsp_message": "",
    }


def _error(now: datetime, bank_tran_id: str, code: str, message: str) -> dict:
    return _base(now, bank_tran_id) | {"rsp_code": code, "rsp_message": message}


def _parse(day: str, time: str) -> datetime | None:
    try:
        return datetime.strptime(day + time, "%Y%m%d%H%M%S")
    except ValueError:
        return None


@router.get("/v2.0/account/transaction_list/fin_num")
def transaction_list(
    bank_tran_id: str = "",
    fintech_use_num: str = "",
    inquiry_type: str = "",
    inquiry_base: str = "",
    from_date: str = "",
    from_time: str = "",
    to_date: str = "",
    to_time: str = "",
    sort_order: str = "",
    tran_dtime: str = "",
    befor_inquiry_trace_info: str = Query("", max_length=20),
):
    now = now_kst()

    # 요청 확인. 빠진 값이 있으면 HTTP 200 + 오류 응답코드로 알려준다
    if not re.fullmatch(r"[A-Za-z0-9]{20}", bank_tran_id):
        return _error(now, bank_tran_id, "M0001", "bank_tran_id 는 영문·숫자 20자리여야 합니다")
    if fintech_use_num not in data.ACCOUNTS:
        return _error(now, bank_tran_id, "M0002", "등록되지 않은 핀테크이용번호입니다")
    if inquiry_type not in ("A", "I", "O"):
        return _error(now, bank_tran_id, "M0003", "inquiry_type 은 A, I, O 중 하나입니다")
    if inquiry_base not in ("D", "T"):
        return _error(now, bank_tran_id, "M0003", "inquiry_base 는 D, T 중 하나입니다")
    if sort_order not in ("D", "A"):
        return _error(now, bank_tran_id, "M0003", "sort_order 는 D, A 중 하나입니다")
    if not re.fullmatch(r"\d{14}", tran_dtime):
        return _error(now, bank_tran_id, "M0003", "tran_dtime 은 YYYYMMDDHHMMSS 14자리입니다")

    if inquiry_base == "T":
        start, end = _parse(from_date, from_time), _parse(to_date, to_time)
    else:
        start, end = _parse(from_date, "000000"), _parse(to_date, "235959")
    if start is None or end is None or start > end:
        return _error(now, bank_tran_id, "M0004", "조회 기간이 올바르지 않습니다")

    # 조회
    rows = [
        r
        for r in data.transactions(fintech_use_num)
        if r["when"] <= now
        and start <= r["when"] <= end
        and (inquiry_type == "A" or r["inout"] == ("입금" if inquiry_type == "I" else "출금"))
    ]
    if sort_order == "D":
        rows.reverse()

    # 페이지 나누기. 직전조회추적정보에는 다음에 읽을 위치를 넣는다
    offset = int(befor_inquiry_trace_info) if befor_inquiry_trace_info.isdigit() else 0
    page = rows[offset : offset + PAGE_SIZE]
    has_next = offset + PAGE_SIZE < len(rows)

    settled = [r for r in data.transactions(fintech_use_num) if r["when"] <= now]
    account = data.ACCOUNTS[fintech_use_num]
    balance = settled[-1]["after_balance"] if settled else account["opening_balance"]

    return _base(now, bank_tran_id) | {
        "bank_name": data.BANK_NAME,
        "savings_bank_name": "",
        "fintech_use_num": fintech_use_num,
        "balance_amt": str(balance),
        "page_record_cnt": str(len(page)),
        "next_page_yn": "Y" if has_next else "N",
        "befor_inquiry_trace_info": str(offset + PAGE_SIZE) if has_next else "",
        "res_list": [
            {
                "tran_date": r["when"].strftime("%Y%m%d"),
                "tran_time": r["when"].strftime("%H%M%S"),
                "inout_type": r["inout"],
                "tran_type": r["tran_type"],
                "print_content": r["content"],
                "tran_amt": str(r["amount"]),
                "after_balance_amt": str(r["after_balance"]),
                "branch_name": "",
            }
            for r in page
        ],
    }
