#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_JS = ROOT / "site" / "attention-pr4.js"
TARGET_VERSION = "10.4.2"

HELPER_BLOCK = r'''  const LOGO_DEV_TOKEN = "__LOGO_DEV_PUBLISHABLE_KEY__";
  const MAX_UNIQUE_LOGOS_PER_PAGE = 6;
  const MAX_NON_DETAIL_LOGOS_PER_PAGE = 5;
  const MAX_LOGO_ATTEMPTS_PER_BROWSER_MONTH = 60;
  const LOGO_FAILURE_TTL_MS = 7 * 24 * 60 * 60 * 1000;
  const LOGO_USAGE_KEY = "stockcheck.logoDev.usage.v2";
  const LOGO_FAILURE_KEY = "stockcheck.logoDev.failures.v2";
  const requestedLogoTickers = new Set();
  let nonDetailLogoRequests = 0;
  let logoFallbackBound = false;

  function readLogoStorage(key, fallback) {
    try {
      const value = JSON.parse(localStorage.getItem(key) || "null");
      return value && typeof value === "object" ? value : fallback;
    } catch {
      return fallback;
    }
  }

  function writeLogoStorage(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* optional */ }
  }

  function logoMonthKey() {
    return new Date().toISOString().slice(0, 7);
  }

  function currentLogoUsage() {
    const stored = readLogoStorage(LOGO_USAGE_KEY, {});
    if (stored.month !== logoMonthKey()) return { month: logoMonthKey(), attempts: 0 };
    return {
      month: stored.month,
      attempts: Math.max(0, Math.min(Number(stored.attempts) || 0, MAX_LOGO_ATTEMPTS_PER_BROWSER_MONTH)),
    };
  }

  function currentLogoFailures() {
    const now = Date.now();
    const stored = readLogoStorage(LOGO_FAILURE_KEY, {});
    const active = {};
    for (const [ticker, failedAt] of Object.entries(stored)) {
      if (Number.isFinite(Number(failedAt)) && now - Number(failedAt) < LOGO_FAILURE_TTL_MS) {
        active[ticker] = Number(failedAt);
      }
    }
    return active;
  }

  let logoUsage = currentLogoUsage();
  let logoFailures = currentLogoFailures();
  const missingLogoTickers = new Set(Object.keys(logoFailures));
  writeLogoStorage(LOGO_USAGE_KEY, logoUsage);
  writeLogoStorage(LOGO_FAILURE_KEY, logoFailures);

  function normaliseLogoTicker(value) {
    return String(value || "")
      .trim()
      .replace(/^[$#]+/, "")
      .toUpperCase()
      .replace(/[^A-Z0-9.\-]/g, "");
  }

  function fallbackLogoMarkup(markClass, fallback, ticker = "") {
    return `<span class="${markClass}" data-logo-shell data-logo-ticker="${esc(ticker)}"><span data-logo-fallback>${fallback}</span></span>`;
  }

  function reserveLogoAttempt(ticker, detailRequest) {
    if (requestedLogoTickers.has(ticker)) return true;
    if (missingLogoTickers.has(ticker)) return false;
    if (logoUsage.attempts >= MAX_LOGO_ATTEMPTS_PER_BROWSER_MONTH) return false;
    if (requestedLogoTickers.size >= MAX_UNIQUE_LOGOS_PER_PAGE) return false;
    if (!detailRequest && nonDetailLogoRequests >= MAX_NON_DETAIL_LOGOS_PER_PAGE) return false;

    requestedLogoTickers.add(ticker);
    if (!detailRequest) nonDetailLogoRequests += 1;
    logoUsage.attempts += 1;
    writeLogoStorage(LOGO_USAGE_KEY, logoUsage);
    return true;
  }

  function companyLogoMarkup(item, markClass = "company-logo-mark") {
    const ticker = normaliseLogoTicker(item?.ticker);
    const fallback = esc(String(ticker || "?").slice(0, 2));
    const detailRequest = String(markClass).includes("stock-detail-company-logo");
    const earningsRequest = String(markClass).includes("er-ticker-mark");
    const relevantEarnings = ["portfolio", "related"].includes(String(item?.relation || ""));

    if (!ticker || (earningsRequest && !relevantEarnings) || !reserveLogoAttempt(ticker, detailRequest)) {
      return fallbackLogoMarkup(markClass, fallback, ticker);
    }

    const loading = detailRequest ? "eager" : "lazy";
    const priority = detailRequest ? "high" : "low";
    const src = `https://img.logo.dev/ticker/${encodeURIComponent(ticker)}?token=${encodeURIComponent(LOGO_DEV_TOKEN)}&size=64&format=webp&theme=dark&retina=true&fallback=404`;
    return `<span class="${markClass}" data-logo-shell data-logo-ticker="${esc(ticker)}"><img src="${src}" data-logo-ticker="${esc(ticker)}" alt="" aria-hidden="true" width="54" height="54" loading="${loading}" decoding="async" fetchpriority="${priority}" referrerpolicy="origin"><span data-logo-fallback hidden>${fallback}</span></span>`;
  }

  function installLogoFallback() {
    if (logoFallbackBound) return;
    logoFallbackBound = true;
    document.addEventListener("error", (event) => {
      const image = event.target;
      if (!(image instanceof HTMLImageElement) || !image.dataset.logoTicker) return;
      const ticker = normaliseLogoTicker(image.dataset.logoTicker);
      if (ticker) {
        missingLogoTickers.add(ticker);
        logoFailures[ticker] = Date.now();
        writeLogoStorage(LOGO_FAILURE_KEY, logoFailures);
      }
      image.hidden = true;
      image.nextElementSibling?.removeAttribute("hidden");
    }, true);
  }
'''


def apply_patch(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if (
        f'const VERSION = "{TARGET_VERSION}"' in text
        and "MAX_UNIQUE_LOGOS_PER_PAGE = 6" in text
        and "MAX_LOGO_ATTEMPTS_PER_BROWSER_MONTH = 60" in text
    ):
        print(f"Company logo budget already applied: {path.relative_to(ROOT)}")
        return

    if text.count('const VERSION = "10.4.1"') != 1:
        raise SystemExit("attention-pr4.js version guard did not match exactly once")
    text = text.replace('const VERSION = "10.4.1"', f'const VERSION = "{TARGET_VERSION}"', 1)

    pattern = re.compile(
        r'  const LOGO_DEV_TOKEN = "__LOGO_DEV_PUBLISHABLE_KEY__";.*?\n  function loadJson\(key, fallback\) \{',
        flags=re.DOTALL,
    )
    text, count = pattern.subn(HELPER_BLOCK + "\n  function loadJson(key, fallback) {", text, count=1)
    if count != 1:
        raise SystemExit("attention-pr4.js logo helper guard did not match exactly once")

    old_export = 'window.StockcheckCompanyLogo = Object.freeze({ version: "1.0.0", markup: companyLogoMarkup });'
    new_export = (
        'window.StockcheckCompanyLogo = Object.freeze({ '
        'version: "2.0.0", markup: companyLogoMarkup, '
        'limits: Object.freeze({ perPage: MAX_UNIQUE_LOGOS_PER_PAGE, nonDetailPerPage: MAX_NON_DETAIL_LOGOS_PER_PAGE, perBrowserMonth: MAX_LOGO_ATTEMPTS_PER_BROWSER_MONTH }) '
        '});'
    )
    if text.count(old_export) != 1:
        raise SystemExit("attention-pr4.js logo export guard did not match exactly once")
    text = text.replace(old_export, new_export, 1)

    path.write_text(text, encoding="utf-8")
    print(f"Applied company logo budget: {path.relative_to(ROOT)}")


def main() -> None:
    apply_patch(SITE_JS)


if __name__ == "__main__":
    main()
