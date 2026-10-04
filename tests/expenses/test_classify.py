"""자동 분류와 ref. 발표자 계좌(A) 시나리오로 확인한다. DB 없이 돈다."""

from datetime import date, datetime

import pytest

from app.expenses import bank, classify
from app.expenses.mockbank import router as mockbank

A = "BTG00000000000000000000A"
START, END = date(2026, 10, 2), date(2026, 10, 8)


@pytest.fixture(autouse=True)
def presentation_time(monkeypatch):
    monkeypatch.setattr(mockbank, "now_kst", lambda: datetime(2026, 10, 8, 17, 0))


def items():
    rows = bank.fetch_transactions(A, date(2026, 9, 25), END)
    return classify.classify(A, rows, bank.holder_name(A), START, END)


def by_merchant(name):
    return [i for i in items() if i["merchant"] == name]


def test_only_withdrawals_are_kept():
    assert len(items()) == 11  # 출금 11, 입금 2(택시 취소 · 친구정산)는 저장하지 않음
    assert not by_merchant("친구정산")


def test_preauth_pair_is_auto_excluded():
    taxis = by_merchant("택시")
    assert [(t["amount"], t["reason"]) for t in taxis] == [(20000, classify.REASON_PREAUTH), (9800, None)]


def test_out_of_period_is_auto_excluded():
    (meal,) = by_merchant("식당")
    assert meal["spent_on"] == date(2026, 10, 1) and meal["reason"] == classify.REASON_OUT_OF_PERIOD


def test_charge_and_own_transfer_are_candidates():
    assert by_merchant("간편결제충전")[0]["reason"] == classify.REASON_CHARGE
    assert by_merchant("이예시")[0]["reason"] == classify.REASON_OWN_TRANSFER


def test_excluded_by_default_only_when_there_is_a_reason():
    for item in items():
        assert item["excluded"] == (item["reason"] is not None)


def test_scenario_total_after_presenter_choices():
    """발표자가 통신비 제외 · 편의점 한 건 제외 · 치킨 4명을 고르면 38,400원."""
    total = 0
    seen_store = False
    for item in items():
        if item["excluded"] or item["merchant"] == "통신비":
            continue
        if item["merchant"] == "편의점":
            if seen_store:
                continue
            seen_store = True
        total += item["amount"] // 4 if item["merchant"] == "치킨집" else item["amount"]
    assert total == 38400


def test_ref_is_stable_and_unique():
    first, second = items(), items()
    assert [i["ref"] for i in first] == [i["ref"] for i in second]
    assert len({i["ref"] for i in first}) == len(first)  # 편의점 두 건도 시간이 달라 서로 다름


def test_preauth_released_later_than_a_week_is_not_paired():
    rows = [
        {"tran_date": "20261002", "tran_time": "100000", "inout_type": "출금", "print_content": "숙소", "tran_amt": "50000"},
        {"tran_date": "20261012", "tran_time": "100000", "inout_type": "입금", "print_content": "숙소", "tran_amt": "50000"},
    ]
    (item,) = classify.classify(A, rows, "", START, END)
    assert item["reason"] is None


def test_duplicate_ids():
    rows = [
        {"id": 1, "spent_on": date(2026, 10, 5), "merchant": "편의점", "amount": 6300},
        {"id": 2, "spent_on": date(2026, 10, 5), "merchant": "편의점", "amount": 6300},
        {"id": 3, "spent_on": date(2026, 10, 5), "merchant": "편의점", "amount": 5000},
    ]
    assert classify.duplicate_ids(rows) == {1, 2}
