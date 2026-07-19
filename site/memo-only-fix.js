(() => {
  "use strict";

  const VIEW_KEY = "stockTimingRadar.appView.v55";

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

  function loadEarningsRadar() {
    loadScript("earnings-radar-pr4.js?v=10.5.0", "earningsRadarPr4Loader");
  }

  function loadAttentionP4() {
    loadScript("attention-pr4.js?v=10.4.0", "attentionPr4Loader", loadEarningsRadar);
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
