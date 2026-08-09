(() => {
  "use strict";

  const VERSION = "10.8.2";
  const desktopQuery = window.matchMedia("(min-width: 1181px)");
  const detailQuery = window.matchMedia("(min-width: 768px)");
  const DRAWER_TRANSITION_MS = 240;
  let frame = 0;
  let detailReturnFocus = null;
  let detailCloseTimer = 0;
  const MAX_LOGO_ADAPTER_RETRIES = 12;
  let detailLogoFrame = 0;
  let detailLogoRetry = 0;
  let detailLogoRetryCount = 0;
  let drawdownFrame = 0;
  let decisionSurfaceFrame = 0;

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

  function htmlEscape(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function moneyLabel(value) {
    const n = numberValue(value);
    if (n === null) return "—";
    const digits = Math.abs(n) < 1 ? 4 : 2;
    return `$${n.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
  }

  function numberLabel(value, digits = 1) {
    const n = numberValue(value);
    if (n === null) return "—";
    return n.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  function signedPctLabel(value) {
    const n = numberValue(value);
    if (n === null) return "—";
    return `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
  }

  function rangePositionPct(price, low, high) {
    const p = numberValue(price);
    const lo = numberValue(low);
    const hi = numberValue(high);
    if (p === null || lo === null || hi === null || hi <= lo) return null;
    return Math.max(0, Math.min(100, ((p - lo) / (hi - lo)) * 100));
  }

  function decisionSurfaceMarkup(stock) {
    const price = numberValue(stock?.price);
    const dayPct = numberValue(stock?.dayPct);
    const score = numberValue(stock?.score);
    const scorePct = score === null ? 0 : Math.max(0, Math.min(100, score));
    const low52 = numberValue(stock?.low52);
    const high52 = numberValue(stock?.high52);
    const position = rangePositionPct(price, low52, high52);
    const signal = String(stock?.signal || "Signal unavailable").trim();
    const pctClass = dayPct === null ? "neutral" : dayPct > 0 ? "positive" : dayPct < 0 ? "negative" : "neutral";
    const markerStyle = position === null ? "" : ` style="--range-position:${position.toFixed(2)}%"`;
    const volumeRatio = numberValue(stock?.vol20);

    return `<section class="stock-detail-decision-grid" data-detail-decision-surface>
      <article class="detail-decision-cell detail-decision-price">
        <span class="detail-decision-label">Current price</span>
        <strong class="detail-decision-price-value">${moneyLabel(price)}</strong>
        <span class="detail-decision-change ${pctClass}">${signedPctLabel(dayPct)}</span>
        <small>Canonical market snapshot</small>
      </article>
      <article class="detail-decision-cell detail-decision-context">
        <span class="detail-decision-label">Signal</span>
        <strong class="detail-signal-text">${htmlEscape(signal)}</strong>
        <div class="detail-range-block"${markerStyle}>
          <div class="detail-range-heading"><span>52-week position</span><strong>${position === null ? "—" : `${position.toFixed(0)}%`}</strong></div>
          <div class="detail-range-track" aria-label="52-week position">
            <span class="detail-range-marker" aria-hidden="true"></span>
          </div>
          <div class="detail-range-labels"><span>${moneyLabel(low52)}</span><span>${moneyLabel(high52)}</span></div>
        </div>
      </article>
      <article class="detail-decision-cell detail-score-cell">
        <span class="detail-decision-label">Technical score</span>
        <div class="detail-score-dial" style="--score-pct:${scorePct.toFixed(0)}" role="img" aria-label="Technical score ${score === null ? "unavailable" : `${score.toFixed(0)} out of 100`}">
          <div><strong>${score === null ? "—" : score.toFixed(0)}</strong><span>/100</span></div>
        </div>
        <small>Same score as Scanner</small>
      </article>
      <article class="detail-decision-cell detail-decision-metrics">
        <span class="detail-decision-label">Key technicals</span>
        <dl>
          <div><dt>RSI (14)</dt><dd>${numberLabel(stock?.rsi, 1)}</dd></div>
          <div><dt>MACD</dt><dd>${numberLabel(stock?.macd, 3)}</dd></div>
          <div><dt>Vol / 20D</dt><dd>${volumeRatio === null ? "—" : `${numberLabel(volumeRatio, 2)}x`}</dd></div>
          <div><dt>52W high</dt><dd>${moneyLabel(high52)}</dd></div>
        </dl>
      </article>
    </section>`;
  }

  function ensureMobileDetailHandle() {
    const modal = document.querySelector("#mobileDetailModal");
    if (!modal || modal.querySelector(".mobile-detail-drag-handle")) return;
    const handle = document.createElement("div");
    handle.className = "mobile-detail-drag-handle";
    handle.setAttribute("aria-hidden", "true");
    modal.prepend(handle);
  }

  function syncStockDetailDecisionSurface() {
    cancelAnimationFrame(decisionSurfaceFrame);
    decisionSurfaceFrame = requestAnimationFrame(() => {
      const stock = selectedStock();
      if (!stock) return;
      ensureMobileDetailHandle();
      document.querySelectorAll("#detailCard .detail-header, #mobileDetailBody .detail-header").forEach((header) => {
        header.classList.add("drawer-detail-header");
        if (header.querySelector("[data-detail-decision-surface]")) return;
        const identity = header.querySelector(".detail-identity");
        if (!identity) return;
        const template = document.createElement("template");
        template.innerHTML = decisionSurfaceMarkup(stock).trim();
        const surface = template.content.firstElementChild;
        if (surface) identity.insertAdjacentElement("afterend", surface);
      });
    });
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

  function finalizeStockDetailClose(panel, backdrop) {
    if (panel) panel.hidden = true;
    if (backdrop) backdrop.hidden = true;
  }

  function closeStockDetail({ restoreFocus = true } = {}) {
    const panel = document.querySelector("#detailPanel");
    const backdrop = document.querySelector("#desktopDetailBackdrop");
    const wasOpen = document.body.classList.contains("stock-detail-open");
    clearTimeout(detailCloseTimer);
    document.body.classList.remove("stock-detail-open");
    if (panel) panel.setAttribute("aria-hidden", "true");
    if (wasOpen && panel && !panel.hidden) {
      detailCloseTimer = window.setTimeout(() => finalizeStockDetailClose(panel, backdrop), DRAWER_TRANSITION_MS);
    } else {
      finalizeStockDetailClose(panel, backdrop);
    }
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
    clearTimeout(detailCloseTimer);
    detailReturnFocus = trigger instanceof HTMLElement ? trigger : document.activeElement;
    panel.hidden = false;
    panel.setAttribute("aria-hidden", "false");
    backdrop.hidden = false;
    document.body.classList.remove("stock-detail-open");
    detailLogoRetryCount = 0;
    syncStockDetailDecisionSurface();
    syncStockDetailLogos();
    syncDrawdownCharts();
    requestAnimationFrame(() => {
      document.body.classList.add("stock-detail-open");
      requestAnimationFrame(() => panel.querySelector("[data-close-stock-detail]")?.focus());
    });
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
    document.documentElement.dataset.stockDetailDrawer = VERSION;
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
      syncStockDetailDecisionSurface();
      syncStockDetailLogos();
      syncDrawdownCharts();
    });
    ["#detailCard", "#mobileDetailBody"].forEach((selector) => {
      const element = document.querySelector(selector);
      if (element) detailObserver.observe(element, { childList: true, subtree: true });
    });
    document.addEventListener("click", () => {
      syncStockDetailDecisionSurface();
      syncStockDetailLogos();
      syncDrawdownCharts();
    }, true);

    bindStockDetail();
    ensurePageGuides();
    ensureMobileDetailHandle();
    closeStockDetail({ restoreFocus: false });
    syncAlertHeight();
    syncStockDetailDecisionSurface();
    syncDrawdownCharts();
  }

  window.StockRadarDetailDialog = Object.freeze({
    version: VERSION,
    open: openStockDetail,
    close: closeStockDetail
  });

  window.StockRadarDetailPresentation = Object.freeze({
    version: VERSION,
    rangePositionPct,
    refresh: syncStockDetailDecisionSurface
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