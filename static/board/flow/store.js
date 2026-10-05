// 시연용 전체 흐름(/flow)의 가짜 서버. 데이터는 이 브라우저의 localStorage 에만 저장한다.
// 서버·DB·다른 레인 기능이 없어도 방 만들기 → 참여 → 불러오기 → 조정 → 결과 카드가 끊기지 않게 하려는 것.
//
// 실제 기능으로 바꿔 끼우는 자리 (기능이 생기면 그 함수만 실제 API 호출로 바꾼다):
//   createRoom   → POST /api/rooms                       (방 레인)
//   join         → POST /api/rooms/{code}/members         (방 레인, 계좌 fintech_use_num 포함)
//   bankRows     → GET  /api/expenses/mockbank/v2.0/account/transaction_list/fin_num (지출 레인)
//   importTx · updateItem · confirm → POST /api/expenses, 조정 완료 (지출 레인)
//   giveUp       → POST /api/rooms/{code}/members/{id}/give-up (방 레인)
//   board        → GET  /api/board/{code}                (보드 레인, 계산 규칙은 app/board/calc.py 와 같다)

window.Flow = (function () {
  "use strict";

  /* ---------- 날짜 (toISOString 을 쓰지 않는다: CLAUDE.md 시간대 규칙) ---------- */

  const pad = (n) => String(n).padStart(2, "0");
  const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const parse = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
  const addDays = (s, n) => { const d = parse(s); d.setDate(d.getDate() + n); return ymd(d); };
  const daysBetween = (a, b) => Math.round((parse(b) - parse(a)) / 86400000);
  const WD = ["일", "월", "화", "수", "목", "금", "토"];
  const md = (s) => { const d = parse(s); return `${d.getMonth() + 1}/${d.getDate()}(${WD[d.getDay()]})`; };
  const won = (n) => Math.abs(Math.round(n)).toLocaleString("ko-KR");
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const TODAY_KEY = "flow:today";   // 발표 설정의 "결과 날로 보기"
  function now() {
    const forced = get(TODAY_KEY);
    if (forced) { const d = parse(forced); d.setHours(23, 59, 0, 0); return d; }
    return new Date();
  }
  const today = () => ymd(now());

  /* ---------- 저장 ---------- */

  function get(key) { try { return JSON.parse(localStorage.getItem(key) || "null"); } catch (e) { return null; } }
  function put(key, v) { try { localStorage.setItem(key, JSON.stringify(v)); } catch (e) { /* 저장이 막힌 브라우저: 이번 화면에서만 유지 */ } }
  function drop(key) { try { localStorage.removeItem(key); } catch (e) { /* 무시 */ } }

  const roomKey = (code) => `flow:room:${code}`;
  const meKey = (code) => `flow:me:${code}`;   // 실제 서비스의 member_id:{code} 와 겹치지 않게 따로 둔다

  /* ---------- 가짜 은행 (app/expenses/mockbank/data.py 와 같은 데이터) ---------- */

  const BANK_START = "2026-10-02";
  const ACCOUNTS = {
    A: {
      fin: "BTG00000000000000000000A", owner: "김가상", hint: "체크카드 · 학식, 카페가 많아요",
      alias: "생활비 통장", masked: "1002-***-**1201",
      tx: [
        ["A-01", 1, "12:10", "학생식당", 5500, "출금"], ["A-02", 1, "21:30", "편의점", 3200, "출금"],
        ["A-03", 2, "10:15", "카페", 4500, "출금"], ["A-04", 3, "09:00", "간편결제충전", 20000, "출금"],
        ["A-05", 3, "12:20", "학생식당", 5500, "출금"], ["A-06", 4, "19:40", "분식집", 24000, "출금"],
        ["A-07", 5, "08:30", "버스", 1500, "출금"], ["A-08", 6, "22:10", "편의점", 2800, "출금"],
      ],
    },
    B: {
      fin: "BTG00000000000000000000B", owner: "이예시", hint: "체크카드 · 교통, 편의점이 많아요",
      alias: "용돈 통장", masked: "1002-***-**1202",
      tx: [
        ["B-01", 0, "19:00", "식당", 9000, "출금"], ["B-02", 1, "10:30", "카페", 4800, "출금"],
        ["B-03", 2, "09:00", "통신비", 55000, "출금"], ["B-04", 4, "18:20", "편의점", 6300, "출금"],
        ["B-05", 4, "18:21", "편의점", 6300, "출금"], ["B-06", 5, "12:10", "학생식당", 5500, "출금"],
        ["B-07", 6, "23:10", "택시", 20000, "출금"], ["B-08", 6, "23:40", "택시", 20000, "입금"],
        ["B-09", 6, "23:40", "택시", 9800, "출금"], ["B-10", 7, "19:30", "치킨집", 48000, "출금"],
        ["B-11", 7, "21:00", "친구정산", 36000, "입금"],
      ],
    },
    C: {
      fin: "BTG00000000000000000000C", owner: "박모의", hint: "토스 · 배달, 쇼핑이 많아요",
      alias: "알바비 통장", masked: "1002-***-**1203",
      tx: [
        ["C-01", 1, "15:00", "카페", 6800, "출금"], ["C-02", 1, "19:00", "식당", 32000, "출금"],
        ["C-03", 2, "14:00", "숙소예약", 50000, "출금"], ["C-04", 2, "20:00", "박모의", 100000, "출금"],
        ["C-05", 3, "16:30", "옷가게", 59000, "출금"], ["C-06", 4, "10:00", "숙소예약", 50000, "입금"],
        ["C-07", 4, "20:10", "배달음식", 27000, "출금"], ["C-08", 5, "01:20", "택시", 18400, "출금"],
        ["C-09", 6, "23:00", "술집", 64000, "출금"], ["C-10", 7, "13:00", "편의점", 4200, "출금"],
      ],
    },
  };

  // 지금까지 일어난 거래만 (오늘 이후 거래는 아직 안 일어난 것으로 본다)
  function bankRows(account) {
    const limit = now().getTime();
    return ACCOUNTS[account].tx.map(([ref, day, hhmm, content, amount, inout]) => {
      const date = addDays(BANK_START, day - 1);
      const [h, m] = hhmm.split(":").map(Number);
      const when = parse(date); when.setHours(h, m, 0, 0);
      return { ref, date, time: hhmm, when: when.getTime(), content, amount, inout };
    }).filter((r) => r.when <= limit).sort((a, b) => a.when - b.when);
  }

  /* ---------- 방 · 멤버 ---------- */

  const CODE_CHARS = "abcdefghjkmnpqrstuvwxyz23456789";

  function seedDemo() {
    // db/seed.sql 의 데모 방과 같은 구성: 발표자(가짜 은행 계좌 A, 아직 조정 전) + 이름 · 총액만 있는 3명 + 중도포기 1명
    const at = (m, d, h, mi = 0) => new Date(2026, m - 1, d, h, mi).getTime();
    const sum = (id, amount, day) => ({ member_id: id, ref: `seed-${id}`, merchant: "시연용 합계", amount, people: 1, excluded: false, auto: null, hint: null, spent_on: `2026-10-0${day}`, created_at: at(10, 3, 12) });
    const state = {
      room: { code: "demo", name: "데모 방", start_date: "2026-10-02", end_date: "2026-10-08" },
      next_id: 6,
      members: [
        { id: 1, nickname: "발표자", budget: 100000, account: "A", confirmed_at: null, gave_up_at: null },
        { id: 2, nickname: "짠돌이", budget: 100000, account: null, confirmed_at: at(10, 7, 21), gave_up_at: null },
        { id: 3, nickname: "카페중독", budget: 80000, account: null, confirmed_at: at(10, 7, 22, 30), gave_up_at: null },
        { id: 4, nickname: "큰손", budget: 70000, account: null, confirmed_at: null, gave_up_at: null },
        { id: 5, nickname: "포기각", budget: 50000, account: null, confirmed_at: null, gave_up_at: at(10, 4, 23) },
      ].map((m) => ({ ...m, pin_hash: pinHash("demo", DEMO_PIN) })),
      expenses: [sum(2, 22000, 7), sum(3, 52000, 7), sum(4, 85000, 7), sum(5, 61000, 4)],
    };
    put(roomKey("demo"), state);
    return state;
  }

  // 개발자 시점: 새로 만든 방에도 가상 참여자(이름 · 총액만 3명 + 중도포기 1명)를 채워 결과 카드를 보여 준다
  function fillDummies(code) {
    const state = load(code);
    const stamp = now().getTime();
    const day = state.room.start_date;
    [["짠돌이", 100000, 22000, true, false], ["카페중독", 80000, 52000, true, false],
     ["큰손", 70000, 85000, false, false], ["포기각", 50000, 61000, false, true]].forEach(([nickname, budget, amount, confirmed, quit]) => {
      if (state.members.some((m) => m.nickname === nickname)) return;
      const id = state.next_id++;
      state.members.push({ id, nickname, budget, account: null, pin_hash: pinHash(code, DEMO_PIN), confirmed_at: confirmed ? stamp + 1 : null, gave_up_at: quit ? stamp : null });
      state.expenses.push({ member_id: id, ref: `dummy-${id}`, merchant: "시연용 합계", amount, people: 1, excluded: false, auto: null, hint: null, spent_on: day, created_at: stamp });
    });
    save(state);
  }

  function load(code) {
    const state = get(roomKey(code));
    if (state) return state;
    return code === "demo" ? seedDemo() : fromLink(code);
  }
  const save = (state) => put(roomKey(state.room.code), state);

  /* ---------- 방 링크: 다른 기기에서도 방이 열리게 이름 · 기간을 링크에 담는다 (10/6 피드백 1) ---------- */
  // 형식: /flow/r/{code}?n=방이름&s=2026-10-06&e=2026-10-12
  // 가짜 서버는 브라우저마다 따로라, 링크만 받은 기기는 이 값으로 빈 방(참여자 0명)을 만든다.
  // 참여 기록은 각자 기기에만 남는다 (실제 서비스는 서버가 방을 알고 있으니 code 만 있으면 된다).
  const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
  const realDate = (s) => DATE_RE.test(s) && ymd(parse(s)) === s;

  function roomLink(code) {
    const enc = encodeURIComponent(code);
    const state = get(roomKey(code));
    const base = `${location.origin}/flow/r/${enc}`;
    if (!state || code === "demo") return base;
    const { name, start_date, end_date } = state.room;
    return `${base}?n=${encodeURIComponent(name)}&s=${start_date}&e=${end_date}`;
  }

  function fromLink(code) {
    if (typeof location === "undefined") return null;
    const q = new URLSearchParams(location.search);
    const name = (q.get("n") || "").trim().slice(0, 30);
    const start_date = q.get("s") || "";
    const end_date = q.get("e") || "";
    if (!name || !realDate(start_date) || !realDate(end_date) || end_date < start_date) return null;
    if (!/^[a-z0-9]{1,12}$/.test(code)) return null;
    const state = { room: { code, name, start_date, end_date }, next_id: 1, members: [], expenses: [] };
    save(state);
    return state;
  }

  function createRoom({ name, start_date, end_date }) {
    let code;
    do { code = Array.from({ length: 6 }, () => CODE_CHARS[Math.floor(Math.random() * CODE_CHARS.length)]).join(""); }
    while (get(roomKey(code)) || code === "demo");
    save({ room: { code, name, start_date, end_date }, next_id: 1, members: [], expenses: [] });
    return code;
  }

  // 방마다 쓰는 숫자 4자리 (회원가입 아님: 연락처 · 실명을 받지 않고, 그 방 안에서만 쓴다).
  // 시연용이라 브라우저에서 간단한 해시만 한다. 실제 서비스는 서버에서 hashlib 으로 해시해 members 에 저장한다
  const pinHash = (code, pin) => {
    let h = 2166136261;
    for (const ch of `${code}:${pin}`) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619) >>> 0; }
    return h.toString(16);
  };
  const DEMO_PIN = "1234";   // 데모방 · 가상 참여자의 4자리 (발표 설정 시트에 적어 둔다)
  const MAX_TRIES = 5;
  const LOCK_MS = 30000;

  function join(code, { nickname, budget, account, pin }) {
    const state = load(code);
    const id = state.next_id++;
    state.members.push({ id, nickname, budget, account, pin_hash: pinHash(code, pin), confirmed_at: null, gave_up_at: null });
    save(state);
    put(meKey(code), id);
    return id;
  }

  const myId = (code) => get(meKey(code));

  // 다른 브라우저(카톡 → 크롬 등)에서 다시 들어올 때: 내 이름 고르기 → 4자리. 5번 틀리면 30초 잠금
  function claim(code, memberId, pin) {
    const state = load(code);
    const m = member(state, memberId);
    const key = `flow:tries:${code}:${memberId}`;
    const t = get(key) || { n: 0, until: 0 };
    const nowMs = Date.now();
    if (t.until > nowMs) return { ok: false, lockedFor: Math.ceil((t.until - nowMs) / 1000) };
    if (m && m.pin_hash === pinHash(code, pin)) {
      drop(key);
      put(meKey(code), memberId);
      return { ok: true };
    }
    t.n += 1;
    if (t.n >= MAX_TRIES) { put(key, { n: 0, until: nowMs + LOCK_MS }); return { ok: false, lockedFor: LOCK_MS / 1000 }; }
    put(key, t);
    return { ok: false, left: MAX_TRIES - t.n };
  }

  // 시연: "다른 기기에서 열었다 치고" 이 브라우저의 내 자리 기억만 지운다
  const forgetMe = (code) => drop(meKey(code));
  const member = (state, id) => state.members.find((m) => m.id === id) || null;

  function reset(code) {
    drop(roomKey(code));
    drop(meKey(code));
    drop("flow:bank-linked");   // 시연을 처음부터: 은행 연결 동의도 다시 보이게
  }

  /* ---------- 불러오기 · 조정 (확인 화면 규칙: docs/BUILD_ORDER.md) ---------- */

  function importTx(code, memberId) {
    const state = load(code);
    const me = member(state, memberId);
    const { owner } = ACCOUNTS[me.account];
    const rows = bankRows(me.account);
    const saved = new Set(state.expenses.filter((e) => e.member_id === memberId).map((e) => e.ref));
    const deposits = rows.filter((r) => r.inout === "입금");
    const out = rows.filter((r) => r.inout === "출금");
    const stamp = now().getTime();
    let added = 0;
    out.forEach((r) => {
      if (saved.has(r.ref)) return;  // 이미 저장한 거래는 두 번 저장하지 않는다
      let auto = null;
      let hint = null;
      if (r.date < state.room.start_date || r.date > state.room.end_date) auto = "기간 밖";
      else if (deposits.some((d) => d.content === r.content && d.amount === r.amount && d.when >= r.when)) auto = "가승인 취소";
      else if (/충전/.test(r.content) || r.content === owner) hint = "충전·내 계좌 이체일 수 있어요";
      else if (out.some((o) => o.ref !== r.ref && o.date === r.date && o.content === r.content && o.amount === r.amount)) hint = "중복일 수 있어요";
      state.expenses.push({
        member_id: memberId, ref: r.ref, merchant: r.content, amount: r.amount, people: 1,
        excluded: auto !== null, auto, hint, spent_on: r.date, time: r.time, created_at: stamp,
      });
      added += 1;
    });
    save(state);
    return added;
  }

  function updateItem(code, memberId, ref, change) {
    const state = load(code);
    const item = state.expenses.find((e) => e.member_id === memberId && e.ref === ref);
    if (!item || item.auto) return;
    Object.assign(item, change);
    member(state, memberId).confirmed_at = null;   // 바꾸면 다시 조정 완료를 눌러야 한다
    save(state);
  }

  function confirm(code, memberId) {
    const state = load(code);
    member(state, memberId).confirmed_at = now().getTime();
    save(state);
  }

  function giveUp(code, memberId) {
    const state = load(code);
    member(state, memberId).gave_up_at = now().getTime();
    save(state);
  }

  /* ---------- 계산 (app/board/calc.py 와 같은 규칙) ---------- */

  const share = (amount, people) => Math.floor((2 * amount + people) / (2 * people));
  const pct = (part, whole) => (whole ? Math.floor((200 * part + whole) / (2 * whole)) : 0);

  function totals(state, m) {
    const mine = state.expenses.filter((e) => e.member_id === m.id);
    const spent = mine.filter((e) => !e.excluded).reduce((s, e) => s + share(e.amount, e.people), 0);
    const unconfirmed = m.confirmed_at == null || mine.some((e) => e.created_at > m.confirmed_at);
    return { spent, remaining: m.budget - spent, usage_pct: pct(spent, m.budget), over: spent > m.budget, unconfirmed, items: mine };
  }

  function roomInfo(room) {
    const t = today();
    const total = daysBetween(room.start_date, room.end_date) + 1;
    const resultOpen = t >= room.end_date;
    return {
      code: room.code, name: room.name, start_date: room.start_date, end_date: room.end_date, today: t,
      started: t >= room.start_date, ended: t > room.end_date, result_open: resultOpen,
      day_index: Math.min(Math.max(daysBetween(room.start_date, t) + 1, 0), total),
      total_days: total, days_left: Math.max(daysBetween(t, room.end_date), 0),
    };
  }

  // GET /api/board/{code} 와 같은 모양
  function board(state, preview) {
    const room = roomInfo(state.room);
    room.preview = Boolean(preview) && !room.result_open;
    const players = state.members.map((m) => ({ member_id: m.id, nickname: m.nickname }));
    if (!room.result_open && !room.preview) return { room, member_count: state.members.length, players, members: [] };

    const rows = state.members.map((m) => {
      if (m.gave_up_at != null) {
        return { member_id: m.id, nickname: m.nickname, budget: null, spent: null, remaining: null, usage_pct: null,
          rank: null, medal: null, over: false, unconfirmed: false, gave_up: true };
      }
      const t = totals(state, m);
      return { member_id: m.id, nickname: m.nickname, budget: m.budget, spent: t.spent, remaining: t.remaining,
        usage_pct: t.usage_pct, rank: null, medal: null, over: t.over, unconfirmed: t.unconfirmed, gave_up: false };
    });
    const ranked = rows.filter((r) => !r.gave_up);
    ranked.forEach((r) => {
      r.rank = 1 + ranked.filter((o) => o.spent * r.budget < r.spent * o.budget).length;
      r.medal = { 1: "gold", 2: "silver", 3: "bronze" }[r.rank] || null;
    });
    ranked.sort((a, b) => a.rank - b.rank || a.member_id - b.member_id);
    const quitAt = Object.fromEntries(state.members.map((m) => [m.id, m.gave_up_at]));
    const quit = rows.filter((r) => r.gave_up).sort((a, b) => quitAt[b.member_id] - quitAt[a.member_id] || a.member_id - b.member_id);
    return { room, member_count: state.members.length, players, members: ranked.concat(quit) };
  }

  /* ---------- 화면에 보이는 말 ---------- */

  // 계좌는 실제 은행 앱처럼 "은행 이름 + 끝자리"로 보여 준다 (등록계좌조회의 bank_name · account_num_masked 모양)
  const BANK_NAME = "가상은행";
  const accountName = (key) => (ACCOUNTS[key] ? `${BANK_NAME} ···${ACCOUNTS[key].masked.slice(-4)}` : "내 계좌");

  // 은행 연결(사용자 인증 · 동의)은 사람마다 한 번. 한 번 연결하면 다른 방에서는 계좌 목록으로 바로 간다 (실제: 토큰 재사용)
  const BANK_KEY = "flow:bank-linked";
  const bankLinked = () => Boolean(get(BANK_KEY));
  const linkBank = () => put(BANK_KEY, true);
  const daysLeft = (n) => `D-${n}`;

  /* ---------- 플레이어 토큰 (board.js 와 같은 규칙: member_id 로 색) ---------- */

  function token(id, nickname, extra) {
    const pc = `p${(((Number(id) - 1) % 6) + 6) % 6 + 1}`;
    return `<span class="token ${pc}${extra ? " " + extra : ""}" aria-hidden="true">${esc(Array.from(String(nickname || "?"))[0])}</span>`;
  }

  /* ---------- 시연 막대: 영수증 위 "참여자 시점 | 개발자 시점" + 설정 (10/3 회의: 버튼 두 개, 10/6 ⋯ → 설정) ---------- */
  // 서비스 화면(영수증)과 다른 질감의 어두운 막대라 보는 사람이 "시연 조작"인 걸 알 수 있다.
  //   참여자 시점: 데모방에 계좌 A 로 참여한 발표자가 되어 내 페이지부터 (불러오기 → 1/N · 제외 → 조정 완료 → 결과 카드)
  //   개발자 시점: 방 만들기부터 기능을 차례로 (링크 → 닉네임 → 은행 연결 → 내 페이지 → 가상 참여자 · 마감 → 결과 카드)
  const DEMO_DAY = "2026-10-08";
  const MODE_KEY = "flow:mode";

  function startParticipant() {
    drop(roomKey("demo"));
    seedDemo();
    put(meKey("demo"), 1);
    put(BANK_KEY, true);
    put(TODAY_KEY, DEMO_DAY);
    put(MODE_KEY, "participant");
    location.href = "/flow/r/demo/me";
  }

  function startDeveloper() {
    drop(TODAY_KEY);
    drop(BANK_KEY);   // 은행 연결 동의 화면부터 보여 주기
    put(MODE_KEY, "developer");
    location.href = "/flow";
  }

  function toolbar(code, page) {
    const forced = get(TODAY_KEY);
    const mode = get(MODE_KEY);
    const enc = code ? encodeURIComponent(code) : "";
    const state = code ? load(code) : null;
    const endDay = state ? state.room.end_date : DEMO_DAY;

    const bar = document.createElement("div");
    bar.className = "demo-bar";
    bar.innerHTML = `
      <span class="db-label">시연</span>
      <span class="db-seg" role="group" aria-label="시연 시점">
        <button type="button" data-act="participant" aria-pressed="${mode === "participant"}">참여자 시점</button>
        <button type="button" data-act="developer" aria-pressed="${mode === "developer"}">개발자 시점</button>
      </span>
      <button type="button" class="db-more db-set" data-act="open" aria-haspopup="dialog" aria-label="발표 설정 열기${forced ? `, 지금 ${md(forced)} 로 보는 중` : ""}">${forced ? `<span class="db-day">${md(forced).replace(/\(.\)/, "")}</span>` : ""}<span>설정</span></button>`;

    const row = (act, title, desc, href) => {
      const sub = desc ? `<span>${desc}</span>` : "";
      return href
        ? `<a class="ds-row" href="${href}"><b>${title}</b>${sub}</a>`
        : `<button type="button" class="ds-row" data-act="${act}"><b>${title}</b>${sub}</button>`;
    };
    const hasDummies = state && ["짠돌이", "카페중독", "큰손", "포기각"].every((n) => state.members.some((m) => m.nickname === n));

    const sheet = document.createElement("div");
    sheet.className = "demo-sheet";
    sheet.hidden = true;
    sheet.innerHTML = `
      <div class="ds-backdrop" data-act="close"></div>
      <section class="ds-panel" role="dialog" aria-modal="true" aria-labelledby="ds-title">
        <span class="ds-handle" aria-hidden="true"></span>
        <h2 id="ds-title">발표 설정</h2>
        <p class="ds-sub">발표할 때만 써요. 실제 서비스에는 없어요.</p>
        <div class="ds-list">
          <button type="button" class="ds-row ds-toggle" role="switch" aria-checked="${Boolean(forced)}" data-act="${forced ? "day-real" : "day-end"}">
            <b>결과 날로 보기</b><span>${forced ? `${md(forced)} 로 보는 중이에요. 끄면 진짜 오늘로` : `오늘을 마감일 ${md(endDay)} 로 바꿔요`}</span>
            <i class="ds-switch" aria-hidden="true"></i>
          </button>
          ${code ? row("", "지금 결과 보기", "마감 전이어도 지금 기록으로", `/flow/r/${enc}/board?preview=1`) : ""}
          ${code && code !== "demo" && !hasDummies ? row("fill", "가상 친구 4명 넣기", "짠돌이 · 카페중독 · 큰손 · 포기각") : ""}
          ${code && get(meKey(code)) != null ? row("forget", "다른 폰에서 들어온 것처럼", `데모 4자리는 ${DEMO_PIN}`) : ""}
          ${row("reset", "처음부터 다시", code ? "참여 · 은행 연결 · 기록을 지워요" : "은행 연결 · 날짜를 처음으로")}
        </div>
        <button type="button" class="ds-close" data-act="close">닫기</button>
      </section>`;

    const openSheet = () => { sheet.hidden = false; document.body.style.overflow = "hidden"; sheet.querySelector(".ds-close").focus(); };
    const closeSheet = () => { sheet.hidden = true; document.body.style.overflow = ""; bar.querySelector(".db-more").focus(); };
    const onAct = (ev) => {
      const el = ev.target.closest("[data-act]");
      if (!el) return;
      const act = el.getAttribute("data-act");
      if (act === "participant" && mode !== "participant") startParticipant();
      if (act === "developer" && mode !== "developer") startDeveloper();
      if (act === "open") openSheet();
      if (act === "close") closeSheet();
      if (act === "day-real") { drop(TODAY_KEY); location.reload(); }
      if (act === "day-end") { put(TODAY_KEY, endDay); location.reload(); }
      if (act === "fill") { fillDummies(code); location.reload(); }
      if (act === "forget") { forgetMe(code); location.href = `/flow/r/${enc}`; }
      if (act === "reset") {
        if (code === "demo" && mode === "participant") { startParticipant(); return; }
        if (!code) { drop(TODAY_KEY); drop(BANK_KEY); location.reload(); return; }
        reset(code); location.href = code === "demo" ? "/flow/r/demo" : "/flow";
      }
    };
    bar.addEventListener("click", onAct);
    sheet.addEventListener("click", onAct);
    document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && !sheet.hidden) closeSheet(); });
    document.body.prepend(bar);
    document.body.append(sheet);
    return page;
  }

  /* ---------- 아래 고정 탭: 참여한 뒤에는 [내 기록 | 결과] 두 곳만 오간다 (토스 · 카카오뱅크 아래 탭) ---------- */

  const TAB_ICON = {
    me: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 3h12v18l-2-1.5-2 1.5-2-1.5-2 1.5-2-1.5L6 21z"/><path d="M9 8h6M9 12h6M9 16h3"/></svg>',
    result: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="14" r="6"/><path d="M8.5 3h7l-2 6.2M10.5 9.2L8.5 3"/><path d="M12 11.5v5"/></svg>',
    lock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>',
  };

  function tabbar(code, active) {
    if (!code || myId(code) == null) return;
    const state = load(code);
    if (!state || !member(state, myId(code))) return;
    const info = roomInfo(state.room);
    const enc = encodeURIComponent(code);
    const sealed = !info.result_open;
    const nav = document.createElement("nav");
    nav.className = "tabbar";
    nav.setAttribute("aria-label", "이 방에서 이동");
    nav.innerHTML = `
      <a href="/flow/r/${enc}/me"${active === "me" ? ' aria-current="page"' : ""}>${TAB_ICON.me}<span>내 기록</span></a>
      <a href="/flow/r/${enc}/board"${active === "result" ? ' aria-current="page"' : ""}>${TAB_ICON.result}<span>결과${sealed ? ` <em>${TAB_ICON.lock}D-${info.days_left}</em>` : ""}</span></a>`;
    document.body.append(nav);
    document.body.classList.add("has-tabbar");
  }

  return {
    ACCOUNTS, BANK_NAME, md, won, esc, today, addDays, parse, token, accountName, daysLeft, bankLinked, linkBank,
    load, createRoom, join, myId, member, reset, claim, tabbar,
    importTx, updateItem, confirm, giveUp, totals, roomInfo, board, share, toolbar, roomLink,
  };
})();
