(() => {
  "use strict";

  const VERSION = "1.0.0";
  const MAX_LOADING_MS = 20000;
  const BUTTON_SELECTORS = ["#scanNowDesktop", "#mobileScanNow"];
  let timer = 0;
  let startedAt = 0;

  function scanningButtons() {
    return BUTTON_SELECTORS
      .map((selector) => document.querySelector(selector))
      .filter(Boolean);
  }

  function isScanning() {
    return scanningButtons().some((button) =>
      button.disabled && /scanning/i.test(button.textContent || "")
    );
  }

  function clearGuard() {
    if (timer) window.clearTimeout(timer);
    timer = 0;
    startedAt = 0;
  }

  function recover() {
    if (!isScanning()) {
      clearGuard();
      return;
    }
    const message = "โหลดข้อมูลไม่สำเร็จ ลองใหม่อีกครั้ง";
    if (typeof window.setLoading === "function") {
      window.setLoading(false, message);
    } else {
      scanningButtons().forEach((button) => {
        button.disabled = false;
        button.textContent = "◎ Scan Now";
      });
      const subtitle = document.querySelector("#scannerSubtitle");
      if (subtitle) subtitle.textContent = message;
    }
    document.documentElement.dataset.scannerLoadingGuard = "recovered";
    window.dispatchEvent(new CustomEvent("stockcheck:scanner-timeout", {
      detail: { version: VERSION, startedAt, recoveredAt: Date.now() },
    }));
    clearGuard();
  }

  function armGuard() {
    if (!isScanning()) {
      clearGuard();
      return;
    }
    if (timer) return;
    startedAt = Date.now();
    document.documentElement.dataset.scannerLoadingGuard = VERSION;
    timer = window.setTimeout(recover, MAX_LOADING_MS);
  }

  function observe() {
    const observer = new MutationObserver(armGuard);
    scanningButtons().forEach((button) => {
      observer.observe(button, {
        attributes: true,
        attributeFilter: ["disabled"],
        childList: true,
        characterData: true,
        subtree: true,
      });
    });
    armGuard();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", observe, { once: true });
  } else {
    observe();
  }
})();
