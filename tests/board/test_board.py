"""보드 계산과 보드 API. DB 없이 돌아간다 (DB 읽기는 가짜로 바꾼다). 10/3 회의 기준."""

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.board import router as board_router
from app.board.calc import build_board, my_share
from app.main import app

client = TestClient(app)

KST = timezone(timedelta(hours=9))
END = date(2026, 10, 8)      # 데모 방 마감일 = 발표날
MIDWAY = date(2026, 10, 5)   # 기간 중


def at(month, day, hour=12):
    return datetime(2026, month, day, hour, tzinfo=KST)


def make_room(start=date(2026, 10, 2), end=END):
    return {"code": "t", "name": "테스트 방", "start_date": start, "end_date": end}


def member(mid, nick, budget, confirmed=None, gave_up=None):
    return {"id": mid, "nickname": nick, "budget": budget, "confirmed_at": confirmed, "gave_up_at": gave_up}


def spend(mid, amount, people=1, excluded=False, saved=at(10, 3)):
    return {"member_id": mid, "amount": amount, "people": people, "excluded": excluded, "created_at": saved}


# db/seed.sql 의 데모 방과 같은 구성 (발표자는 아직 불러오기 전)
DEMO_ROOM = make_room()
DEMO_MEMBERS = [
    member(1, "발표자", 100000),
    member(2, "짠돌이", 100000, confirmed=at(10, 7, 21)),
    member(3, "카페중독", 80000, confirmed=at(10, 7, 22)),
    member(4, "큰손", 70000),
    member(5, "포기각", 50000, gave_up=at(10, 4, 23)),
]
DEMO_EXPENSES = [spend(2, 22000), spend(3, 52000), spend(4, 85000), spend(5, 61000, saved=at(10, 4))]


def by_nick(board):
    return {m["nickname"]: m for m in board["members"]}


def test_my_share_rounds_half_up():
    assert my_share(10000, 3) == 3333
    assert my_share(10000, 1) == 10000
    assert my_share(5, 2) == 3        # 2.5 → 3 (짝수 쪽으로 가지 않는다)
    assert my_share(36000, 3) == 12000


def test_demo_room_totals():
    m = by_nick(build_board(DEMO_ROOM, DEMO_MEMBERS, DEMO_EXPENSES, END))
    assert (m["짠돌이"]["spent"], m["짠돌이"]["remaining"], m["짠돌이"]["usage_pct"]) == (22000, 78000, 22)
    assert (m["카페중독"]["usage_pct"], m["카페중독"]["over"]) == (65, False)
    assert (m["큰손"]["spent"], m["큰손"]["remaining"], m["큰손"]["usage_pct"]) == (85000, -15000, 121)
    assert m["큰손"]["over"] is True


def test_share_and_excluded_items():
    members = [member(1, "a", 100000, confirmed=at(10, 7))]
    expenses = [spend(1, 36000, people=3), spend(1, 45000, excluded=True), spend(1, 1500)]
    row = build_board(DEMO_ROOM, members, expenses, END)["members"][0]
    assert row["spent"] == 13500


def test_ranking_medals_and_order():
    board = build_board(DEMO_ROOM, DEMO_MEMBERS, DEMO_EXPENSES, END)
    got = [(r["nickname"], r["rank"], r["medal"]) for r in board["members"]]
    # 발표자는 아직 0원이라 1등 (마감 자동 반영 전), 항복은 맨 아래
    assert got == [("발표자", 1, "gold"), ("짠돌이", 2, "silver"), ("카페중독", 3, "bronze"),
                   ("큰손", 4, None), ("포기각", None, None)]


def test_ties_share_rank_and_medal():
    members = [member(1, "a", 10000), member(2, "b", 20000), member(3, "c", 10000), member(4, "d", 10000)]
    expenses = [spend(1, 5000), spend(2, 10000), spend(3, 8000), spend(4, 9000)]  # 50, 50, 80, 90%
    board = build_board(DEMO_ROOM, members, expenses, END)
    got = [(r["nickname"], r["rank"], r["medal"]) for r in board["members"]]
    assert got == [("a", 1, "gold"), ("b", 1, "gold"), ("c", 3, "bronze"), ("d", 4, None)]


def test_unconfirmed_rules():
    members = [
        member(1, "조정전", 50000),
        member(2, "조정함", 50000, confirmed=at(10, 6)),
        member(3, "조정뒤새지출", 50000, confirmed=at(10, 6)),
    ]
    expenses = [spend(1, 1000), spend(2, 1000, saved=at(10, 5)), spend(3, 1000, saved=at(10, 5)),
                spend(3, 2000, saved=at(10, 7))]
    m = by_nick(build_board(DEMO_ROOM, members, expenses, END))
    assert m["조정전"]["unconfirmed"] is True
    assert m["조정함"]["unconfirmed"] is False
    assert m["조정뒤새지출"]["unconfirmed"] is True
    # 미확인이어도 불러온 금액은 전부 반영되고 순위에 들어간다
    assert m["조정뒤새지출"]["spent"] == 3000 and m["조정뒤새지출"]["rank"] is not None


def test_gave_up_hides_amounts_and_earliest_goes_last():
    members = [
        member(1, "버팀", 50000),
        member(2, "먼저포기", 50000, gave_up=at(10, 3)),
        member(3, "나중포기", 50000, gave_up=at(10, 6)),
    ]
    expenses = [spend(1, 1000), spend(2, 90000), spend(3, 20000)]
    board = build_board(DEMO_ROOM, members, expenses, END)
    assert [r["nickname"] for r in board["members"]] == ["버팀", "나중포기", "먼저포기"]
    quit_row = by_nick(board)["먼저포기"]
    assert quit_row["gave_up"] is True and quit_row["rank"] is None
    assert all(quit_row[k] is None for k in ("budget", "spent", "remaining", "usage_pct"))
    assert quit_row["over"] is False


def test_no_transaction_details_leak():
    board = build_board(DEMO_ROOM, DEMO_MEMBERS, DEMO_EXPENSES, END)
    keys = {k for m in board["members"] for k in m}
    assert keys == {"member_id", "nickname", "budget", "spent", "remaining", "usage_pct",
                    "rank", "medal", "over", "unconfirmed", "gave_up"}


def test_ranks_hidden_until_end_date():
    during = build_board(DEMO_ROOM, DEMO_MEMBERS, DEMO_EXPENSES, MIDWAY)
    assert during["members"] == [] and during["member_count"] == 5
    # 이름은 보이지만 금액과 순위는 없다
    assert during["players"][0] == {"member_id": 1, "nickname": "발표자"}
    assert during["room"]["result_open"] is False and during["room"]["preview"] is False
    # 마감일 당일부터 공개 (발표날 = 마감일)
    on_end = build_board(DEMO_ROOM, DEMO_MEMBERS, DEMO_EXPENSES, END)
    assert on_end["room"]["result_open"] is True and on_end["room"]["ended"] is False
    assert len(on_end["members"]) == 5


def test_preview_shows_result_during_period():
    board = build_board(DEMO_ROOM, DEMO_MEMBERS, DEMO_EXPENSES, MIDWAY, preview=True)
    assert board["room"]["preview"] is True and len(board["members"]) == 5
    # 마감 뒤에는 미리 보기가 아니다
    assert build_board(DEMO_ROOM, DEMO_MEMBERS, DEMO_EXPENSES, END, preview=True)["room"]["preview"] is False


def test_room_info():
    info = build_board(DEMO_ROOM, [], [], MIDWAY)["room"]
    assert (info["started"], info["day_index"], info["total_days"], info["days_left"]) == (True, 4, 7, 3)
    before = build_board(make_room(date(2026, 10, 10), date(2026, 10, 16)), [], [], MIDWAY)["room"]
    assert before["started"] is False and before["day_index"] == 0
    after = build_board(make_room(date(2026, 9, 20), date(2026, 9, 26)), [], [], MIDWAY)["room"]
    assert after["ended"] is True and after["day_index"] == 7 and after["days_left"] == 0


def test_api_hides_ranks_until_end_and_previews(monkeypatch):
    monkeypatch.setattr(board_router, "load_board_rows", lambda code: (DEMO_ROOM, DEMO_MEMBERS, DEMO_EXPENSES))
    monkeypatch.setattr(board_router, "date", type("D", (), {"today": staticmethod(lambda: MIDWAY)}))
    body = client.get("/api/board/t").json()
    assert set(body) == {"room", "member_count", "players", "members"} and body["members"] == []
    res = client.get("/api/board/t?preview=1")
    assert len(res.json()["members"]) == 5
    assert "merchant" not in res.text


def test_api_unknown_room(monkeypatch):
    monkeypatch.setattr(board_router, "load_board_rows", lambda code: None)
    assert client.get("/api/board/nope").status_code == 404


def test_flow_demo_pages_open():
    # 시연용 전체 흐름: 방 만들기 → 방 홈 → 내 페이지 → 결과 카드 (데이터는 브라우저에만 있다)
    for path, marker in [("/flow", "링크 만들기"), ("/flow/r/demo", "flow/store.js"),
                         ("/flow/r/demo/me", "내 페이지"), ("/flow/r/demo/board", "board.js")]:
        res = client.get(path)
        assert res.status_code == 200 and marker in res.text, path


def test_privacy_policy_page_and_footer():
    # 개인정보 처리방침은 홈페이지에 계속 보여야 한다 (개인정보보호법 30조 · 시행령 31조 2항)
    res = client.get("/flow/privacy")
    assert res.status_code == 200
    for must in ["처리 목적", "보유 기간", "처리 위탁", "국외 이전", "보호책임자"]:
        assert must in res.text, must
    # 결과 화면에도 바닥글 링크가 있다
    assert "/flow/privacy" in client.get("/flow/r/demo/board").text

