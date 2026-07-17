(() => {
  "use strict";

  const desktopQuery = window.matchMedia("(min-width: 1181px)");
  let frame = 0;

  function scannerViewIsActive() {
    return !document.body.classList.contains("memo-active")
      && !document.body.classList.contains("attention-active");
  }

  function clearHeight(alertCenter) {
    alertCenter?.style.removeProperty("--final-alert-height");
    alertCenter?.classList.remove("final-height-coordinated");
  }

  function syncAlertHeight() {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      const alertCenter = document.querySelector("#alertCenter");
      const leftRail = document.querySelector("#watchlistPanel");

      if (!alertCenter || !leftRail || !desktopQuery.matches || !scannerViewIsActive()) {
        clearHeight(alertCenter);
        return;
      }

      const railHeight = Math.ceil(leftRail.getBoundingClientRect().height);
      if (railHeight <= 0) {
        clearHeight(alertCenter);
        return;
      }

      alertCenter.style.setProperty("--final-alert-height", `${railHeight}px`);
      alertCenter.classList.add("final-height-coordinated");
    });
  }

  function boot() {
    const resizeObserver = new ResizeObserver(syncAlertHeight);
    [
      "#watchlistPanel",
      "#watchlistPanel .watchlist-card",
      "#watchlistPanel .filter-card",
      ".workspace"
    ].forEach((selector) => {
      const element = document.querySelector(selector);
      if (element) resizeObserver.observe(element);
    });

    const viewObserver = new MutationObserver(syncAlertHeight);
    viewObserver.observe(document.body, {
      attributes: true,
      attributeFilter: ["class"]
    });

    desktopQuery.addEventListener?.("change", syncAlertHeight);
    window.addEventListener("resize", syncAlertHeight, { passive: true });
    window.addEventListener("pageshow", syncAlertHeight);
    document.addEventListener("click", () => requestAnimationFrame(syncAlertHeight), true);

    syncAlertHeight();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
