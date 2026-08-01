(() => {
  "use strict";

  const VERSION = "10.8.0";
  const desktopQuery = window.matchMedia("(min-width: 1181px)");
  const detailQuery = window.matchMedia("(min-width: 768px)");
  let frame = 0;
  let detailReturnFocus = null;
  const MAX_LOGO_ADAPTER_RETRIES = 12;
  let detailLogoFrame = 0;
  let detailLogoRetry = 0;
  let detailLogoRetryCount = 0;
  let drawdownFrame = 0;

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

  function selectedStock() {
    try {
      return typeof window.getSelected === "function" ? window.getSelected() : null;
    } catch (_) {
      return null;
    }
  }

  function numberValue(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function drawdownData(stock) {
    const raw = Array.isArray(stock?.quote?.series) ? stock.quote.series : [];
    const rows = raw
      .map((row) => ({
        date: row?.date,
        close: numberValue(row?.adjClose ?? row?.adjustedClose ?? row?.close)
      }))
      .filter((row) => row.date && row.close !== null && row.close > 0)
      .slice(-756);

    if (rows.length < 2) return null;

    let runningPeak = -Infinity;
    let maxDrawdown = 0;
    let peakDate = rows[0].date;
    let troughDate = rows[0].date;
    const series = rows.map((row) => {
      if (row.close > runningPeak) {
        runningPeak = row.close;
        peakDate = row.date;
      }
      const drawdown = (row.close / runningPeak - 1) * 100;
      if (drawdown < maxDrawdown) {
        maxDrawdown = drawdown;
        troughDate = row.date;
      }
      return { date: row.date, value: drawdown };
    });

    return {
      series,
      current: series.at(-1)?.value ?? 0,
      maximum: maxDrawdown,
      peakDate,
      troughDate,
      asOf: series.at(-1)?.date
    };
  }

  function dateLabel(value) {
    if (!value) return "—";
    const date = new Date(String(value));
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }

  function drawdownMarkup(stock) {
    const data = drawdownData(stock);
    if (!data) {
      return `<section class="chart-panel drawdown-panel" data-drawdown-panel><div class="chart-title"><h3>Drawdown</h3><span>Historical price series unavailable</span></div><div class="chart-empty">ยังไม่มีข้อมูลราคาย้อนหลังเพียงพอสำหรับคำนวณ Drawdown</div></section>`;
    }

    const width = 320;
    const height = 150;
    const left = 12;
    const right = 308;
    const top = 10;
    const bottom = 132;
    const floor = Math.min(-10, Math.floor(data.maximum / 10) * 10);
    const span = Math.abs(floor) || 10;
    const step = data.series.length > 1 ? (right - left) / (data.series.length - 1) : 0;
    const y = (value) => top + (Math.abs(value) / span) * (bottom - top);
    const points = data.series.map((point, index) => [left + index * step, y(point.value)]);
    const path = points.map((point, index) => `${index ? "L" : "M"}${point[0].toFixed(2)},${point[1].toFixed(2)}`).join(" ");
    const area = `${path} L${right},${top} L${left},${top} Z`;
    const middle = floor / 2;
    const first = data.series[0]?.date;
    const mid = data.series[Math.floor(data.series.length / 2)]?.date;
    const last = data.series.at(-1)?.date;

    return `<section class="chart-panel drawdown-panel" data-drawdown-panel>
      <div class="chart-title drawdown-title">
        <h3>Drawdown</h3>
        <span>Current: <strong class="drawdown-current">${data.current.toFixed(1)}%</strong> · Max: ${data.maximum.toFixed(1)}%</span>
      </div>
      <div class="drawdown-chart-wrap">
        <svg class="fake-chart drawdown-chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Drawdown chart from zero percent to ${floor} percent">
          <defs><linearGradient id="drawdownFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#f85149" stop-opacity="0.08"/><stop offset="100%" stop-color="#f85149" stop-opacity="0.22"/></linearGradient></defs>
          <line x1="${left}" y1="${top}" x2="${right}" y2="${top}" class="drawdown-grid"/>
          <line x1="${left}" y1="${y(middle)}" x2="${right}" y2="${y(middle)}" class="drawdown-grid"/>
          <line x1="${left}" y1="${bottom}" x2="${right}" y2="${bottom}" class="drawdown-grid"/>
          <path d="${area}" fill="url(#drawdownFill)"/>
          <path d="${path}" class="drawdown-line"/>
        </svg>
        <div class="drawdown-y-axis" aria-hidden="true"><span>0%</span><span>${middle.toFixed(0)}%</span><span>${floor.toFixed(0)}%</span></div>
      </div>
      <div class="chart-axis"><span>${dateLabel(first)}</span><span>${dateLabel(mid)}</span><span>${dateLabel(last)}</span></div>
      <div class="drawdown-meta"><span>Peak ${dateLabel(data.peakDate)}</span><span>Trough ${dateLabel(data.troughDate)}</span><span>As of ${dateLabel(data.asOf)}</span></div>
    </section>`;
  }

  function syncDrawdownCharts() {
    cancelAnimationFrame(drawdownFrame);
    drawdownFrame = requestAnimationFrame(() => {
      const stock = selectedStock();
      document.querySelectorAll("#detailCard .chart-stack, #mobileDetailBody .chart-stack").forEach((stack) => {
        if (stack.querySelector("[data-drawdown-panel]")) return;
        stack.insertAdjacentHTML("beforeend", drawdownMarkup(stock));
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
    syncDrawdownCharts();
    requestAnimationFrame(() => panel.querySelector("[data-close-stock-detail]")?.focus());
  }

  function bindStockDetail() {
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
    document.documentElement.dataset.drawdownChart = VERSION;
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

    const detailObserver = new MutationObserver(() => {
      syncStockDetailLogos();
      syncDrawdownCharts();
    });
    ["#detailCard", "#mobileDetailBody"].forEach((selector) => {
      const element = document.querySelector(selector);
      if (element) detailObserver.observe(element, { childList: true, subtree: true });
    });
    document.addEventListener("click", () => {
      syncStockDetailLogos();
      syncDrawdownCharts();
    }, true);

    bindStockDetail();
    ensurePageGuides();
    closeStockDetail({ restoreFocus: false });
    syncAlertHeight();
    syncDrawdownCharts();
  }

  window.StockRadarDetailDialog = Object.freeze({
    version: VERSION,
    open: openStockDetail,
    close: closeStockDetail
  });

  window.StockRadarDrawdown = Object.freeze({
    version: VERSION,
    calculate: drawdownData,
    refresh: syncDrawdownCharts
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
