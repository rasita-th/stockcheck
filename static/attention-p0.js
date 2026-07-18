(() => {
  "use strict";

  const DATA_URL = "data/attention_today.json";
  const CACHE_KEY = "stockcheck.attention.lastKnownGood.v2";
  const PRIORITY_ORDER = { Critical: 0, Risk: 1, Action: 2, Watch: 3, Developing: 4 };
  const VALID_PRIORITIES = new Set(Object.keys(PRIORITY_ORDER));
  const NEWS_TYPES = new Set(["news", "corporate_event", "regulatory", "litigation"]);
  const NEWS_SOURCES = new Set(["gdelt", "company_ir", "company_press_release", "regulator"]);
  const state = { data: null, loading: false, error: null, filter: "all", fallbackNote: "" };

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
  const num = (value) => Number.isFinite(Number(value)) ? Number(value) : null;
  const money = (value) => num(value) == null ? "—" : `$${num(value).toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
  const pct = (value) => num(value) == null ? "—" : `${num(value) > 0 ? "+" : ""}${num(value).toFixed(1)}%`;
  const pctClass = (value) => num(value) == null || num(value) === 0 ? "neutral" : num(value) < 0 ? "red" : "green";
  const asArray = (value) => Array.isArray(value) ? value : [];

  function formatTime(value) {
    if (!value) return "—";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value);
    return parsed.toLocaleString(undefined, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZoneName: "short" });
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
      why_today: reasons.length ? reasons : ["Event details are unavailable."],
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
    const sourceHealth = raw.source_health && typeof raw.source_health === "object" ? raw.source_health : {};
    return {
      ...raw,
      schema_version: String(raw.schema_version || "legacy"),
      contract_version: String(raw.contract_version || "2.0-p0"),
      features: raw.features && typeof raw.features === "object" ? raw.features : {},
      coverage_status: raw.coverage_status === "complete" ? "complete" : "partial",
      summary: raw.summary && typeof raw.summary === "object" ? raw.summary : {},
      source_health: sourceHealth,
      items,
      errors: asArray(raw.errors),
    };
  }

  function saveLastKnownGood(payload) {
    try { localStorage.setItem(CACHE_KEY, JSON.stringify(payload)); } catch { /* storage is optional */ }
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

  function priorityBadge(value) {
    const label = VALID_PRIORITIES.has(value) ? value : "Developing";
    return `<span class="p0-priority p0-priority-${esc(label.toLowerCase())}">${esc(label)}</span>`;
  }

  function verificationBadge(item) {
    const status = String(item?.verification_status || "unknown");
    const level = String(item?.verification_level || status);
    const labels = {
      confirmed_primary: "Confirmed · primary",
      corroborated: "Confirmed · corroborated",
      corroborated_secondary: "Reported · corroborated",
      unverified_report: "Unverified report",
      estimated: "Estimated",
    };
    const label = labels[level] || (status === "confirmed" ? `Confirmed · ${item?.source_status || "source"}` : status === "estimated" ? "Estimated" : status);
    return `<span class="p0-verification p0-verification-${esc(status)}">${esc(label)}</span>`;
  }

  function actionButtons(item) {
    const actions = item?.actions || {};
    const definitions = [["primary_source", "Open source"], ["company_ir", "Company IR"], ["tradingview", "Chart"]];
    return definitions.filter(([key]) => actions[key]).map(([key, label]) => `<a class="p0-action" href="${esc(actions[key])}" target="_blank" rel="noopener noreferrer">${label}</a>`).join("");
  }

  function reasons(item) {
    return asArray(item?.why_today).slice(0, 3);
  }

  function isNewsEvent(event) {
    return NEWS_TYPES.has(String(event?.event_type || "")) || NEWS_SOURCES.has(String(event?.source?.type || ""));
  }

  function matches(item) {
    if (state.filter === "all") return true;
    if (state.filter === "holdings") return item.portfolio_status === "holding";
    if (state.filter === "unverified") return item.verification_status !== "confirmed";
    if (state.filter === "sec") return item.events.some((event) => event.event_type === "sec_filing");
    if (state.filter === "earnings") return item.events.some((event) => event.event_type === "earnings");
    if (state.filter === "news") return item.events.some(isNewsEvent);
    if (state.filter === "technical") return item.events.some((event) => event.event_type === "technical");
    return true;
  }

  function items() {
    return asArray(state.data?.items).filter(matches).sort((a, b) => (PRIORITY_ORDER[a.priority] ?? 9) - (PRIORITY_ORDER[b.priority] ?? 9) || (b.priority_score || 0) - (a.priority_score || 0));
  }

  function sourceStrip() {
    const health = state.data?.source_health || {};
    const labels = { sec: "SEC", earnings: "Earnings", market_data: "Market", news: "News", ir: "IR", gdelt: "GDELT", sec_ticker_map: "Ticker map" };
    return `<section class="p0-source-strip">${Object.entries(health).map(([key, value]) => {
      const status = String(value?.status || "unknown");
      const tone = status === "ok" ? "ok" : status === "error" ? "error" : "partial";
      return `<div class="p0-source p0-source-${tone}" title="${esc(value?.note || value?.source || "")}"><span>${esc(labels[key] || key)}</span><strong>${esc(status)}</strong></div>`;
    }).join("")}</section>`;
  }

  function hero() {
    const summary = state.data?.summary || {};
    const coverage = String(state.data?.coverage_status || "partial");
    const fallback = state.fallbackNote ? `<p class="p0-fallback-note">${esc(state.fallbackNote)}</p>` : "";
    return `<section class="panel-card p0-hero"><div><span class="p0-eyebrow">Event-first morning risk desk</span><h2>Today Attention</h2><p>${Number(state.data?.total_monitored || 0)} monitored · Updated ${esc(formatTime(state.data?.updated_at))}</p>${fallback}</div><div class="p0-summary-grid">${["Critical", "Risk", "Action", "Watch"].map((label) => `<div><strong>${Number(summary[label] || 0)}</strong><span>${label}</span></div>`).join("")}</div><div class="p0-coverage p0-coverage-${esc(coverage)}"><strong>${coverage === "complete" ? "Coverage complete" : "Partial coverage"}</strong><span>${coverage === "complete" ? "All configured sources are healthy." : "At least one source is partial or unavailable; this is not a full all-clear."}</span></div></section>`;
  }

  function filters() {
    const definitions = [["all", "All"], ["holdings", "Holdings"], ["sec", "SEC"], ["earnings", "Earnings"], ["news", "News & Events"], ["technical", "Technical"], ["unverified", "Unverified"]];
    return `<section class="p0-filters">${definitions.map(([key, label]) => `<button type="button" class="${state.filter === key ? "active" : ""}" data-p0-filter="${key}">${label}</button>`).join("")}</section>`;
  }

  function sourceChain(event) {
    const sources = asArray(event?.source_chain);
    if (!sources.length) return "";
    return `<div class="p0-source-chain"><strong>Source chain</strong>${sources.slice(0, 5).map((source) => source.url ? `<a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${esc(source.type)} · ${esc(source.quality)}</a>` : `<span>${esc(source.type)} · ${esc(source.quality)}</span>`).join("")}${event.verification_reason ? `<small>${esc(event.verification_reason)}</small>` : ""}</div>`;
  }

  function eventDetails(item) {
    const events = asArray(item.events);
    if (!events.length) return "";
    return `<details class="p0-events"><summary>${events.length} linked event${events.length === 1 ? "" : "s"}</summary>${events.map((event) => `<article><strong>${esc(event.headline || event.event_subtype)}</strong><span>${esc(event.summary || "")}</span><small>${esc(formatTime(event.event_time))} · ${esc(event.verification_level || event.verification_status || "unknown")}</small>${sourceChain(event)}</article>`).join("")}</details>`;
  }

  function table(rows) {
    return `<section class="panel-card p0-table-card"><div class="p0-table-wrap"><table class="p0-table"><thead><tr><th>Priority</th><th>Stock</th><th>Why today</th><th>Event</th><th>Market reaction</th><th>Source</th><th>Actions</th></tr></thead><tbody>${rows.map((item) => `<tr class="p0-row p0-row-${esc(String(item.priority || "developing").toLowerCase())}"><td>${priorityBadge(item.priority)}<small>Score ${esc(item.priority_score ?? "—")}</small></td><td><strong>${esc(item.ticker)}</strong><span>${esc(item.name || "")}</span><small>${esc(item.portfolio_status || "watchlist")} · ${esc(item.role || "")}</small></td><td><ul>${reasons(item).map((reason) => `<li>${esc(reason)}</li>`).join("")}</ul>${eventDetails(item)}</td><td><strong>${esc(item.event_subtype || item.event_type || "—")}</strong><span>${esc(formatTime(item.event_time))}</span></td><td><strong>${money(item.price)}</strong><span class="${pctClass(item.day_change_pct)}">${pct(item.day_change_pct)}</span>${num(item.relative_volume) != null ? `<small>Rel vol ${num(item.relative_volume).toFixed(1)}x</small>` : ""}</td><td>${verificationBadge(item)}<small>${esc(item.source?.type || "unknown")}</small></td><td><div class="p0-actions">${actionButtons(item)}</div></td></tr>`).join("")}</tbody></table></div></section>`;
  }

  function cards(rows) {
    return `<section class="p0-card-list">${rows.map((item) => `<article class="panel-card p0-card p0-card-${esc(String(item.priority || "developing").toLowerCase())}"><header><div><strong>${esc(item.ticker)}</strong><span>${esc(item.name || "")}</span></div>${priorityBadge(item.priority)}</header><div class="p0-card-meta"><span>${esc(item.portfolio_status || "watchlist")}</span><span>${esc(item.event_subtype || item.event_type || "event")}</span><span>${esc(formatTime(item.event_time))}</span></div><ul class="p0-reasons">${reasons(item).map((reason) => `<li>${esc(reason)}</li>`).join("")}</ul><div class="p0-card-market"><span>Price <strong>${money(item.price)}</strong></span><span class="${pctClass(item.day_change_pct)}">${pct(item.day_change_pct)}</span></div><div class="p0-card-source">${verificationBadge(item)}<span>${esc(item.source?.type || "unknown")}</span></div>${eventDetails(item)}<div class="p0-actions">${actionButtons(item)}</div></article>`).join("")}</section>`;
  }

  function render() {
    const page = ensurePage();
    try {
      if (state.loading) { page.innerHTML = `<div class="attention-shell p0-shell"><section class="panel-card p0-loading"><h2>Today Attention</h2><p>Building event-first view…</p></section></div>`; return; }
      if (state.error && !state.data) { page.innerHTML = `<div class="attention-shell p0-shell"><section class="panel-card p0-error"><h2>Today Attention unavailable</h2><p>${esc(state.error)}</p><button type="button" data-p0-retry>Retry</button></section></div>`; return; }
      const rows = items();
      const empty = `<section class="panel-card p0-empty"><h3>${state.data?.coverage_status === "complete" ? "All clear today" : "No material item found — coverage is partial"}</h3><p>${state.data?.coverage_status === "complete" ? "No event met the attention threshold." : "One or more sources are incomplete, so this is not a full all-clear."}</p></section>`;
      page.innerHTML = `<div class="attention-shell p0-shell">${hero()}${sourceStrip()}${filters()}${rows.length ? table(rows) + cards(rows) : empty}</div>`;
      const badge = document.getElementById("attentionNavBadge");
      if (badge) { badge.textContent = String(state.data?.items?.length || 0); badge.hidden = !(state.data?.items?.length); }
    } catch (error) {
      page.innerHTML = `<div class="attention-shell p0-shell"><section class="panel-card p0-error"><h2>Today Attention render error</h2><p>${esc(error?.message || String(error))}</p><button type="button" data-p0-retry>Retry</button></section></div>`;
    }
  }

  async function load() {
    state.loading = true; state.error = null; state.fallbackNote = ""; render();
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
        state.fallbackNote = `Showing last known good data because the latest payload failed validation: ${state.error}`;
      } else {
        state.data = null;
        state.error = error?.message || String(error);
      }
    } finally {
      state.loading = false; render();
    }
  }

  function init() {
    ensurePage();
    document.addEventListener("click", (event) => {
      const filter = event.target.closest?.("[data-p0-filter]");
      if (filter) { event.preventDefault(); state.filter = filter.dataset.p0Filter || "all"; render(); }
      if (event.target.closest?.("[data-p0-retry]")) { event.preventDefault(); load(); }
    });
    load();
    window.__stockcheckAttentionRefresh = load;
    window.StockcheckAttentionP0 = { version: "10.1.0", load, render, normalizePayload };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
