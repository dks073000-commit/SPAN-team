# 버티기 (SPAN-team)

대학생이 친구들과 예산을 걸고, 각자 남은 돈을 한 화면에서 같이 보는 웹서비스. 10/8 공모전 발표용이다.

작업 전에 반드시 읽는다:
- `docs/PRD.md`: 무엇을 만드는가
- `docs/BUILD_ORDER.md`: 누가 무엇을 만들고, 레인끼리 어떤 약속(주소 · 테이블 · 계산식)을 지키는가

## 가장 먼저 할 일

세션을 시작하면 사용자가 누구인지 확인한다 (안정훈 / 이태윤 / 김경은). 사용자가 말하지 않았으면 묻는다. 그 사람의 레인 폴더만 고친다.

| 이름 | 레인 | 고칠 수 있는 곳 | 브랜치 |
|---|---|---|---|
| 안정훈 | 방 + 공용 | `app/rooms/` `static/rooms/` `tests/rooms/` + 공용 파일 | `feat/s0-ahn`, `feat/s1-room-ahn` |
| 이태윤 | 지출 (가상 계좌) | `app/expenses/` `static/expenses/` `tests/expenses/` | `feat/s1-expense-lee` |
| 김경은 | 보드 | `app/board/` `static/board/` `tests/board/` | `feat/s1-board-kim` |

공용 파일: `app/main.py` `app/db.py` `db/schema.sql` `db/seed.sql` `static/common.css` `requirements.txt` `render.yaml` `.gitignore` `.env.example` `README.md` `CLAUDE.md`

## 반드시 지키는 규칙

- **다른 레인의 폴더와 공용 파일은 읽기만 한다.** 고쳐야 할 것 같으면 고치지 말고, 무엇을 왜 바꿔야 하는지 사용자에게 알려 단톡방에 올리게 한다. 공용 파일은 안정훈만 별도 PR로 고친다.
- **약속을 마음대로 바꾸지 않는다.** 주소, 테이블 칸, 계산식은 `docs/BUILD_ORDER.md`를 따른다. 바꿔야 하면 먼저 사용자에게 말한다.
- **비밀값을 코드에 쓰지 않는다.** 이 레포는 공개다. DB 주소는 환경변수(`DATABASE_URL`)로만 읽는다. `.env`는 커밋하지 않는다.
- **범위 밖 기능을 만들지 않는다.** 오픈뱅킹이나 마이데이터 같은 실제 계좌 연동, 외부 금융 API 호출, 캡처(스크린샷) 인식, 회원가입과 로그인, 송금, 카테고리 분류, 광고는 만들지 않는다.
- **가상 계좌를 실제 계좌처럼 보이게 하지 않는다.** 화면에 "가상 계좌"라고 적는다. 실제 은행 이름이나 로고를 쓰지 않는다.
- **main에 직접 커밋하거나 push 하지 않는다.** 자기 브랜치에서 작업하고 PR로 합친다.

## 기술 스택

- 서버: FastAPI (Python)
- 화면: 빌드 단계 없는 HTML + JavaScript. 프레임워크와 번들러를 쓰지 않는다
- DB: 외부 Postgres. 테이블은 `db/schema.sql`, 데모 데이터는 `db/seed.sql`
- 배포: Render 웹 서비스 (`render.yaml`)
- 외부 API는 쓰지 않는다

## 구조

```
app/
  main.py        앱 시작. 레인별 라우터를 붙인다 (공용)
  db.py          DB 연결 (공용)
  rooms/         방 레인: /, /r/{code}, /api/rooms/...
  expenses/      지출 레인: /r/{code}/add, /api/expenses/... + 가상 계좌 데이터
  board/         보드 레인: /r/{code}/board, /api/board/...
static/
  common.css     공용 스타일 (공용)
  rooms/ expenses/ board/
db/
  schema.sql  seed.sql
tests/
  rooms/ expenses/ board/
docs/
```

한 레인이 자기 화면, API, DB 조회를 전부 가진다. 레인끼리 서로의 코드를 import 하지 않는다. 필요한 값은 DB나 API로 받는다.

## 실행

```
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # 값을 채운다
uvicorn app.main:app --reload
```

데모 방은 `/r/demo`다. 방 레인이 끝나지 않아도 지출과 보드는 데모 방으로 개발한다.

## 지출 입력

- 주 입력은 가상 계좌다. "계좌 연결"을 누르면 서버가 `app/expenses/` 안의 가상 거래내역을 돌려준다. 외부 서비스를 부르지 않는다.
- 가상 거래의 날짜는 방의 기간에 맞춰 계산한다 (BUILD_ORDER.md의 "가상 계좌 데이터").
- 직접 입력은 예비다. 파일 업로드는 사용자가 하자고 할 때만 만든다.
- 거래내역을 불러오는 부분은 함수 하나로 분리해 둔다. 나중에 실제 계좌 연결로 바꿀 때 그 함수만 바꾸면 되게 한다.

## 계산식

- 내 몫 = `amount ÷ people`
- 쓴 돈 = 제외하지 않은(`excluded = false`) 항목의 내 몫 합계
- 남은 예산 = `budget − 쓴 돈`
- 사용률 = `쓴 돈 ÷ budget`, 순위 = 사용률이 낮은 순
- 초과 = 남은 예산이 0보다 작다

## 상태와 보드 (10/3 회의)

- **미제출은 없다.** 참여할 때 가짜 은행 계좌를 고르고(`members.fintech_use_num`), 마감 때는 그 계좌 내역이 자동으로 반영된다.
- **미확인** = 항목 조정(1/N · 제외)을 아직 안 한 상태(`members.confirmed_at`이 null). 쓴 돈은 불러온 금액이 전부 반영된다. 결과 페이지로 가려면 조정을 거쳐야 한다.
- **항복** = 중도포기(`members.gave_up_at`). 금액은 보여주지 않고, 순위는 항복하지 않은 사람 아래에 둔다. 먼저 포기한 사람이 맨 아래다.
- 순위 1 · 2 · 3등은 금 · 은 · 동(또는 왕관)으로 강조한다.
- **기간 중에는 팀 차트를 보여주지 않는다.** 본인 페이지(불러오기 · 1/N · 제외 · 목표까지 남은 금액)만 있고, 순위는 마감일 결과 카드에서 공개한다. 결과에서도 다른 사람은 총액만 보이고 상세 내역(어디서 얼마)은 보이지 않는다.

## 시간대

- "오늘", 마감, 기간 판정은 모두 한국 시간(KST) 기준이다.
- 서버(`TZ=Asia/Seoul`, `render.yaml`)와 DB 연결(`app/db.py`가 `set timezone`)이 이미 KST로 맞춰져 있다. 파이썬은 `date.today()`, SQL은 `current_date`를 그대로 쓰면 된다.
- 화면 JS에서 `new Date().toISOString()`으로 날짜를 만들지 않는다 (UTC로 바뀌어 오전 9시 전에는 하루 전 날짜가 된다). 오늘 날짜가 필요하면 서버에서 받거나 로컬 시간으로 만든다.

## 작업 방식

- 시작 전에 `git pull` 하고 자기 브랜치인지 확인한다.
- 커밋 메시지는 한국어로 "무엇을: 왜" 형식으로 쓴다. 예: `방 참여 API 추가: 링크로 들어온 사람이 닉네임과 예산을 넣을 수 있게 하기 위해`
- 작게 만들고 자주 확인한다. 한 기능이 화면에서 동작하는 것을 확인한 뒤 다음으로 넘어간다.
- 사용자는 개발 입문자다. 무엇을 만들었는지, 어떻게 확인하는지를 쉬운 말로 짧게 설명한다.
- 화면은 단순하게 만든다. 멘토 피드백이 "UI가 너무 복잡하다"였다.
- 발표 때 동작하는 것이 가장 중요하다. 멋진 것보다 확실히 되는 것을 고른다.
