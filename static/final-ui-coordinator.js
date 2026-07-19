(() => {
  "use strict";

  const VERSION = "10.7.0";
  const desktopQuery = window.matchMedia("(min-width: 1181px)");
  const detailQuery = window.matchMedia("(min-width: 768px)");
  let frame = 0;
  let detailReturnFocus = null;
  const MAX_LOGO_ADAPTER_RETRIES = 12;
  let detailLogoFrame = 0;
  let detailLogoRetry = 0;
  let detailLogoRetryCount = 0;

  function syncStockDetailLogos() {
    cancelAnimationFrame(detailLogoFrame);
    detailLogoFrame = requestAnimationFrame(() => {
      const identities = document.querySelectorAll(
        "body.stock-detail-open #detailPanel .detail-identity, #mobileDetailModal:not([hidden]) .detail-identity"
      );
      if (!identities.length) {
        clearTimeout(detailLogoRetry);
        detailLogoRetryCount = 0;
        return;
      }
      const adapter = window.StockcheckCompanyLogo;
      if (!adapter?.markup) {
        clearTimeout(detailLogoRetry);
        if (detailLogoRetryCount < MAX_LOGO_ADAPTER_RETRIES) {
          detailLogoRetryCount += 1;
          detailLogoRetry = window.setTimeout(syncStockDetailLogos, 250);
        }
        return;
      }
      clearTimeout(detailLogoRetry);
      detailLogoRetryCount = 0;
      identities.forEach((identity) => {
        if (identity.querySelector("[data-logo-shell]")) return;
        const mark = identity.querySelector(".logo-box");
        const ticker = identity.querySelector("h2, strong")?.textContent?.trim();
        if (!mark || !ticker) return;
        const template = document.createElement("template");
        template.innerHTML = adapter.markup(
          { ticker },
          `${mark.className} stock-detail-company-logo`
        );
        const logo = template.content.firstElementChild;
        if (logo) mark.replaceWith(logo);
      });
    });
  }

  function scannerViewIsActive() {
    return !document.body.classList.contains("memo-active")
      && !document.body.classList.contains("attention-active");
  }

  function clearHeight(alertCenter) {
    alertCenter?.style.removeProperty("--final-alert-height");
    alertCenter?.classList.remove("final-height-coordinated");
  }

  function guideMarkup(kind) {
    const guides = {
      memo: {
        kicker: "ใช้หน้านี้เมื่อมี thesis",
        title: "Memo เก็บเหตุผล ราคาเป้าหมาย และเงื่อนไขที่ต้องกลับมาตรวจ",
        text: "เริ่มจาก Add From Screener เพื่อดึงหุ้นที่สนใจเข้ามา แล้วเขียนเหตุผลสั้น ๆ ว่าอะไรจะทำให้เพิ่ม ลด หรือยกเลิกแผน",
        steps: ["เลือกหุ้นจาก Screener", "เขียนเหตุผลและ Target", "กลับมาตรวจเมื่อมี Alert"]
      },
      today: {
        kicker: "อ่านก่อนเริ่มวัน",
        title: "Today รวมเฉพาะหุ้นและเหตุการณ์ที่ควรเปิดดูตอนนี้",
        text: "เริ่มจากรายการความสำคัญสูง ตรวจเหตุผลและแหล่งข้อมูล แล้วค่อยเปิดกราฟหรือ Memo — ไม่ต้องไล่อ่านทุกหุ้นในพอร์ต",
        steps: ["ดู High priority", "ตรวจเหตุผลและแหล่งข้อมูล", "ทำเครื่องหมายเมื่อดูแล้ว"]
      }
    };
    const g = guides[kind];
    return `<div class="page-guide-copy"><span class="page-guide-kicker">${g.kicker}</span><strong>${g.title}</strong><p>${g.text}</p></div><ol class="page-guide-steps">${g.steps.map((step, index) => `<li><span>${index + 1}</span>${step}</li>`).join("")}</ol>`;
  }

  function ensureGuide(page, kind) {
    if (!page || page.querySelector(`.page-guide[data-page-guide="${kind}"]`)) return;
    const guide = document.createElement("section");
    guide.className = "page-guide";
    guide.dataset.pageGuide = kind;
    guide.setAttribute("aria-label", kind === "memo" ? "วิธีใช้หน้า Memo" : "วิธีใช้หน้า Today");
    guide.innerHTML = guideMarkup(kind);
    const mount = page.querySelector(kind === "memo" ? ".memo-shell" : ".pr3-shell, .p0-shell, .attention-shell") || page;
    mount.prepend(guide);
  }

  function ensurePageGuides() {
    ensureGuide(document.querySelector("#memoPage"), "memo");
    document.querySelectorAll("#attentionPage, #attentionPageP0, #attentionPageP3").forEach((page) => ensureGuide(page, "today"));
  }

  function closeStockDetail({ restoreFocus = true } = {}) {
    const panel = document.querySelector("#detailPanel");
    const backdrop = document.querySelector("#desktopDetailBackdrop");
    if (document.body.classList.contains("stock-detail-open")) {
      document.body.classList.remove("stock-detail-open");
    }
    if (panel) {
      panel.hidden = true;
      panel.setAttribute("aria-hidden", "true");
    }
    if (backdrop) backdrop.hidden = true;
    if (restoreFocus && detailReturnFocus instanceof HTMLElement) detailReturnFocus.focus({ preventScroll: true });
    detailReturnFocus = null;
    clearTimeout(detailLogoRetry);
    detailLogoRetryCount = 0;
  }

  function openStockDetail(trigger) {
    if (!detailQuery.matches || !scannerViewIsActive()) return;
    const panel = document.querySelector("#detailPanel");
    const backdrop = document.querySelector("#desktopDetailBackdrop");
    if (!panel || !backdrop) return;
    detailReturnFocus = trigger instanceof HTMLElement ? trigger : document.activeElement;
    panel.hidden = false;
    panel.setAttribute("aria-hidden", "false");
    backdrop.hidden = false;
    document.body.classList.add("stock-detail-open");
    detailLogoRetryCount = 0;
    syncStockDetailLogos();
    requestAnimationFrame(() => panel.querySelector("[data-close-stock-detail]")?.focus());
  }

  function bindStockDetail() {
    // Capture the stock target before app.js rerenders the selected row in its
    // body-level click handler. Once that row is detached, a later delegated
    // selector can no longer prove that it came from the screener.
    document.addEventListener("click", (event) => {
      const close = event.target.closest("[data-close-stock-detail]");
      if (close) {
        event.preventDefault();
        closeStockDetail();
        return;
      }
      const stock = event.target.closest(".decision-screener [data-select], #watchlistPanel [data-select]");
      if (stock && detailQuery.matches) requestAnimationFrame(() => openStockDetail(stock));
    }, true);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && document.body.classList.contains("stock-detail-open")) closeStockDetail();
    });
    detailQuery.addEventListener?.("change", () => {
      if (!detailQuery.matches) closeStockDetail({ restoreFocus: false });
    });
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

      const nextHeight = `${railHeight}px`;
      if (alertCenter.style.getPropertyValue("--final-alert-height") !== nextHeight) {
        alertCenter.style.setProperty("--final-alert-height", nextHeight);
      }
      alertCenter.classList.add("final-height-coordinated");
    });
  }

  function boot() {
    document.documentElement.dataset.stockDetailDialog = VERSION;
    const resizeObserver = new ResizeObserver(syncAlertHeight);
    [
      "#watchlistPanel",
      "#watchlistPanel .watchlist-card",
      "#watchlistPanel .filter-card"
    ].forEach((selector) => {
      const element = document.querySelector(selector);
      if (element) resizeObserver.observe(element);
    });

    const viewObserver = new MutationObserver(() => {
      syncAlertHeight();
      if (!scannerViewIsActive()) closeStockDetail({ restoreFocus: false });
    });
    viewObserver.observe(document.body, {
      attributes: true,
      attributeFilter: ["class"]
    });

    const guideObserver = new MutationObserver(ensurePageGuides);
    guideObserver.observe(document.body, {
      childList: true,
      subtree: true
    });

    desktopQuery.addEventListener?.("change", syncAlertHeight);
    window.addEventListener("resize", syncAlertHeight, { passive: true });
    window.addEventListener("pageshow", syncAlertHeight);
    document.addEventListener("click", () => requestAnimationFrame(syncAlertHeight), true);

    const detailObserver = new MutationObserver(syncStockDetailLogos);
    ["#detailCard", "#mobileDetailBody"].forEach((selector) => {
      const element = document.querySelector(selector);
      if (element) detailObserver.observe(element, { childList: true, subtree: true });
    });
    document.addEventListener("click", syncStockDetailLogos, true);

    bindStockDetail();
    ensurePageGuides();
    closeStockDetail({ restoreFocus: false });
    syncAlertHeight();
  }

  window.StockRadarDetailDialog = Object.freeze({
    version: VERSION,
    open: openStockDetail,
    close: closeStockDetail
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();

