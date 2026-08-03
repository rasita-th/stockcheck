(() => {
  "use strict";

  const VIEW_KEY = "stockTimingRadar.appView.v55";
  const ATTENTION_DATA_URL = "data/attention_today.json";
  const ATTENTION_CACHE_WINDOW_MS = 15 * 1000;
  const DRAWDOWN_VERSION = "10.9.0";
  const SCANNER_GUARD_VERSION = "1.0.0";

  function installAttentionDataStore() {
    if (window.StockcheckAttentionDataStore?.load) return window.StockcheckAttentionDataStore;
    let requestPromise = null;
    let loadedAt = 0;
    const clone = (payload) => typeof structuredClone === "function"
      ? structuredClone(payload)
      : JSON.parse(JSON.stringify(payload));
    const load = async () => {
      const fresh = requestPromise && Date.now() - loadedAt < ATTENTION_CACHE_WINDOW_MS;
      if (!fresh) {
        loadedAt = Date.now();
        requestPromise = fetch(`${ATTENTION_DATA_URL}?v=${loadedAt}`, { cache: "no-store" })
          .then((response) => {
            if (!response.ok) throw new Error(`attention_today.json HTTP ${response.status}`);
            return response.json();
          })
          .then((payload) => {
            if (!payload || typeof payload !== "object") throw new Error("attention_today.json is not an object");
            return payload;
          })
          .catch((error) => {
            requestPromise = null;
            loadedAt = 0;
            throw error;
          });
      }
      return clone(await requestPromise);
    };
    window.StockcheckAttentionDataStore = Object.freeze({ version: "1.0.0", load });
    return window.StockcheckAttentionDataStore;
  }

  function preferredView(explicitView = "") {
    if (explicitView) return explicitView;
    try {
      return localStorage.getItem(VIEW_KEY) || "";
    } catch {
      return "";
    }
  }

  function enforceExclusiveView(explicitView = "") {
    const body = document.body;
    if (!body) return;
    const memoActive = body.classList.contains("memo-active");
    const attentionActive = body.classList.contains("attention-active");
    if (!memoActive || !attentionActive) return;
    const activeControl = document.querySelector("[data-app-view].active");
    const view = preferredView(explicitView || activeControl?.dataset.appView || "");
    if (view === "attention") body.classList.remove("memo-active");
    else body.classList.remove("attention-active");
  }

  function loadScript(src, datasetKey, onload) {
    if (document.querySelector(`script[data-${datasetKey}]`)) {
      if (onload) onload();
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.async = false;
    script.dataset[datasetKey] = "true";
    if (onload) script.addEventListener("load", onload, { once: true });
    script.addEventListener("error", () => console.error(`Could not load ${src}`), { once: true });
    document.head.appendChild(script);
  }

  function loadStylesheet(href, datasetKey) {
    if (document.querySelector(`link[data-${datasetKey}]`)) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = href;
    link.dataset[datasetKey] = "true";
    link.addEventListener("error", () => console.error(`Could not load ${href}`), { once: true });
    document.head.appendChild(link);
  }

  function loadScannerGuard() {
    loadScript(`scanner-loading-guard.js?v=${SCANNER_GUARD_VERSION}`, "scannerLoadingGuardLoader");
  }

  function loadDrawdownScreener() {
    loadStylesheet(`drawdown-screener-v10-9.css?v=${DRAWDOWN_VERSION}`, "drawdownScreenerStyle");
    loadScript(`drawdown-screener-v10-9.js?v=${DRAWDOWN_VERSION}`, "drawdownScreenerLoader");
  }

  function loadEarningsRadar() {
    loadScript("earnings-radar-pr4.js?v=10.7.1", "earningsRadarPr4Loader");
  }

  function loadAttentionP4() {
    loadScript("attention-pr4.js?v=10.7.1", "attentionPr4Loader", loadEarningsRadar);
  }

  function loadAttentionP3() {
    loadScript("attention-pr3.js?v=10.3.0", "attentionPr3Loader", loadAttentionP4);
  }

  function loadAttentionP0() {
    if (document.querySelector("script[data-attention-p0-loader]")) {
      loadAttentionP3();
      return;
    }
    const script = document.createElement("script");
    script.src = "attention-p0.js?v=10.2.0";
    script.async = false;
    script.dataset.attentionP0Loader = "true";
    script.addEventListener("load", loadAttentionP3, { once: true });
    script.addEventListener("error", () => {
      console.error("Could not load attention-p0.js");
      loadAttentionP3();
    }, { once: true });
    document.head.appendChild(script);
  }

  function boot() {
    enforceExclusiveView();
    installAttentionDataStore();
    loadScannerGuard();
    loadDrawdownScreener();
    loadAttentionP0();
    document.addEventListener("click", (event) => {
      const control = event.target.closest?.("[data-app-view]");
      if (!control) return;
      const view = control.dataset.appView || "";
      if (view === "memo") document.body.classList.remove("attention-active");
      else if (view === "attention") document.body.classList.remove("memo-active");
      requestAnimationFrame(() => enforceExclusiveView(view));
    }, true);
    const classObserver = new MutationObserver(() => enforceExclusiveView());
    classObserver.observe(document.body, { attributes: true, attributeFilter: ["class"] });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
