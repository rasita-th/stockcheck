(() => {
  "use strict";

  const VERSION = "10.5.1";
  const ROOT_ID = "earningsRadarRootP4";
  const PAGE_ID = "attentionPageP4";
  const RETRY_DELAY_MS = 900;
  let observer = null;
  let timer = null;

  function errorMarkup() {
    return `<section class="er-radar er-error-state" role="alert">
      <div class="er-error">
        <strong>ยังเปิด Earnings Radar ไม่ได้</strong>
        <span>ข้อมูลปฏิทินงบอาจกำลังอัปเดต หรือรูปแบบข้อมูลไม่สมบูรณ์</span>
        <button type="button" data-er-error-retry>ลองโหลดอีกครั้ง</button>
      </div>
    </section>`;
  }

  function ensureVisibleError() {
    const page = document.getElementById(PAGE_ID);
    if (!page || !document.body.classList.contains("attention-p4-ready")) return;
    if (document.getElementById(ROOT_ID)) return;
    if (!window.StockcheckEarningsRadarP4) return;
    const shell = page.querySelector(".p4-shell");
    if (!shell) return;
    const root = document.createElement("div");
    root.id = ROOT_ID;
    root.className = "er-root er-root-error";
    root.innerHTML = errorMarkup();
    shell.appendChild(root);
  }

  function scheduleCheck(delay = 1500) {
    window.clearTimeout(timer);
    timer = window.setTimeout(ensureVisibleError, delay);
  }

  function observe() {
    const page = document.getElementById(PAGE_ID);
    if (!page || observer) return;
    observer = new MutationObserver(() => {
      if (!document.getElementById(ROOT_ID)) scheduleCheck();
    });
    observer.observe(page, { childList: true, subtree: true });
    scheduleCheck(3500);
  }

  function boot() {
    const interval = window.setInterval(() => {
      if (document.getElementById(PAGE_ID) && window.StockcheckEarningsRadarP4) {
        window.clearInterval(interval);
        observe();
      }
    }, 100);
    window.setTimeout(() => {
      window.clearInterval(interval);
      ensureVisibleError();
    }, 10000);

    document.addEventListener("click", (event) => {
      if (!event.target.closest?.("[data-er-error-retry]")) return;
      const root = document.getElementById(ROOT_ID);
      if (root) root.remove();
      window.StockcheckEarningsRadarP4?.load?.();
      scheduleCheck(RETRY_DELAY_MS + 2500);
    });

    window.StockcheckEarningsRadarErrorGuard = { version: VERSION, check: ensureVisibleError };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
