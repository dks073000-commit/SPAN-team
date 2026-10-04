"""가짜 은행 거래내역조회가 명세 모양대로 응답하는지 확인한다. DB 없이 돈다.

시나리오 기준: 1일째 = 2026-10-02(금), 7일째 = 2026-10-08(목, 발표일).
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.expenses.mockbank import router as mockbank
from app.main import app

client = TestClient(app)

URL = "/api/expenses/mockbank/v2.0/account/transaction_list/fin_num"
A = "BTG00000000000000000000A"
SAVINGS = "BTG00000000000000000000S"
PRESENTER = A  # 시연 장면(치킨 · 택시 가승인 · 중복)이 있는 계좌


def ask(fintech_use_num=PRESENTER, **overrides):
    params = {
        "bank_tran_id": "M202600001U123456789",
        "fintech_use_num": fintech_use_num,
        "inquiry_type": "A",
        "inquiry_base": "D",
        "from_date": "20261001",
        "to_date": "20261008",
        "sort_order": "A",
        "tran_dtime": "20261008170000",
    } | overrides
    return client.get(URL, params=params).json()


@pytest.fixture(autouse=True)
def presentation_evening(monkeypatch):
    """기본 시각: 발표일 10/8 오후 11시. 모든 거래가 일어난 뒤."""
    monkeypatch.setattr(mockbank, "now_kst", lambda: datetime(2026, 10, 8, 23, 0))


def set_now(monkeypatch, when):
    monkeypatch.setattr(mockbank, "now_kst", lambda: when)


def test_response_has_spec_fields():
    res = ask()
    assert res["rsp_code"] == "A0000"
    for key in [
        "api_tran_id", "api_tran_dtm", "rsp_message", "bank_tran_id", "bank_tran_date", "bank_code_tran",
        "bank_rsp_code", "bank_rsp_message", "bank_name", "savings_bank_name", "fintech_use_num",
        "balance_amt", "page_record_cnt", "next_page_yn", "befor_inquiry_trace_info", "res_list",
    ]:
        assert key in res, key
    assert len(res["api_tran_dtm"]) == 17
    assert res["bank_tran_id"] == "M202600001U123456789"
    row = res["res_list"][0]
    assert set(row) == {
        "tran_date", "tran_time", "inout_type", "tran_type", "print_content", "tran_amt", "after_balance_amt",
        "branch_name",
    }
    assert isinstance(row["tran_amt"], str)


def test_first_day_is_start_date_and_day_zero_is_before():
    rows = ask()["res_list"]
    assert (rows[0]["tran_date"], rows[0]["print_content"]) == ("20261001", "식당")  # A-01, 0일째
    assert (rows[1]["tran_date"], rows[1]["print_content"]) == ("20261002", "카페")  # A-02, 1일째


def test_counts():
    def count(num, kind):
        return len(ask(num, inquiry_type=kind)["res_list"])

    assert (count(A, "O"), count(A, "I")) == (11, 2)


def test_withdrawals_only():
    rows = ask(inquiry_type="O")["res_list"]
    assert {r["inout_type"] for r in rows} == {"출금"}


def test_future_transactions_are_hidden(monkeypatch):
    set_now(monkeypatch, datetime(2026, 10, 8, 16, 0))  # 발표 당일 오후 4시: 치킨(16:30)은 아직
    contents = [r["print_content"] for r in ask()["res_list"]]
    assert "택시" in contents and "치킨집" not in contents

    set_now(monkeypatch, datetime(2026, 10, 7, 12, 0))  # 리허설 전날: 7일째 거래는 없음
    assert all(r["tran_date"] <= "20261007" for r in ask()["res_list"])


def test_chicken_is_ready_before_presentation(monkeypatch):
    set_now(monkeypatch, datetime(2026, 10, 8, 17, 0))  # 발표 시작 시각 (10/8 17:00 ~ 19:30)
    assert ask(inquiry_type="O", sort_order="D")["res_list"][0]["print_content"] == "치킨집"


def test_date_range_and_time_range():
    rows = ask(from_date="20261005", to_date="20261005")["res_list"]
    assert [r["print_content"] for r in rows] == ["편의점", "편의점"]  # A-06, A-07

    rows = ask(inquiry_base="T", from_date="20261007", from_time="232000", to_date="20261007", to_time="235959")["res_list"]
    assert [(r["inout_type"], r["tran_amt"]) for r in rows] == [("입금", "20000"), ("출금", "9800")]


def test_sort_order():
    asc = ask(sort_order="A")["res_list"]
    desc = ask(sort_order="D")["res_list"]
    assert desc == list(reversed(asc))


def test_balance_follows_transactions():
    res = ask()
    assert res["res_list"][-1]["after_balance_amt"] == "271300"
    assert res["balance_amt"] == "271300"


def test_paging(monkeypatch):
    monkeypatch.setattr(mockbank, "PAGE_SIZE", 4)
    first = ask()
    assert (first["page_record_cnt"], first["next_page_yn"]) == ("4", "Y")
    second = ask(befor_inquiry_trace_info=first["befor_inquiry_trace_info"])
    assert second["res_list"][0] != first["res_list"][0]
    pages = [first, second, ask(befor_inquiry_trace_info="8"), ask(befor_inquiry_trace_info="12")]
    assert [p["next_page_yn"] for p in pages] == ["Y", "Y", "Y", "N"]
    assert sum(len(p["res_list"]) for p in pages) == 13


def test_no_token_needed():
    res = client.get(URL, params={
        "bank_tran_id": "M202600001U123456789", "fintech_use_num": A, "inquiry_type": "A", "inquiry_base": "D",
        "from_date": "20261001", "to_date": "20261008", "sort_order": "A", "tran_dtime": "20261008170000",
    }, headers={"Authorization": "Bearer anything"})
    assert res.json()["rsp_code"] == "A0000"


@pytest.mark.parametrize(
    "overrides, code",
    [
        ({"bank_tran_id": "short"}, "M0001"),
        ({"fintech_use_num": "nope"}, "M0002"),
        ({"inquiry_type": "X"}, "M0003"),
        ({"from_date": "20261010", "to_date": "20261001"}, "M0004"),
        ({"inquiry_base": "T"}, "M0004"),  # T 인데 시간이 없다
    ],
)
def test_bad_requests(overrides, code):
    res = ask(**overrides)
    assert res["rsp_code"] == code
    assert "res_list" not in res


BALANCE_URL = "/api/expenses/mockbank/v2.0/account/balance/fin_num"


def ask_balance(fintech_use_num=PRESENTER, **overrides):
    params = {
        "bank_tran_id": "M202600001U123456789",
        "fintech_use_num": fintech_use_num,
        "tran_dtime": "20261008170000",
    } | overrides
    return client.get(BALANCE_URL, params=params).json()


def test_balance_has_spec_fields():
    res = ask_balance()
    assert res["rsp_code"] == "A0000"
    for key in [
        "api_tran_id", "api_tran_dtm", "rsp_message", "bank_tran_id", "bank_tran_date", "bank_code_tran",
        "bank_rsp_code", "bank_rsp_message", "bank_name", "savings_bank_name", "fintech_use_num", "balance_amt",
        "available_amt", "account_type", "product_name", "account_issue_date", "maturity_date", "last_tran_date",
    ]:
        assert key in res, key
    assert res["account_type"] == "1"


def test_balance_matches_transaction_list():
    assert ask_balance()["balance_amt"] == ask()["balance_amt"] == "271300"
    assert ask_balance()["last_tran_date"] == "20261008"


def test_balance_ignores_future(monkeypatch):
    set_now(monkeypatch, datetime(2026, 10, 3, 12, 0))  # 0~2일째만 일어남
    res = ask_balance()
    assert res["balance_amt"] == "431200"  # 500,000 - 9,000 - 4,800 - 55,000
    assert res["last_tran_date"] == "20261003"


def test_balance_bad_request():
    assert ask_balance(fintech_use_num="nope")["rsp_code"] == "M0002"
    assert ask_balance(tran_dtime="2026")["rsp_code"] == "M0003"



AUTH_URL = "/api/expenses/mockbank/oauth/2.0/authorize"


def test_connect_page_shows_consent_and_my_accounts():
    res = client.get(AUTH_URL, params={"redirect_uri": "/r/demo", "state": "xyz"})
    assert res.status_code == 200
    page = res.text
    assert "계좌 연결" in page and "시연용 가상 계좌" in page and "[필수]" in page
    assert "버티기 입출금통장" in page and "123-****-1234" in page  # 입출금 (시연 거래)
    assert "버티기 자유적금" in page and "123-****-5678" in page  # 적금
    assert "이예시" not in page and "500000" not in page  # 주인 이름 · 잔액은 안 보여 줌


def test_connect_returns_chosen_account_to_redirect_uri():
    res = client.post(
        AUTH_URL, data={"redirect_uri": "/r/demo?step=join", "state": "xyz", "fintech_use_num": A}, follow_redirects=False
    )
    assert res.status_code == 303
    assert res.headers["location"] == (
        "/r/demo?step=join&fintech_use_num=BTG00000000000000000000A&account_alias=%EB%B2%84%ED%8B%B0%EA%B8%B0+%EC%9E%85%EC%B6%9C%EA%B8%88%ED%86%B5%EC%9E%A5&state=xyz"
    )


def test_connect_savings_account():
    res = client.post(AUTH_URL, data={"redirect_uri": "/r/demo", "fintech_use_num": SAVINGS}, follow_redirects=False)
    assert f"fintech_use_num={SAVINGS}" in res.headers["location"]


def test_connect_needs_a_chosen_account():
    for bad in ["", "BTG00000000000000000000Z"]:
        res = client.post(AUTH_URL, data={"redirect_uri": "/r/demo", "fintech_use_num": bad}, follow_redirects=False)
        assert res.status_code == 400


def test_savings_has_no_withdrawals():
    assert ask(SAVINGS, inquiry_type="O")["res_list"] == []
    (deposit,) = ask(SAVINGS, inquiry_type="I")["res_list"]
    assert (deposit["print_content"], deposit["tran_amt"]) == ("이예시", "100000")  # A 에서 보낸 내 계좌 이체
    bal = ask_balance(SAVINGS)
    assert (bal["account_type"], bal["product_name"], bal["maturity_date"], bal["balance_amt"]) == (
        "2", "버티기 자유적금", "20270302", "1300000"
    )


@pytest.mark.parametrize("bad", ["", "https://evil.example", "//evil.example", "/\\evil.example", "/\t/evil.example", "/\n/evil"])
def test_connect_only_redirects_inside_site(bad):
    assert client.get(AUTH_URL, params={"redirect_uri": bad}).status_code == 400
    assert client.post(AUTH_URL, data={"redirect_uri": bad, "fintech_use_num": A}, follow_redirects=False).status_code == 400
