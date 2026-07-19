(() => {
  "use strict";

  const DATA_URL = "data/attention_today.json";
  const ACTIONS_KEY = "stockcheck.attention.pr3.actions.v1";
  const PREFS_KEY = "stockcheck.attention.pr3.preferences.v1";
  const PRIORITY_ORDER = { Critical: 0, Risk: 1, Action: 2, Watch: 3, Developing: 4 };
  const EXTERNAL_SOURCE_TYPES = new Set(["sec", "company_ir", "company_press_release", "regulator", "gdelt", "media"]);
  const SOURCE_LABELS = {
    sec: "SEC",
    company_ir: "Investor Relations",
    company_press_release: "ข่าวจากบริษัท",
    regulator: "หน่วยงานกำกับ",
    gdelt: "สื่อภายนอก",
    media: "สื่อภายนอก",
  };
  const PRIORITY_LABELS = {
    Critical: "เร่งด่วน",
    Risk: "ความเสี่ยง",
    Action: "ควรตรวจสอบ",
    Watch: "จับตา",
    Developing: "กำลังพัฒนา",
  };
  const EVENT_LABELS = {
    earnings_today: "ประกาศงบวันนี้",
    earnings_upcoming: "ใกล้ประกาศงบ",
    earnings_reported: "ประกาศงบแล้ว",
    earnings_call_pending: "รอฟัง Earnings Call",
    capital_raise: "ความเสี่ยงเพิ่มทุน",
    late_filing: "ยื่นงบล่าช้า",
    auditor_change: "เปลี่ยนผู้สอบบัญชี",
    delisting_risk: "ความเสี่ยงด้านการจดทะเบียน",
    debt_obligation: "ภาระหนี้ใหม่",
    periodic_report: "งบการเงินฉบับใหม่",
    management_change: "เปลี่ยนผู้บริหารหรือกรรมการ",
    transaction: "ธุรกรรมสำคัญ",
    material_agreement: "ข้อตกลงสำคัญ",
    ownership_change: "การถือหุ้นเปลี่ยนแปลง",
    tender_offer: "คำเสนอซื้อหลักทรัพย์",
    current_report: "รายงาน 8-K ใหม่",
    regulatory: "ข่าวจากหน่วยงานกำกับ",
    litigation: "ประเด็นทางกฎหมาย",
    technical_risk: "สัญญาณทางเทคนิคอ่อนแอ",
    technical_setup: "สัญญาณทางเทคนิคแข็งแรง",
  };

  const state = {
    data: null,
    loading: false,
    error: null,
    filter: "all",
    actions: loadJson(ACTIONS_KEY, {}),
    preferences: { holdingsFirst: true, showReviewed: true, ...loadJson(PREFS_KEY, {}) },
  };

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  }[char]));
  const asArray = (value) => Array.isArray(value) ? value : [];
  const num = (value) => Number.isFinite(Number(value)) ? Number(value) : null;
  const money = (value) => num(value) == null ? "—" : `$${num(value).toLocaleString("en-US", { maximumFractionDigits: 2 })}`;

  function loadJson(key, fallback) {
    try {
      const value = JSON.parse(localStorage.getItem(key) || "null");
      return value && typeof value === "object" ? value : fallback;
    } catch {
      return fallback;
    }
  }

  function saveJson(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* optional */ }
  }

  function formatTime(value) {
    if (!value) return "ยังไม่ระบุเวลา";
    const raw = String(value);
    const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(raw);
    const parsed = new Date(dateOnly ? `${raw}T12:00:00Z` : raw);
    if (Number.isNaN(parsed.getTime())) return raw;
    const options = dateOnly
      ? { day: "numeric", month: "short", year: "numeric" }
      : { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZoneName: "short" };
    return parsed.toLocaleString("th-TH", options);
  }

  function ensurePage() {
    let page = document.getElementById("attentionPageP3");
    if (page) return page;
    const shell = document.querySelector(".app-shell") || document.body;
    page = document.createElement("section");
    page.id = "attentionPageP3";
    page.className = "attention-page attention-p3-page";
    page.setAttribute("aria-live", "polite");
    const topbar = shell.querySelector(".topbar");
    if (topbar) topbar.insertAdjacentElement("afterend", page);
    else shell.prepend(page);
    return page;
  }

  function sourceList(item) {
    const rows = [];
    const seen = new Set();
    for (const event of asArray(item?.events)) {
      const chain = asArray(event?.source_chain).concat(event?.source ? [event.source] : []);
      for (const source of chain) {
        if (!source?.url || !EXTERNAL_SOURCE_TYPES.has(String(source.type || ""))) continue;
        const key = `${source.type}:${source.url}`;
        if (seen.has(key)) continue;
        seen.add(key);
        rows.push(source);
      }
    }
    return rows;
  }

  function sourceName(source) {
    return source?.name || SOURCE_LABELS[source?.type] || source?.domain || "แหล่งข้อมูลภายนอก";
  }

  function primaryEvent(item) {
    return asArray(item?.events)[0] || {};
  }

  function itemKey(item) {
    const event = primaryEvent(item);
    return String(event.event_id || `${item.ticker}:${item.event_subtype || event.event_subtype || "event"}:${item.event_time || event.event_time || ""}`);
  }

  function actionState(item) {
    return state.actions[itemKey(item)] || {};
  }

  function snoozed(item) {
    const until = actionState(item).snoozedUntil;
    return until && new Date(until).getTime() > Date.now();
  }

  function hiddenToday(item) {
    const row = actionState(item);
    const today = new Date().toISOString().slice(0, 10);
    return row.dismissedDate === today || snoozed(item);
  }

  function visibleItem(item) {
    if (hiddenToday(item)) return false;
    if (!state.preferences.showReviewed && actionState(item).reviewed) return false;
    if (state.filter === "holdings" && item.portfolio_status !== "holding") return false;
    if (state.filter === "earnings" && item.event_type !== "earnings") return false;
    if (state.filter === "sec" && item.event_type !== "sec_filing") return false;
    if (state.filter === "regulator" && !asArray(item.events).some((event) => event.event_type === "regulatory" || event.source?.type === "regulator")) return false;
    if (state.filter === "technical" && !asArray(item.events).every((event) => event.event_type === "technical")) return false;
    if (state.filter === "all" || state.filter === "technical") return true;
    return state.filter === "holdings" || state.filter === "earnings" || state.filter === "sec" || state.filter === "regulator";
  }

  function sortRows(rows) {
    return rows.sort((a, b) => {
      if (state.preferences.holdingsFirst) {
        const holdingDelta = Number(b.portfolio_status === "holding") - Number(a.portfolio_status === "holding");
        if (holdingDelta) return holdingDelta;
      }
      return (PRIORITY_ORDER[a.priority] ?? 9) - (PRIORITY_ORDER[b.priority] ?? 9)
        || Number(b.personal_priority_score || b.priority_score || 0) - Number(a.personal_priority_score || a.priority_score || 0)
        || String(a.ticker || "").localeCompare(String(b.ticker || ""));
    });
  }

  function eventLabel(item) {
    const event = primaryEvent(item);
    return EVENT_LABELS[item.event_subtype] || EVENT_LABELS[event.event_subtype] || "เหตุการณ์ที่ควรตรวจสอบ";
  }

  function friendlySummary(item) {
    const event = primaryEvent(item);
    const subtype = String(item.event_subtype || event.event_subtype || "");
    if (subtype === "earnings_upcoming") {
      const days = num(event.days_to_event);
      return days == null ? "บริษัทใกล้ประกาศผลประกอบการ" : `บริษัทจะประกาศผลประกอบการในอีก ${days} วัน`;
    }
    if (subtype === "earnings_today") return "บริษัทมีกำหนดประกาศผลประกอบการวันนี้";
    if (subtype === "regulatory") return event.headline || "มีประกาศใหม่จากหน่วยงานกำกับ";
    if (subtype === "capital_raise") return "มีเอกสารที่อาจเกี่ยวข้องกับการเพิ่มทุนหรือ dilution";
    if (subtype === "material_agreement") return "บริษัทเปิดเผยข้อตกลงสำคัญฉบับใหม่";
    if (subtype === "technical_risk") return "โมเมนตัมและโครงสร้างราคายังอ่อนแอ ควรเปิดกราฟตรวจระดับความเสี่ยง";
    if (subtype === "technical_setup") return "โครงสร้างราคาแข็งแรงกว่าหุ้นอื่นในพอร์ต ควรเปิดกราฟยืนยันจังหวะ";
    return event.summary || item.why_today?.[0] || "มีเหตุการณ์ใหม่ที่ควรตรวจสอบ";
  }

  function whyItMatters(item) {
    const subtype = String(item.event_subtype || primaryEvent(item).event_subtype || "");
    if (subtype.startsWith("earnings")) return "รายได้ กำไร และ guidance อาจเปลี่ยนมุมมองต่อหุ้นและทำให้ราคาผันผวน";
    if (subtype === "regulatory") return "ประกาศจากหน่วยงานทางการอาจกระทบการอนุมัติ การดำเนินงาน หรือกำหนดเวลาโครงการ";
    if (["capital_raise", "debt_obligation"].includes(subtype)) return "อาจกระทบจำนวนหุ้น กระแสเงินสด หรือความแข็งแรงของงบดุล";
    if (subtype === "technical_risk") return "ใช้ทบทวน downside และระดับราคาที่รับความเสี่ยงได้ ไม่ใช่คำแนะนำขาย";
    if (subtype === "technical_setup") return "ใช้ช่วยเลือกจังหวะเปิดกราฟ ไม่ใช่คำแนะนำซื้อ";
    return "ควรตรวจแหล่งข้อมูลต้นฉบับและประเมินผลต่อ thesis ของหุ้นในพอร์ต";
  }

  function priorityBadge(item) {
    const key = PRIORITY_LABELS[item.priority] ? item.priority : "Developing";
    return `<span class="pr3-priority pr3-priority-${esc(key.toLowerCase())}">${esc(PRIORITY_LABELS[key])}</span>`;
  }

  function changeBadge(item) {
    const change = item.change || {};
    const status = String(change.status || "ongoing");
    return `<span class="pr3-change pr3-change-${esc(status)}">${esc(change.label_th || "ติดตามต่อ")}</span>`;
  }

  function impactText(item) {
    const impact = item.impact || {};
    const value = num(impact.change_pct);
    const label = impact.label_th || "ยังไม่มีข้อมูลผลกระทบ";
    return `<span class="pr3-impact ${value == null ? "" : value < 0 ? "negative" : value > 0 ? "positive" : ""}">${esc(label)}</span>`;
  }

  function sourceLinks(item) {
    const sources = sourceList(item);
    if (!sources.length) return "";
    return `<div class="pr3-sources">${sources.slice(0, 3).map((source) => `<a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${esc(sourceName(source))}</a>`).join("")}</div>`;
  }

  function chartUrl(item) {
    return item?.actions?.tradingview || "";
  }

  function workflowButtons(item) {
    const row = actionState(item);
    const key = esc(itemKey(item));
    const reviewLabel = row.reviewed ? "ยกเลิกตรวจแล้ว" : "ตรวจแล้ว";
    const buttons = [
      `<button type="button" data-pr3-action="review" data-pr3-key="${key}">${reviewLabel}</button>`,
      `<button type="button" data-pr3-action="snooze" data-pr3-key="${key}">พัก 1 วัน</button>`,
      `<button type="button" data-pr3-action="dismiss" data-pr3-key="${key}">ซ่อนวันนี้</button>`,
    ];
    const chart = chartUrl(item);
    if (chart) buttons.unshift(`<a href="${esc(chart)}" target="_blank" rel="noopener noreferrer">ดูกราฟ</a>`);
    const sources = sourceList(item);
    if (sources.length) buttons.unshift(`<a href="${esc(sources[0].url)}" target="_blank" rel="noopener noreferrer">ดูข้อมูลต้นฉบับ</a>`);
    return `<div class="pr3-actions">${buttons.join("")}</div>`;
  }

  function itemCard(item, technical = false) {
    const reviewed = actionState(item).reviewed ? " reviewed" : "";
    const activeDays = num(item.change?.active_days);
    const timeline = activeDays == null ? "" : activeDays === 0 ? "เริ่มติดตามวันนี้" : `ติดตามมา ${activeDays} วัน`;
    return `<article class="panel-card pr3-item${technical ? " technical" : ""}${reviewed}">
      <header>
        <div><strong>${esc(item.ticker)}</strong><span>${esc(item.name || "")}</span></div>
        <div class="pr3-badges">${priorityBadge(item)}${changeBadge(item)}</div>
      </header>
      <div class="pr3-meta"><span>${item.portfolio_status === "holding" ? "หุ้นในพอร์ต" : "รายการติดตาม"}</span><span>${esc(eventLabel(item))}</span><span>${esc(formatTime(item.event_time))}</span></div>
      <h4>เกิดอะไรขึ้น</h4>
      <p>${esc(friendlySummary(item))}</p>
      <h4>ทำไมสำคัญ</h4>
      <p>${esc(whyItMatters(item))}</p>
      <div class="pr3-impact-row">${impactText(item)}<span>${esc(timeline)}</span></div>
      ${sourceLinks(item)}
      ${workflowButtons(item)}
    </article>`;
  }

  function summaryCards() {
    const changes = state.data?.changes_summary || {};
    const all = asArray(state.data?.items).concat(asArray(state.data?.technical_watch));
    const reviewed = all.filter((item) => actionState(item).reviewed).length;
    const hidden = all.filter(hiddenToday).length;
    const regulator = asArray(state.data?.items).filter((item) => asArray(item.events).some((event) => event.source?.type === "regulator")).length;
    const cards = [
      ["เปลี่ยนจากรอบก่อน", `${Number(changes.new || 0)} ใหม่ · ${Number(changes.escalated || 0)} สำคัญขึ้น`],
      ["ข่าวทางการ", `${regulator} รายการจากหน่วยงานกำกับ`],
      ["บันทึกการตรวจ", `${reviewed} ตรวจแล้ว · ${hidden} พัก/ซ่อน`],
      ["ออกจากรายการ", `${Number(changes.resolved || 0)} รายการล่าสุด`],
    ];
    return `<section class="pr3-summary-grid">${cards.map(([title, value]) => `<div><span>${esc(title)}</span><strong>${esc(value)}</strong></div>`).join("")}</section>`;
  }

  function controls() {
    const filters = [["all", "ทั้งหมด"], ["holdings", "หุ้นในพอร์ต"], ["earnings", "งบการเงิน"], ["sec", "SEC"], ["regulator", "หน่วยงานกำกับ"], ["technical", "เทคนิค"]];
    return `<section class="pr3-controls">
      <div class="pr3-filters">${filters.map(([key, label]) => `<button type="button" data-pr3-filter="${key}" class="${state.filter === key ? "active" : ""}">${label}</button>`).join("")}</div>
      <details class="pr3-preferences"><summary>ตั้งค่าการจัดลำดับ</summary>
        <label><input type="checkbox" data-pr3-pref="holdingsFirst" ${state.preferences.holdingsFirst ? "checked" : ""}> เน้นหุ้นในพอร์ตก่อน</label>
        <label><input type="checkbox" data-pr3-pref="showReviewed" ${state.preferences.showReviewed ? "checked" : ""}> แสดงรายการที่ตรวจแล้ว</label>
        <button type="button" data-pr3-action="reset">ล้างสถานะตรวจ/พักทั้งหมด</button>
      </details>
    </section>`;
  }

  function hero() {
    const coverage = state.data?.coverage_status === "complete";
    const items = asArray(state.data?.items);
    const technical = asArray(state.data?.technical_watch);
    return `<section class="panel-card pr3-hero">
      <div><span>PR3 · PERSONAL RISK DESK</span><h2>สิ่งที่ต้องจับตาวันนี้</h2><p>ติดตาม ${Number(state.data?.total_monitored || 0)} หุ้น · อัปเดต ${esc(formatTime(state.data?.updated_at))}</p></div>
      <div class="pr3-hero-counts"><div><strong>${items.length}</strong><span>เหตุการณ์สำคัญ</span></div><div><strong>${technical.length}</strong><span>จับตาทางเทคนิค</span></div></div>
      <div class="pr3-coverage ${coverage ? "complete" : "partial"}"><strong>${coverage ? "ข้อมูลพร้อมครบ" : "ข้อมูลบางแหล่งยังไม่ครบ"}</strong><span>${coverage ? "ตรวจแหล่งข้อมูลที่ตั้งค่าไว้ครบแล้ว" : "รายการที่แสดงยังใช้ได้ แต่ไม่ควรตีความว่าเป็น all-clear"}</span></div>
    </section>`;
  }

  function section(title, description, rows, technical = false) {
    if (!rows.length) return `<section class="pr3-section"><header><div><h3>${esc(title)}</h3><p>${esc(description)}</p></div><span>0 รายการ</span></header><div class="panel-card pr3-empty">ยังไม่มีรายการในตัวกรองนี้</div></section>`;
    return `<section class="pr3-section"><header><div><h3>${esc(title)}</h3><p>${esc(description)}</p></div><span>${rows.length} รายการ</span></header><div class="pr3-list">${rows.map((item) => itemCard(item, technical)).join("")}</div></section>`;
  }

  function render() {
    const page = ensurePage();
    if (state.loading) {
      page.innerHTML = `<div class="pr3-shell"><section class="panel-card pr3-empty">กำลังรวมข้อมูลเหตุการณ์และประวัติการติดตาม…</section></div>`;
      return;
    }
    if (state.error || !state.data) {
      page.innerHTML = `<div class="pr3-shell"><section class="panel-card pr3-empty"><strong>ยังเปิด PR3 ไม่ได้</strong><span>${esc(state.error || "ไม่พบข้อมูล")}</span><button type="button" data-pr3-retry>ลองใหม่</button></section></div>`;
      document.body.classList.remove("attention-p3-ready");
      return;
    }

    const catalysts = sortRows(asArray(state.data.items).filter(visibleItem));
    const technical = sortRows(asArray(state.data.technical_watch).filter(visibleItem));
    const showCatalysts = state.filter !== "technical";
    const showTechnical = ["all", "holdings", "technical"].includes(state.filter);
    page.innerHTML = `<div class="pr3-shell">${hero()}${summaryCards()}${controls()}
      ${showCatalysts ? section("เหตุการณ์สำคัญวันนี้", "งบการเงิน SEC ข่าวบริษัท และประกาศจากหน่วยงานกำกับ", catalysts) : ""}
      ${showTechnical ? section("จับตาทางเทคนิค", "ใช้ช่วยเลือกจังหวะเปิดกราฟเท่านั้น ไม่ใช่คำแนะนำซื้อหรือขาย", technical, true) : ""}
    </div>`;
    document.body.classList.add("attention-p3-ready");

    const badge = document.getElementById("attentionNavBadge");
    const total = catalysts.length + technical.length;
    if (badge) { badge.textContent = String(total); badge.hidden = !total; }
  }

  function mutateAction(action, key) {
    if (action === "reset") {
      state.actions = {};
      saveJson(ACTIONS_KEY, state.actions);
      render();
      return;
    }
    if (!key) return;
    const row = { ...(state.actions[key] || {}) };
    if (action === "review") row.reviewed = !row.reviewed;
    if (action === "snooze") row.snoozedUntil = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
    if (action === "dismiss") row.dismissedDate = new Date().toISOString().slice(0, 10);
    state.actions[key] = row;
    saveJson(ACTIONS_KEY, state.actions);
    render();
  }

  async function load() {
    state.loading = true;
    state.error = null;
    render();
    try {
      let payload;
      if (typeof window.StockcheckAttentionDataStore?.load === "function") {
        payload = await window.StockcheckAttentionDataStore.load();
      } else {
        const response = await fetch(`${DATA_URL}?v=${Date.now()}`, { cache: "no-store" });
        if (!response.ok) throw new Error(`attention_today.json HTTP ${response.status}`);
        payload = await response.json();
      }
      if (!payload || typeof payload !== "object" || !Array.isArray(payload.items) || !Array.isArray(payload.technical_watch)) {
        throw new Error("รูปแบบข้อมูล PR3 ไม่ถูกต้อง");
      }
      state.data = payload;
    } catch (error) {
      state.error = error?.message || String(error);
      state.data = null;
    } finally {
      state.loading = false;
      render();
    }
  }

  function init() {
    ensurePage();
    document.addEventListener("click", (event) => {
      const filter = event.target.closest?.("[data-pr3-filter]");
      if (filter) {
        state.filter = filter.dataset.pr3Filter || "all";
        render();
        return;
      }
      const action = event.target.closest?.("[data-pr3-action]");
      if (action) {
        event.preventDefault();
        mutateAction(action.dataset.pr3Action || "", action.dataset.pr3Key || "");
        return;
      }
      if (event.target.closest?.("[data-pr3-retry]")) load();
    });
    document.addEventListener("change", (event) => {
      const input = event.target.closest?.("[data-pr3-pref]");
      if (!input) return;
      state.preferences[input.dataset.pr3Pref] = Boolean(input.checked);
      saveJson(PREFS_KEY, state.preferences);
      render();
    });
    load();
    window.StockcheckAttentionP3 = { version: "10.3.0", load, render };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
