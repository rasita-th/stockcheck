(() => {
  "use strict";

  const VERSION = "10.9.1";
  const SNAPSHOT_URL = `data/screener_snapshot.json?v=${encodeURIComponent(VERSION)}`;
  const STORAGE_KEY = "stockTimingRadar.drawdownFilter.v1";
  const DEFAULTS = Object.freeze({ enabled: false, preset: "5-15" });
  const PRESETS = Object.freeze({
    "0-5": [0, 5],
    "5-15": [5, 15],
    "15-30": [15, 30],
    "30+": [30, Infinity]
  });

  let metrics = new Map();
  let settings = loadSettings();
  let renderFrame = 0;
  let applying = false;

  function loadSettings() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (saved && typeof saved === "object") {
        return {
          enabled: Boolean(saved.enabled),
          preset: Object.hasOwn(PRESETS, saved.preset) ? saved.preset : DEFAULTS.preset
        };
      }
    } catch (_) {}
    return { ...DEFAULTS };
  }

  function saveSettings() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch (_) {}
  }

  function numberValue(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function normalizeTicker(value) {
    return String(value || "").trim().replace(/^[$#]+/, "").toUpperCase();
  }

  function metricFor(ticker) {
    const normalized = normalizeTicker(ticker);
    const rowMetric = window.StockcheckTechnicalV2?.drawdownFor?.(normalized);
    return rowMetric || metrics.get(normalized) || null;
  }

  function depthFor(metric) {
    const current = numberValue(metric?.currentPct ?? metric?.drawdownCurrentPct);
    return current === null ? null : Math.abs(Math.min(0, current));
  }

  function drawdownClass(depth) {
    if (depth === null) return "drawdown-unavailable";
    if (depth < 5) return "drawdown-near";
    if (depth < 15) return "drawdown-moderate";
    if (depth < 30) return "drawdown-deep";
    return "drawdown-severe";
  }

  function formatDepth(metric) {
    const current = numberValue(metric?.currentPct ?? metric?.drawdownCurrentPct);
    return current === null ? "—" : `${current.toFixed(1)}%`;
  }

  function tickerFromRow(row) {
    const first = row?.querySelector("td, th");
    const selected = row?.querySelector("[data-select]");
    const candidate = row?.dataset?.select || row?.dataset?.symbol || selected?.dataset?.select || selected?.dataset?.symbol || first?.textContent || "";
    const match = String(candidate).toUpperCase().match(/[A-Z0-9.\-]{1,18}/);
    return normalizeTicker(match?.[0]);
  }

  function tickerFromCard(card) {
    const selected = card?.matches?.("[data-select]") ? card : card?.querySelector?.("[data-select]");
    const candidate = selected?.dataset?.select || selected?.dataset?.symbol || card?.textContent || "";
    const match = String(candidate).toUpperCase().match(/[A-Z0-9.\-]{1,18}/);
    return normalizeTicker(match?.[0]);
  }

  function isMatch(metric) {
    if (!settings.enabled) return true;
    const depth = depthFor(metric);
    if (depth === null) return false;
    const [min, max] = PRESETS[settings.preset] || PRESETS[DEFAULTS.preset];
    return depth >= min && depth < max;
  }

  function makeControl(idPrefix) {
    const wrap = document.createElement("section");
    wrap.className = "drawdown-filter-block";
    wrap.dataset.drawdownFilter = idPrefix;
    wrap.innerHTML = `
      <div class="drawdown-filter-head">
        <label class="toggle-row drawdown-filter-toggle">
          <span>Drawdown depth</span>
          <input id="${idPrefix}DrawdownEnabled" type="checkbox" ${settings.enabled ? "checked" : ""} />
        </label>
      </div>
      <div class="segmented drawdown-presets" role="group" aria-label="Drawdown depth preset">
        ${Object.keys(PRESETS).map((key) => `<button type="button" data-drawdown-preset="${key}" class="${settings.preset === key ? "active" : ""}">${key.replace("-", "–")}%${key.endsWith("+") ? "" : ""}</button>`).join("")}
      </div>
      <p class="helper-text drawdown-helper">วัดว่าราคาต่ำกว่าจุดสูงสุดก่อนหน้ากี่เปอร์เซ็นต์ · หุ้นที่ข้อมูลไม่ครบจะถูกตัดออกเมื่อเปิดฟิลเตอร์</p>`;
    return wrap;
  }

  function mountControls() {
    const desktopStack = document.querySelector("#watchlistPanel .filter-card .filter-stack");
    if (desktopStack && !desktopStack.querySelector('[data-drawdown-filter="desktop"]')) {
      desktopStack.append(makeControl("desktop"));
    }
    const sheetBody = document.querySelector("#filtersSheet .sheet-body");
    if (sheetBody && !sheetBody.querySelector('[data-drawdown-filter="sheet"]')) {
      const heading = document.createElement("h3");
      heading.className = "drawdown-sheet-heading";
      heading.textContent = "Drawdown";
      sheetBody.append(heading, makeControl("sheet"));
    }
  }

  function syncControlState() {
    document.querySelectorAll("[data-drawdown-filter]").forEach((root) => {
      const toggle = root.querySelector('input[type="checkbox"]');
      if (toggle) toggle.checked = settings.enabled;
      root.querySelectorAll("[data-drawdown-preset]").forEach((button) => {
        button.classList.toggle("active", button.dataset.drawdownPreset === settings.preset);
        button.disabled = !settings.enabled;
      });
      root.classList.toggle("is-disabled", !settings.enabled);
    });
  }

  function decorateHeader(table) {
    const header = table?.querySelector("thead tr");
    if (!header || header.querySelector("[data-sort-drawdown]")) return;
    const th = document.createElement("th");
    th.dataset.sortDrawdown = "asc";
    th.scope = "col";
    th.tabIndex = 0;
    th.title = "Drawdown from the prior peak";
    th.textContent = "Drawdown";
    header.append(th);
  }

  function decorateRow(row) {
    const ticker = tickerFromRow(row);
    if (!ticker) return;
    const metric = metricFor(ticker);
    let cell = row.querySelector("[data-drawdown-cell]");
    if (!cell) {
      cell = document.createElement("td");
      cell.dataset.drawdownCell = "";
      row.append(cell);
    }
    const depth = depthFor(metric);
    cell.className = `drawdown-value ${drawdownClass(depth)}`;
    cell.textContent = formatDepth(metric);
    cell.title = metric?.status === "unavailable"
      ? "Drawdown history unavailable"
      : `${depth?.toFixed(1) ?? "—"}% below prior peak · as of ${metric?.asOf || "—"}`;
    row.classList.toggle("drawdown-filter-hidden", !isMatch(metric));
  }

  function decorateCards() {
    document.querySelectorAll("#technicalMobileCards > *").forEach((card) => {
      const ticker = tickerFromCard(card);
      if (!ticker) return;
      const metric = metricFor(ticker);
      let item = card.querySelector("[data-drawdown-card-metric]");
      if (!item) {
        item = document.createElement("div");
        item.className = "drawdown-card-metric";
        item.dataset.drawdownCardMetric = "";
        card.append(item);
      }
      const depth = depthFor(metric);
      item.innerHTML = `<span>Drawdown</span><strong class="drawdown-value ${drawdownClass(depth)}">${formatDepth(metric)}</strong><small>${metric?.daysSincePeak ?? metric?.drawdownDaysSincePeak ?? "—"} days since peak</small>`;
      card.classList.toggle("drawdown-filter-hidden", !isMatch(metric));
    });
  }

  function decorateTables() {
    ["#technicalTable", "#technicalMobileTable"].forEach((selector) => {
      const table = document.querySelector(selector);
      if (!table) return;
      decorateHeader(table);
      table.querySelectorAll("tbody tr").forEach(decorateRow);
    });
  }

  function visibleCount() {
    return Array.from(document.querySelectorAll("#technicalTableBody tr")).filter((row) => !row.classList.contains("drawdown-filter-hidden")).length;
  }

  function updateResultCopy() {
    if (!settings.enabled) return;
    const count = visibleCount();
    const pill = document.querySelector("#filterResultPill");
    if (pill) pill.textContent = `✓ ${count} results`;
    document.querySelectorAll(".mini-badge").forEach((badge) => { badge.textContent = String(count); });
  }

  function sortTable(table, direction) {
    const body = table?.tBodies?.[0];
    if (!body) return;
    const rows = Array.from(body.rows);
    rows.sort((a, b) => {
      const aDepth = depthFor(metricFor(tickerFromRow(a)));
      const bDepth = depthFor(metricFor(tickerFromRow(b)));
      const av = aDepth === null ? Infinity : aDepth;
      const bv = bDepth === null ? Infinity : bDepth;
      return direction === "desc" ? bv - av : av - bv;
    });
    rows.forEach((row) => body.append(row));
  }

  function bindEvents() {
    document.addEventListener("change", (event) => {
      const toggle = event.target.closest?.('[data-drawdown-filter] input[type="checkbox"]');
      if (!toggle) return;
      settings.enabled = Boolean(toggle.checked);
      saveSettings();
      syncControlState();
      scheduleRender();
    });

    document.addEventListener("click", (event) => {
      const preset = event.target.closest?.("[data-drawdown-preset]");
      if (preset) {
        settings.enabled = true;
        settings.preset = preset.dataset.drawdownPreset;
        saveSettings();
        syncControlState();
        scheduleRender();
        return;
      }
      const header = event.target.closest?.("[data-sort-drawdown]");
      if (header) {
        const direction = header.dataset.sortDrawdown === "asc" ? "desc" : "asc";
        header.dataset.sortDrawdown = direction;
        header.textContent = `Drawdown ${direction === "asc" ? "↑" : "↓"}`;
        sortTable(header.closest("table"), direction);
      }
    });

    document.addEventListener("keydown", (event) => {
      if ((event.key === "Enter" || event.key === " ") && event.target.matches?.("[data-sort-drawdown]")) {
        event.preventDefault();
        event.target.click();
      }
    });
  }

  function scheduleRender() {
    cancelAnimationFrame(renderFrame);
    renderFrame = requestAnimationFrame(() => {
      if (applying) return;
      applying = true;
      try {
        mountControls();
        syncControlState();
        decorateTables();
        decorateCards();
        updateResultCopy();
        document.documentElement.dataset.drawdownScreener = VERSION;
      } finally {
        applying = false;
      }
    });
  }

  async function loadSnapshot() {
    const response = await fetch(SNAPSHOT_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`drawdown snapshot ${response.status}`);
    const payload = await response.json();
    const rows = Array.isArray(payload?.rows) ? payload.rows : [];
    metrics = new Map(rows.map((row) => [normalizeTicker(row.symbol || row.ticker), row.drawdown || row]));
    return payload;
  }

  async function boot() {
    bindEvents();
    mountControls();
    syncControlState();
    try {
      await loadSnapshot();
    } catch (error) {
      console.warn("Drawdown screener unavailable", error);
      document.documentElement.dataset.drawdownScreener = "degraded";
    }
    scheduleRender();
    const observer = new MutationObserver(scheduleRender);
    observer.observe(document.body, { childList: true, subtree: true });
    window.addEventListener("pageshow", scheduleRender);
  }

  window.StockRadarDrawdownScreener = Object.freeze({
    version: VERSION,
    refresh: scheduleRender,
    metricFor,
    get settings() { return { ...settings }; }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
