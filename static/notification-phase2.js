(() => {
  "use strict";

  const STORAGE_KEY = "stockRadar.notificationPhase2.v1";
  const LIST_SELECTOR = "#alertList";
  const CARD_SELECTOR = ":scope > *";
  const ENHANCED_ATTR = "data-phase2-enhanced";

  const state = loadState();
  let activePhase2Filter = "all";

  function loadState() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
      return {
        read: parsed.read && typeof parsed.read === "object" ? parsed.read : {},
        dismissed: parsed.dismissed && typeof parsed.dismissed === "object" ? parsed.dismissed : {}
      };
    } catch {
      return { read: {}, dismissed: {} };
    }
  }

  function saveState() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // Local storage may be unavailable; UI still works for the current session.
    }
  }

  function text(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function hashString(value) {
    let hash = 2166136261;
    for (let i = 0; i < value.length; i += 1) {
      hash ^= value.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(36);
  }

  function cardKey(card) {
    const ticker = detectTicker(card);
    const signature = text(card.textContent).slice(0, 260);
    return `${ticker || "GEN"}:${hashString(signature)}`;
  }

  function detectTicker(card) {
    const explicit =
      card.dataset.ticker ||
      card.getAttribute("data-symbol") ||
      card.querySelector("[data-ticker]")?.dataset.ticker ||
      card.querySelector("[data-symbol]")?.dataset.symbol;
    if (explicit) return text(explicit).toUpperCase();

    const body = text(card.textContent);
    const candidates = body.match(/\b[A-Z]{1,6}(?:\.[A-Z]{1,3})?\b/g) || [];
    const blocked = new Set([
      "HOT", "RSI", "EMA", "MACD", "MEMO", "RISK", "NEAR", "HIGH", "LOW",
      "ACTION", "ACTIONABLE", "PRIORITY", "NEW", "NOW", "ALL"
    ]);
    return candidates.find((candidate) => !blocked.has(candidate)) || "";
  }

  function classifyPriority(card) {
    const body = text(card.textContent).toUpperCase();
    if (/\b(CRITICAL|URGENT|BREAKOUT|BREAKDOWN|RISK|STOP|INVALID)\b/.test(body)) {
      return { level: "critical", label: "Critical" };
    }
    if (/\b(HOT|ACTIONABLE|BUY|SELL|CROSS|ALERT)\b/.test(body)) {
      return { level: "high", label: "High" };
    }
    if (/\b(NEAR|WATCH|MEMO|UPDATE)\b/.test(body)) {
      return { level: "medium", label: "Medium" };
    }
    return { level: "normal", label: "Normal" };
  }

  function freshnessLabel(card) {
    const explicit =
      card.querySelector("time")?.getAttribute("datetime") ||
      card.dataset.timestamp ||
      card.getAttribute("data-created-at");

    if (!explicit) return "Latest scan";

    const timestamp = Date.parse(explicit);
    if (!Number.isFinite(timestamp)) return "Latest scan";

    const minutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60000));
    if (minutes < 1) return "Now";
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  }

  function createButton(label, action, className = "") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `phase2-alert-action ${className}`.trim();
    button.dataset.phase2Action = action;
    button.textContent = label;
    return button;
  }

  function enhanceCard(card) {
    if (!(card instanceof HTMLElement)) return;
    if (card.hasAttribute(ENHANCED_ATTR)) return;
    if (card.matches(".phase2-empty-state")) return;

    const key = cardKey(card);
    const ticker = detectTicker(card);
    const priority = classifyPriority(card);

    card.setAttribute(ENHANCED_ATTR, "true");
    card.dataset.phase2Key = key;
    card.dataset.phase2Priority = priority.level;
    if (ticker) card.dataset.phase2Ticker = ticker;

    const meta = document.createElement("div");
    meta.className = "phase2-alert-meta";

    const priorityBadge = document.createElement("span");
    priorityBadge.className = `phase2-priority phase2-priority-${priority.level}`;
    priorityBadge.textContent = priority.label;

    const freshness = document.createElement("span");
    freshness.className = "phase2-freshness";
    freshness.textContent = freshnessLabel(card);

    const readState = document.createElement("span");
    readState.className = "phase2-read-state";

    meta.append(priorityBadge, freshness, readState);

    const actions = document.createElement("div");
    actions.className = "phase2-alert-actions";

    const readButton = createButton("", "toggle-read", "phase2-read-button");
    const scannerButton = createButton(
      ticker ? `Open ${ticker}` : "Open Scanner",
      "open-scanner",
      "phase2-open-button"
    );
    const dismissButton = createButton("Dismiss", "dismiss", "phase2-dismiss-button");

    actions.append(readButton, scannerButton, dismissButton);
    card.append(meta, actions);

    updateCardState(card);
  }

  function updateCardState(card) {
    const key = card.dataset.phase2Key;
    const isRead = Boolean(state.read[key]);
    const isDismissed = Boolean(state.dismissed[key]);

    card.classList.toggle("phase2-is-read", isRead);
    card.classList.toggle("phase2-is-unread", !isRead);
    card.hidden = isDismissed;

    const readState = card.querySelector(".phase2-read-state");
    if (readState) readState.textContent = isRead ? "Read" : "Unread";

    const readButton = card.querySelector(".phase2-read-button");
    if (readButton) readButton.textContent = isRead ? "Mark unread" : "Mark read";
  }

  function applyFilter() {
    const list = document.querySelector(LIST_SELECTOR);
    if (!list) return;

    for (const card of list.querySelectorAll(CARD_SELECTOR)) {
      if (!(card instanceof HTMLElement) || !card.dataset.phase2Key) continue;

      const dismissed = Boolean(state.dismissed[card.dataset.phase2Key]);
      const read = Boolean(state.read[card.dataset.phase2Key]);
      const priority = card.dataset.phase2Priority;

      let visible = !dismissed;
      if (activePhase2Filter === "unread") visible = visible && !read;
      if (activePhase2Filter === "priority") {
        visible = visible && (priority === "critical" || priority === "high");
      }
      card.hidden = !visible;
    }

    updateToolbarCounts();
  }

  function updateToolbarCounts() {
    const list = document.querySelector(LIST_SELECTOR);
    if (!list) return;

    const cards = [...list.querySelectorAll(CARD_SELECTOR)].filter(
      (card) => card instanceof HTMLElement && card.dataset.phase2Key
    );
    const unread = cards.filter(
      (card) => !state.dismissed[card.dataset.phase2Key] && !state.read[card.dataset.phase2Key]
    ).length;
    const priority = cards.filter(
      (card) =>
        !state.dismissed[card.dataset.phase2Key] &&
        ["critical", "high"].includes(card.dataset.phase2Priority)
    ).length;

    const unreadButton = document.querySelector('[data-phase2-filter="unread"]');
    const priorityButton = document.querySelector('[data-phase2-filter="priority"]');
    if (unreadButton) unreadButton.textContent = `Unread ${unread}`;
    if (priorityButton) priorityButton.textContent = `Priority ${priority}`;

    const center = document.querySelector("#alertCenter");
    if (center) center.dataset.phase2Unread = String(unread);
  }

  function ensureToolbar() {
    const center = document.querySelector("#alertCenter");
    const existingFilters = document.querySelector("#alertFilterRow");
    if (!center || !existingFilters || center.querySelector(".phase2-toolbar")) return;

    const toolbar = document.createElement("div");
    toolbar.className = "phase2-toolbar";
    toolbar.setAttribute("aria-label", "Notification status filters");

    const all = createButton("All status", "filter");
    all.dataset.phase2Filter = "all";
    all.classList.add("active");

    const unread = createButton("Unread 0", "filter");
    unread.dataset.phase2Filter = "unread";

    const priority = createButton("Priority 0", "filter");
    priority.dataset.phase2Filter = "priority";

    const markAll = createButton("Mark all read", "mark-all-read", "phase2-mark-all");

    toolbar.append(all, unread, priority, markAll);
    existingFilters.insertAdjacentElement("afterend", toolbar);
  }

  function openScanner(card) {
    const ticker = card.dataset.phase2Ticker || "";
    const search = document.querySelector("#symbolSearch");
    if (ticker && search) {
      search.value = ticker;
      search.dispatchEvent(new Event("input", { bubbles: true }));
      search.dispatchEvent(new Event("change", { bubbles: true }));
    }

    const scanner =
      document.querySelector(".decision-screener") ||
      document.querySelector(".scanner-panel") ||
      document.querySelector("#technicalTable");

    scanner?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function markAllRead() {
    const list = document.querySelector(LIST_SELECTOR);
    if (!list) return;
    for (const card of list.querySelectorAll(CARD_SELECTOR)) {
      if (!(card instanceof HTMLElement) || !card.dataset.phase2Key) continue;
      state.read[card.dataset.phase2Key] = Date.now();
      updateCardState(card);
    }
    saveState();
    applyFilter();
  }

  function handleClick(event) {
    const button = event.target.closest("[data-phase2-action]");
    if (!button) return;

    const action = button.dataset.phase2Action;

    if (action === "filter") {
      activePhase2Filter = button.dataset.phase2Filter || "all";
      for (const sibling of button.parentElement.querySelectorAll("[data-phase2-filter]")) {
        sibling.classList.toggle("active", sibling === button);
      }
      applyFilter();
      return;
    }

    if (action === "mark-all-read") {
      markAllRead();
      return;
    }

    const card = button.closest(`[${ENHANCED_ATTR}]`);
    if (!card) return;

    const key = card.dataset.phase2Key;
    if (action === "toggle-read") {
      if (state.read[key]) delete state.read[key];
      else state.read[key] = Date.now();
      saveState();
      updateCardState(card);
      applyFilter();
      return;
    }

    if (action === "dismiss") {
      state.dismissed[key] = Date.now();
      saveState();
      applyFilter();
      return;
    }

    if (action === "open-scanner") {
      state.read[key] = Date.now();
      saveState();
      updateCardState(card);
      openScanner(card);
    }
  }

  function enhanceAll() {
    ensureToolbar();
    const list = document.querySelector(LIST_SELECTOR);
    if (!list) return;
    for (const card of list.querySelectorAll(CARD_SELECTOR)) enhanceCard(card);
    applyFilter();
  }

  function observe() {
    const list = document.querySelector(LIST_SELECTOR);
    if (!list) return false;

    const observer = new MutationObserver(() => {
      queueMicrotask(enhanceAll);
    });
    observer.observe(list, { childList: true, subtree: false });
    return true;
  }

  function boot() {
    document.addEventListener("click", handleClick);
    enhanceAll();

    if (!observe()) {
      const retry = new MutationObserver(() => {
        if (document.querySelector(LIST_SELECTOR)) {
          enhanceAll();
          observe();
          retry.disconnect();
        }
      });
      retry.observe(document.documentElement, { childList: true, subtree: true });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
