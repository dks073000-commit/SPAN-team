# 보드 API 약속 (`GET /api/board/{code}`) · 10/3 회의 기준

마감일 결과 카드(`/r/{code}/board`, 보드 레인)가 쓰는 형식이다.
10/3 회의로 방 홈에는 참여자 이름만 보이므로 방 홈은 이 API가 없어도 된다. 다른 레인에서 쓰게 되면 칸 이름을 바꾸기 전에 단톡방에 먼저 말한다.

**10/2 형식에서 바뀐 것**: `missed` `uploaded` `elapsed_pct` `cycle_start` `deadline` 삭제 · `result_open` `preview` `member_count` `players` `medal` `unconfirmed` `gave_up` 추가 · 마감일 전에는 `members`가 빈 목록.

## 응답 예시 (데모 방, 마감일 10/8)

```json
{
  "room": {
    "code": "demo", "name": "데모 방",
    "start_date": "2026-10-02", "end_date": "2026-10-08", "today": "2026-10-08",
    "started": true, "ended": false, "result_open": true, "preview": false,
    "day_index": 7, "total_days": 7, "days_left": 0
  },
  "member_count": 5,
  "players": [{ "member_id": 1, "nickname": "발표자" }, { "member_id": 2, "nickname": "짠돌이" }],
  "members": [
    { "member_id": 2, "nickname": "짠돌이", "budget": 100000, "spent": 22000, "remaining": 78000,
      "usage_pct": 22, "rank": 1, "medal": "gold", "over": false, "unconfirmed": false, "gave_up": false },
    { "member_id": 4, "nickname": "큰손", "budget": 70000, "spent": 85000, "remaining": -15000,
      "usage_pct": 121, "rank": 4, "medal": null, "over": true, "unconfirmed": true, "gave_up": false },
    { "member_id": 5, "nickname": "포기각", "budget": null, "spent": null, "remaining": null,
      "usage_pct": null, "rank": null, "medal": null, "over": false, "unconfirmed": false, "gave_up": true }
  ]
}
```
(예시는 줄였다. 실제로는 멤버 전원이 온다.)

- **마감일 전**: `members`는 `[]`이고 `member_count`와 `players`(이름만)가 온다. 기간 중에는 팀 순위를 보여주지 않는다.
- `players`: 참여 순서대로 `member_id`, `nickname`. 방 홈에도 보이는 정보다. 화면의 플레이어 색은 `member_id`로 정한다 (`(member_id - 1) % 6`).
- **시연용 미리 보기**: `?preview=1`을 붙이면 마감 전에도 지금까지 기록으로 결과를 돌려준다 (`room.preview: true`).
- 없는 방이면 `404`.

## room

| 칸 | 뜻 |
|---|---|
| `today` | 서버의 오늘 날짜 (한국 시간). 화면에서 오늘을 따로 계산하지 말고 이 값을 쓴다 |
| `started` | 시작일이 됐는지 |
| `result_open` | 마감일(`end_date`) 당일부터 `true`. 결과 카드가 열린다 |
| `ended` | 마감일이 지났는지 (마감 다음 날부터 `true`) |
| `preview` | 마감 전인데 `?preview=1`로 미리 본 결과인지 |
| `day_index` | 오늘이 기간의 며칠째인지 (시작 전 0, 끝난 뒤 `total_days`) |
| `total_days` | 기간 일수 (시작일과 종료일 포함) |
| `days_left` | 마감일까지 남은 날 (오늘 제외, 최소 0). 봉인 화면의 D-day |

날짜는 모두 `YYYY-MM-DD`.

## members (순서 = 화면에 그릴 순서)

| 칸 | 뜻 |
|---|---|
| `member_id` | "나" 찾기: 브라우저의 `member_id:{code}` 값과 비교한다 |
| `budget` `spent` `remaining` | 원 단위 정수. `remaining`이 음수면 그만큼 넘긴 것. 항복한 사람은 `null` |
| `usage_pct` | 사용률 = 쓴 돈 ÷ 예산 (정수 %, 100 넘을 수 있음). 항복한 사람은 `null` |
| `rank` | 사용률이 낮은 순. 같으면 같은 순위(1, 1, 3). 항복한 사람은 `null` |
| `medal` | `gold` `silver` `bronze` (1 · 2 · 3등), 그 밖에는 `null` |
| `over` | 예산을 넘겼는지 |
| `unconfirmed` | 미확인: 조정 완료(`confirmed_at`)가 없거나 그 뒤에 새 지출이 저장됐다. 순위에는 들어간다 |
| `gave_up` | 항복했는지 (`gave_up_at`) |

정렬: 순위 순(같으면 먼저 참여한 순), 그다음 항복한 사람(나중에 포기한 사람이 위, 먼저 포기한 사람이 맨 아래).

## 계산 규칙

- 내 몫 = 금액 ÷ 인원, 항목마다 원 단위 반올림 (0.5는 올림)
- 쓴 돈 = 제외하지 않은 항목의 내 몫 합계. 미확인이어도 불러온 금액은 전부 반영
- 미확인 판정은 지출을 **저장한 시각**(`expenses.created_at`)과 `members.confirmed_at`을 비교한다
- 마감 자동 반영: 결과 카드 화면(`static/board/board.js`)이 결과가 열린 날(`result_open`)이나 미리 보기(`preview`)일 때
  지출 레인의 `POST /api/expenses/rooms/{code}/settle` 을 한 번 부르고, 새로 저장된 거래가 있으면 이 API 를 다시 부른다.
  기간 중에는 부르지 않는다(남의 거래가 저장되면 그 사람이 미확인이 됨). settle 이 실패 · 404 · 8초 초과면 무시하고 그대로 그린다.
  마감일에 자동으로 들어온 거래는 조정 완료 뒤 저장이라 그 사람은 미확인으로 보인다 (3회차 합의: 조정 안 하면 전액 반영 + 미확인).
- 거래 항목(상호, 개별 금액)은 응답에 넣지 않는다. 테스트(`tests/board/test_board.py`)가 지킨다
