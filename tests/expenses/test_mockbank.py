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
A, B, C = (f"BTG00000000000000000000{x}" for x in "ABC")


def ask(fintech_use_num=B, **overrides):
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
    assert (rows[0]["tran_date"], rows[0]["print_content"]) == ("20261001", "식당")  # B-01, 0일째
    assert (rows[1]["tran_date"], rows[1]["print_content"]) == ("20261002", "카페")  # B-02, 1일째


def test_counts_per_account():
    def count(num, kind):
        return len(ask(num, inquiry_type=kind)["res_list"])

    assert (count(A, "O"), count(A, "I")) == (8, 0)
    assert (count(B, "O"), count(B, "I")) == (9, 2)
    assert (count(C, "O"), count(C, "I")) == (9, 1)


def test_withdrawals_only():
    rows = ask(inquiry_type="O")["res_list"]
    assert {r["inout_type"] for r in rows} == {"출금"}


def test_future_transactions_are_hidden(monkeypatch):
    set_now(monkeypatch, datetime(2026, 10, 8, 17, 0))  # 발표 시각: 치킨(19:30)은 아직
    contents = [r["print_content"] for r in ask()["res_list"]]
    assert "택시" in contents and "치킨집" not in contents

    set_now(monkeypatch, datetime(2026, 10, 7, 12, 0))  # 리허설 전날: 7일째 거래는 없음
    assert all(r["tran_date"] <= "20261007" for r in ask()["res_list"])


def test_chicken_appears_after_payment(monkeypatch):
    set_now(monkeypatch, datetime(2026, 10, 8, 19, 30))
    assert ask(inquiry_type="O", sort_order="D")["res_list"][0]["print_content"] == "치킨집"


def test_date_range_and_time_range():
    rows = ask(from_date="20261005", to_date="20261005")["res_list"]
    assert [r["print_content"] for r in rows] == ["편의점", "편의점"]  # B-04, B-05

    rows = ask(inquiry_base="T", from_date="20261007", from_time="232000", to_date="20261007", to_time="235959")["res_list"]
    assert [(r["inout_type"], r["tran_amt"]) for r in rows] == [("입금", "20000"), ("출금", "9800")]


def test_sort_order():
    asc = ask(sort_order="A")["res_list"]
    desc = ask(sort_order="D")["res_list"]
    assert desc == list(reversed(asc))


def test_balance_follows_transactions():
    res = ask()
    assert res["res_list"][-1]["after_balance_amt"] == "391300"
    assert res["balance_amt"] == "391300"


def test_paging(monkeypatch):
    monkeypatch.setattr(mockbank, "PAGE_SIZE", 4)
    first = ask()
    assert (first["page_record_cnt"], first["next_page_yn"]) == ("4", "Y")
    second = ask(befor_inquiry_trace_info=first["befor_inquiry_trace_info"])
    assert second["res_list"][0] != first["res_list"][0]
    pages = [first, second, ask(befor_inquiry_trace_info="8")]
    assert pages[-1]["next_page_yn"] == "N"
    assert sum(len(p["res_list"]) for p in pages) == 11


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
