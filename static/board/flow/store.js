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

  const TODAY_KEY = "flow:today";   // 시연 도구 막대의 "날짜 바꿔 보기"
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
    // db/seed.sql 의 데모 방과 같은 구성 (발표자는 시연 중에 직접 참여한다)
    const at = (m, d, h, mi = 0) => new Date(2026, m - 1, d, h, mi).getTime();
    const state = {
      room: { code: "demo", name: "데모 방", start_date: "2026-10-02", end_date: "2026-10-08" },
      next_id: 5,
      members: [
        { id: 1, nickname: "짠돌이", budget: 100000, account: null, confirmed_at: at(10, 7, 21), gave_up_at: null },
        { id: 2, nickname: "카페중독", budget: 80000, account: null, confirmed_at: at(10, 7, 22, 30), gave_up_at: null },
        { id: 3, nickname: "큰손", budget: 70000, account: null, confirmed_at: null, gave_up_at: null },
        { id: 4, nickname: "포기각", budget: 50000, account: null, confirmed_at: null, gave_up_at: at(10, 4, 23) },
      ],
      expenses: [
        { member_id: 1, ref: "seed-1", merchant: "시연용 합계", amount: 22000, people: 1, excluded: false, auto: null, hint: null, spent_on: "2026-10-07", created_at: at(10, 3, 12) },
        { member_id: 2, ref: "seed-2", merchant: "시연용 합계", amount: 52000, people: 1, excluded: false, auto: null, hint: null, spent_on: "2026-10-07", created_at: at(10, 3, 12) },
        { member_id: 3, ref: "seed-3", merchant: "시연용 합계", amount: 85000, people: 1, excluded: false, auto: null, hint: null, spent_on: "2026-10-07", created_at: at(10, 3, 12) },
        { member_id: 4, ref: "seed-4", merchant: "시연용 합계", amount: 61000, people: 1, excluded: false, auto: null, hint: null, spent_on: "2026-10-04", created_at: at(10, 3, 12) },
      ],
    };
    put(roomKey("demo"), state);
    return state;
  }

  function load(code) {
    const state = get(roomKey(code));
    if (state) return state;
    return code === "demo" ? seedDemo() : null;
  }
  const save = (state) => put(roomKey(state.room.code), state);

  function createRoom({ name, start_date, end_date }) {
    let code;
    do { code = Array.from({ length: 6 }, () => CODE_CHARS[Math.floor(Math.random() * CODE_CHARS.length)]).join(""); }
    while (get(roomKey(code)) || code === "demo");
    save({ room: { code, name, start_date, end_date }, next_id: 1, members: [], expenses: [] });
    return code;
  }

  function join(code, { nickname, budget, account }) {
    const state = load(code);
    const id = state.next_id++;
    state.members.push({ id, nickname, budget, account, confirmed_at: null, gave_up_at: null });
    save(state);
    put(meKey(code), id);
    return id;
  }

  const myId = (code) => get(meKey(code));
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

  /* ---------- 시연 도구 막대 (개발자 시점 버튼) ---------- */

  function toolbar(code, page) {
    const forced = get(TODAY_KEY);
    const bar = document.createElement("nav");
    bar.className = "flowbar";
    bar.setAttribute("aria-label", "시연 도구");
    const preview = code ? `<a href="/flow/r/${encodeURIComponent(code)}/board?preview=1">결과 미리 보기</a>` : "";
    const reset = code ? '<button type="button" data-act="reset">이 방 처음부터</button>' : "";
    const demo = code === "demo" ? "" : '<a href="/flow/r/demo">발표용 데모 방</a>';
    bar.innerHTML = `
      <span class="fb-chip">시연 모드</span>
      ${demo}
      ${preview}
      <button type="button" data-act="day">${forced ? `날짜 ${md(forced)} → 진짜 오늘로` : "발표날(10/8)로 보기"}</button>
      ${reset}`;
    bar.addEventListener("click", (ev) => {
      const act = ev.target.getAttribute("data-act");
      if (act === "day") { if (forced) drop(TODAY_KEY); else put(TODAY_KEY, "2026-10-08"); location.reload(); }
      if (act === "reset") { reset(code); location.href = code === "demo" ? "/flow/r/demo" : "/flow"; }
    });
    document.body.prepend(bar);
    return page;
  }

  return {
    ACCOUNTS, BANK_NAME, md, won, esc, today, addDays, parse, token, accountName, daysLeft, bankLinked, linkBank,
    load, createRoom, join, myId, member, reset,
    importTx, updateItem, confirm, giveUp, totals, roomInfo, board, share, toolbar,
  };
})();
