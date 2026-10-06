// 발표용 시연 막대. /flow 로 들어온 브라우저에서만 실제 화면 위에 뜬다 (일반 사용자에게는 보이지 않는다).
// 화면 · 기능은 전부 실제 서비스 것이다 (방 만들기 /, 방 /r/{code}, 내 기록 /r/{code}/add, 결과 /r/{code}/board).
// 그래서 시연 중에 만든 방 링크는 진짜 링크다. 단톡방 · 관객 폰에서 열면 막대 없는 실제 서비스로 열리고 같은 방에 참여된다.
// 각 실제 화면은 <script src="/static/board/flow/demo-bar.js" defer> 한 줄만 둔다.
(function () {
  "use strict";
  const KEY = "flow:demo";   // /flow 가 켠다. 발표 설정의 "발표 모드 끄기"로 끈다
  const on = (() => { try { return localStorage.getItem(KEY) === "1"; } catch (e) { return false; } })();
  if (!on) return;

  const m = location.pathname.match(/^\/r\/([^/]+)/);
  const code = m ? decodeURIComponent(m[1]) : "";
  const enc = encodeURIComponent(code);
  const joined = (() => { try { return Boolean(code && localStorage.getItem(`member_id:${code}`)); } catch (e) { return false; } })();
  const drop = (k) => { try { localStorage.removeItem(k); } catch (e) {} };

  // 시연 막대 모양 · 클래스는 flow.css (.demo-bar · .demo-sheet). 실제 화면이 flow.css 를 이미 읽는다
  if (!document.querySelector('link[href="/static/board/flow/flow.css"]')) {
    const css = document.createElement("link");
    css.rel = "stylesheet";
    css.href = "/static/board/flow/flow.css";
    document.head.appendChild(css);
  }

  const bar = document.createElement("div");
  bar.className = "demo-bar";
  bar.innerHTML = `
    <span class="db-label">시연</span>
    <span class="db-seg" role="group" aria-label="시연 시점">
      <button type="button" data-act="developer" aria-pressed="true">개발자 시점</button>
    </span>
    <button type="button" class="db-more db-set" data-act="open" aria-haspopup="dialog" aria-label="발표 설정 열기"><span aria-hidden="true">⋯</span></button>`;

  const row = (act, title, desc, href) => {
    const sub = desc ? `<span>${desc}</span>` : "";
    return href
      ? `<a class="ds-row" href="${href}"><b>${title}</b>${sub}</a>`
      : `<button type="button" class="ds-row" data-act="${act}"><b>${title}</b>${sub}</button>`;
  };

  const sheet = document.createElement("div");
  sheet.className = "demo-sheet";
  sheet.hidden = true;
  sheet.innerHTML = `
    <div class="ds-backdrop" data-act="close"></div>
    <section class="ds-panel" role="dialog" aria-modal="true" aria-labelledby="ds-title">
      <span class="ds-handle" aria-hidden="true"></span>
      <h2 id="ds-title">발표 설정</h2>
      <p class="ds-sub">발표하는 이 브라우저에만 보여요. 친구에게 보낸 링크에는 없어요.</p>
      <div class="ds-list">
        ${code ? row("", "지금 결과 보기", "마감 전이어도 지금 기록으로 결과 카드", `/r/${enc}/board?preview=1`) : ""}
        ${code ? row("friends", "가상 친구 4명 넣기", "짠돌이 · 카페중독 · 큰손 · 포기각 (실제로 참여시켜요)") : ""}
        ${code && joined ? row("forget", "다른 폰에서 들어온 것처럼", "이 방의 참여 기억을 지우고 방 링크로") : ""}
        ${row("restart", "처음부터 다시", "방 만들기 화면으로")}
        ${row("off", "발표 모드 끄기", "이 막대를 숨겨요. 다시 켜려면 /flow")}
      </div>
      <button type="button" class="ds-close" data-act="close">닫기</button>
    </section>`;

  const openSheet = () => { sheet.hidden = false; document.body.style.overflow = "hidden"; sheet.querySelector(".ds-close").focus(); };
  const closeSheet = () => { sheet.hidden = true; document.body.style.overflow = ""; bar.querySelector(".db-more").focus(); };
  const onAct = (ev) => {
    const el = ev.target.closest("[data-act]");
    if (!el) return;
    const act = el.getAttribute("data-act");
    if (act === "developer" || act === "restart") location.href = "/";
    if (act === "open") openSheet();
    if (act === "close") closeSheet();
    if (act === "forget") { drop(`member_id:${code}`); drop(`pin:${code}`); location.href = `/r/${enc}`; }
    if (act === "off") { drop(KEY); location.reload(); }
    if (act === "friends") addFriends(el);
  };
  bar.addEventListener("click", onAct);
  sheet.addEventListener("click", onAct);
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && !sheet.hidden) closeSheet(); });

  // 가상 친구 4명: 실제 참여 API 로 이 방에 넣는다 (가짜 은행 계좌로 연결 → 결과 카드의 자동 반영이 거래를 불러온다).
  // 결과가 고르게 나오게 예산을 다르게 두고, 둘은 조정 완료 · 하나는 미확인 · 하나는 항복으로 만든다.
  // 이미 같은 닉네임이 있으면 건너뛴다. 다른 레인 코드를 부르지 않고 공개 API 만 쓴다.
  const FRIENDS = [
    { nickname: "짠돌이", budget: 400000, account: "BTG00000000000000000000A", confirm: true },
    { nickname: "카페중독", budget: 250000, account: "BTG00000000000000000000A", confirm: true },
    { nickname: "큰손", budget: 150000, account: "BTG00000000000000000000A", confirm: false },
    { nickname: "포기각", budget: 100000, account: "BTG00000000000000000000S", giveUp: true },
  ];
  const FRIEND_PIN = "0000";
  const post = (url, body, pin) => fetch(url, {
    method: "POST",
    headers: Object.assign({ "Content-Type": "application/json" }, pin ? { "X-Member-Pin": pin } : {}),
    body: body ? JSON.stringify(body) : undefined,
  });

  async function addFriends(el) {
    const label = el.querySelector("span");
    el.disabled = true;
    try {
      const res = await fetch(`/api/rooms/${enc}`, { cache: "no-store" });
      if (!res.ok) throw new Error("room");
      const taken = new Set((await res.json()).members.map((mm) => mm.nickname));
      let added = 0;
      for (const f of FRIENDS) {
        if (taken.has(f.nickname)) continue;
        if (label) label.textContent = `${f.nickname} 넣는 중이에요`;
        const j = await post(`/api/rooms/${enc}/members`, { nickname: f.nickname, budget: f.budget, pin: FRIEND_PIN, fintech_use_num: f.account });
        if (!j.ok) continue;
        const id = (await j.json()).id;
        added += 1;
        if (f.confirm) {
          await post("/api/expenses/import", { member_id: id }, FRIEND_PIN);
          await post("/api/expenses/confirm", { member_id: id }, FRIEND_PIN);
        }
        if (f.giveUp) await post(`/api/rooms/${enc}/members/${id}/give-up`);
      }
      if (label) label.textContent = added ? `${added}명 넣었어요` : "이미 다 들어와 있어요";
      setTimeout(() => location.reload(), 700);
    } catch (e) {
      if (label) label.textContent = "넣지 못했어요. 잠시 후 다시 눌러 주세요";
      el.disabled = false;
    }
  }

  function mount() {
    // 결과 카드(board.html)는 회색 계산대(.counter) 안 영수증 위에, 나머지는 화면 맨 위에
    const counter = document.querySelector("main.counter");
    if (counter) counter.prepend(bar); else document.body.prepend(bar);
    document.body.append(sheet);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount); else mount();
})();
