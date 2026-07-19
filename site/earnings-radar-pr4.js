(() => {
  "use strict";

  const VERSION = "10.5.1";
  const DATA_URL = "data/earnings_radar.json";
  const PAGE_SIZE = 30;
  const FILTERS = [
    ["all", "ทั้งหมด"],
    ["before_market", "ก่อนตลาดเปิด"],
    ["after_market", "หลังตลาดปิด"],
    ["unknown", "ไม่ระบุเวลา"],
    ["portfolio", "หุ้นในพอร์ต"],
    ["related", "เกี่ยวข้องกับพอร์ต"],
    ["coverage", "Coverage universe"],
  ];
  const TIME_LABELS = {
    before_market: "ก่อนตลาดเปิด",
    during_market: "ระหว่างตลาด",
    after_market: "หลังตลาดปิด",
    unknown: "ยังไม่ระบุเวลา",
  };
  const RELATION_LABELS = {
    portfolio: "หุ้นในพอร์ต",
    related: "เกี่ยวข้องกับพอร์ต",
    coverage: "Coverage universe",
    market: "ตลาดทั่วไป",
  };
  const SOURCE_LABELS = {
    company_ir: "Investor Relations",
    company_press_release: "ข่าวจากบริษัท",
    sec: "SEC",
    regulator: "หน่วยงานกำกับ",
    finnhub: "Finnhub estimate",
    unknown: "ยังไม่ระบุแหล่ง",
  };
  const ICONS = {
    calendar: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 2v3M17 2v3M3.5 9h17M5 4.5h14A1.5 1.5 0 0 1 20.5 6v13A1.5 1.5 0 0 1 19 20.5H5A1.5 1.5 0 0 1 3.5 19V6A1.5 1.5 0 0 1 5 4.5Z"/></svg>',
    filter: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16l-6 7v5l-4 2v-7Z"/></svg>',
    download: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m0 0 4-4m-4 4-4-4M4 19h16"/></svg>',
    external: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M18 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h6"/></svg>',
    chevron: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>',
    close: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>',
    left: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 18-6-6 6-6"/></svg>',
    right: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>',
  };

  const state = {
    data: null,
    error: null,
    loading: false,
    selectedDate: "",
    filter: "all",
    visibleCount: PAGE_SIZE,
    selectedItem: null,
    observer: null,
    renderQueued: false,
    personalTickers: new Set(),
  };

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  }[char]));
  const asArray = (value) => Array.isArray(value) ? value : [];
  const asNumber = (value) => Number.isFinite(Number(value)) ? Number(value) : null;
  const PERSONAL_STORAGE = Object.freeze({
    portfolio: "stockTimingRadar.myPortfolio.v1",
    screeners: "stockTimingRadar.screeners.v54",
    watchlist: "stockTimingRadar.watchlist.v54",
  });

  function normaliseTicker(value) {
    return String(value || "").trim().replace(/^[$#]+/, "").toUpperCase().replace(/[^A-Z0-9.\-]/g, "");
  }

  function loadPersonalTickers() {
    try {
      const direct = localStorage.getItem(PERSONAL_STORAGE.portfolio);
      if (direct !== null) return new Set(asArray(JSON.parse(direct)).map(normaliseTicker).filter(Boolean));
    } catch (_) {}
    try {
      const screeners = JSON.parse(localStorage.getItem(PERSONAL_STORAGE.screeners) || "{}");
      if (Array.isArray(screeners?.default?.watchlist)) {
        return new Set(screeners.default.watchlist.map(normaliseTicker).filter(Boolean));
      }
    } catch (_) {}
    try {
      return new Set(asArray(JSON.parse(localStorage.getItem(PERSONAL_STORAGE.watchlist) || "[]")).map(normaliseTicker).filter(Boolean));
    } catch (_) {
      return new Set();
    }
  }

  function personaliseItem(item) {
    const ticker = normaliseTicker(item?.ticker);
    const relatedTo = asArray(item?.related_to).map(normaliseTicker).filter((value) => state.personalTickers.has(value));
    let relation = ["coverage", "market"].includes(item?.relation) ? item.relation : "coverage";
    if (state.personalTickers.has(ticker)) relation = "portfolio";
    else if (relatedTo.length) relation = "related";
    return { ...item, relation, related_to: relatedTo, source_relation: item?.relation || "market" };
  }

  function personalisedItems() {
    return asArray(state.data?.items).map(personaliseItem);
  }

  function formatDate(value, long = false) {
    const parsed = new Date(`${String(value || "").slice(0, 10)}T12:00:00Z`);
    if (Number.isNaN(parsed.getTime())) return String(value || "—");
    return parsed.toLocaleDateString("th-TH", long
      ? { weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }
      : { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  }

  function formatMoney(value, compact = false) {
    const number = asNumber(value);
    if (number == null) return "—";
    if (compact && Math.abs(number) >= 1e9) return `$${(number / 1e9).toFixed(number >= 1e11 ? 1 : 2)}B`;
    if (compact && Math.abs(number) >= 1e6) return `$${(number / 1e6).toFixed(1)}M`;
    return `$${number.toLocaleString("en-US", { maximumFractionDigits: 4 })}`;
  }

  function validate(payload) {
    if (!payload || typeof payload !== "object") throw new Error("รูปแบบ Earnings Radar ไม่ถูกต้อง");
    if (!String(payload.schema_version || "").startsWith("1.0")) throw new Error("Earnings Radar schema ไม่รองรับ");
    if (!Array.isArray(payload.items) || !Array.isArray(payload.daily_summary)) throw new Error("Earnings Radar ไม่มีรายการหรือ daily summary");
    for (const item of payload.items) {
      if (!item || typeof item !== "object" || !item.ticker || !item.earnings_date) throw new Error("พบรายการงบที่ไม่สมบูรณ์");
    }
    return payload;
  }

  function daySummary(dateValue) {
    const fallback = {
      date: dateValue, total: 0, before_market: 0, during_market: 0, after_market: 0,
      unknown: 0, portfolio: 0, related: 0, coverage: 0, market: 0, confirmed: 0, estimated: 0,
    };
    const source = asArray(state.data?.daily_summary).find((row) => row?.date === dateValue) || fallback;
    const rows = personalisedItems().filter((item) => item.earnings_date === dateValue);
    const relationCount = (relation) => rows.filter((item) => item.relation === relation).length;
    return {
      ...source,
      portfolio: relationCount("portfolio"),
      related: relationCount("related"),
      coverage: relationCount("coverage"),
      market: relationCount("market"),
    };
  }

  function activeDates() {
    return asArray(state.data?.daily_summary).filter((row) => Number(row?.total || 0) > 0).map((row) => row.date);
  }

  function chooseInitialDate() {
    const preferred = String(state.data?.selected_date || "");
    if (daySummary(preferred).total > 0) return preferred;
    const active = activeDates();
    return active.find((value) => value >= preferred) || active[0] || preferred || new Date().toISOString().slice(0, 10);
  }

  function filteredRows() {
    const rows = personalisedItems().filter((item) => item.earnings_date === state.selectedDate);
    if (state.filter === "all") return rows;
    if (["before_market", "after_market", "during_market", "unknown"].includes(state.filter)) {
      return rows.filter((item) => item.time === state.filter);
    }
    return rows.filter((item) => item.relation === state.filter);
  }

  function relationClass(item) {
    return ["portfolio", "related", "coverage", "market"].includes(item?.relation) ? item.relation : "market";
  }

  function relationText(item) {
    if (item.relation === "related" && asArray(item.related_to).length) {
      return `เกี่ยวข้องกับ ${item.related_to.join(", ")}`;
    }
    return RELATION_LABELS[item.relation] || "ตลาดทั่วไป";
  }

  function sourceText(item) {
    const base = SOURCE_LABELS[item.source_type] || item.source_type || "ยังไม่ระบุแหล่ง";
    return item.status === "confirmed" ? `${base} · ยืนยันแล้ว` : `${base} · ประมาณการ`;
  }

  function tickerMark(item) {
    const logoMarkup = window.StockcheckCompanyLogo?.markup;
    if (typeof logoMarkup === "function") return logoMarkup(item, "er-ticker-mark");
    return `<span class="er-ticker-mark" data-logo-shell><span data-logo-fallback>${esc(String(item.ticker || "?").slice(0, 2))}</span></span>`;
  }

  function selectedSummaryCards() {
    const summary = daySummary(state.selectedDate);
    const coverage = state.data?.coverage || {};
    const days = Number(state.data?.window?.days_forward || 0) + Number(state.data?.window?.days_back || 0) + 1;
    return `<section class="er-radar" aria-labelledby="erRadarTitle">
      <header><div><span class="er-line-icon">${ICONS.calendar}</span><div><h2 id="erRadarTitle">Earnings Radar</h2><p>ภาพรวมงบการเงินวันที่ ${esc(formatDate(state.selectedDate, true))}</p></div></div><button type="button" data-er-scroll-calendar>เปิดปฏิทินทั้งหมด${ICONS.chevron}</button></header>
      <div class="er-stat-grid">
        <div><span>บริษัทที่ประกาศงบ</span><strong>${Number(summary.total || 0).toLocaleString()}</strong><small>ก่อนตลาด ${Number(summary.before_market || 0)} · หลังตลาด ${Number(summary.after_market || 0)} · ไม่ระบุ ${Number(summary.unknown || 0)}</small></div>
        <div class="actionable"><span>เกี่ยวข้องกับพอร์ตคุณ</span><strong>${Number(summary.related || 0).toLocaleString()}</strong><small>มี mapping ที่ตรวจสอบย้อนกลับได้</small></div>
        <div><span>หุ้นในพอร์ตใกล้ประกาศ</span><strong>${Number(summary.portfolio || 0).toLocaleString()}</strong><small>จาก My Portfolio ${state.personalTickers.size} ตัว</small></div>
        <div><span>ข้อมูลในช่วง ${days} วัน</span><strong>${Number(coverage.published_rows || 0).toLocaleString()}</strong><small>จาก market source ${Number(coverage.market_source_rows || 0).toLocaleString()} แถว</small></div>
      </div>
    </section>`;
  }

  function filterBar(rows) {
    const allDateRows = personalisedItems().filter((item) => item.earnings_date === state.selectedDate);
    const countFor = (key) => {
      if (key === "all") return allDateRows.length;
      if (["before_market", "after_market", "during_market", "unknown"].includes(key)) return allDateRows.filter((item) => item.time === key).length;
      return allDateRows.filter((item) => item.relation === key).length;
    };
    return `<div class="er-filters" aria-label="ตัวกรองปฏิทินงบ">${FILTERS.map(([key, label]) => `<button type="button" data-er-filter="${key}" class="${state.filter === key ? "active" : ""}">${esc(label)} <span>${countFor(key)}</span></button>`).join("")}</div>`;
  }

  function calendarControls() {
    const dates = activeDates();
    const index = dates.indexOf(state.selectedDate);
    const previous = index > 0 ? dates[index - 1] : "";
    const next = index >= 0 && index < dates.length - 1 ? dates[index + 1] : "";
    return `<div class="er-calendar-controls">
      <button type="button" data-er-date="${esc(previous)}" ${previous ? "" : "disabled"} aria-label="วันที่มีงบก่อนหน้า">${ICONS.left}</button>
      <label>${ICONS.calendar}<input type="date" value="${esc(state.selectedDate)}" min="${esc(state.data?.window?.from || "")}" max="${esc(state.data?.window?.to || "")}" data-er-date-input></label>
      <button type="button" data-er-date="${esc(next)}" ${next ? "" : "disabled"} aria-label="วันที่มีงบถัดไป">${ICONS.right}</button>
      <button type="button" class="er-export" data-er-export ${filteredRows().length ? "" : "disabled"}>${ICONS.download}<span>ส่งออก CSV</span></button>
    </div>`;
  }

  function desktopRow(item) {
    const relation = relationClass(item);
    return `<tr class="er-relation-${relation}">
      <td><div class="er-company">${tickerMark(item)}<div><strong>${esc(item.ticker)}</strong><span>${esc(item.name || item.ticker)}</span></div></div></td>
      <td><strong>${esc(TIME_LABELS[item.time] || TIME_LABELS.unknown)}</strong><span>${esc(formatDate(item.earnings_date))}</span></td>
      <td><strong>${esc(formatMoney(item.eps_estimate))}</strong><span>${item.eps_actual == null ? "ประมาณการ" : `Actual ${esc(formatMoney(item.eps_actual))}`}</span></td>
      <td><strong>${esc(formatMoney(item.revenue_estimate, true))}</strong><span>${item.revenue_actual == null ? "ประมาณการ" : `Actual ${esc(formatMoney(item.revenue_actual, true))}`}</span></td>
      <td><strong>${esc(sourceText(item))}</strong><span>${esc(item.fiscal_quarter || "")}</span></td>
      <td><span class="er-relation-text">${esc(relationText(item))}</span></td>
      <td><button type="button" data-er-details="${esc(item.ticker)}|${esc(item.earnings_date)}">ดูรายละเอียด${ICONS.chevron}</button></td>
    </tr>`;
  }

  function mobileCard(item) {
    const relation = relationClass(item);
    return `<article class="er-mobile-card er-relation-${relation}">
      <header><div class="er-company">${tickerMark(item)}<div><strong>${esc(item.ticker)}</strong><span>${esc(item.name || item.ticker)}</span></div></div><div><strong>${esc(TIME_LABELS[item.time] || TIME_LABELS.unknown)}</strong><span>${esc(formatDate(item.earnings_date))}</span></div></header>
      <dl><div><dt>EPS คาดการณ์</dt><dd>${esc(formatMoney(item.eps_estimate))}</dd></div><div><dt>Revenue คาดการณ์</dt><dd>${esc(formatMoney(item.revenue_estimate, true))}</dd></div><div><dt>แหล่งข้อมูล</dt><dd>${esc(sourceText(item))}</dd></div><div><dt>เกี่ยวข้องกับพอร์ต</dt><dd>${esc(relationText(item))}</dd></div></dl>
      <button type="button" data-er-details="${esc(item.ticker)}|${esc(item.earnings_date)}">ดูรายละเอียด${ICONS.chevron}</button>
    </article>`;
  }

  function calendarSection() {
    const rows = filteredRows();
    const visible = rows.slice(0, state.visibleCount);
    return `<section class="er-calendar" id="earningsCalendarP4" aria-labelledby="erCalendarTitle">
      <header><div><h2 id="erCalendarTitle">Earnings Calendar</h2><p>${esc(formatDate(state.selectedDate, true))} · แสดง ${visible.length.toLocaleString()} จาก ${rows.length.toLocaleString()} บริษัทในตัวกรอง</p></div>${calendarControls()}</header>
      ${filterBar(rows)}
      ${state.error ? `<div class="er-error">${esc(state.error)}</div>` : ""}
      ${rows.length ? `<div class="er-table-wrap"><table><thead><tr><th>บริษัท</th><th>เวลา</th><th>คาดการณ์ EPS</th><th>คาดการณ์ Revenue</th><th>ยืนยันโดย</th><th>เกี่ยวข้องกับพอร์ต</th><th>ดูต่อ</th></tr></thead><tbody>${visible.map(desktopRow).join("")}</tbody></table></div><div class="er-mobile-list">${visible.map(mobileCard).join("")}</div>${visible.length < rows.length ? `<button type="button" class="er-load-more" data-er-load-more>แสดงเพิ่มอีก ${Math.min(PAGE_SIZE, rows.length - visible.length)} บริษัท</button>` : ""}` : '<div class="er-empty">ไม่มีบริษัทในวันที่และตัวกรองนี้ ลองเลือกวันที่มีรายการถัดไป</div>'}
    </section>`;
  }

  function dialogMarkup() {
    const item = state.selectedItem;
    if (!item) return "";
    return `<dialog class="er-dialog" id="earningsDetailDialog" open><form method="dialog"><button value="close" aria-label="ปิด">${ICONS.close}</button></form><div class="er-dialog-company">${tickerMark(item)}<div><span>${esc(item.name || item.ticker)}</span><h2>${esc(item.ticker)}</h2><p>${esc(item.fiscal_quarter || "ผลประกอบการ")}</p></div></div><div class="er-dialog-grid">
      <div><span>วันที่ / เวลา</span><strong>${esc(formatDate(item.earnings_date, true))}</strong><small>${esc(TIME_LABELS[item.time] || TIME_LABELS.unknown)}</small></div>
      <div><span>สถานะข้อมูล</span><strong>${esc(sourceText(item))}</strong><small>${esc(item.confidence || "medium")} confidence</small></div>
      <div><span>EPS คาดการณ์</span><strong>${esc(formatMoney(item.eps_estimate))}</strong><small>${item.eps_actual == null ? "ยังไม่มี actual" : `Actual ${esc(formatMoney(item.eps_actual))}`}</small></div>
      <div><span>Revenue คาดการณ์</span><strong>${esc(formatMoney(item.revenue_estimate, true))}</strong><small>${item.revenue_actual == null ? "ยังไม่มี actual" : `Actual ${esc(formatMoney(item.revenue_actual, true))}`}</small></div>
      <div><span>ความเกี่ยวข้อง</span><strong>${esc(relationText(item))}</strong><small>${esc(item.relation_reason_th || "")}</small></div>
      <div><span>อุตสาหกรรม</span><strong>${esc(item.industry || "ยังไม่มีข้อมูล")}</strong><small>${esc(item.exchange || "")}</small></div>
    </div>${item.source_url ? `<a class="er-dialog-source" href="${esc(item.source_url)}" target="_blank" rel="noopener noreferrer">เปิดแหล่งข้อมูลต้นฉบับ${ICONS.external}</a>` : '<p class="er-dialog-note">รายการนี้เป็นข้อมูลประมาณการจาก provider จึงไม่มีลิงก์แหล่งต้นฉบับบริษัท</p>'}</dialog><div class="er-dialog-backdrop" data-er-close></div>`;
  }

  function renderIntoShell() {
    if (!state.data || state.loading) return;
    const shell = document.querySelector("#attentionPageP4 .p4-shell");
    if (!shell) return;
    let root = document.getElementById("earningsRadarRootP4");
    if (!root) {
      root = document.createElement("div");
      root.id = "earningsRadarRootP4";
      root.className = "er-root";
      shell.appendChild(root);
    }
    root.innerHTML = `${selectedSummaryCards()}${calendarSection()}${dialogMarkup()}`;
    document.body.classList.add("earnings-radar-p4-ready");
  }

  function scheduleAttach() {
    if (state.renderQueued) return;
    state.renderQueued = true;
    requestAnimationFrame(() => {
      state.renderQueued = false;
      renderIntoShell();
    });
  }

  function observePage() {
    const page = document.getElementById("attentionPageP4");
    if (!page || state.observer) return;
    state.observer = new MutationObserver(() => {
      if (!document.getElementById("earningsRadarRootP4")) scheduleAttach();
    });
    state.observer.observe(page, { childList: true, subtree: true });
  }

  function setDate(value) {
    if (!value) return;
    state.selectedDate = value;
    state.visibleCount = PAGE_SIZE;
    state.selectedItem = null;
    renderIntoShell();
  }

  function selectItem(key) {
    const [ticker, eventDate] = String(key || "").split("|");
    state.selectedItem = personalisedItems().find((item) => item.ticker === ticker && item.earnings_date === eventDate) || null;
    renderIntoShell();
  }

  function csvValue(value) {
    const text = String(value ?? "");
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  }

  function exportCsv() {
    const rows = filteredRows();
    if (!rows.length) return;
    const header = ["ticker", "name", "date", "time", "eps_estimate", "revenue_estimate", "status", "source", "relation", "related_to"];
    const lines = [header.join(",")];
    for (const item of rows) {
      lines.push([
        item.ticker, item.name, item.earnings_date, item.time, item.eps_estimate,
        item.revenue_estimate, item.status, item.source_type, item.relation,
        asArray(item.related_to).join("|"),
      ].map(csvValue).join(","));
    }
    const blob = new Blob(["\ufeff", lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `earnings-calendar-${state.selectedDate}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async function load() {
    state.loading = true;
    state.error = null;
    try {
      const response = await fetch(`${DATA_URL}?v=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`earnings_radar.json HTTP ${response.status}`);
      state.data = validate(await response.json());
      state.personalTickers = loadPersonalTickers();
      state.selectedDate = chooseInitialDate();
    } catch (error) {
      state.error = error?.message || String(error);
      state.data = null;
      console.error("Could not load Earnings Radar", error);
    } finally {
      state.loading = false;
      if (state.data) scheduleAttach();
    }
  }

  function init() {
    state.personalTickers = loadPersonalTickers();
    const syncPersonalPortfolio = () => {
      state.personalTickers = loadPersonalTickers();
      state.visibleCount = PAGE_SIZE;
      renderIntoShell();
    };
    window.addEventListener("stockcheck:portfolio-change", syncPersonalPortfolio);
    window.addEventListener("storage", (event) => {
      if (Object.values(PERSONAL_STORAGE).includes(event.key)) syncPersonalPortfolio();
    });
    document.addEventListener("click", (event) => {
      const scroll = event.target.closest?.("[data-er-scroll-calendar]");
      if (scroll) document.getElementById("earningsCalendarP4")?.scrollIntoView({ behavior: "smooth", block: "start" });
      const filter = event.target.closest?.("[data-er-filter]");
      if (filter) {
        state.filter = filter.dataset.erFilter || "all";
        state.visibleCount = PAGE_SIZE;
        renderIntoShell();
      }
      const dateButton = event.target.closest?.("[data-er-date]");
      if (dateButton && dateButton.dataset.erDate) setDate(dateButton.dataset.erDate);
      const details = event.target.closest?.("[data-er-details]");
      if (details) selectItem(details.dataset.erDetails);
      if (event.target.closest?.("[data-er-load-more]")) {
        state.visibleCount += PAGE_SIZE;
        renderIntoShell();
      }
      if (event.target.closest?.("[data-er-export]")) exportCsv();
      if (event.target.closest?.("[data-er-close]") || event.target.closest?.(".er-dialog form button")) {
        state.selectedItem = null;
        renderIntoShell();
      }
    });
    document.addEventListener("change", (event) => {
      const input = event.target.closest?.("[data-er-date-input]");
      if (input?.value) setDate(input.value);
    });
    const interval = window.setInterval(() => {
      if (document.getElementById("attentionPageP4")) {
        window.clearInterval(interval);
        observePage();
        scheduleAttach();
      }
    }, 100);
    window.setTimeout(() => window.clearInterval(interval), 10000);
    load();
    window.StockcheckEarningsRadarP4 = { version: VERSION, load, render: renderIntoShell };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
