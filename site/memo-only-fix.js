(() => {
  "use strict";

  function isMemoButton(node) {
    if (!(node instanceof Element)) return false;
    const label = (node.textContent || "").replace(/\s+/g, " ").trim().toLowerCase();
    return label === "memo" || label.startsWith("memo ");
  }

  function memoIsActive() {
    const shell = document.querySelector(".app-shell");
    if (shell?.dataset.view === "memo") return true;
    if (document.body.classList.contains("attention-active")) return true;
    if (document.body.classList.contains("memo-active")) return true;

    return [...document.querySelectorAll("button.active,a.active,[role='tab'].active")]
      .some(isMemoButton);
  }

  function syncMemoIsolation() {
    const active = memoIsActive();
    document.documentElement.classList.toggle("memo-only-view", active);
    document.body.classList.toggle("memo-view-isolated", active);

    const scanner = document.querySelector(".decision-screener, .scanner-panel");
    const workspace = document.querySelector(".workspace");
    const lowerGrid = document.querySelector(".lower-grid");

    for (const element of [scanner, workspace, lowerGrid]) {
      if (!(element instanceof HTMLElement)) continue;
      if (active) {
        element.dataset.memoPreviousDisplay = element.style.display || "";
        element.style.setProperty("display", "none", "important");
        element.setAttribute("aria-hidden", "true");
      } else if (element.hasAttribute("data-memo-previous-display")) {
        const previous = element.dataset.memoPreviousDisplay || "";
        element.style.removeProperty("display");
        if (previous) element.style.display = previous;
        element.removeAttribute("data-memo-previous-display");
        element.removeAttribute("aria-hidden");
      }
    }
  }

  function boot() {
    syncMemoIsolation();

    const observer = new MutationObserver(() => queueMicrotask(syncMemoIsolation));
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["class", "data-view", "aria-selected", "hidden"]
    });

    document.addEventListener("click", () => {
      requestAnimationFrame(syncMemoIsolation);
      setTimeout(syncMemoIsolation, 80);
    }, true);

    window.addEventListener("popstate", syncMemoIsolation);
    window.addEventListener("hashchange", syncMemoIsolation);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
