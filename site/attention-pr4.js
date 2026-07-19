(() => {
  "use strict";

  const VERSION = "10.4.1";
  const DATA_URL = "data/attention_today.json";
  const ACTIONS_KEY = "stockcheck.attention.pr3.actions.v1";
  const PREFS_KEY = "stockcheck.attention.pr4.preferences.v1";
  const LOGO_DEV_TOKEN = "__LOGO_DEV_PUBLISHABLE_KEY__";
  const missingLogoTickers = new Set();
  let logoFallbackBound = false;
  const EXTERNAL_SOURCE_TYPES = new Set(["sec", "company_ir", "company_press_release", "regulator", "gdelt", "media"]);
  const PRIORITY_ORDER = { Critical: 0, Risk: 1, Action: 2, Watch: 3, Developing: 4 };
  const SOURCE_LABELS = {
    sec: "SEC",
    company_ir: "Investor Relations",
    company_press_release: "ข่าวจากบริษัท",
    regulator: "หน่วยงานกำกับ",
    gdelt: "สื่อภายนอก",
    media: "สื่อภายนอก",
  };
  const STATUS_LABELS = {
    Critical: "เร่งด่วน",
    Risk: "ความเสี่ยง",
    Action: "ควรตรวจสอบ",
    Watch: "จับตา",
    Developing: "กำลังติดตาม",
  };
  const EVENT_LABELS = {
    earnings_today: "ประกาศผลประกอบการวันนี้",
    earnings_upcoming: "ใกล้ประกาศผลประกอบการ",
    earnings_reported: "ประกาศผลประกอบการแล้ว",
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
    regulatory: "ประกาศจากหน่วยงานกำกับ",
    litigation: "ประเด็นทางกฎหมาย",
    technical_risk: "สัญญาณทางเทคนิคอ่อนแอ",
    technical_setup: "สัญญาณทางเทคนิคแข็งแรง",
  };

  const ICONS = {
    calendar: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 2v3M17 2v3M3.5 9h17M5 4.5h14a1.5 1.5 0 0 1 1.5 1.5v13A1.5 1.5 0 0 1 19 20.5H5A1.5 1.5 0 0 1 3.5 19V6A1.5 1.5 0 0 1 5 4.5Z"/></svg>',
    activity: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12h4l2.2-6 4.1 12 2.2-6H21"/></svg>',
    database: '<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></svg>',
    chart: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19V5M4 19h16M7 15l4-4 3 2 5-6"/></svg>',
    check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>',
    clock: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
    eyeOff: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 3 18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 4.3A10.7 10.7 0 0 1 12 4c5.5 0 9 5 9 8a10 10 0 0 1-2 3.6M6.2 6.2C4.1 7.6 3 10.1 3 12c0 3 3.5 8 9 8 1.5 0 2.8-.4 4-.9"/></svg>',
    external: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M18 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h6"/></svg>',
    refresh: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6v5h-5M4 18v-5h5M18.5 9A7 7 0 0 0 6.7 6.7L4 11M5.5 15A7 7 0 0 0 17.3 17.3L20 13"/></svg>',
  };

  const state = {
    data: null,
    loading: false,
    error: null,
    filter: "all",
    actions: loadJson(ACTIONS_KEY, {}),
    preferences: { showReviewed: true, ...loadJson(PREFS_KEY, {}) },
  };

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  }[char]));
  const asArray = (value) => Array.isArray(value) ? value : [];
  const num = (value) => Number.isFinite(Number(value)) ? Number(value) : null;
  const money = (value) => num(value) == null ? "—" : `$${num(value).toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
  const signed = (value, digits = 1) => num(value) == null ? "—" : `${num(value) > 0 ? "+" : ""}${num(value).toFixed(digits)}%`;

  function normaliseLogoTicker(value) {
    return String(value || "")
      .trim()
      .replace(/^[$#]+/, "")
      .toUpperCase()
      .replace(/[^A-Z0-9.\-]/g, "");
  }

  function companyLogoMarkup(item, markClass = "company-logo-mark") {
    const ticker = normaliseLogoTicker(item?.ticker);
    const fallback = esc(String(ticker || "?").slice(0, 2));
    if (!ticker || missingLogoTickers.has(ticker)) {
      return `<span class="${markClass}" data-logo-shell><span data-logo-fallback>${fallback}</span></span>`;
    }
    const src = `https://img.logo.dev/ticker/${encodeURIComponent(ticker)}?token=${encodeURIComponent(LOGO_DEV_TOKEN)}&size=64&format=png&theme=dark&retina=true&fallback=404`;
    return `<span class="${markClass}" data-logo-shell><img src="${src}" data-logo-ticker="${esc(ticker)}" alt="" aria-hidden="true" width="54" height="54" loading="lazy" decoding="async" fetchpriority="low"><span data-logo-fallback hidden>${fallback}</span></span>`;
  }

  function installLogoFallback() {
    if (logoFallbackBound) return;
    logoFallbackBound = true;
    document.addEventListener("error", (event) => {
      const image = event.target;
      if (!(image instanceof HTMLImageElement) || !image.dataset.logoTicker) return;
      missingLogoTickers.add(image.dataset.logoTicker);
      image.hidden = true;
      image.nextElementSibling?.removeAttribute("hidden");
    }, true);
  }

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

  function ensurePage() {
    let page = document.getElementById("attentionPageP4");
    if (page) return page;
    const shell = document.querySelector(".app-shell") || document.body;
    page = document.createElement("section");
    page.id = "attentionPageP4";
    page.className = "attention-page attention-p4-page";
    page.setAttribute("aria-live", "polite");
    const topbar = shell.querySelector(".topbar");
    if (topbar) topbar.insertAdjacentElement("afterend", page);
    else shell.prepend(page);
    return page;
  }

  function formatTime(value, includeTime = true) {
    if (!value) return "ยังไม่ระบุเวลา";
    const raw = String(value);
    const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(raw);
    const parsed = new Date(dateOnly ? `${raw}T12:00:00Z` : raw);
    if (Number.isNaN(parsed.getTime())) return raw;
    const options = dateOnly || !includeTime
      ? { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }
      : { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZoneName: "short", timeZone: "Asia/Bangkok" };
    return parsed.toLocaleString("th-TH", options);
  }

  function primaryEvent(item) {
    return asArray(item?.events)[0] || {};
  }

  function itemKey(item) {
    const event = primaryEvent(item);
    return String(event.event_id || `${item?.ticker || ""}:${item?.event_subtype || event.event_subtype || "event"}:${item?.event_time || event.event_time || ""}`);
  }

  function actionState(item) {
    return state.actions[itemKey(item)] || {};
  }

  function hiddenToday(item) {
    const row = actionState(item);
    const today = new Date().toISOString().slice(0, 10);
    return row.dismissedDate === today || (row.snoozedUntil && new Date(row.snoozedUntil).getTime() > Date.now());
  }

  function visible(item, section) {
    if (hiddenToday(item)) return false;
    if (!state.preferences.showReviewed && actionState(item).reviewed) return false;
    if (state.filter === "holdings" && item.portfolio_status !== "holding") return false;
    if (state.filter === "earnings" && item.event_type !== "earnings") return false;
    if (state.filter === "technical" && section !== "technical") return false;
    if (state.filter === "catalysts" && section !== "catalyst") return false;
    return true;
  }

  function externalSources(item) {
    const rows = [];
    const seen = new Set();
    for (const event of asArray(item?.events)) {
      for (const source of asArray(event?.source_chain).concat(event?.source ? [event.source] : [])) {
        const type = String(source?.type || "");
        if (!source?.url || !EXTERNAL_SOURCE_TYPES.has(type)) continue;
        const key = `${type}:${source.url}`;
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

  function eventLabel(item) {
    const event = primaryEvent(item);
    return EVENT_LABELS[item.event_subtype] || EVENT_LABELS[event.event_subtype] || "เหตุการณ์ที่ควรตรวจสอบ";
  }

  function eventSummary(item) {
    const event = primaryEvent(item);
    const subtype = String(item.event_subtype || event.event_subtype || "");
    if (subtype === "earnings_today") return "บริษัทมีกำหนดประกาศผลประกอบการวันนี้";
    if (subtype === "earnings_upcoming") return event.summary || "บริษัทใกล้ประกาศผลประกอบการ";
    if (subtype === "capital_raise") return "มีเอกสารที่อาจเกี่ยวข้องกับการเพิ่มทุนหรือ dilution";
    if (subtype === "material_agreement") return "บริษัทเปิดเผยข้อตกลงสำคัญฉบับใหม่";
    if (subtype === "regulatory") return event.headline || "มีประกาศใหม่จากหน่วยงานกำกับ";
    return event.summary || asArray(item.why_today)[0] || "มีเหตุการณ์ใหม่ที่ควรตรวจสอบ";
  }

  function whyMatters(item) {
    const subtype = String(item.event_subtype || primaryEvent(item).event_subtype || "");
    if (subtype.startsWith("earnings")) return "รายได้ กำไร และ guidance อาจเปลี่ยนมุมมองต่อหุ้นและเพิ่มความผันผวน";
    if (subtype === "regulatory") return "ประกาศทางการอาจกระทบการอนุมัติ การดำเนินงาน หรือกำหนดเวลาโครงการ";
    if (["capital_raise", "debt_obligation"].includes(subtype)) return "อาจกระทบจำนวนหุ้น กระแสเงินสด หรือความแข็งแรงของงบดุล";
    return "ควรตรวจแหล่งข้อมูลต้นฉบับและประเมินผลต่อ thesis ของหุ้นในพอร์ต";
  }

  function tone(item, technical = false) {
    if (technical) return item.event_subtype === "technical_setup" ? "positive" : "negative";
    if (["Critical", "Risk"].includes(item.priority)) return "negative";
    if (item.priority === "Action") return "action";
    return "neutral";
  }

  function metric(label, value, extraClass = "") {
    if (value == null || value === "" || value === "—") return "";
    return `<div class="p4-metric ${esc(extraClass)}"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`;
  }

  function sourceLink(item, compact = false) {
    const source = externalSources(item)[0];
    if (!source) return "";
    if (compact) return `<a class="p4-text-link" href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${esc(sourceName(source))}${ICONS.external}</a>`;
    return `<a class="p4-primary-action" href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">ดูข้อมูลต้นฉบับ${ICONS.external}</a>`;
  }

  function chartLink(item, compact = false) {
    const url = item?.actions?.tradingview;
    if (!url) return "";
    return `<a class="${compact ? "p4-icon-action" : "p4-secondary-action"}" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${ICONS.chart}<span>${compact ? "ดูกราฟ" : "เปิดกราฟ"}</span></a>`;
  }

  function workflowMenu(item) {
    const key = esc(itemKey(item));
    const reviewed = Boolean(actionState(item).reviewed);
    return `<details class="p4-workflow"><summary aria-label="ตัวเลือกการติดตาม">•••</summary><div>
      <button type="button" data-p4-action="review" data-p4-key="${key}">${ICONS.check}<span>${reviewed ? "ยกเลิกตรวจแล้ว" : "ตรวจแล้ว"}</span></button>
      <button type="button" data-p4-action="snooze" data-p4-key="${key}">${ICONS.clock}<span>พัก 1 วัน</span></button>
      <button type="button" data-p4-action="dismiss" data-p4-key="${key}">${ICONS.eyeOff}<span>ซ่อนวันนี้</span></button>
    </div></details>`;
  }

  function statusText(item) {
    const change = item.change || {};
    const status = STATUS_LABELS[item.priority] || "ติดตาม";
    const changeText = change.label_th || "ยังต้องติดตามต่อ";
    return `<div class="p4-status-line"><strong>${esc(status)}</strong><span>${esc(changeText)}</span></div>`;
  }

  function heroCatalyst(item) {
    const event = primaryEvent(item);
    const source = externalSources(item)[0];
    const timing = event.earnings_timing === "after_market" ? "หลังตลาดปิด"
      : event.earnings_timing === "before_market" ? "ก่อนตลาดเปิด"
      : event.earnings_timing === "during_market" ? "ระหว่างตลาด" : "";
    const impact = num(item.impact?.change_pct);
    return `<article class="p4-catalyst-hero p4-tone-${tone(item)}">
      <div class="p4-rail" aria-hidden="true"></div>
      <div class="p4-catalyst-main">
        <div class="p4-catalyst-top">
          <div class="p4-ticker-block">${companyLogoMarkup(item, "p4-ticker-mark")}<div><strong>${esc(item.ticker)}</strong><span>${esc(item.name || "")}</span></div></div>
          ${statusText(item)}
        </div>
        <p class="p4-kicker">${esc(eventLabel(item))}</p>
        <h3>${esc(eventSummary(item))}</h3>
        <p class="p4-why">${esc(whyMatters(item))}</p>
        <div class="p4-hero-actions">${sourceLink(item)}${chartLink(item)}${workflowMenu(item)}</div>
      </div>
      <div class="p4-catalyst-facts">
        ${metric("วันที่", formatTime(item.event_time, false))}
        ${metric("เวลา", timing || "ยังไม่ระบุ")}
        ${metric("ยืนยันโดย", source ? sourceName(source) : "ยังไม่มีแหล่งภายนอก")}
        ${metric("ราคาล่าสุด", money(item.price))}
        ${impact == null ? "" : metric("ตั้งแต่เริ่มติดตาม", signed(impact), impact < 0 ? "negative" : impact > 0 ? "positive" : "")}
      </div>
    </article>`;
  }

  function compactCatalyst(item) {
    return `<article class="p4-catalyst-row p4-tone-${tone(item)}">
      <div class="p4-rail" aria-hidden="true"></div>
      <div class="p4-ticker-block compact">${companyLogoMarkup(item, "p4-ticker-mark")}<div><strong>${esc(item.ticker)}</strong><span>${esc(item.name || "")}</span></div></div>
      <div><span>${esc(eventLabel(item))}</span><strong>${esc(eventSummary(item))}</strong></div>
      <div><span>วันที่</span><strong>${esc(formatTime(item.event_time, false))}</strong></div>
      <div class="p4-row-actions">${sourceLink(item, true)}${chartLink(item, true)}${workflowMenu(item)}</div>
    </article>`;
  }

  function technicalMetrics(item) {
    const event = primaryEvent(item);
    return {
      score: num(event.technical_score),
      signal: event.technical_signal || "",
      rsi: num(event.rsi14),
      ema20: num(event.pct_vs_ema20),
      ema200: num(event.pct_vs_ema200),
      volume: num(event.volume_ratio20 ?? item.relative_volume),
    };
  }

  function technicalCard(item) {
    const metrics = technicalMetrics(item);
    const cardTone = tone(item, true);
    const scoreText = metrics.score == null ? "" : `${metrics.score.toFixed(0)}/100`;
    return `<article class="p4-technical-card p4-tone-${cardTone}">
      <header><div class="p4-ticker-block compact">${companyLogoMarkup(item, "p4-ticker-mark")}<div><strong>${esc(item.ticker)}</strong><span>${esc(item.name || "")}</span></div></div><div class="p4-price"><strong>${esc(money(item.price))}</strong><span class="${cardTone}">${esc(item.event_subtype === "technical_setup" ? "แนวโน้มแข็งแรง" : "แนวโน้มอ่อนแอ")}</span></div></header>
      <div class="p4-technical-label"><strong>${esc(eventLabel(item))}</strong>${scoreText ? `<span>คะแนน ${esc(scoreText)}</span>` : ""}</div>
      <p>${esc(metrics.signal || (item.event_subtype === "technical_setup" ? "โครงสร้างราคาแข็งแรงกว่าหุ้นอื่นในพอร์ต" : "โมเมนตัมและโครงสร้างราคายังอ่อนแอ"))}</p>
      <dl>
        <div><dt>RSI</dt><dd>${metrics.rsi == null ? "—" : metrics.rsi.toFixed(1)}</dd></div>
        <div><dt>เทียบ EMA20</dt><dd class="${metrics.ema20 == null ? "" : metrics.ema20 < 0 ? "negative" : "positive"}">${esc(signed(metrics.ema20))}</dd></div>
        <div><dt>เทียบ EMA200</dt><dd class="${metrics.ema200 == null ? "" : metrics.ema200 < 0 ? "negative" : "positive"}">${esc(signed(metrics.ema200))}</dd></div>
        <div><dt>Volume</dt><dd>${metrics.volume == null ? "—" : `${metrics.volume.toFixed(2)}x`}</dd></div>
      </dl>
      <footer>${chartLink(item, true)}${workflowMenu(item)}</footer>
    </article>`;
  }

  function summaryStrip(catalysts, technical) {
    const coverage = state.data?.coverage_status === "complete";
    return `<section class="p4-summary-strip" aria-label="สรุป Today">
      <div><span>ติดตามทั้งหมด</span><strong>${Number(state.data?.total_monitored || 0)}</strong><small>หุ้นในพอร์ต</small></div>
      <div><span>เหตุการณ์สำคัญ</span><strong>${catalysts.length}</strong><small>รายการ</small></div>
      <div><span>จับตาทางเทคนิค</span><strong>${technical.length}</strong><small>รายการ</small></div>
      <div class="p4-summary-health ${coverage ? "complete" : "partial"}"><span>${coverage ? "ข้อมูลพร้อมครบ" : "ข้อมูลบางแหล่งยังไม่ครบ"}</span><strong>${coverage ? "พร้อมใช้งาน" : "Partial coverage"}</strong><small>${coverage ? "ตรวจแหล่งข้อมูลครบแล้ว" : "รายการยังใช้ได้ แต่ไม่ใช่ all-clear"}</small></div>
    </section>`;
  }

  function toolbar() {
    const filters = [["all", "ทั้งหมด"], ["catalysts", "เหตุการณ์สำคัญ"], ["technical", "เทคนิค"], ["holdings", "หุ้นในพอร์ต"], ["earnings", "งบการเงิน"]];
    return `<div class="p4-toolbar"><nav aria-label="ตัวกรอง Today">${filters.map(([key, label]) => `<button type="button" data-p4-filter="${key}" class="${state.filter === key ? "active" : ""}">${label}</button>`).join("")}</nav><label><input type="checkbox" data-p4-pref="showReviewed" ${state.preferences.showReviewed ? "checked" : ""}> แสดงรายการที่ตรวจแล้ว</label></div>`;
  }

  function sectionHeader(icon, title, description, count) {
    return `<header class="p4-section-header"><div class="p4-section-title"><span class="p4-line-icon">${icon}</span><div><h2>${esc(title)} <small>(${Number(count)})</small></h2><p>${esc(description)}</p></div></div></header>`;
  }

  function render() {
    const page = ensurePage();
    if (state.loading) {
      page.innerHTML = `<div class="p4-shell"><section class="p4-loading">กำลังจัดลำดับเหตุการณ์ที่สำคัญ…</section></div>`;
      return;
    }
    if (state.error || !state.data) {
      page.innerHTML = `<div class="p4-shell"><section class="p4-error"><strong>ยังเปิด Today รุ่นใหม่ไม่ได้</strong><span>${esc(state.error || "ไม่พบข้อมูล")}</span><button type="button" data-p4-retry>${ICONS.refresh}ลองใหม่</button></section></div>`;
      document.body.classList.remove("attention-p4-ready");
      return;
    }

    const catalysts = asArray(state.data.items)
      .filter((item) => visible(item, "catalyst"))
      .sort((a, b) => (PRIORITY_ORDER[a.priority] ?? 9) - (PRIORITY_ORDER[b.priority] ?? 9) || Number(b.personal_priority_score || 0) - Number(a.personal_priority_score || 0));
    const technical = asArray(state.data.technical_watch)
      .filter((item) => visible(item, "technical"))
      .sort((a, b) => Number(b.personal_priority_score || 0) - Number(a.personal_priority_score || 0));
    const showCatalysts = state.filter !== "technical";
    const showTechnical = !["catalysts", "earnings"].includes(state.filter);
    const hero = catalysts[0];
    const secondary = catalysts.slice(1);

    page.innerHTML = `<div class="p4-shell">
      <header class="p4-page-heading"><div><span>PR4 · DECISION-FIRST TODAY</span><h1>สิ่งที่ต้องจับตาวันนี้</h1><p>อัปเดตล่าสุด ${esc(formatTime(state.data.updated_at))}</p></div></header>
      ${summaryStrip(catalysts, technical)}
      ${toolbar()}
      ${showCatalysts ? `<section class="p4-section">${sectionHeader(ICONS.calendar, "เหตุการณ์สำคัญวันนี้", "งบการเงิน SEC ข่าวบริษัท และประกาศทางการ", catalysts.length)}${hero ? heroCatalyst(hero) : '<div class="p4-empty">ยังไม่มีเหตุการณ์สำคัญในตัวกรองนี้</div>'}${secondary.length ? `<div class="p4-catalyst-list">${secondary.map(compactCatalyst).join("")}</div>` : ""}</section>` : ""}
      ${showTechnical ? `<section class="p4-section">${sectionHeader(ICONS.activity, "จับตาทางเทคนิค", "ใช้ช่วยเลือกจังหวะเปิดกราฟ ไม่ใช่คำแนะนำซื้อหรือขาย", technical.length)}${technical.length ? `<div class="p4-technical-grid">${technical.map(technicalCard).join("")}</div>` : '<div class="p4-empty">ยังไม่มีรายการทางเทคนิคในตัวกรองนี้</div>'}</section>` : ""}
    </div>`;

    document.body.classList.add("attention-p4-ready");
    const badge = document.getElementById("attentionNavBadge");
    const total = catalysts.length + technical.length;
    if (badge) { badge.textContent = String(total); badge.hidden = !total; }
  }

  function mutateAction(action, key) {
    if (!key) return;
    const row = { ...(state.actions[key] || {}) };
    if (action === "review") row.reviewed = !row.reviewed;
    if (action === "snooze") row.snoozedUntil = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
    if (action === "dismiss") row.dismissedDate = new Date().toISOString().slice(0, 10);
    state.actions[key] = row;
    saveJson(ACTIONS_KEY, state.actions);
    render();
  }

  function validatePayload(payload) {
    if (!payload || typeof payload !== "object") throw new Error("รูปแบบข้อมูล Today ไม่ถูกต้อง");
    if (!Array.isArray(payload.items) || !Array.isArray(payload.technical_watch)) throw new Error("ไม่พบส่วนเหตุการณ์สำคัญหรือ Technical Watch");
    for (const item of payload.items) {
      if (!item || typeof item !== "object" || !item.ticker || !Array.isArray(item.events)) throw new Error("รายการเหตุการณ์สำคัญไม่สมบูรณ์");
      if (item.events.length && item.events.every((event) => event?.event_type === "technical")) throw new Error("พบ technical-only item ในเหตุการณ์สำคัญ");
    }
    for (const item of payload.technical_watch) {
      if (!item || typeof item !== "object" || !item.ticker || !Array.isArray(item.events) || !item.events.length || item.events.some((event) => event?.event_type !== "technical")) throw new Error("Technical Watch ไม่สมบูรณ์");
    }
    return payload;
  }

  async function load() {
    state.loading = true;
    state.error = null;
    render();
    try {
      const response = await fetch(`${DATA_URL}?v=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`attention_today.json HTTP ${response.status}`);
      state.data = validatePayload(await response.json());
    } catch (error) {
      state.error = error?.message || String(error);
      state.data = null;
    } finally {
      state.loading = false;
      render();
    }
  }

  function init() {
    installLogoFallback();
    window.StockcheckCompanyLogo = Object.freeze({ version: "1.0.0", markup: companyLogoMarkup });
    ensurePage();
    document.addEventListener("click", (event) => {
      const filter = event.target.closest?.("[data-p4-filter]");
      if (filter) {
        state.filter = filter.dataset.p4Filter || "all";
        render();
        return;
      }
      const action = event.target.closest?.("[data-p4-action]");
      if (action) {
        event.preventDefault();
        mutateAction(action.dataset.p4Action || "", action.dataset.p4Key || "");
        return;
      }
      if (event.target.closest?.("[data-p4-retry]")) load();
    });
    document.addEventListener("change", (event) => {
      const input = event.target.closest?.("[data-p4-pref]");
      if (!input) return;
      state.preferences[input.dataset.p4Pref] = Boolean(input.checked);
      saveJson(PREFS_KEY, state.preferences);
      render();
    });
    load();
    window.StockcheckAttentionP4 = { version: VERSION, load, render };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
