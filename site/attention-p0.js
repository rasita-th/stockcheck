(() => {
  "use strict";

  const DATA_URL = "data/attention_today.json";
  const CACHE_KEY = "stockcheck.attention.lastKnownGood.v3";
  const PRIORITY_ORDER = { Critical: 0, Risk: 1, Action: 2, Watch: 3, Developing: 4 };
  const VALID_PRIORITIES = new Set(Object.keys(PRIORITY_ORDER));
  const NEWS_TYPES = new Set(["news", "corporate_event", "regulatory", "litigation"]);
  const NEWS_SOURCES = new Set(["gdelt", "company_ir", "company_press_release", "regulator"]);
  const EXTERNAL_SOURCE_TYPES = new Set(["sec", "company_ir", "company_press_release", "regulator", "gdelt", "media"]);
  const state = { data: null, loading: false, error: null, filter: "all", fallbackNote: "" };

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
  const num = (value) => Number.isFinite(Number(value)) ? Number(value) : null;
  const money = (value) => num(value) == null ? "—" : `$${num(value).toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
  const pct = (value) => num(value) == null ? "—" : `${num(value) > 0 ? "+" : ""}${num(value).toFixed(1)}%`;
  const pctClass = (value) => num(value) == null || num(value) === 0 ? "neutral" : num(value) < 0 ? "red" : "green";
  const asArray = (value) => Array.isArray(value) ? value : [];

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
    technical_risk: "สัญญาณทางเทคนิคอ่อนแอ",
    technical_setup: "สัญญาณทางเทคนิคแข็งแรง",
    price_drop: "ราคาปรับลงแรง",
    price_move: "ราคาเคลื่อนไหวแรง",
    buy_zone_cross: "เข้าสู่โซนที่กำหนดไว้",
    trim_zone_cross: "แตะโซนลดสัดส่วน",
  };

  const SOURCE_LABELS = {
    sec: "SEC",
    company_ir: "Investor Relations",
    company_press_release: "ข่าวจากบริษัท",
    regulator: "หน่วยงานกำกับ",
    gdelt: "สื่อภายนอก",
    media: "สื่อภายนอก",
  };

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

  function normalizeSource(raw) {
    const source = raw && typeof raw === "object" ? raw : {};
    return {
      type: String(source.type || source.provider || "unknown"),
      quality: String(source.quality || "unknown"),
      url: String(source.url || ""),
      published_at: source.published_at || source.data_generated_at || "",
      domain: String(source.domain || ""),
      form: String(source.form || ""),
    };
  }

  function normalizeEvent(raw, ticker = "") {
    const event = raw && typeof raw === "object" ? raw : {};
    const source = normalizeSource(event.source);
    const sourceChain = asArray(event.source_chain).map(normalizeSource).filter((item) => item.type !== "unknown" || item.url);
    if (!sourceChain.length && (source.type !== "unknown" || source.url)) sourceChain.push(source);
    return {
      ...event,
      event_id: String(event.event_id || `${ticker}:${event.event_subtype || event.event_type || "event"}:${event.event_time || "unknown"}`),
      ticker: String(event.ticker || ticker || "").toUpperCase(),
      event_type: String(event.event_type || "event"),
      event_subtype: String(event.event_subtype || event.event_type || "event"),
      headline: String(event.headline || event.event_subtype || event.event_type || "Event"),
      summary: String(event.summary || event.why_today || ""),
      why_today: String(event.why_today || event.summary || event.headline || ""),
      verification_status: String(event.verification_status || "unknown"),
      verification_level: String(event.verification_level || event.verification_status || "unknown"),
      verification_reason: String(event.verification_reason || ""),
      entity_confidence: String(event.entity_confidence || "unknown"),
      source,
      source_chain: sourceChain,
      secondary_source_count: Number(event.secondary_source_count || sourceChain.filter((item) => item.quality !== "primary").length || 0),
    };
  }

  function normalizeItem(raw) {
    const item = raw && typeof raw === "object" ? raw : {};
    const ticker = String(item.ticker || item.symbol || "").toUpperCase();
    const events = asArray(item.events).map((event) => normalizeEvent(event, ticker));
    const source = normalizeSource(item.source || events[0]?.source);
    const priority = VALID_PRIORITIES.has(item.priority) ? item.priority : "Developing";
    const reasons = (Array.isArray(item.why_today) ? item.why_today : [item.why_today || item.signals]).flat().filter(Boolean).map(String);
    return {
      ...item,
      ticker,
      name: String(item.name || ticker),
      portfolio_status: String(item.portfolio_status || "watchlist"),
      role: String(item.role || ""),
      priority,
      priority_score: Number.isFinite(Number(item.priority_score)) ? Number(item.priority_score) : 0,
      why_today: reasons,
      event_type: String(item.event_type || events[0]?.event_type || "event"),
      event_subtype: String(item.event_subtype || events[0]?.event_subtype || "event"),
      event_time: item.event_time || events[0]?.event_time || "",
      verification_status: String(item.verification_status || events[0]?.verification_status || "unknown"),
      verification_level: String(item.verification_level || events[0]?.verification_level || item.verification_status || "unknown"),
      verification_reason: String(item.verification_reason || events[0]?.verification_reason || ""),
      source_status: String(item.source_status || source.quality || "unknown"),
      source,
      events,
      actions: item.actions && typeof item.actions === "object" ? item.actions : {},
    };
  }

  function normalizePayload(raw) {
    if (!raw || typeof raw !== "object" || !Array.isArray(raw.items)) throw new Error("attention_today.json has an invalid contract");
    const items = raw.items.map(normalizeItem).filter((item) => item.ticker && item.events.length);
    const technicalWatch = asArray(raw.technical_watch).map(normalizeItem).filter((item) => item.ticker && item.events.length);
    return {
      ...raw,
      schema_version: String(raw.schema_version || "legacy"),
      contract_version: String(raw.contract_version || "2.0-p0"),
      features: raw.features && typeof raw.features === "object" ? raw.features : {},
      coverage_status: raw.coverage_status === "complete" ? "complete" : "partial",
      summary: raw.summary && typeof raw.summary === "object" ? raw.summary : {},
      technical_summary: raw.technical_summary && typeof raw.technical_summary === "object" ? raw.technical_summary : {},
      source_health: raw.source_health && typeof raw.source_health === "object" ? raw.source_health : {},
      items,
      technical_watch: technicalWatch,
      errors: asArray(raw.errors),
    };
  }

  function saveLastKnownGood(payload) {
    try { localStorage.setItem(CACHE_KEY, JSON.stringify(payload)); } catch { /* optional */ }
  }

  function loadLastKnownGood() {
    try {
      const raw = localStorage.getItem(CACHE_KEY);
      return raw ? normalizePayload(JSON.parse(raw)) : null;
    } catch { return null; }
  }

  function ensurePage() {
    let page = document.getElementById("attentionPageP0");
    if (page) return page;
    const shell = document.querySelector(".app-shell") || document.body;
    page = document.createElement("section");
    page.id = "attentionPageP0";
    page.className = "attention-page attention-p0-page";
    page.setAttribute("aria-live", "polite");
    const topbar = shell.querySelector(".topbar");
    if (topbar) topbar.insertAdjacentElement("afterend", page);
    else shell.prepend(page);
    document.body.classList.add("attention-p0-ready");
    return page;
  }

  function primaryEvent(item) {
    return asArray(item?.events)[0] || {};
  }

  function isTechnicalItem(item) {
    const events = asArray(item?.events);
    return events.length > 0 && events.every((event) => event.event_type === "technical");
  }

  function isNewsEvent(event) {
    return NEWS_TYPES.has(String(event?.event_type || "")) || NEWS_SOURCES.has(String(event?.source?.type || ""));
  }

  function externalSources(item) {
    const collected = [];
    const seen = new Set();
    for (const event of asArray(item?.events)) {
      for (const source of asArray(event.source_chain).concat([event.source])) {
        if (!source || !source.url || !EXTERNAL_SOURCE_TYPES.has(String(source.type || ""))) continue;
        const key = `${source.type}:${source.url}`;
        if (seen.has(key)) continue;
        seen.add(key);
        collected.push(source);
      }
    }
    return collected;
  }

  function priorityBadge(value) {
    const key = VALID_PRIORITIES.has(value) ? value : "Developing";
    return `<span class="p0-priority p0-priority-${esc(key.toLowerCase())}">${esc(PRIORITY_LABELS[key])}</span>`;
  }

  function eventLabel(item) {
    return EVENT_LABELS[item?.event_subtype] || EVENT_LABELS[primaryEvent(item)?.event_subtype] || "เหตุการณ์ที่ควรตรวจสอบ";
  }

  function portfolioLabel(value) {
    return value === "holding" ? "ถืออยู่ในพอร์ต" : value === "watchlist" ? "อยู่ในรายการติดตาม" : "ยังไม่ได้ถือ";
  }

  function timingLabel(item) {
    const event = primaryEvent(item);
    const timing = String(event.earnings_timing || item.earnings_timing || "");
    const timingText = timing === "after_market" ? " · หลังตลาดปิด" : timing === "before_market" ? " · ก่อนตลาดเปิด" : "";
    return `${formatTime(item.event_time || event.event_time)}${timingText}`;
  }

  function technicalReason(item) {
    const event = primaryEvent(item);
    const rsi = num(event.rsi14);
    const ema20 = num(event.pct_vs_ema20);
    const ema200 = num(event.pct_vs_ema200);
    const score = num(event.technical_score);
    const parts = [];
    if (score != null) parts.push(`คะแนนเทคนิค ${score.toFixed(0)}/100`);
    if (rsi != null) parts.push(`RSI ${rsi.toFixed(1)}`);
    if (ema20 != null) parts.push(`ราคาอยู่${ema20 >= 0 ? "เหนือ" : "ต่ำกว่า"} EMA20 ${Math.abs(ema20).toFixed(1)}%`);
    if (ema200 != null) parts.push(`อยู่${ema200 >= 0 ? "เหนือ" : "ต่ำกว่า"} EMA200 ${Math.abs(ema200).toFixed(1)}%`);
    return parts.length ? parts.join(" · ") : "มีสัญญาณทางเทคนิคที่ควรเปิดกราฟตรวจสอบ";
  }

  function whatChanged(item) {
    const event = primaryEvent(item);
    const subtype = String(item.event_subtype || event.event_subtype || "");
    const days = num(event.days_to_event);
    if (subtype === "earnings_today") return "บริษัทมีกำหนดประกาศผลประกอบการวันนี้";
    if (subtype === "earnings_upcoming") return days != null ? `บริษัทจะประกาศผลประกอบการในอีก ${days} วัน` : "บริษัทใกล้ประกาศผลประกอบการ";
    if (subtype === "earnings_reported") return "บริษัทประกาศผลประกอบการแล้ว ควรตรวจรายได้ กำไร และ guidance";
    if (subtype === "earnings_call_pending") return "ผลประกอบการออกแล้ว แต่ยังรอฟังคำอธิบายจากผู้บริหาร";
    if (subtype === "capital_raise") return "บริษัทมีเอกสารที่อาจเกี่ยวข้องกับการเพิ่มทุนหรือ dilution";
    if (subtype === "late_filing") return "บริษัทแจ้งว่าจะยื่นรายงานทางการเงินล่าช้า";
    if (subtype === "auditor_change") return "มีการเปลี่ยนแปลงหรือประเด็นเกี่ยวกับผู้สอบบัญชี";
    if (subtype === "management_change") return "บริษัทเปิดเผยการเปลี่ยนแปลงผู้บริหารหรือคณะกรรมการ";
    if (subtype === "material_agreement") return "บริษัทเปิดเผยข้อตกลงสำคัญฉบับใหม่";
    if (subtype === "transaction") return "บริษัทเปิดเผยการซื้อ ขาย หรือโอนสินทรัพย์สำคัญ";
    if (subtype === "periodic_report") return "มีงบการเงินฉบับใหม่ให้ตรวจสอบ";
    if (isTechnicalItem(item)) return technicalReason(item);
    return String(event.summary || item.why_today?.[0] || "มีเหตุการณ์ใหม่ที่ควรตรวจสอบ");
  }

  function whyItMatters(item) {
    const subtype = String(item.event_subtype || primaryEvent(item)?.event_subtype || "");
    if (subtype.startsWith("earnings")) return "ตัวเลขรายได้ กำไร และ guidance อาจเปลี่ยนมุมมองต่อหุ้นและทำให้ราคาผันผวนได้";
    if (["capital_raise", "debt_obligation"].includes(subtype)) return "อาจกระทบจำนวนหุ้น กระแสเงินสด หรือความแข็งแรงของงบดุล";
    if (["late_filing", "auditor_change", "delisting_risk"].includes(subtype)) return "เป็นความเสี่ยงที่ควรตรวจเอกสารต้นฉบับและทบทวนสมมติฐานการลงทุน";
    if (["material_agreement", "transaction", "management_change"].includes(subtype)) return "เหตุการณ์นี้อาจกระทบรายได้ การดำเนินงาน หรือความเชื่อมั่นของตลาด";
    if (subtype === "technical_risk") return "ใช้เป็นสัญญาณให้ทบทวน downside และระดับราคาที่รับความเสี่ยงได้ ไม่ใช่คำแนะนำขาย";
    if (subtype === "technical_setup") return "เป็นเพียงบริบททางเทคนิคเพื่อช่วยเลือกจังหวะตรวจกราฟ ไม่ใช่คำแนะนำซื้อ";
    return "ควรเปิดแหล่งข้อมูลต้นฉบับเพื่อประเมินว่ากระทบ thesis หรือความเสี่ยงของพอร์ตหรือไม่";
  }

  function verificationBadge(item) {
    if (isTechnicalItem(item)) return "";
    const status = String(item?.verification_status || "unknown");
    const level = String(item?.verification_level || status);
    const labels = {
      confirmed_primary: "ยืนยันจากแหล่งต้นทาง",
      corroborated: "ยืนยันจากหลายแหล่ง",
      corroborated_secondary: "มีหลายสื่อรายงาน",
      unverified_report: "ยังไม่พบแหล่งต้นทาง",
      estimated: "วันโดยประมาณ",
    };
    const label = labels[level] || (status === "confirmed" ? "ยืนยันแล้ว" : status === "estimated" ? "วันโดยประมาณ" : "ยังไม่ยืนยัน");
    return `<span class="p0-verification p0-verification-${esc(status)}">${esc(label)}</span>`;
  }

  function sourceName(source) {
    return SOURCE_LABELS[source?.type] || source?.domain || "แหล่งข้อมูลภายนอก";
  }

  function sourceCell(item) {
    const sources = externalSources(item);
    if (!sources.length) return `<span class="p0-no-source">—</span>`;
    const primary = sources.find((source) => source.quality === "primary") || sources[0];
    return `${verificationBadge(item)}<a class="p0-source-link" href="${esc(primary.url)}" target="_blank" rel="noopener noreferrer">${esc(sourceName(primary))}</a>`;
  }

  function actionButtons(item) {
    const actions = item?.actions || {};
    const external = externalSources(item);
    const buttons = [];
    if (external.length) {
      const source = external.find((row) => row.quality === "primary") || external[0];
      buttons.push(`<a class="p0-action" href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">ดูข้อมูลต้นฉบับ</a>`);
    }
    if (actions.company_ir && !external.some((source) => source.url === actions.company_ir)) {
      buttons.push(`<a class="p0-action" href="${esc(actions.company_ir)}" target="_blank" rel="noopener noreferrer">Investor Relations</a>`);
    }
    if (actions.tradingview) buttons.push(`<a class="p0-action" href="${esc(actions.tradingview)}" target="_blank" rel="noopener noreferrer">ดูกราฟ</a>`);
    return buttons.join("");
  }

  function eventDetails(item) {
    const events = asArray(item.events);
    if (!events.length) return "";
    return `<details class="p0-events"><summary>ดูรายละเอียด ${events.length} เหตุการณ์</summary>${events.map((event) => {
      const external = asArray(event.source_chain).filter((source) => source.url && EXTERNAL_SOURCE_TYPES.has(String(source.type || "")));
      const links = external.length ? `<div class="p0-source-chain">${external.slice(0, 4).map((source) => `<a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${esc(sourceName(source))}</a>`).join("")}</div>` : "";
      return `<article><strong>${esc(EVENT_LABELS[event.event_subtype] || event.headline || "รายละเอียดเหตุการณ์")}</strong><span>${esc(event.summary || event.why_today || "")}</span><small>${esc(formatTime(event.event_time))}</small>${links}</article>`;
    }).join("")}</details>`;
  }

  function matchesCatalyst(item) {
    if (state.filter === "all") return true;
    if (state.filter === "holdings") return item.portfolio_status === "holding";
    if (state.filter === "unverified") return item.verification_status !== "confirmed";
    if (state.filter === "sec") return item.events.some((event) => event.event_type === "sec_filing");
    if (state.filter === "earnings") return item.events.some((event) => event.event_type === "earnings");
    if (state.filter === "news") return item.events.some(isNewsEvent);
    if (state.filter === "technical") return false;
    return true;
  }

  function matchesTechnical(item) {
    if (state.filter === "technical" || state.filter === "all") return true;
    if (state.filter === "holdings") return item.portfolio_status === "holding";
    return false;
  }

  function sortItems(rows) {
    return rows.sort((a, b) => (PRIORITY_ORDER[a.priority] ?? 9) - (PRIORITY_ORDER[b.priority] ?? 9) || (b.priority_score || 0) - (a.priority_score || 0));
  }

  function catalystItems() {
    return sortItems(asArray(state.data?.items).filter(matchesCatalyst));
  }

  function technicalItems() {
    return sortItems(asArray(state.data?.technical_watch).filter(matchesTechnical));
  }

  function hero() {
    const summary = state.data?.summary || {};
    const coverage = String(state.data?.coverage_status || "partial");
    const fallback = state.fallbackNote ? `<p class="p0-fallback-note">${esc(state.fallbackNote)}</p>` : "";
    const cards = [["Critical", "เร่งด่วน"], ["Risk", "ความเสี่ยง"], ["Action", "ควรตรวจสอบ"], ["Watch", "จับตา"]];
    return `<section class="panel-card p0-hero"><div><span class="p0-eyebrow">สรุปสิ่งสำคัญของหุ้นในพอร์ต</span><h2>สิ่งที่ต้องจับตาวันนี้</h2><p>ติดตาม ${Number(state.data?.total_monitored || 0)} หุ้น · อัปเดต ${esc(formatTime(state.data?.updated_at))}</p>${fallback}</div><div class="p0-summary-grid">${cards.map(([key, label]) => `<div><strong>${Number(summary[key] || 0)}</strong><span>${label}</span></div>`).join("")}</div><div class="p0-coverage p0-coverage-${esc(coverage)}"><strong>${coverage === "complete" ? "ข้อมูลพร้อมครบ" : "ข้อมูลบางแหล่งยังไม่ครบ"}</strong><span>${coverage === "complete" ? "ระบบตรวจแหล่งข้อมูลที่ตั้งค่าไว้ครบแล้ว" : "รายการที่แสดงยังใช้ได้ แต่ไม่ควรตีความว่าไม่มีความเสี่ยงอื่นเลย"}</span></div></section>`;
  }

  function sourceStrip() {
    const health = state.data?.source_health || {};
    const labels = { sec: "SEC", earnings: "ปฏิทินงบ", market_data: "ข้อมูลตลาด", news: "ข่าว", ir: "Investor Relations", gdelt: "ข่าวภายนอก", sec_ticker_map: "ทะเบียนบริษัท" };
    const entries = Object.entries(health);
    const degraded = entries.filter(([, value]) => String(value?.status || "unknown") !== "ok").length;
    return `<details class="p0-data-status"><summary>สถานะข้อมูล: ${degraded ? `มี ${degraded} แหล่งที่ยังไม่สมบูรณ์` : "พร้อมใช้งาน"}</summary><section class="p0-source-strip">${entries.map(([key, value]) => {
      const status = String(value?.status || "unknown");
      const tone = status === "ok" ? "ok" : status === "error" ? "error" : "partial";
      const statusLabel = status === "ok" ? "พร้อม" : status === "error" ? "ขัดข้อง" : "บางส่วน";
      return `<div class="p0-source p0-source-${tone}" title="${esc(value?.note || value?.source || "")}"><span>${esc(labels[key] || key)}</span><strong>${esc(statusLabel)}</strong></div>`;
    }).join("")}</section></details>`;
  }

  function filters() {
    const definitions = [["all", "ทั้งหมด"], ["holdings", "หุ้นในพอร์ต"], ["earnings", "งบการเงิน"], ["sec", "SEC"], ["news", "ข่าวและเหตุการณ์"], ["technical", "เทคนิค"], ["unverified", "ยังไม่ยืนยัน"]];
    return `<section class="p0-filters">${definitions.map(([key, label]) => `<button type="button" class="${state.filter === key ? "active" : ""}" data-p0-filter="${key}">${label}</button>`).join("")}</section>`;
  }

  function catalystTable(rows) {
    return `<section class="panel-card p0-table-card"><div class="p0-table-wrap"><table class="p0-table p0-catalyst-table"><thead><tr><th>ระดับ</th><th>หุ้น</th><th>เกิดอะไรขึ้น</th><th>ทำไมสำคัญ</th><th>เวลา</th><th>ยืนยันโดย</th><th>ดูต่อ</th></tr></thead><tbody>${rows.map((item) => `<tr class="p0-row p0-row-${esc(String(item.priority || "developing").toLowerCase())}"><td>${priorityBadge(item.priority)}</td><td><strong>${esc(item.ticker)}</strong><span>${esc(item.name || "")}</span><small>${esc(portfolioLabel(item.portfolio_status))}</small></td><td><strong>${esc(eventLabel(item))}</strong><span>${esc(whatChanged(item))}</span>${eventDetails(item)}</td><td><span>${esc(whyItMatters(item))}</span></td><td><span>${esc(timingLabel(item))}</span></td><td>${sourceCell(item)}</td><td><div class="p0-actions">${actionButtons(item)}</div></td></tr>`).join("")}</tbody></table></div></section>`;
  }

  function technicalTable(rows) {
    return `<section class="panel-card p0-table-card"><div class="p0-table-wrap"><table class="p0-table p0-technical-table"><thead><tr><th>หุ้น</th><th>สัญญาณ</th><th>เหตุผลที่ต้องจับตา</th><th>ราคา</th><th>ข้อมูลล่าสุด</th><th>ดูต่อ</th></tr></thead><tbody>${rows.map((item) => `<tr class="p0-row"><td><strong>${esc(item.ticker)}</strong><span>${esc(item.name || "")}</span><small>${esc(portfolioLabel(item.portfolio_status))}</small></td><td>${priorityBadge(item.priority)}<strong>${esc(eventLabel(item))}</strong></td><td><span>${esc(technicalReason(item))}</span><small>${esc(whyItMatters(item))}</small></td><td><strong>${money(item.price)}</strong><span class="${pctClass(item.day_change_pct)}">${pct(item.day_change_pct)}</span>${num(item.relative_volume) != null ? `<small>ปริมาณซื้อขาย ${num(item.relative_volume).toFixed(2)} เท่าของค่าเฉลี่ย</small>` : ""}</td><td><span>${esc(formatTime(item.event_time))}</span></td><td><div class="p0-actions">${actionButtons(item)}</div></td></tr>`).join("")}</tbody></table></div></section>`;
  }

  function catalystCards(rows) {
    return `<section class="p0-card-list">${rows.map((item) => `<article class="panel-card p0-card p0-card-${esc(String(item.priority || "developing").toLowerCase())}"><header><div><strong>${esc(item.ticker)}</strong><span>${esc(item.name || "")}</span></div>${priorityBadge(item.priority)}</header><div class="p0-card-meta"><span>${esc(portfolioLabel(item.portfolio_status))}</span><span>${esc(eventLabel(item))}</span><span>${esc(timingLabel(item))}</span></div><h4>เกิดอะไรขึ้น</h4><p>${esc(whatChanged(item))}</p><h4>ทำไมสำคัญ</h4><p>${esc(whyItMatters(item))}</p><div class="p0-card-source">${sourceCell(item)}</div>${eventDetails(item)}<div class="p0-actions">${actionButtons(item)}</div></article>`).join("")}</section>`;
  }

  function technicalCards(rows) {
    return `<section class="p0-card-list">${rows.map((item) => `<article class="panel-card p0-card"><header><div><strong>${esc(item.ticker)}</strong><span>${esc(item.name || "")}</span></div>${priorityBadge(item.priority)}</header><div class="p0-card-meta"><span>${esc(eventLabel(item))}</span><span>${esc(formatTime(item.event_time))}</span></div><p>${esc(technicalReason(item))}</p><small>${esc(whyItMatters(item))}</small><div class="p0-card-market"><span>ราคา <strong>${money(item.price)}</strong></span>${num(item.relative_volume) != null ? `<span>Volume ${num(item.relative_volume).toFixed(2)}x</span>` : ""}</div><div class="p0-actions">${actionButtons(item)}</div></article>`).join("")}</section>`;
  }

  function sectionHeader(title, description, count) {
    return `<header class="p0-section-header"><div><h3>${esc(title)}</h3><p>${esc(description)}</p></div><span>${Number(count || 0)} รายการ</span></header>`;
  }

  function render() {
    const page = ensurePage();
    try {
      if (state.loading) {
        page.innerHTML = `<div class="attention-shell p0-shell"><section class="panel-card p0-loading"><h2>กำลังเตรียมข้อมูลวันนี้</h2><p>กำลังรวมงบการเงิน ข่าว SEC และสัญญาณตลาด…</p></section></div>`;
        return;
      }
      if (state.error && !state.data) {
        page.innerHTML = `<div class="attention-shell p0-shell"><section class="panel-card p0-error"><h2>ยังเปิดข้อมูล Today ไม่ได้</h2><p>${esc(state.error)}</p><button type="button" data-p0-retry>ลองใหม่</button></section></div>`;
        return;
      }

      const catalysts = catalystItems();
      const technical = technicalItems();
      const showCatalysts = state.filter !== "technical";
      const showTechnical = ["all", "holdings", "technical"].includes(state.filter);
      const catalystEmpty = `<section class="panel-card p0-empty"><h3>ยังไม่พบเหตุการณ์บริษัทที่สำคัญในตัวกรองนี้</h3><p>${state.data?.coverage_status === "complete" ? "วันนี้ยังไม่มี earnings, SEC filing หรือข่าวบริษัทที่ผ่านเกณฑ์" : "ข้อมูลบางแหล่งยังตรวจไม่ครบ จึงยังไม่ควรตีความว่าเป็น all-clear"}</p></section>`;
      const technicalEmpty = `<section class="panel-card p0-empty"><h3>ยังไม่มีสัญญาณทางเทคนิคที่ต้องเน้น</h3><p>ระบบจะแสดงเฉพาะข้อมูลล่าสุดและสัญญาณที่เด่นจริง</p></section>`;

      const catalystSection = showCatalysts ? `<section class="p0-section">${sectionHeader("เหตุการณ์สำคัญวันนี้", "งบการเงิน SEC และข่าวบริษัทจะมาก่อนสัญญาณทางเทคนิค", catalysts.length)}${catalysts.length ? catalystTable(catalysts) + catalystCards(catalysts) : catalystEmpty}</section>` : "";
      const technicalSection = showTechnical ? `<section class="p0-section p0-technical-section">${sectionHeader("จับตาทางเทคนิค", "ใช้ช่วยเลือกจังหวะเปิดกราฟเท่านั้น ไม่ใช่คำแนะนำซื้อหรือขาย", technical.length)}${technical.length ? technicalTable(technical) + technicalCards(technical) : technicalEmpty}</section>` : "";
      page.innerHTML = `<div class="attention-shell p0-shell">${hero()}${sourceStrip()}${filters()}${catalystSection}${technicalSection}</div>`;

      const badge = document.getElementById("attentionNavBadge");
      const total = asArray(state.data?.items).length + asArray(state.data?.technical_watch).length;
      if (badge) { badge.textContent = String(total); badge.hidden = !total; }
    } catch (error) {
      page.innerHTML = `<div class="attention-shell p0-shell"><section class="panel-card p0-error"><h2>เกิดข้อผิดพลาดในการแสดงผล Today</h2><p>${esc(error?.message || String(error))}</p><button type="button" data-p0-retry>ลองใหม่</button></section></div>`;
      console.error("Today render error", error);
    }
  }

  async function load() {
    state.loading = true;
    state.error = null;
    state.fallbackNote = "";
    render();
    try {
      const response = await fetch(`${DATA_URL}?v=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`attention_today.json HTTP ${response.status}`);
      const payload = normalizePayload(await response.json());
      state.data = payload;
      saveLastKnownGood(payload);
    } catch (error) {
      const cached = loadLastKnownGood();
      if (cached) {
        state.data = cached;
        state.error = error?.message || String(error);
        state.fallbackNote = "กำลังแสดงข้อมูลล่าสุดที่เคยโหลดสำเร็จ เนื่องจากรอบใหม่ยังไม่พร้อม";
      } else {
        state.data = null;
        state.error = error?.message || String(error);
      }
    } finally {
      state.loading = false;
      render();
    }
  }

  function init() {
    ensurePage();
    document.addEventListener("click", (event) => {
      const filter = event.target.closest?.("[data-p0-filter]");
      if (filter) {
        event.preventDefault();
        state.filter = filter.dataset.p0Filter || "all";
        render();
      }
      if (event.target.closest?.("[data-p0-retry]")) {
        event.preventDefault();
        load();
      }
    });
    load();
    window.__stockcheckAttentionRefresh = load;
    window.StockcheckAttentionP0 = { version: "10.2.0", load, render, normalizePayload };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
