import { chromium, devices } from "playwright";
import fs from "node:fs";

const base = (process.env.PRODUCTION_URL || "https://rasita-th.github.io/stockcheck/").replace(/\/?$/, "/");
const outDir = process.env.NAV_SMOKE_OUT_DIR || "primary-navigation-smoke-artifacts";
fs.mkdirSync(outDir, { recursive: true });

const profiles = [
  { name: "desktop-nav", viewport: { width: 1440, height: 1000 } },
  { name: "iphone-nav", device: devices["iPhone 13"] },
  {
    name: "desktop-storage-blocked-nav",
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

const browser = await chromium.launch({ headless: true });
const results = [];
let failed = false;

function visibleNodeScript(selector) {
  return (sel) => Array.from(document.querySelectorAll(sel)).some((node) => {
    const style = getComputedStyle(node);
    const rect = node.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  });
}

for (const profile of profiles) {
  console.log(`[primary-nav] ${profile.name}: start`);
  const context = await browser.newContext(profile.device || { viewport: profile.viewport });
  const page = await context.newPage();
  const pageErrors = [];
  const consoleErrors = [];
  const firstPartyFailures = [];

  page.on("pageerror", (error) => pageErrors.push(String(error?.stack || error)));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("requestfailed", (request) => {
    const url = request.url();
    const error = request.failure()?.errorText || "failed";
    if (url.startsWith(base) && error !== "net::ERR_ABORTED") firstPartyFailures.push({ url, type: request.resourceType(), error });
  });
  await profile.beforeLoad?.(page);

  const checks = { scannerBoot: false, today: false, memo: false, scannerReturn: false, detailCloseOnViewSwitch: true, marketPulse: false };
  let errorText = null;
  try {
    const response = await page.goto(`${base}?primary_nav_smoke=${Date.now()}`, { waitUntil: "domcontentloaded", timeout: 30000 });
    if (response?.status() !== 200) throw new Error(`index HTTP ${response?.status()}`);
    await page.waitForSelector(".app-shell", { state: "visible", timeout: 15000 });
    await page.waitForSelector('.app-mode-nav [data-app-view="attention"]', { state: "visible", timeout: 15000 });
    await page.waitForFunction(() => typeof window.StockRadarDetailDialog?.version === "string", null, { timeout: 10000 });
    checks.scannerBoot = true;
    console.log(`[primary-nav] ${profile.name}: scanner boot ok`);

    console.log(`[primary-nav] ${profile.name}: click Today from closed detail`);
    await page.locator('.app-mode-nav [data-app-view="attention"]').click({ timeout: 5000, noWaitAfter: true });
    await page.waitForFunction(visibleNodeScript(".attention-page"), ".attention-page", { timeout: 10000 });
    await page.waitForFunction(() => document.body.classList.contains("attention-active") && !document.body.classList.contains("memo-active"), null, { timeout: 5000 });
    checks.today = true;

    console.log(`[primary-nav] ${profile.name}: click Memo`);
    await page.locator('.app-mode-nav [data-app-view="memo"]').click({ timeout: 5000, noWaitAfter: true });
    await page.waitForFunction(visibleNodeScript("#memoPage"), "#memoPage", { timeout: 10000 });
    await page.waitForFunction(() => document.body.classList.contains("memo-active") && !document.body.classList.contains("attention-active"), null, { timeout: 5000 });
    checks.memo = true;

    console.log(`[primary-nav] ${profile.name}: return Scanner`);
    await page.locator('.app-mode-nav [data-app-view="scanner"]').click({ timeout: 5000, noWaitAfter: true });
    await page.waitForFunction(() => !document.body.classList.contains("memo-active") && !document.body.classList.contains("attention-active"), null, { timeout: 5000 });
    checks.scannerReturn = true;

    if (!profile.device) {
      const stock = page.locator('#watchlistPanel [data-select]').first();
      if (await stock.count()) {
        await stock.click({ timeout: 5000, noWaitAfter: true });
        await page.waitForFunction(() => document.body.classList.contains("stock-detail-open"), null, { timeout: 5000 });
        console.log(`[primary-nav] ${profile.name}: switch Today with detail open`);
        await page.locator('.app-mode-nav [data-app-view="attention"]').click({ timeout: 5000, noWaitAfter: true });
        await page.waitForFunction(() => document.body.classList.contains("attention-active") && !document.body.classList.contains("stock-detail-open"), null, { timeout: 5000 });
        checks.detailCloseOnViewSwitch = true;
        await page.locator('.app-mode-nav [data-app-view="scanner"]').click({ timeout: 5000, noWaitAfter: true });
        await page.waitForFunction(() => !document.body.classList.contains("memo-active") && !document.body.classList.contains("attention-active"), null, { timeout: 5000 });
      }
    }

    console.log(`[primary-nav] ${profile.name}: open Market Pulse`);
    await page.waitForSelector('.app-mode-nav a.market-mode-btn', { state: "visible", timeout: 5000 });
    await Promise.all([
      page.waitForURL((url) => /\/market\.html$/.test(url.pathname), { timeout: 10000 }),
      page.locator('.app-mode-nav a.market-mode-btn').click({ timeout: 5000, noWaitAfter: true }),
    ]);
    await page.waitForSelector("#marketBriefing", { state: "visible", timeout: 10000 });
    checks.marketPulse = true;
  } catch (error) {
    errorText = String(error?.stack || error);
    failed = true;
    console.error(`[primary-nav] ${profile.name}: failed`, errorText);
  }

  const criticalFailures = firstPartyFailures.filter((item) => ["document", "script", "stylesheet", "xhr", "fetch"].includes(item.type));
  if (pageErrors.length || criticalFailures.length || Object.values(checks).some((value) => value !== true)) failed = true;

  await page.screenshot({ path: `${outDir}/${profile.name}.png`, fullPage: true, timeout: 10000 }).catch(() => {});
  results.push({ profile: profile.name, checks, errorText, pageErrors, consoleErrors, firstPartyFailures });
  await context.close();
}

await browser.close();
fs.writeFileSync(`${outDir}/result.json`, JSON.stringify({ base, results }, null, 2));
console.log(JSON.stringify({ base, results }, null, 2));
if (failed) process.exit(1);
