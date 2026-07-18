(() => {
  "use strict";
  const DATA_URL = "data/attention_today.json";
  const state = { data: null, loading: false, error: null, filter: "all" };
  const order = { Critical: 0, Risk: 1, Action: 2, Watch: 3, Developing: 4 };
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[char]));
  const num = (value) => Number.isFinite(Number(value)) ? Number(value) : null;
  const money = (value) => num(value) == null ? "—" : `$${num(value).toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
  const pct = (value) => num(value) == null ? "—" : `${num(value) > 0 ? "+" : ""}${num(value).toFixed(1)}%`;
  const pctClass = (value) => num(value) == null || num(value) === 0 ? "neutral" : num(value) < 0 ? "red" : "green";
  const formatTime = (value) => {
    if (!value) return "—";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value);
    return parsed.toLocaleString(undefined, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZoneName: "short" });
  };

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
    const label = String(value || "Developing");
    return `<span class="p0-priority p0-priority-${esc(label.toLowerCase())}">${esc(label)}</span>`;
  }

  function verificationBadge(item) {
    const status = String(item?.verification_status || "unknown");
    const source = String(item?.source_status || "unknown");
    const label = status === "confirmed" ? `Confirmed · ${source}` : status === "estimated" ? "Estimated" : status;
    return `<span class="p0-verification p0-verification-${esc(status)}">${esc(label)}</span>`;
  }

  function actionButtons(item) {
    const actions = item?.actions || {};
    const definitions = [["primary_source","Open source"],["company_ir","Company IR"],["tradingview","Chart"],["raw_data","Raw data"]];
    return definitions.filter(([key]) => actions[key]).map(([key, label]) => `<a class="p0-action" href="${esc(actions[key])}" target="_blank" rel="noopener noreferrer">${label}</a>`).join("");
  }

  function reasons(item) {
    const values = Array.isArray(item?.why_today) ? item.why_today : [item?.why_today].filter(Boolean);
    return values.slice(0, 3);
  }

  function matches(item) {
    if (state.filter === "all") return true;
    if (state.filter === "holdings") return item.portfolio_status === "holding";
    if (state.filter === "unverified") return item.verification_status !== "confirmed";
    if (state.filter === "sec") return item.events?.some((event) => event.event_type === "sec_filing");
    if (state.filter === "earnings") return item.events?.some((event) => event.event_type === "earnings");
    if (state.filter === "technical") return item.events?.some((event) => event.event_type === "technical");
    return true;
  }

  function items() {
    return (Array.isArray(state.data?.items) ? [...state.data.items] : []).filter(matches).sort((a, b) => (order[a.priority] ?? 9) - (order[b.priority] ?? 9) || (b.priority_score || 0) - (a.priority_score || 0));
  }

  function sourceStrip() {
    const health = state.data?.source_health || {};
    const labels = { sec: "SEC", earnings: "Earnings", market_data: "Market", news: "News", sec_ticker_map: "Ticker map" };
    return `<section class="p0-source-strip">${Object.entries(health).map(([key, value]) => {
      const status = String(value?.status || "unknown");
      const tone = status === "ok" ? "ok" : status === "error" ? "error" : "partial";
      return `<div class="p0-source p0-source-${tone}" title="${esc(value?.note || value?.source || "")}"><span>${esc(labels[key] || key)}</span><strong>${esc(status)}</strong></div>`;
    }).join("")}</section>`;
  }

  function hero() {
    const summary = state.data?.summary || {};
    const coverage = String(state.data?.coverage_status || "partial");
    return `<section class="panel-card p0-hero"><div><span class="p0-eyebrow">Event-first morning risk desk</span><h2>Today Attention</h2><p>${Number(state.data?.total_monitored || 0)} monitored · Updated ${esc(formatTime(state.data?.updated_at))}</p></div><div class="p0-summary-grid">${["Critical","Risk","Action","Watch"].map((label) => `<div><strong>${Number(summary[label] || 0)}</strong><span>${label}</span></div>`).join("")}</div><div class="p0-coverage p0-coverage-${esc(coverage)}"><strong>${coverage === "complete" ? "Coverage complete" : "Partial coverage"}</strong><span>${coverage === "complete" ? "All configured sources are healthy." : "At least one source is partial or unavailable; this is not a full all-clear."}</span></div></section>`;
  }

  function filters() {
    const definitions = [["all","All"],["holdings","Holdings"],["sec","SEC"],["earnings","Earnings"],["technical","Technical"],["unverified","Unverified"]];
    return `<section class="p0-filters">${definitions.map(([key, label]) => `<button type="button" class="${state.filter === key ? "active" : ""}" data-p0-filter="${key}">${label}</button>`).join("")}</section>`;
  }

  function eventDetails(item) {
    const events = Array.isArray(item.events) ? item.events : [];
    if (events.length <= 1) return "";
    return `<details class="p0-events"><summary>${events.length} linked events</summary>${events.map((event) => `<article><strong>${esc(event.headline || event.event_subtype)}</strong><span>${esc(event.summary || "")}</span><small>${esc(formatTime(event.event_time))} · ${esc(event.verification_status || "unknown")}</small></article>`).join("")}</details>`;
  }

  function table(rows) {
    return `<section class="panel-card p0-table-card"><div class="p0-table-wrap"><table class="p0-table"><thead><tr><th>Priority</th><th>Stock</th><th>Why today</th><th>Event</th><th>Market reaction</th><th>Source</th><th>Actions</th></tr></thead><tbody>${rows.map((item) => `<tr class="p0-row p0-row-${esc(String(item.priority || "developing").toLowerCase())}"><td>${priorityBadge(item.priority)}<small>Score ${esc(item.priority_score ?? "—")}</small></td><td><strong>${esc(item.ticker)}</strong><span>${esc(item.name || "")}</span><small>${esc(item.portfolio_status || "watchlist")} · ${esc(item.role || "")}</small></td><td><ul>${reasons(item).map((reason) => `<li>${esc(reason)}</li>`).join("")}</ul>${eventDetails(item)}</td><td><strong>${esc(item.event_subtype || item.event_type || "—")}</strong><span>${esc(formatTime(item.event_time))}</span></td><td><strong>${money(item.price)}</strong><span class="${pctClass(item.day_change_pct)}">${pct(item.day_change_pct)}</span>${num(item.relative_volume) != null ? `<small>Rel vol ${num(item.relative_volume).toFixed(1)}x</small>` : ""}</td><td>${verificationBadge(item)}<small>${esc(item.source?.type || "unknown")}</small></td><td><div class="p0-actions">${actionButtons(item)}</div></td></tr>`).join("")}</tbody></table></div></section>`;
  }

  function cards(rows) {
    return `<section class="p0-card-list">${rows.map((item) => `<article class="panel-card p0-card p0-card-${esc(String(item.priority || "developing").toLowerCase())}"><header><div><strong>${esc(item.ticker)}</strong><span>${esc(item.name || "")}</span></div>${priorityBadge(item.priority)}</header><div class="p0-card-meta"><span>${esc(item.portfolio_status || "watchlist")}</span><span>${esc(item.event_subtype || item.event_type || "event")}</span><span>${esc(formatTime(item.event_time))}</span></div><ul class="p0-reasons">${reasons(item).map((reason) => `<li>${esc(reason)}</li>`).join("")}</ul><div class="p0-card-market"><span>Price <strong>${money(item.price)}</strong></span><span class="${pctClass(item.day_change_pct)}">${pct(item.day_change_pct)}</span></div><div class="p0-card-source">${verificationBadge(item)}<span>${esc(item.source?.type || "unknown")}</span></div>${eventDetails(item)}<div class="p0-actions">${actionButtons(item)}</div></article>`).join("")}</section>`;
  }

  function render() {
    const page = ensurePage();
    if (state.loading) { page.innerHTML = `<div class="attention-shell p0-shell"><section class="panel-card p0-loading"><h2>Today Attention</h2><p>Building event-first view…</p></section></div>`; return; }
    if (state.error) { page.innerHTML = `<div class="attention-shell p0-shell"><section class="panel-card p0-error"><h2>Today Attention unavailable</h2><p>${esc(state.error)}</p><button type="button" data-p0-retry>Retry</button></section></div>`; return; }
    const rows = items();
    const empty = `<section class="panel-card p0-empty"><h3>${state.data?.coverage_status === "complete" ? "All clear today" : "No material item found — coverage is partial"}</h3><p>${state.data?.coverage_status === "complete" ? "No event met the attention threshold." : "One or more sources are incomplete, so this is not a full all-clear."}</p></section>`;
    page.innerHTML = `<div class="attention-shell p0-shell">${hero()}${sourceStrip()}${filters()}${rows.length ? table(rows) + cards(rows) : empty}</div>`;
    const badge = document.getElementById("attentionNavBadge");
    if (badge) { badge.textContent = String(state.data?.items?.length || 0); badge.hidden = !(state.data?.items?.length); }
  }

  async function load() {
    state.loading = true; state.error = null; render();
    try {
      const response = await fetch(`${DATA_URL}?v=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`attention_today.json HTTP ${response.status}`);
      const payload = await response.json();
      if (!Array.isArray(payload?.items)) throw new Error("attention_today.json has an invalid schema");
      state.data = payload;
    } catch (error) {
      state.error = error?.message || String(error);
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
    window.StockcheckAttentionP0 = { version: "10.0.0", load, render };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
