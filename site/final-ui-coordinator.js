(() => {
  "use strict";

  const DESKTOP_MIN = 1181;
  const SELECTORS = {
    workspace: ".workspace",
    leftRail: "#watchlistPanel",
    alertCenter: "#alertCenter",
    scanner: ".decision-screener, .scanner-panel",
    memoCandidates: [
      "#memoPage",
      "#memoView",
      ".memo-page",
      ".memo-view",
      ".attention-page",
      "[data-page='memo']",
      "[data-view='memo']"
    ]
  };

  let frame = 0;

  function isDesktop() {
    return window.innerWidth >= DESKTOP_MIN;
  }

  function matchAlertHeight() {
    const leftRail = document.querySelector(SELECTORS.leftRail);
    const alertCenter = document.querySelector(SELECTORS.alertCenter);
    const workspace = document.querySelector(SELECTORS.workspace);
    if (!leftRail || !alertCenter || !workspace) return;

    if (!isDesktop()) {
      alertCenter.style.removeProperty("--final-alert-height");
      alertCenter.classList.remove("final-height-coordinated");
      return;
    }

    const railHeight = Math.ceil(leftRail.getBoundingClientRect().height);
    if (railHeight > 0) {
      alertCenter.style.setProperty("--final-alert-height", `${railHeight}px`);
      alertCenter.classList.add("final-height-coordinated");
    }
  }

  function isVisible(element) {
    if (!(element instanceof HTMLElement)) return false;
    const style = getComputedStyle(element);
    return style.display !== "none" && style.visibility !== "hidden" && !element.hidden;
  }

  function findMemoView() {
    for (const selector of SELECTORS.memoCandidates) {
      const elements = [...document.querySelectorAll(selector)];
      const visible = elements.find(isVisible);
      if (visible) return visible;
    }

    const headings = [...document.querySelectorAll("h1,h2,h3,[role='heading']")];
    const heading = headings.find((node) => /^memo\b/i.test((node.textContent || "").trim()));
    return heading?.closest("section,main,article,div") || null;
  }

  function memoModeActive() {
    const bodyClass = document.body.className.toLowerCase();
    const shellView = (document.querySelector(".app-shell")?.dataset.view || "").toLowerCase();
    const activeNav = [...document.querySelectorAll("button,a,[role='tab']")]
      .find((node) => node.classList.contains("active") && /^memo\b/i.test((node.textContent || "").trim()));
    return bodyClass.includes("memo") || shellView === "memo" || Boolean(activeNav);
  }

  function placeMemoBeforeScanner() {
    if (!memoModeActive()) return;

    const memo = findMemoView();
    const scanner = document.querySelector(SELECTORS.scanner);
    if (!memo || !scanner || memo === scanner || memo.contains(scanner)) return;

    const memoTop = memo.getBoundingClientRect().top;
    const scannerTop = scanner.getBoundingClientRect().top;
    if (memoTop <= scannerTop && memo.nextElementSibling === scanner) return;

    const commonParent =
      memo.parentElement === scanner.parentElement
        ? memo.parentElement
        : scanner.parentElement;

    if (!commonParent) return;

    if (memo.parentElement !== commonParent) {
      commonParent.insertBefore(memo, scanner);
    } else {
      commonParent.insertBefore(memo, scanner);
    }

    memo.classList.add("final-memo-primary");
    scanner.classList.add("final-scanner-secondary");
  }

  function coordinate() {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      matchAlertHeight();
      placeMemoBeforeScanner();
    });
  }

  function boot() {
    coordinate();

    const resizeObserver = new ResizeObserver(coordinate);
    const leftRail = document.querySelector(SELECTORS.leftRail);
    const workspace = document.querySelector(SELECTORS.workspace);
    if (leftRail) resizeObserver.observe(leftRail);
    if (workspace) resizeObserver.observe(workspace);

    const mutationObserver = new MutationObserver(coordinate);
    mutationObserver.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["class", "hidden", "data-view", "aria-selected"]
    });

    window.addEventListener("resize", coordinate, { passive: true });
    document.addEventListener("click", coordinate, true);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
