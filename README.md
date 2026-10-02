# 버티기 (가칭) · SPAN-team

대학생이 친구들과 예산을 걸고, 각자 남은 돈을 한 화면에서 같이 보는 웹서비스.

- 배포 주소: (S0 배포 후 채운다)
- 데모 방: `/r/demo`

## 문서

| 문서 | 내용 |
|---|---|
| [docs/PRD.md](docs/PRD.md) | 무엇을 만드는가 |
| [docs/BUILD_ORDER.md](docs/BUILD_ORDER.md) | 담당, 순서, 레인끼리의 약속(주소 · 테이블 · 계산식) |
| [docs/CLAUDE_PROMPTS.md](docs/CLAUDE_PROMPTS.md) | Claude Code에 붙여 넣는 지시문 |
| [CLAUDE.md](CLAUDE.md) | Claude Code가 자동으로 읽는 프로젝트 규칙 |

## 담당

| 이름 | 레인 | 폴더 | 브랜치 |
|---|---|---|---|
| 안정훈 | 방 + 뼈대(공용) | `app/rooms/` `static/rooms/` + 공용 파일 | `feat/s0-ahn` → `feat/s1-room-ahn` |
| 이태윤 | 지출 (가상 계좌) | `app/expenses/` `static/expenses/` | `feat/s1-expense-lee` |
| 김경은 | 보드 | `app/board/` `static/board/` | `feat/s1-board-kim` |

## 처음 시작하기

```
git clone https://github.com/dks073000-commit/SPAN-team.git
cd SPAN-team
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # 값은 팀원에게 따로 받는다. 공개된 곳에 올리지 않는다
uvicorn app.main:app --reload
```

브라우저에서 `http://localhost:8000/r/demo`를 연다.

## 매일 작업 순서

```
git checkout main
git pull
git checkout feat/s1-<레인>-<이름>      # 처음이면 git checkout -b
git merge main                          # main의 새 내용을 내 브랜치로 가져온다
# ... 작업 ...
git add <고친 파일>
git commit -m "무엇을: 왜"
git push -u origin feat/s1-<레인>-<이름>
```

GitHub에서 PR을 만들고, 팀원 1명이 확인한 뒤 merge 한다.

## 규칙

- 자기 레인 폴더만 고친다. 공용 파일은 단톡방에 말한 뒤 안정훈이 별도 PR로 고친다.
- main에 직접 push 하지 않는다.
- `.env`와 실제 거래내역 파일은 커밋하지 않는다. 이 레포는 공개 레포다.
- 약속을 바꿀 때는 `docs/BUILD_ORDER.md`를 먼저 고친다.

## 알아 둘 것

- 거래내역은 서버에 미리 넣어 둔 **가상 계좌** 데이터다. 실제 계좌가 아니다.
- 오픈뱅킹은 핀테크 사업자와 전자금융업자만 이용할 수 있어 이번 범위에서 뺐다.
