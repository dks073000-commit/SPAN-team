// 보드 레인 화면: /r/{code}/board = 마감일 결과 카드 (10/3 회의)
// 기간 중에는 순위를 보여주지 않고 "언제 열리는지"만 보여 준다 (봉인 화면).
// 데이터는 /api/board/{code} (형식은 app/board/API.md). 여기서 금액을 다시 계산하지 않는다.
// "나"는 localStorage 의 member_id:{code}.
// 시연용: ?preview=1 이면 마감 전에도 결과 카드를 미리 본다.
// 개발용: ?sample 을 붙이면 예시 데이터로 그린다 (&preview=1 결과, &end 마감일인 척, &guest 참여 전, &me=4 다른 사람 시점).
// 시연용 전체 흐름: /flow/r/{code}/board 는 브라우저에 저장한 가짜 데이터(static/board/flow/store.js)로 그린다.

(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const isSample = params.has("sample");
  const wantPreview = ["1", "true", "result"].includes(params.get("preview"));
  const pathMatch = location.pathname.match(/^(\/flow)?\/r\/([^/]+)\/board/) || [];
  const isFlow = Boolean(pathMatch[1]);
  const code = decodeURIComponent(pathMatch[2] || "");
  const base = isFlow ? "/flow" : "";
  const myPage = isFlow ? `/flow/r/${encodeURIComponent(code)}/me` : `/r/${encodeURIComponent(code)}/add`;
  const roomPage = `${base}/r/${encodeURIComponent(code)}`;

  const WD = ["일", "월", "화", "수", "목", "금", "토"];
  const won = (n) => Math.abs(Math.round(n)).toLocaleString("ko-KR");
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  // 서버가 준 "YYYY-MM-DD"를 로컬 날짜로 읽는다 (toISOString 을 쓰지 않는다: CLAUDE.md 시간대 규칙)
  const day = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
  const md = (s) => { const d = day(s); return `${d.getMonth() + 1}/${d.getDate()}(${WD[d.getDay()]})`; };

  // 서비스 이름·로고 자리. 투표 전 임시로 A안(톱니 방패 + 텅장방어전)이 기본. ?logo=c / ?logo=d 로 다른 후보를 미리 본다 (정해지면 하나만 남긴다)
  const SHIELD_A = '<svg class="mark-a" viewBox="0 0 60 68" aria-hidden="true"><path d="M6 9 L9 4 L12 9 L15 4 L18 9 L21 4 L24 9 L27 4 L30 9 L33 4 L36 9 L39 4 L42 9 L45 4 L48 9 L51 4 L54 9 V31 C54 46 44 57 30 64 C16 57 6 46 6 31 Z" fill="#fff" stroke="#1c1c21" stroke-width="3.2" stroke-linejoin="round"/><rect x="10" y="28" width="40" height="10" fill="#e4ff4a"/><polyline points="17,19 23.5,45 30,26 36.5,45 43,19" fill="none" stroke="#1c1c21" stroke-width="4.2" stroke-linecap="round" stroke-linejoin="round"/><line x1="10.5" y1="29.5" x2="49.5" y2="29.5" stroke="#1c1c21" stroke-width="3.4" stroke-linecap="round"/><line x1="10.5" y1="36.5" x2="49.5" y2="36.5" stroke="#1c1c21" stroke-width="3.4" stroke-linecap="round"/></svg>';
  const SHIELD_C = '<svg class="mark-c" viewBox="0 0 11 11" shape-rendering="crispEdges" aria-hidden="true"><g fill="#1c1c21"><rect x="0" y="0" width="11" height="1"/><rect x="0" y="1" width="1" height="6"/><rect x="10" y="1" width="1" height="6"/><rect x="1" y="7" width="1" height="1"/><rect x="9" y="7" width="1" height="1"/><rect x="2" y="8" width="1" height="1"/><rect x="8" y="8" width="1" height="1"/><rect x="3" y="9" width="1" height="1"/><rect x="7" y="9" width="1" height="1"/><rect x="4" y="10" width="3" height="1"/><rect x="2" y="2" width="1" height="2"/><rect x="8" y="2" width="1" height="2"/><rect x="5" y="3" width="1" height="1"/><rect x="3" y="5" width="1" height="1"/><rect x="5" y="5" width="1" height="1"/><rect x="7" y="5" width="1" height="1"/><rect x="4" y="6" width="1" height="1"/><rect x="6" y="6" width="1" height="1"/></g><rect x="1" y="4" width="9" height="1" fill="#c8e600"/></svg>';
  const FLAG = '<svg class="flag" viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 15V1.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M4.3 2.2h8.6l-2.2 3.2 2.2 3.2H4.3z" fill="#fff" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  const logo = (params.get("logo") || "").toLowerCase();

  // D안: 흑백 컴퓨터 창. 진행 막대가 방 기간을 그대로 보여 준다
  function brandD(room) {
    let label = "방어 준비 중";
    let done = 0;
    let total = 0;
    if (room) {
      total = room.total_days;
      if (!room.started) label = `${md(room.start_date)} 방어 시작`;
      else if (room.result_open) { label = "방어 완료"; done = total; }
      else { label = "방어 중"; done = room.day_index; }
    }
    const pct = total ? Math.round((done / total) * 100) : 0;
    const days = room && room.started ? `<span class="n">${done}/${total}</span>일` : "";
    return `
      <div class="brand-d" role="img" aria-label="텅장방어전${room && room.started ? ` · ${done}일째 / ${total}일` : ""}">
        <p class="bd-title"><i aria-hidden="true"></i><span>텅장방어전.exe</span></p>
        <div class="bd-body">
          ${SHIELD_C.replace('class="mark-c"', 'class="mark-d"').replace(/fill="#c8e600"/, 'fill="#1c1c21"')}
          <div class="bd-state">
            <p>${label} ${days}</p>
            <div class="bd-bar"><span style="width:${pct}%"></span></div>
          </div>
        </div>
      </div>`;
  }

  function brand(room) {
    if (logo === "d") return brandD(room);
    if (logo === "c") {
      return `<p class="brand brand-c" aria-label="텅장방어전">${SHIELD_C}<span class="sub">텅장</span><span class="tall">방어전</span></p>`;
    }
    return `<p class="brand brand-a" aria-label="텅장방어전">${SHIELD_A}<span>텅장방어전</span></p>`;
  }

  function myId() {
    try {
      const raw = localStorage.getItem(`member_id:${code}`);
      // 방 레인은 숫자 문자열로, 또는 JSON 으로 저장할 수 있다
      return Number(raw && raw.startsWith('"') ? JSON.parse(raw) : raw) || null;
    } catch (e) { return null; }
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const el = document.createElement("script");
      el.src = src;
      el.onload = resolve;
      el.onerror = () => reject(Object.assign(new Error("server"), { kind: "server" }));
      document.head.appendChild(el);
    });
  }

  async function load() {
    if (isFlow) {
      const css = document.createElement("link");
      css.rel = "stylesheet";
      css.href = "/static/board/flow/flow.css";
      document.head.appendChild(css);
      await loadScript("/static/board/flow/store.js");
      const state = window.Flow.load(code);
      window.Flow.toolbar(code);   // 영수증 위 시연 막대 (참여자 시점 | 개발자 시점 + 도구)
      const bar = document.querySelector(".demo-bar");
      if (bar) document.querySelector(".counter").prepend(bar);
      window.Flow.tabbar(code, "result");   // 아래 고정 탭 [내 기록 | 결과]
      if (!state) throw Object.assign(new Error("missing"), { kind: "missing" });
      return { data: window.Flow.board(state, wantPreview), me: window.Flow.myId(code) };
    }
    if (isSample) {
      const res = await fetch("/static/board/sample-board.json", { cache: "no-store" });
      const data = await res.json();
      const room = data.room;
      if (params.has("end")) { room.result_open = true; room.today = room.end_date; room.day_index = room.total_days; room.days_left = 0; }
      room.preview = wantPreview && !room.result_open;
      if (!room.result_open && !room.preview) data.members = [];
      const me = params.has("guest") ? null : Number(params.get("me")) || data.sample_me;
      return { data, me };
    }
    let data = await fetchBoard();
    // 마감 자동 반영: 결과가 열리는 날(또는 시연 미리 보기)에만, 본인이 불러오기를 안 눌렀어도 거래가 반영되게 한다.
    // 지출 레인 API 를 화면에서 부른다 (레인끼리 import 하지 않는다, CLAUDE.md). 기간 중에는 부르지 않는다:
    // 남의 거래가 저장되면 그 사람이 갑자기 미확인이 되기 때문이다. 실패해도 결과 카드는 그대로 연다.
    if (data.room && (data.room.result_open || data.room.preview) && await settle()) {
      data = await fetchBoard().catch(() => data);
    }
    return { data, me: myId() };
  }

  async function fetchBoard() {
    const q = wantPreview ? "?preview=1" : "";
    const res = await fetch(`/api/board/${encodeURIComponent(code)}${q}`, { cache: "no-store" });
    if (res.status === 404) throw Object.assign(new Error("missing"), { kind: "missing" });
    if (!res.ok) throw Object.assign(new Error("server"), { kind: "server" });
    return res.json();
  }

  // POST /api/expenses/rooms/{code}/settle (지출 레인). 금액 · 상세는 돌려주지 않는다. 새로 저장한 게 있으면 true
  async function settle() {
    const ctrl = typeof AbortController === "function" ? new AbortController() : null;
    const timer = ctrl ? setTimeout(() => ctrl.abort(), 8000) : null;
    try {
      const res = await fetch(`/api/expenses/rooms/${encodeURIComponent(code)}/settle`, {
        method: "POST", cache: "no-store", signal: ctrl ? ctrl.signal : undefined,
      });
      if (!res.ok) return false;   // 404 · 은행 오류: 무시하고 지금 결과로 그린다
      const body = await res.json();
      return (body.members || []).some((m) => Number(m.added) > 0);
    } catch (e) {
      return false;                // 네트워크 오류 · 8초 넘김
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  function head(room) {
    let when;
    if (!room.started) when = `${md(room.start_date)} 시작 · ${room.total_days}일`;
    else if (room.result_open) when = `${md(room.start_date)} – ${md(room.end_date)} · ${room.total_days}일`;
    else when = `${md(room.start_date)} – ${md(room.end_date)} · ${room.day_index}일째 / ${room.total_days}일`;
    return `
      <header class="r-head r-reveal" style="--i:0">
        ${brand(room)}
        <h1 class="r-room">${esc(room.name)}</h1>
        <p class="r-meta">${when}</p>
      </header>`;
  }

  /* ---------- 플레이어 토큰: 사람마다 고유 색 (member_id 로 정한다, API.md) ---------- */

  const playerClass = (id) => `p${(((Number(id) - 1) % 6) + 6) % 6 + 1}`;
  function token(id, nickname, extra) {
    const first = Array.from(String(nickname || "?"))[0];
    return `<span class="token ${playerClass(id)}${extra ? " " + extra : ""}" aria-hidden="true">${esc(first)}</span>`;
  }

  /* ---------- 메달: 금 · 은 · 동 동전. 사람 토큰(각진 그림자 스티커)과 달리 그림자 없이 안쪽 점선 링 (영수증 절취선) ---------- */

  function medalSvg(kind, rank) {
    return `<svg class="medal-svg coin-${kind}" viewBox="0 0 40 40" aria-hidden="true">
      <circle class="coin" cx="20" cy="20" r="18.5"/>
      <circle class="ring" cx="20" cy="20" r="14"/>
      <text x="20" y="25.5" text-anchor="middle">${rank}</text>
    </svg>`;
  }

  /* ---------- 봉인: 마감일 전 ---------- */

  function renderSealed({ data, me }) {
    const { room, member_count: count } = data;
    const players = data.players || [];
    const joined = me != null;
    const dday = `D-${room.days_left}`;
    const lead = room.started
      ? `${md(room.end_date)} 순위 공개`
      : `${md(room.start_date)} 시작 · ${md(room.end_date)} 순위 공개`;
    $("receipt").innerHTML = `
      ${head(room)}
      <hr class="r-cut">
      <section class="r-seal r-reveal" style="--i:1" aria-label="결과 공개까지 남은 날">
        <p class="seal-d"><span class="num n">${dday}</span></p>
        <p class="seal-lead">${lead}</p>
      </section>
      <hr class="r-cut">
      <section class="r-prize r-reveal" style="--i:2" aria-label="아직 주인이 없는 메달">
        <div class="slots">${medalSvg("gold", 1)}${medalSvg("silver", 2)}${medalSvg("bronze", 3)}</div>
        <p class="prize-q">누가 가져갈까?</p>
      </section>
      <hr class="r-cut">
      <section class="r-reveal" style="--i:3">
        <p class="seal-who">참전 <span class="n">${count}</span>명</p>
        <ul class="lineup">${players.map((p) => `
          <li class="player">${token(p.member_id, p.nickname, p.member_id === me ? "is-me" : "")}<span class="pname">${esc(p.nickname)}</span></li>`).join("")}</ul>
        <p class="invite-row"><button type="button" class="invite-copy" id="invite-copy">초대 링크 복사</button></p>
        <p class="privacy-note">결과 날에도 친구에게는 총액만 보여요</p>
      </section>`;
    // 친구 더 부르기: 참여한 뒤에는 방 홈으로 못 돌아가니 링크를 여기서 다시 꺼낸다
    // (시연 흐름은 방 이름 · 기간을 담은 링크라 다른 폰에서도 열린다)
    $("invite-copy").addEventListener("click", (ev) => copyInvite(ev.currentTarget));
    // 시연 흐름에서 참여한 사람은 아래 고정 탭 [내 기록 | 결과] 로 오가니 버튼을 겹쳐 두지 않는다
    const tabbed = isFlow && document.body.classList.contains("has-tabbar");
    $("actions").innerHTML = tabbed ? ""
      : joined ? `<a class="btn" href="${myPage}">내 페이지로</a>`
      : `<a class="btn" href="${roomPage}">이 방에 참여하기</a>`;
    $("actions").hidden = tabbed;
    document.title = `${room.name} · ${dday}`;
  }

  function inviteLink() {
    if (isFlow && window.Flow && window.Flow.roomLink) return window.Flow.roomLink(code);
    return `${location.origin}/r/${encodeURIComponent(code)}`;
  }

  async function copyInvite(btn) {
    const link = inviteLink();
    const done = (msg) => {
      btn.textContent = msg;
      setTimeout(() => { btn.textContent = "초대 링크 복사"; }, 1800);
    };
    try {
      await navigator.clipboard.writeText(link);
      done("복사했어요");
    } catch (e) {
      window.prompt("이 링크를 복사해 단톡방에 보내 주세요", link);   // 복사 권한이 없는 브라우저
    }
  }

  /* ---------- 조정 먼저: 내가 미확인일 때 ---------- */

  function renderConfirmFirst({ data }) {
    const { room } = data;
    $("receipt").innerHTML = `
      ${head(room)}
      <hr class="r-cut">
      <section class="r-seal r-reveal" style="--i:1">
        <p class="seal-lead">조정을 마치면 내 결산이 나와요</p>
        <p class="r-pace">1/N · 제외를 고르고 조정 완료를 눌러 주세요.</p>
      </section>`;
    $("actions").innerHTML = `<a class="btn" href="${myPage}">조정하러 가기</a>`;
    $("actions").hidden = false;
    document.title = `조정 먼저 · ${room.name}`;
  }

  /* ---------- 결산 영수증 (결과 카드) ---------- */

  // 결산 도장: 항복 → 항복, 넘김 → 텅장 엔딩, 1위 → 방어전 MVP, 예산 안 → 완주
  function verdict(m) {
    if (m.gave_up) return { text: "항복", cls: "stamp-gray" };
    if (m.over) return { text: "텅장 엔딩", cls: "stamp-red" };
    if (m.rank === 1) return { text: "방어전 MVP", cls: "stamp-blue" };
    return { text: "완주", cls: "stamp-blue" };
  }

  function rankCell(m) {
    if (m.gave_up) return `<span class="no is-flag" aria-label="항복">${FLAG}</span>`;
    if (m.medal) return `<span class="no medal" role="img" aria-label="${m.rank}위">${medalSvg(m.medal, m.rank)}</span>`;
    return `<span class="no">${m.rank}</span>`;
  }

  function resultHero(mine) {
    if (!mine) return "";
    const nick = esc(mine.nickname);
    const v = verdict(mine);
    let line;
    if (mine.gave_up) line = `${nick}님은 이번엔 항복했어요. 다음 방에서 다시 버텨요`;
    else if (mine.over) line = `${nick}님은 ${mine.rank}위, <span class="n">${won(mine.remaining)}</span>원 넘겼어요`;
    else line = `${nick}님은 ${mine.rank}위로 <mark><span class="n">${won(mine.remaining)}</span>원 남기고</mark> 버텼어요`;
    return `
      <section class="s-me r-reveal" style="--i:2">
        <p class="s-me-line">${line}</p>
        <span class="stamp stamp-xl ${v.cls} s-stamp">${v.text}</span>
      </section>
      <hr class="r-cut">`;
  }

  function renderResult({ data, me }) {
    const { room, members } = data;
    const mine = members.find((m) => m.member_id === me);
    const playing = members.filter((m) => !m.gave_up);
    const finishers = playing.filter((m) => !m.over).length;
    const kept = playing.reduce((sum, m) => sum + Math.max(m.remaining, 0), 0);

    const rows = members.map((m, i) => {
      const v = verdict(m);
      const isMe = m.member_id === me;
      return `
        <li class="s-line r-reveal${isMe ? " is-me" : ""}${m.gave_up ? " is-quit" : ""}" style="--i:${i + 4}">
          ${rankCell(m)}
          <span class="who">
            ${token(m.member_id, m.nickname, m.gave_up ? "is-quit" : isMe ? "is-me" : "")}
            <span class="name">${esc(m.nickname)}</span>
            ${isMe ? '<span class="me-tag">나</span>' : ""}
            <span class="stamp ${v.cls}">${v.text}</span>
            ${m.unconfirmed ? '<span class="unc-tag">미확인</span>' : ""}
          </span>
          <span class="pct">${m.gave_up ? "" : m.usage_pct + "%"}</span>
        </li>`;
    }).join("");

    $("slip").classList.add("is-story");
    $("receipt").innerHTML = `
      <header class="r-head r-reveal" style="--i:0">
        ${brand(room)}
        <h1 class="s-title">결산 영수증</h1>
        <p class="r-meta">${esc(room.name)}</p>
        <p class="r-meta">${md(room.start_date)} – ${md(room.end_date)} · ${room.total_days}일</p>
      </header>
      <hr class="r-cut">
      ${resultHero(mine)}
      <ol class="s-lines">${rows}</ol>
      <hr class="r-cut">
      <dl class="s-total r-reveal" style="--i:${members.length + 5}">
        <div><dt>예산 안에서 버틴 사람</dt><dd><span class="n">${finishers}</span> / <span class="n">${members.length}</span>명</dd></div>
        <div><dt>다 같이 남긴 돈</dt><dd><span class="n">${won(kept)}</span>원</dd></div>
      </dl>`;

    lastResult = { data, me };
    $("actions").innerHTML = `
      <div class="save-row">
        <button class="btn" type="button" id="save-story">스토리로 저장</button>
        <button class="btn btn-line" type="button" id="save-sticker">영수증만 저장</button>
      </div>
      <p class="story-hint">영수증만 저장하면 배경이 투명해서 사진 위에 붙일 수 있어요</p>
      <p class="story-hint" id="save-error" hidden>저장하지 못했어요. 화면을 캡처해 주세요</p>
      ${mine && !mine.gave_up && !document.body.classList.contains("has-tabbar") ? `<a class="link" href="${myPage}">내 페이지로</a>` : ""}`;
    $("actions").hidden = false;
    $("save-story").addEventListener("click", (ev) => saveImage("story", room, ev.currentTarget));
    $("save-sticker").addEventListener("click", (ev) => saveImage("sticker", room, ev.currentTarget));
    document.title = `결산 영수증 · ${room.name}`;
  }

  /* ---------- 공유용 "나만의 결산 영수증" 이미지 ---------- */
  // 화면의 결과 카드와 따로 만든다. 참고: Receiptify(영수증 모양 공유), 심리테스트 결과 카드(큰 칭호 하나 + 나도 해보기 링크)
  //   스토리로 저장: 9:16(1080×1920) 어두운 바탕 위에 살짝 기운 영수증
  //   영수증만 저장: 톱니 영수증만 투명 배경(가로 1080) → 인스타 스토리 사진 위에 스티커처럼 붙인다
  const HTML_TO_IMAGE = "https://cdn.jsdelivr.net/npm/html-to-image@1.11.11/dist/html-to-image.js";
  const SHARE_W = 360;

  // unicode-range 가 영수증 글자와 겹치는 @font-face 만 골라 글꼴 파일을 data URL 로 넣는다
  // (Noto Sans KR 은 수백 조각으로 나뉘어 있어서 다 넣으면 느리다)
  function rangeHits(range, used) {
    return range.split(",").some((part) => {
      const [a, b] = part.trim().replace(/^U\+/i, "").split("-");
      const lo = parseInt(a.replace(/\?/g, "0"), 16);
      const hi = b ? parseInt(b, 16) : parseInt(a.replace(/\?/g, "F"), 16);
      for (const cp of used) if (cp >= lo && cp <= hi) return true;
      return false;
    });
  }
  async function toDataURL(url) {
    const blob = await (await fetch(url)).blob();
    return new Promise((resolve) => { const r = new FileReader(); r.onload = () => resolve(r.result); r.readAsDataURL(blob); });
  }
  async function fontCSSFor(node) {
    const used = new Set(Array.from(node.textContent + "0123456789,%원").map((c) => c.codePointAt(0)));
    const links = Array.from(document.querySelectorAll('link[rel="stylesheet"][href*="fonts.googleapis.com"]'));
    let out = "";
    for (const link of links) {
      const css = await (await fetch(link.href)).text();
      for (const block of css.match(/@font-face\s*{[^}]*}/g) || []) {
        const range = /unicode-range:\s*([^;]+);/.exec(block);
        if (range && !rangeHits(range[1], used)) continue;
        const src = /url\((https:[^)]+)\)/.exec(block);
        if (!src) continue;
        out += block.replace(src[1], await toDataURL(src[1])) + "\n";
      }
    }
    return out;
  }

  const homeLink = () => `${location.host}${isFlow ? "/flow" : "/"}`;

  // 장식용 바코드: 방 코드와 내 번호로 늘 같은 줄무늬 (스캔해도 아무 정보가 없다)
  function barcode(seed) {
    let h = 2166136261;
    for (const ch of seed) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619) >>> 0; }
    let x = 0;
    let bars = "";
    while (x < 236) {
      h = Math.imul(h ^ (h >>> 13), 1274126177) >>> 0;
      const w = 1 + (h % 3);
      const gap = 1 + ((h >>> 3) % 3);
      bars += `<rect x="${x}" width="${w}" height="40"/>`;
      x += w + gap;
    }
    return `<svg class="sr-barcode" viewBox="0 0 236 40" preserveAspectRatio="none" aria-hidden="true">${bars}</svg>`;
  }

  function shareReceipt(data, me) {
    const { room, members } = data;
    const mine = members.find((m) => m.member_id === me);
    const playing = members.filter((m) => !m.gave_up);
    const kept = playing.reduce((sum, m) => sum + Math.max(m.remaining, 0), 0);
    // 공유 이미지는 SNS 에 올라간다. 방 링크를 넣으면 모르는 사람이 친구 방에 들어올 수 있어서 서비스 첫 화면(방 만들기)만 넣는다
    const link = homeLink();
    const no = `${String(room.code).toUpperCase()}-${String(me || 0).padStart(4, "0")}`;
    const line = (k, v) => `<div class="sr-item"><dt>${k}</dt><span class="sr-dots" aria-hidden="true"></span><dd>${v}</dd></div>`;

    let mineHtml = "";
    if (mine) {
      const v = verdict(mine);
      const rank = mine.gave_up ? "항복" : `${mine.rank}위 / ${members.length}명`;
      mineHtml = `
        <section class="sr-me">
          <span class="stamp sr-verdict ${v.cls}">${v.text}</span>
          <p class="sr-who">${token(mine.member_id, mine.nickname, mine.gave_up ? "is-quit" : "is-me")}<b>${esc(mine.nickname)}</b>
            ${mine.medal ? medalSvg(mine.medal, mine.rank) : ""}</p>
          <dl class="sr-items">
            ${line("순위", rank)}
            ${mine.gave_up ? line("금액", "비공개") : `
              ${line("예산", `${won(mine.budget)}원`)}
              ${line("쓴 돈", `${won(mine.spent)}원`)}
              ${line("사용률", `${mine.usage_pct}%`)}`}
          </dl>
          ${mine.gave_up ? "" : `
            <div class="sr-total"><span>${mine.remaining >= 0 ? "남긴 돈" : "넘긴 돈"}</span>
              ${mine.remaining >= 0 ? `<mark>${won(mine.remaining)}원</mark>` : `<b>${won(mine.remaining)}원</b>`}</div>`}
        </section>
        <hr class="sr-cut">`;
    }

    const rows = members.map((m) => `
      <li${m.member_id === me ? ' class="is-me"' : ""}>
        <span class="sr-no">${m.gave_up ? FLAG : m.medal ? medalSvg(m.medal, m.rank) : m.rank}</span>
        <span class="sr-name">${esc(m.nickname)}</span>
        <span class="sr-pct">${m.gave_up ? "항복" : m.usage_pct + "%"}</span>
      </li>`).join("");

    return `
      <article class="share-receipt">
        ${brand(room)}
        <p class="sr-title">결산 영수증</p>
        <p class="sr-meta">${esc(room.name)}<br>${md(room.start_date)} – ${md(room.end_date)} · No.${esc(no)}</p>
        <hr class="sr-cut">
        ${mineHtml}
        <p class="sr-sub">이번 방 순위</p>
        <ol class="sr-rows">${rows}</ol>
        <hr class="sr-cut">
        <div class="sr-total sr-team"><span>다 같이 남긴 돈</span><b>${won(kept)}원</b></div>
        <hr class="sr-cut">
        ${barcode(no)}
        <p class="sr-link">${esc(link)}</p>
        <p class="sr-thanks">다음 주도 같이 버텨요</p>
      </article>`;
  }

  async function makeShareImage(kind) {
    await loadScript(HTML_TO_IMAGE);
    const holder = document.createElement("div");
    holder.className = "share-holder";
    document.body.appendChild(holder);
    try {
      let node;
      let width;
      let height;
      if (kind === "sticker") {
        holder.innerHTML = `<div class="sr-sticker">${shareReceipt(lastResult.data, lastResult.me)}</div>`;
        node = holder.firstElementChild;
        width = node.offsetWidth;
        height = node.offsetHeight;
      } else {
        holder.innerHTML = `
          <div class="sr-story">
            <p class="sf-top">이번 주 텅장 방어 결과</p>
            <div class="sf-slot"><div class="sf-tilt">${shareReceipt(lastResult.data, lastResult.me)}</div></div>
            <p class="sf-bottom">너도 버틸 수 있어? 친구랑 붙어 보기<br><b>${esc(homeLink())}</b></p>
          </div>`;
        node = holder.firstElementChild;
        // 영수증이 길어도 9:16 안에 다 들어가게 줄인다
        const slot = node.querySelector(".sf-slot");
        const tilt = node.querySelector(".sf-tilt");
        const scale = Math.min(1, slot.clientHeight / tilt.offsetHeight, slot.clientWidth / tilt.offsetWidth);
        tilt.style.transform = `rotate(-2.5deg) scale(${scale})`;
        width = SHARE_W;
        height = SHARE_W * 16 / 9;
      }
      await document.fonts.ready;
      const fontEmbedCSS = await fontCSSFor(node).catch(() => "");
      // 화면 밖에 둔 위치는 그림에 옮기지 않는다
      const style = { position: "static", left: "0", top: "0", margin: "0" };
      return await window.htmlToImage.toBlob(node, { width, height, pixelRatio: 1080 / SHARE_W, fontEmbedCSS, style });
    } finally {
      holder.remove();
    }
  }
  window.__tjShareImage = makeShareImage;   // 개발 확인용

  let lastResult = null;

  async function saveImage(kind, room, button) {
    const label = button.textContent;
    button.disabled = true;
    button.textContent = "영수증 뽑는 중이에요";
    try {
      const blob = await makeShareImage(kind);
      const safe = room.name.replace(/[\\/:*?"<>|\s]+/g, "_");
      const name = `텅장방어전_${kind === "sticker" ? "영수증" : "스토리"}_${safe}.png`;
      const file = new File([blob], name, { type: "image/png" });
      const phone = /Android|iPhone|iPad|Mobile/i.test(navigator.userAgent);
      if (phone && navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file] }).catch(() => {});   // 공유 시트: 인스타 스토리 · 카톡 · 사진에 저장
      } else {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      }
      button.textContent = label;
    } catch (e) {
      button.textContent = label;
      $("save-error").hidden = false;
    } finally {
      button.disabled = false;
    }
  }

  /* ---------- 오류 ---------- */

  function renderError(kind) {
    const missing = kind === "missing";
    $("receipt").innerHTML = `
      <header class="r-head">
        ${brand()}
        <h1 class="r-room">${missing ? "없는 방이에요" : "결과를 불러오지 못했어요"}</h1>
      </header>
      <hr class="r-cut">
      <p class="r-pace" style="text-align:center">${missing
        ? "링크가 맞는지 한 번 더 확인해 주세요."
        : "잠시 뒤에 다시 열어 주세요. 서버가 잠들어 있으면 첫 접속에 1분쯤 걸려요."}</p>`;
    $("actions").innerHTML = missing
      ? `<a class="btn" href="${isFlow ? "/flow" : "/"}">새 방 만들기</a>`
      : '<button class="btn" type="button" id="retry">다시 불러오기</button>';
    $("actions").hidden = false;
    const retry = $("retry");
    if (retry) retry.addEventListener("click", () => location.reload());
  }

  /* ---------- 시작 ---------- */

  async function start() {
    const receipt = $("receipt");
    try {
      const state = await load();
      const { room, members } = state.data;
      const mine = members.find((m) => m.member_id === state.me);
      $("sample-flag").hidden = !isSample || room.preview;
      if (!room.result_open && !room.preview) renderSealed(state);
      // 결과 페이지로 가려면 조정을 거쳐야 한다 (PRD). 시연용 미리 보기(?preview=1)에서는 막지 않는다
      else if (mine && mine.unconfirmed && !room.preview && !wantPreview) renderConfirmFirst(state);
      else renderResult(state);
      receipt.classList.add("is-printing");
    } catch (e) {
      renderError(e.kind || "server");
    } finally {
      receipt.setAttribute("aria-busy", "false");
    }
  }

  start();
})();
