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
    rows = bank.fetch_transactions(A, *classify.fetch_range(START, END))
    return classify.classify(A, rows, bank.holder_name(A), START, END)


def by_merchant(name):
    return [i for i in items() if i["merchant"] == name]


def row(day, hhmm, content, amount, inout="출금"):
    return {"tran_date": day, "tran_time": hhmm + "00", "inout_type": inout, "print_content": content, "tran_amt": str(amount)}


def test_only_withdrawals_are_kept():
    assert len(items()) == 10  # 출금 10, 입금 2(택시 취소 · 친구정산)는 저장하지 않음
    assert not by_merchant("친구정산")


def test_preauth_pair_is_auto_excluded():
    taxis = by_merchant("택시")
    assert [(t["amount"], t["reason"]) for t in taxis] == [(20000, classify.REASON_PREAUTH), (9800, None)]


def test_only_room_period_is_kept():
    """방 기간(1주일) 밖 거래는 저장하지 않는다 (10/6). 마감 다음 날 새벽만 예외."""
    rows = [
        row("20261001", "2300", "전날 밤", 1000),
        row("20261002", "0130", "시작일 새벽", 2000),
        row("20261002", "1200", "시작일 낮", 3000),
        row("20261008", "2330", "마감일 밤", 4000),
        row("20261009", "0200", "마감 다음 날 새벽", 5000),
        row("20261009", "0600", "마감 다음 날 아침", 6000),
    ]
    got = {i["merchant"]: (i["excluded"], i["reason"]) for i in classify.classify(A, rows, "", START, END)}
    assert got == {
        "시작일 새벽": (False, classify.REASON_START_DAWN),
        "시작일 낮": (False, None),
        "마감일 밤": (False, None),
        "마감 다음 날 새벽": (True, classify.REASON_END_DAWN),
    }


def test_fetch_range_reaches_the_dawn_after_end():
    assert classify.fetch_range(START, END) == (START, date(2026, 10, 9))


def test_charge_and_own_transfer_are_kept_with_a_tag():
    for name in ["간편결제충전", "이예시"]:
        (item,) = by_merchant(name)
        assert (item["excluded"], item["reason"]) == (False, classify.REASON_TRANSFER)


def test_only_preauth_is_excluded_by_default_in_the_scenario():
    assert [i["merchant"] for i in items() if i["excluded"]] == ["택시"]


def test_scenario_total_after_presenter_choices():
    """발표자가 통신비 · 충전 · 내 계좌 이체 · 편의점 한 건을 제외하고 치킨 4명을 고르면 38,400원."""
    total = 0
    seen_store = False
    for item in items():
        if item["excluded"] or item["merchant"] in ("통신비", "간편결제충전", "이예시"):
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
    rows = [row("20261002", "1000", "숙소", 50000), row("20261012", "1000", "숙소", 50000, "입금")]
    (item,) = classify.classify(A, rows, "", START, END)
    assert item["reason"] is None


def test_duplicate_ids():
    rows = [
        {"id": 1, "spent_on": date(2026, 10, 5), "merchant": "편의점", "amount": 6300},
        {"id": 2, "spent_on": date(2026, 10, 5), "merchant": "편의점", "amount": 6300},
        {"id": 3, "spent_on": date(2026, 10, 5), "merchant": "편의점", "amount": 5000},
    ]
    assert classify.duplicate_ids(rows) == {1, 2}
