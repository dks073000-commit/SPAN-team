"""가짜 은행: 금융결제원 오픈뱅킹 명세 모양으로 가상 계좌의 거래내역과 잔액을 돌려준다.

명세 주소                                   여기 주소 (앞에 /api/expenses/mockbank)
GET /v2.0/account/transaction_list/fin_num   거래내역조회
GET /v2.0/account/balance/fin_num            잔액조회 (우리 앱 화면에는 쓰지 않는다. 명세를 맞춰 둔 것)
GET /oauth/2.0/authorize                     계좌 연결 (사용자인증을 흉내 냄: 동의 화면 → 계좌 하나 연결 → 돌려보냄)

명세와 다른 점 (시연용이라 일부러 단순하게 한 것):
- 사용자 인증과 토큰을 쓰지 않는다. Authorization 헤더는 없어도, 아무 값이어도 통과한다.
- 오늘(한국 시간) 이후의 거래는 아직 일어나지 않은 것으로 보고 돌려주지 않는다.
- 오류 응답코드 M로 시작하는 값은 이 가짜 은행이 정한 것이다 (명세의 응답코드 목록이 아니다).
- 아무것도 저장하지 않는다. 같은 요청에는 언제나 같은 거래가 나온다.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.expenses.mockbank import data

KST = timezone(timedelta(hours=9))  # 한국은 서머타임이 없다. Windows 에서도 tzdata 없이 돈다
PAGE_SIZE = 25  # 명세: 한 페이지는 최대 25건
BANK_CODE = "999"  # 가짜 은행 코드

STATIC = Path(__file__).resolve().parents[3] / "static" / "expenses"

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


def _check_common(bank_tran_id: str, fintech_use_num: str, tran_dtime: str) -> tuple[str, str] | None:
    """두 API 가 같이 쓰는 요청 확인. 문제가 있으면 (응답코드, 메시지)."""
    if not re.fullmatch(r"[A-Za-z0-9]{20}", bank_tran_id):
        return "M0001", "bank_tran_id 는 영문·숫자 20자리여야 합니다"
    if fintech_use_num not in data.ACCOUNTS:
        return "M0002", "등록되지 않은 핀테크이용번호입니다"
    if not re.fullmatch(r"\d{14}", tran_dtime):
        return "M0003", "tran_dtime 은 YYYYMMDDHHMMSS 14자리입니다"
    return None


def _settled(fintech_use_num: str, now: datetime) -> list[dict]:
    """지금까지 일어난 거래만."""
    return [r for r in data.transactions(fintech_use_num) if r["when"] <= now]


def _balance(fintech_use_num: str, now: datetime) -> int:
    settled = _settled(fintech_use_num, now)
    return settled[-1]["after_balance"] if settled else data.ACCOUNTS[fintech_use_num]["opening_balance"]


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
    if problem := _check_common(bank_tran_id, fintech_use_num, tran_dtime):
        return _error(now, bank_tran_id, *problem)
    if inquiry_type not in ("A", "I", "O"):
        return _error(now, bank_tran_id, "M0003", "inquiry_type 은 A, I, O 중 하나입니다")
    if inquiry_base not in ("D", "T"):
        return _error(now, bank_tran_id, "M0003", "inquiry_base 는 D, T 중 하나입니다")
    if sort_order not in ("D", "A"):
        return _error(now, bank_tran_id, "M0003", "sort_order 는 D, A 중 하나입니다")

    if inquiry_base == "T":
        start, end = _parse(from_date, from_time), _parse(to_date, to_time)
    else:
        start, end = _parse(from_date, "000000"), _parse(to_date, "235959")
    if start is None or end is None or start > end:
        return _error(now, bank_tran_id, "M0004", "조회 기간이 올바르지 않습니다")

    # 조회
    rows = [
        r
        for r in _settled(fintech_use_num, now)
        if start <= r["when"] <= end
        and (inquiry_type == "A" or r["inout"] == ("입금" if inquiry_type == "I" else "출금"))
    ]
    if sort_order == "D":
        rows.reverse()

    # 페이지 나누기. 직전조회추적정보에는 다음에 읽을 위치를 넣는다
    offset = int(befor_inquiry_trace_info) if befor_inquiry_trace_info.isdigit() else 0
    page = rows[offset : offset + PAGE_SIZE]
    has_next = offset + PAGE_SIZE < len(rows)

    return _base(now, bank_tran_id) | {
        "bank_name": data.BANK_NAME,
        "savings_bank_name": "",
        "fintech_use_num": fintech_use_num,
        "balance_amt": str(_balance(fintech_use_num, now)),
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


@router.get("/v2.0/account/balance/fin_num")
def balance(bank_tran_id: str = "", fintech_use_num: str = "", tran_dtime: str = ""):
    now = now_kst()
    if problem := _check_common(bank_tran_id, fintech_use_num, tran_dtime):
        return _error(now, bank_tran_id, *problem)

    settled = _settled(fintech_use_num, now)
    amount = str(_balance(fintech_use_num, now))
    return _base(now, bank_tran_id) | {
        "bank_name": data.BANK_NAME,
        "savings_bank_name": "",
        "fintech_use_num": fintech_use_num,
        "balance_amt": amount,
        "available_amt": amount,
        "account_type": "1",  # 수시입출금
        "product_name": data.PRODUCT_NAME,
        "account_issue_date": data.ACCOUNT_ISSUE_DATE.strftime("%Y%m%d"),
        "maturity_date": "",  # 수시입출금이라 만기 없음
        "last_tran_date": settled[-1]["when"].strftime("%Y%m%d") if settled else "",
    }



# ---------------------------------------------------------------------------
# 계좌 연결 (오픈뱅킹 사용자인증을 흉내 낸 것)
#
# 실제 오픈뱅킹: 앱이 은행 인증 화면(GET /oauth/2.0/authorize)으로 보낸다 → 사용자가 본인 인증 ·
# 계좌 선택 · 동의 → 은행이 redirect_uri 로 돌려보낸다 → 앱이 토큰을 받아 핀테크이용번호를 얻는다.
# 가짜 은행: 인증 · 토큰을 생략하고, 동의 버튼 한 번으로 가상 계좌(발표자 시나리오)를 연결해
# redirect_uri 로 핀테크이용번호를 바로 돌려준다. 아무것도 저장하지 않는다.
# ---------------------------------------------------------------------------

AUTH_PAGE = STATIC / "mockbank_authorize.html"


def _safe_redirect(redirect_uri: str) -> bool:
    """같은 사이트 안의 주소("/r/abc" 같은)만 허용한다. 다른 사이트로 보내는 데 쓰이지 않게."""
    return redirect_uri.startswith("/") and not redirect_uri.startswith("//") and "\\" not in redirect_uri


def _pick_account() -> str:
    """연결할 계좌. 지금은 발표자 시나리오 계좌 하나뿐이라 누가 연결해도 같은 계좌가 된다 (10/5).
    계좌가 여러 개가 되면 여기서 고르면 된다. 테스트에서 바꿔 끼울 수 있게 함수로 둔다."""
    return next(iter(data.ACCOUNTS))


@router.get("/oauth/2.0/authorize", include_in_schema=False)
def authorize_page(redirect_uri: str = "", state: str = ""):
    """가짜 은행 인증 화면. 참여 폼의 [계좌 연결하기] 버튼이 이 주소로 보낸다."""
    if not _safe_redirect(redirect_uri):
        return HTMLResponse("redirect_uri 는 같은 사이트 안의 주소(/로 시작)여야 합니다.", status_code=400)
    return FileResponse(AUTH_PAGE)


@router.post("/oauth/2.0/authorize", include_in_schema=False)
def authorize_agree(redirect_uri: str = Form(""), state: str = Form("")):
    """[동의하고 연결]을 누르면 계좌 하나를 연결하고 redirect_uri 로 돌려보낸다."""
    if not _safe_redirect(redirect_uri):
        return HTMLResponse("redirect_uri 는 같은 사이트 안의 주소(/로 시작)여야 합니다.", status_code=400)
    fintech_use_num = _pick_account()
    query = urlencode({
        "fintech_use_num": fintech_use_num,
        "account_alias": data.ACCOUNTS[fintech_use_num]["label"],
        "state": state,
    })
    return RedirectResponse(f"{redirect_uri}{'&' if '?' in redirect_uri else '?'}{query}", status_code=303)
