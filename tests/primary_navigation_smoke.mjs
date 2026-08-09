import { chromium, devices } from "playwright";
import fs from "node:fs";

const base = (process.env.PRODUCTION_URL || "https://rasita-th.github.io/stockcheck/").replace(/\/?$/, "/");
const outDir = process.env.NAV_SMOKE_OUT_DIR || "primary-navigation-smoke-artifacts";
fs.mkdirSync(outDir, { recursive: true });

const profiles = [
  { name: "desktop-nav", viewport: { width: 1440, height: 1000 } },
  { name: "iphone-nav", device: devices["iPhone 13"] },
];

const browser = await chromium.launch({ headless: true });
const results = [];
let failed = false;

for (const profile of profiles) {
  console.log(`[primary-nav] ${profile.name}: start`);
  const context = await browser.newContext(profile.device || { viewport: profile.viewport });
  const page = await context.newPage();
  const pageErrors = [];
  const firstPartyFailures = [];

  page.on("pageerror", (error) => pageErrors.push(String(error?.stack || error)));
  page.on("requestfailed", (request) => {
    const url = request.url();
    const error = request.failure()?.errorText || "failed";
    if (url.startsWith(base) && error !== "net::ERR_ABORTED") firstPartyFailures.push({ url, type: request.resourceType(), error });
  });

  const checks = { runtime: false, today: false, memo: false, scanner: false, marketPulse: false };
  let errorText = null;
  try {
    const response = await page.goto(`${base}?primary_nav_smoke=${Date.now()}`, { waitUntil: "domcontentloaded", timeout: 30000 });
    if (response?.status() !== 200) throw new Error(`index HTTP ${response?.status()}`);
    await page.waitForSelector(".app-shell", { state: "visible", timeout: 15000 });
    await page.waitForSelector('.app-mode-nav [data-app-view="attention"]', { state: "visible", timeout: 15000 });
    await page.waitForFunction(() => window.__stockcheckPrimaryNavVersion === "10.8.7" || window.StockRadarShellV946?.version === "10.8.7", null, { timeout: 10000 });
    checks.runtime = true;
    console.log(`[primary-nav] ${profile.name}: runtime ok`);

    await page.locator('.app-mode-nav [data-app-view="attention"]').click({ timeout: 10000, noWaitAfter: true });
    await page.waitForFunction(() => {
      const visibleToday = Array.from(document.querySelectorAll(".attention-page")).some((node) => {
        const style = getComputedStyle(node);
        const rect = node.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
      });
      return document.body.classList.contains("attention-active") && !document.body.classList.contains("memo-active") && visibleToday;
    }, null, { timeout: 15000 });
    checks.today = true;
    console.log(`[primary-nav] ${profile.name}: Today ok`);

    await page.locator('.app-mode-nav [data-app-view="memo"]').click({ timeout: 10000, noWaitAfter: true });
    await page.waitForFunction(() => {
      const memo = document.querySelector("#memoPage");
      if (!memo) return false;
      const style = getComputedStyle(memo);
      const rect = memo.getBoundingClientRect();
      return document.body.classList.contains("memo-active") && !document.body.classList.contains("attention-active") && style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
    }, null, { timeout: 15000 });
    checks.memo = true;
    console.log(`[primary-nav] ${profile.name}: Memo ok`);

    await page.locator('.app-mode-nav [data-app-view="scanner"]').click({ timeout: 10000, noWaitAfter: true });
    await page.waitForFunction(() => !document.body.classList.contains("memo-active") && !document.body.classList.contains("attention-active"), null, { timeout: 10000 });
    checks.scanner = true;
    console.log(`[primary-nav] ${profile.name}: Scanner ok`);

    await page.waitForSelector('.app-mode-nav a.market-mode-btn', { state: "visible", timeout: 10000 });
    await Promise.all([
      page.waitForURL((url) => /\/market\.html$/.test(url.pathname), { timeout: 15000 }),
      page.locator('.app-mode-nav a.market-mode-btn').click({ timeout: 10000, noWaitAfter: true }),
    ]);
    await page.waitForSelector("#marketBriefing", { state: "visible", timeout: 15000 });
    checks.marketPulse = true;
    console.log(`[primary-nav] ${profile.name}: Market Pulse ok`);
  } catch (error) {
    errorText = String(error?.stack || error);
    failed = true;
    console.error(`[primary-nav] ${profile.name}: failed`, errorText);
  }

  const criticalFailures = firstPartyFailures.filter((item) => ["document", "script", "stylesheet", "xhr", "fetch"].includes(item.type));
  if (pageErrors.length || criticalFailures.length || Object.values(checks).some((value) => value !== true)) failed = true;

  await page.screenshot({ path: `${outDir}/${profile.name}.png`, fullPage: true, timeout: 10000 }).catch(() => {});
  results.push({ profile: profile.name, checks, errorText, pageErrors, firstPartyFailures });
  await context.close();
}

await browser.close();
fs.writeFileSync(`${outDir}/result.json`, JSON.stringify({ base, results }, null, 2));
console.log(JSON.stringify({ base, results }, null, 2));
if (failed) process.exit(1);
