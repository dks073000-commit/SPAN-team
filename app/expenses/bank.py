"""은행 연결부. 거래내역을 가져오는 곳은 이 파일 하나다.

지금은 같은 서버 안의 가짜 은행(mockbank)을 부른다. 실제 오픈뱅킹으로 바꿀 때는 이 파일만 바꾼다:
- fetch_transactions: GET /v2.0/account/transaction_list/fin_num 을 Authorization 헤더(토큰)와 함께 부른다
- holder_name: 사용자정보조회(user/me)의 이름을 쓴다
"""

import secrets
from datetime import date

from app.expenses.mockbank import data as mockbank_data
from app.expenses.mockbank import router as mockbank

ORG_CODE = "M202600001"  # 이용기관코드 (가짜)


class BankError(Exception):
    pass


def _bank_tran_id() -> str:
    """명세: 이용기관코드 10자리 + "U" + 9자리. 요청마다 새로 만든다."""
    return f"{ORG_CODE}U{secrets.randbelow(10**9):09d}"


def fetch_transactions(fintech_use_num: str, from_date: date, to_date: date) -> list[dict]:
    """입금 · 출금 전부를 오래된 순으로. 25건씩 나뉜 페이지를 끝까지 읽는다."""
    rows: list[dict] = []
    trace = ""
    while True:
        res = mockbank.transaction_list(
            bank_tran_id=_bank_tran_id(),
            fintech_use_num=fintech_use_num,
            inquiry_type="A",
            inquiry_base="D",
            from_date=from_date.strftime("%Y%m%d"),
            from_time="",
            to_date=to_date.strftime("%Y%m%d"),
            to_time="",
            sort_order="A",
            tran_dtime=mockbank.now_kst().strftime("%Y%m%d%H%M%S"),
            befor_inquiry_trace_info=trace,
        )
        if res["rsp_code"] != "A0000":
            raise BankError(res["rsp_message"] or res["rsp_code"])
        rows += res["res_list"]
        if res["next_page_yn"] != "Y":
            return rows
        trace = res["befor_inquiry_trace_info"]


def holder_name(fintech_use_num: str) -> str:
    account = mockbank_data.ACCOUNTS.get(fintech_use_num)
    return account["owner"] if account else ""


def account_alias(fintech_use_num: str) -> str:
    account = mockbank_data.ACCOUNTS.get(fintech_use_num)
    return account["label"] if account else ""
