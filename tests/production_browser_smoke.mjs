import { chromium, devices } from "playwright";
import fs from "node:fs";

const base = (process.env.PRODUCTION_URL || "https://rasita-th.github.io/stockcheck/").replace(/\/?$/, "/");
const outDir = process.env.SMOKE_OUT_DIR || "production-smoke-artifacts";
fs.mkdirSync(outDir, { recursive: true });

const profiles = [
  { name: "desktop-cold", viewport: { width: 1440, height: 1000 } },
  { name: "iphone-cold", device: devices["iPhone 13"] },
  {
    name: "desktop-corrupt-persisted-alerts",
    viewport: { width: 1440, height: 1000 },
    beforeLoad: async (page) => {
      await page.addInitScript(() => {
        localStorage.setItem("stockTimingRadar.alertDismissed.v62", "{");
      });
    },
  },
  {
    name: "desktop-storage-blocked",
    viewport: { width: 1440, height: 1000 },
    beforeLoad: async (page) => {
      await page.addInitScript(() => {
        const deny = () => { throw new DOMException("Storage access denied", "SecurityError"); };
        Storage.prototype.getItem = deny;
        Storage.prototype.setItem = deny;
        Storage.prototype.removeItem = deny;
      });
    },
  },
];

async function verifyPrimaryNavigation(page) {
  const checks = { today: false, memo: false, scanner: false, marketPulse: false };

  await page.waitForSelector('.app-mode-nav [data-app-view="attention"]', { state: "visible", timeout: 15000 });
  await page.click('.app-mode-nav [data-app-view="attention"]');
  await page.waitForFunction(() => {
    const page = document.querySelector(".attention-page");
    return document.body.classList.contains("attention-active") && page && getComputedStyle(page).display !== "none";
  }, null, { timeout: 10000 });
  checks.today = true;

  await page.click('.app-mode-nav [data-app-view="memo"]');
  await page.waitForFunction(() => {
    const memo = document.querySelector("#memoPage");
    return document.body.classList.contains("memo-active") && !document.body.classList.contains("attention-active") && memo && getComputedStyle(memo).display !== "none";
  }, null, { timeout: 10000 });
  checks.memo = true;

  await page.click('.app-mode-nav [data-app-view="scanner"]');
  await page.waitForFunction(() => !document.body.classList.contains("memo-active") && !document.body.classList.contains("attention-active"), null, { timeout: 10000 });
  checks.scanner = true;

  await page.waitForSelector('.app-mode-nav a.market-mode-btn', { state: "visible", timeout: 10000 });
  await Promise.all([
    page.waitForURL((url) => /\/market\.html(?:$|[?#])/.test(url.pathname + url.search + url.hash), { timeout: 15000 }),
    page.click('.app-mode-nav a.market-mode-btn'),
  ]);
  await page.waitForSelector("#marketBriefing", { state: "attached", timeout: 15000 });
  checks.marketPulse = true;

  await page.goto(`${base}?browser_smoke_return=${Date.now()}`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForSelector(".app-shell", { state: "visible", timeout: 30000 });
  return checks;
}

const results = [];
let failed = false;
const browser = await chromium.launch({ headless: true });

for (const profile of profiles) {
  const context = await browser.newContext(profile.device || { viewport: profile.viewport });
  const page = await context.newPage();
  const pageErrors = [];
  const firstPartyFailures = [];
  const consoleErrors = [];
  let navChecks = null;

  page.on("pageerror", (error) => pageErrors.push(String(error?.stack || error)));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("requestfailed", (request) => {
    const url = request.url();
    const error = request.failure()?.errorText || "failed";
    if (url.startsWith(base) && error !== "net::ERR_ABORTED") {
      firstPartyFailures.push({ url, type: request.resourceType(), error });
    }
  });

  await profile.beforeLoad?.(page);

  let status = null;
  let navigationError = null;
  try {
    const response = await page.goto(`${base}?browser_smoke=${Date.now()}`, { waitUntil: "domcontentloaded", timeout: 60000 });
    status = response?.status() ?? null;
    await page.waitForSelector(".app-shell", { state: "visible", timeout: 30000 });
    await page.waitForSelector("#technicalTableBody", { state: "attached", timeout: 30000 });
    await page.waitForFunction(() => {
      const body = document.querySelector("#technicalTableBody");
      const mobile = document.querySelector("#technicalMobileCards");
      return (body && body.children.length > 0) || (mobile && mobile.children.length > 0);
    }, null, { timeout: 45000 });
    await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForSelector(".app-shell", { state: "visible", timeout: 30000 });
    await page.waitForFunction(() => {
      const body = document.querySelector("#technicalTableBody");
      const mobile = document.querySelector("#technicalMobileCards");
      return (body && body.children.length > 0) || (mobile && mobile.children.length > 0);
    }, null, { timeout: 45000 });
    await page.waitForTimeout(1000);
    if (profile.name === "desktop-cold" || profile.name === "iphone-cold") {
      navChecks = await verifyPrimaryNavigation(page);
    }
  } catch (error) {
    navigationError = String(error?.stack || error);
  }

  const runtime = await page.evaluate(() => {
    const shell = document.querySelector(".app-shell");
    const table = document.querySelector("#technicalTableBody");
    const mobile = document.querySelector("#technicalMobileCards");
    const bodyStyle = getComputedStyle(document.body);
    return {
      href: location.href,
      title: document.title,
      readyState: document.readyState,
      bodyTextLength: document.body?.innerText?.trim().length || 0,
      bodyHeight: document.body?.scrollHeight || 0,
      bodyDisplay: bodyStyle.display,
      shellVisible: !!shell && getComputedStyle(shell).display !== "none",
      desktopRows: table?.children.length || 0,
      mobileCards: mobile?.children.length || 0,
      coordinator: window.StockRadarDetailPresentation || window.StockRadarWatchlistDrawer || null,
      canonicalSource: window.StockcheckCanonicalScreener?.source || window.StockcheckCanonicalScreener?.identity || null,
      storageMode: window.__stockcheckStorageMode || null,
      recoveryVersion: window.__stockcheckStorageRecoveryVersion || null,
      sheetBootGuard: window.__stockcheckDesktopSheetBootGuard || null,
      visibleSheets: Array.from(document.querySelectorAll(".bottom-sheet")).filter((sheet) => {
        const style = getComputedStyle(sheet);
        const rect = sheet.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || 1) > 0 && rect.width > 1 && rect.height > 1 && rect.right > 0 && rect.bottom > 0 && rect.left < innerWidth && rect.top < innerHeight;
      }).map((sheet) => ({ id: sheet.id || null, ariaHidden: sheet.getAttribute("aria-hidden"), classes: sheet.className })),
    };
  }).catch(() => ({}));

  await page.screenshot({ path: `${outDir}/${profile.name}.png`, fullPage: true }).catch(() => {});
  const record = { profile: profile.name, status, navigationError, pageErrors, firstPartyFailures, consoleErrors, navChecks, runtime };
  results.push(record);

  const criticalFailures = firstPartyFailures.filter((item) => ["document", "script", "stylesheet", "xhr", "fetch"].includes(item.type));
  const navFailed = navChecks && Object.values(navChecks).some((value) => value !== true);
  if (status !== 200 || navigationError || pageErrors.length || criticalFailures.length || navFailed || !runtime.shellVisible || runtime.bodyTextLength < 100 || (runtime.desktopRows + runtime.mobileCards) < 1 || (runtime.visibleSheets?.length || 0) > 0) {
    failed = true;
  }

  await context.close();
}

await browser.close();
fs.writeFileSync(`${outDir}/result.json`, JSON.stringify({ base, results }, null, 2));
console.log(JSON.stringify({ base, results }, null, 2));
if (failed) process.exit(1);
