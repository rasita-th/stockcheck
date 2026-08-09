(() => {
  "use strict";
  const VERSION = "10.8.6";
  let bootSettled = false;

  function closeStrayBootSheets() {
    document.querySelectorAll(".bottom-sheet").forEach((sheet) => {
      sheet.classList.remove("open", "sheet-visible-force");
      sheet.setAttribute("aria-hidden", "true");
      sheet.style.transform = "";
      sheet.style.opacity = "";
      sheet.style.visibility = "";
      sheet.style.pointerEvents = "";
    });
    const backdrop = document.querySelector("#sheetBackdrop");
    if (backdrop) backdrop.hidden = true;
    document.body.classList.remove("sheet-open");
    window.__stockcheckDesktopSheetBootGuard = { version: VERSION, settled: true };
    bootSettled = true;
  }

  function settleBoot() {
    closeStrayBootSheets();
    requestAnimationFrame(closeStrayBootSheets);
    setTimeout(closeStrayBootSheets, 0);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", settleBoot, { once: true });
  } else {
    settleBoot();
  }

  window.addEventListener("pageshow", (event) => {
    if (event.persisted || !bootSettled) settleBoot();
  });
})();
