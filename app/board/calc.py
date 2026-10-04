"""보드 계산 (DB 없이 동작하는 순수 함수). 계산식은 docs/BUILD_ORDER.md 를 따른다 (10/3 회의 기준).

- 내 몫 = amount ÷ people, 항목마다 원 단위 반올림(0.5 는 올림)
- 쓴 돈 = 제외하지 않은 항목의 내 몫 합계 (미확인이어도 불러온 금액은 전부 반영)
- 남은 예산 = budget − 쓴 돈 (음수면 초과)
- 순위 = 사용률(쓴 돈 ÷ budget)이 낮은 순. 같으면 같은 순위 (1, 1, 3). 1 · 2 · 3등은 금 · 은 · 동
- 미확인 = 조정 완료(confirmed_at)가 없거나, 그 뒤에 새 지출이 저장됐다
- 항복 = gave_up_at 이 있다. 순위에서 빼고 금액을 숨긴다. 항복하지 않은 사람 아래, 먼저 포기한 사람이 맨 아래
- 결과 공개 = 마감일(end_date) 당일부터. 그 전에는 순위를 내보내지 않는다 (preview 는 시연용)
"""

from datetime import date

MEDALS = {1: "gold", 2: "silver", 3: "bronze"}


def my_share(amount: int, people: int) -> int:
    """나눠 낸 금액의 내 몫. 0.5 원은 올린다 (파이썬 round 는 짝수 쪽으로 가서 쓰지 않는다)."""
    return (2 * amount + people) // (2 * people)


def _pct(part: int, whole: int) -> int:
    """정수 퍼센트, 0.5 는 올림."""
    return (200 * part + whole) // (2 * whole) if whole else 0


def _row(m: dict, mine: list[dict]) -> dict:
    if m["gave_up_at"] is not None:
        # 항복: 금액은 아무것도 내보내지 않는다
        return {
            "member_id": m["id"], "nickname": m["nickname"],
            "budget": None, "spent": None, "remaining": None, "usage_pct": None,
            "rank": None, "medal": None, "over": False, "unconfirmed": False, "gave_up": True,
        }
    spent = sum(my_share(e["amount"], e["people"]) for e in mine if not e["excluded"])
    confirmed = m["confirmed_at"]
    unconfirmed = confirmed is None or any(e["created_at"] > confirmed for e in mine)
    return {
        "member_id": m["id"], "nickname": m["nickname"],
        "budget": m["budget"], "spent": spent, "remaining": m["budget"] - spent,
        "usage_pct": _pct(spent, m["budget"]),
        "rank": None, "medal": None, "over": spent > m["budget"],
        "unconfirmed": unconfirmed, "gave_up": False,
    }


def build_board(room: dict, members: list[dict], expenses: list[dict], today: date, preview: bool = False) -> dict:
    """보드 API 응답을 만든다.

    room: code, name, start_date, end_date
    members: id, nickname, budget, confirmed_at, gave_up_at
    expenses: member_id, amount, people, excluded, created_at
    """
    start, end = room["start_date"], room["end_date"]
    total_days = (end - start).days + 1
    result_open = today >= end

    room_out = {
        "code": room["code"],
        "name": room["name"],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "today": today.isoformat(),
        "started": today >= start,
        "ended": today > end,
        "result_open": result_open,
        "preview": preview and not result_open,
        "day_index": min(max((today - start).days + 1, 0), total_days),
        "total_days": total_days,
        "days_left": max((end - today).days, 0),
    }

    # 참여자 이름은 방 홈에도 보이는 정보라 언제나 준다 (봉인 화면의 참전자 줄, 플레이어 색은 member_id 로 정한다)
    players = [{"member_id": m["id"], "nickname": m["nickname"]} for m in members]

    # 기간 중에는 팀 순위를 보여주지 않는다 (10/3). 참여자 수와 이름만 알려 준다
    if not (result_open or preview):
        return {"room": room_out, "member_count": len(members), "players": players, "members": []}

    rows = [_row(m, [e for e in expenses if e["member_id"] == m["id"]]) for m in members]

    # 순위: 사용률 비교는 나눗셈 대신 곱셈으로 (소수 오차를 피한다)
    ranked = [r for r in rows if not r["gave_up"]]
    for r in ranked:
        r["rank"] = 1 + sum(1 for o in ranked if o["spent"] * r["budget"] < r["spent"] * o["budget"])
        r["medal"] = MEDALS.get(r["rank"])
    ranked.sort(key=lambda r: (r["rank"], r["member_id"]))

    # 항복: 나중에 포기한 사람이 위, 먼저 포기한 사람이 맨 아래
    gave_up_at = {m["id"]: m["gave_up_at"] for m in members}
    quit_rows = sorted((r for r in rows if r["gave_up"]), key=lambda r: r["member_id"])
    quit_rows.sort(key=lambda r: gave_up_at[r["member_id"]], reverse=True)

    return {"room": room_out, "member_count": len(members), "players": players, "members": ranked + quit_rows}
