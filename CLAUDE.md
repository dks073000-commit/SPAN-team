# 버티기 (SPAN-team)

대학생이 친구들과 예산을 걸고, 각자 남은 돈을 한 화면에서 같이 보는 웹서비스. 10/8 공모전 발표용이다.

작업 전에 반드시 읽는다:
- `docs/PRD.md`: 무엇을 만드는가
- `docs/BUILD_ORDER.md`: 누가 무엇을 만들고, 레인끼리 어떤 약속(주소 · 테이블 · 계산식 · 환경변수)을 지키는가

## 가장 먼저 할 일

세션을 시작하면 사용자가 누구인지 확인한다 (안정훈 / 이태윤 / 김경은). 사용자가 말하지 않았으면 묻는다. 그 사람의 레인 폴더만 고친다.

| 이름 | 레인 | 고칠 수 있는 곳 | 브랜치 |
|---|---|---|---|
| 안정훈 | 방 + 공용 | `app/rooms/` `static/rooms/` `tests/rooms/` + 공용 파일 | `feat/s0-ahn`, `feat/s1-room-ahn` |
| 이태윤 | 지출 + 테스트베드 | `app/expenses/` `static/expenses/` `tests/expenses/` | `feat/s1-expense-lee` |
| 김경은 | 보드 | `app/board/` `static/board/` `tests/board/` | `feat/s1-board-kim` |

공용 파일: `app/main.py` `app/db.py` `db/schema.sql` `db/seed.sql` `static/common.css` `requirements.txt` `render.yaml` `.gitignore` `.env.example` `README.md` `CLAUDE.md`

## 반드시 지키는 규칙

- **다른 레인의 폴더와 공용 파일은 읽기만 한다.** 고쳐야 할 것 같으면 고치지 말고, 무엇을 왜 바꿔야 하는지 사용자에게 알려 단톡방에 올리게 한다. 공용 파일은 안정훈만 별도 PR로 고친다.
- **약속을 마음대로 바꾸지 않는다.** 주소, 테이블 칸, 계산식, 환경변수 이름은 `docs/BUILD_ORDER.md`를 따른다. 바꿔야 하면 먼저 사용자에게 말한다.
- **비밀값을 코드에 쓰지 않는다.** 이 레포는 공개다. `client_secret`, 토큰, DB 주소는 환경변수로만 읽는다. `.env`는 커밋하지 않는다. 화면(JavaScript)에는 어떤 비밀값도 넣지 않는다.
- **범위 밖 기능을 만들지 않는다.** 캡처(스크린샷) 인식, 회원가입과 로그인, 실제 계좌 연동, 송금, 카테고리 분류, 광고는 만들지 않는다.
- **main에 직접 커밋하거나 push 하지 않는다.** 자기 브랜치에서 작업하고 PR로 합친다.
- 테스트베드 API의 주소, 파라미터, 응답 형식은 추측하지 않는다. 공식 명세서나 실제 응답으로 확인한다. 확인하지 못한 것은 확인하지 못했다고 말한다.

## 기술 스택

- 서버: FastAPI (Python)
- 화면: 빌드 단계 없는 HTML + JavaScript. 프레임워크와 번들러를 쓰지 않는다
- DB: 외부 Postgres. 테이블은 `db/schema.sql`, 데모 데이터는 `db/seed.sql`
- 배포: Render 웹 서비스 (`render.yaml`)

## 구조

```
app/
  main.py        앱 시작. 레인별 라우터를 붙인다 (공용)
  db.py          DB 연결 (공용)
  rooms/         방 레인: /, /r/{code}, /api/rooms/...
  expenses/      지출 레인: /r/{code}/add, /api/expenses/...
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
`OB_MOCK=1`이면 테스트베드 없이 예시 거래내역으로 동작한다.

## 계산식

- 내 몫 = `amount ÷ people`
- 쓴 돈 = 제외하지 않은(`excluded = false`) 항목의 내 몫 합계
- 남은 예산 = `budget − 쓴 돈`
- 사용률 = `쓴 돈 ÷ budget`, 순위 = 사용률이 낮은 순

## 작업 방식

- 시작 전에 `git pull` 하고 자기 브랜치인지 확인한다.
- 커밋 메시지는 한국어로 "무엇을: 왜" 형식으로 쓴다. 예: `방 참여 API 추가: 링크로 들어온 사람이 닉네임과 예산을 넣을 수 있게 하기 위해`
- 작게 만들고 자주 확인한다. 한 기능이 화면에서 동작하는 것을 확인한 뒤 다음으로 넘어간다.
- 사용자는 개발 입문자다. 무엇을 만들었는지, 어떻게 확인하는지를 쉬운 말로 짧게 설명한다.
- 화면은 단순하게 만든다. 멘토 피드백이 "UI가 너무 복잡하다"였다.
- 발표 때 동작하는 것이 가장 중요하다. 멋진 것보다 확실히 되는 것을 고른다.
