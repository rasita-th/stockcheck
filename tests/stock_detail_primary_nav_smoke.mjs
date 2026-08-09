import { chromium } from "playwright";
import fs from "node:fs";

const base = (process.env.PRODUCTION_URL || "https://rasita-th.github.io/stockcheck/").replace(/\/?$/, "/");
const outDir = process.env.DETAIL_NAV_SMOKE_OUT_DIR || "stock-detail-primary-nav-smoke-artifacts";
fs.mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const pageErrors = [];
page.on("pageerror", (error) => pageErrors.push(String(error?.stack || error)));

let errorText = null;
let geometry = null;
const checks = { scanner: false, detailOpen: false, headerClearance: false, todayReachable: false, detailClosed: false };
try {
  const response = await page.goto(`${base}?stock_detail_nav_smoke=${Date.now()}`, { waitUntil: "domcontentloaded", timeout: 30000 });
  if (response?.status() !== 200) throw new Error(`index HTTP ${response?.status()}`);
  await page.waitForSelector(".app-shell", { state: "visible", timeout: 15000 });
  await page.waitForSelector('.app-mode-nav [data-app-view="attention"]', { state: "visible", timeout: 15000 });
  await page.waitForFunction(() => typeof window.StockRadarDetailDialog?.open === "function", null, { timeout: 10000 });
  checks.scanner = true;

  const stock = page.locator('#watchlistPanel [data-select]').first();
  await stock.waitFor({ state: "visible", timeout: 10000 });
  await stock.click({ timeout: 5000, noWaitAfter: true });
  await page.waitForFunction(() => document.body.classList.contains("stock-detail-open"), null, { timeout: 5000 });
  await page.waitForTimeout(350);
  checks.detailOpen = true;

  geometry = await page.evaluate(() => {
    const header = document.querySelector("header.topbar")?.getBoundingClientRect();
    const nav = document.querySelector('.app-mode-nav [data-app-view="attention"]')?.getBoundingClientRect();
    const panel = document.querySelector("#detailPanel")?.getBoundingClientRect();
    const backdrop = document.querySelector("#desktopDetailBackdrop")?.getBoundingClientRect();
    const pick = (rect) => rect ? { top: rect.top, bottom: rect.bottom, left: rect.left, right: rect.right, width: rect.width, height: rect.height } : null;
    return {
      header: pick(header),
      nav: pick(nav),
      panel: pick(panel),
      backdrop: pick(backdrop),
      offset: getComputedStyle(document.documentElement).getPropertyValue("--stock-detail-top-offset").trim(),
    };
  });
  console.log(`[stock-detail-nav] geometry=${JSON.stringify(geometry)}`);
  if (!geometry?.header || !geometry?.panel || !geometry?.backdrop) throw new Error(`missing geometry: ${JSON.stringify(geometry)}`);
  if (geometry.panel.top + 1 < geometry.header.bottom) throw new Error(`detail overlaps header: ${JSON.stringify(geometry)}`);
  if (geometry.backdrop.top + 1 < geometry.header.bottom) throw new Error(`detail backdrop overlaps header: ${JSON.stringify(geometry)}`);
  checks.headerClearance = true;

  // This must remain a real pointer click. The primary navigation is part of
  // the shared shell and must stay reachable while the desktop detail is open.
  await page.locator('.app-mode-nav [data-app-view="attention"]').click({ timeout: 5000, noWaitAfter: true });
  await page.waitForFunction(() => document.body.classList.contains("attention-active"), null, { timeout: 5000 });
  checks.todayReachable = true;
  await page.waitForFunction(() => !document.body.classList.contains("stock-detail-open"), null, { timeout: 5000 });
  checks.detailClosed = true;
} catch (error) {
  errorText = String(error?.stack || error);
  console.error(errorText);
}

await page.screenshot({ path: `${outDir}/desktop-detail-primary-nav.png`, fullPage: true, timeout: 10000 }).catch(() => {});
fs.writeFileSync(`${outDir}/result.json`, JSON.stringify({ base, checks, geometry, errorText, pageErrors }, null, 2));
await context.close();
await browser.close();

console.log(JSON.stringify({ base, checks, geometry, errorText, pageErrors }, null, 2));
if (errorText || pageErrors.length || Object.values(checks).some((value) => value !== true)) process.exit(1);
