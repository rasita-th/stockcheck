import { chromium, devices } from "playwright";
import fs from "node:fs";

const base = (process.env.PRODUCTION_URL || "https://rasita-th.github.io/stockcheck/").replace(/\/?$/, "/");
const outDir = process.env.SMOKE_OUT_DIR || "production-smoke-artifacts";
fs.mkdirSync(outDir, { recursive: true });

const profiles = [
  { name: "desktop", viewport: { width: 1440, height: 1000 } },
  { name: "iphone", device: devices["iPhone 13"] },
];

const results = [];
let failed = false;
const browser = await chromium.launch({ headless: true });

for (const profile of profiles) {
  const context = await browser.newContext(profile.device || { viewport: profile.viewport });
  const page = await context.newPage();
  const pageErrors = [];
  const firstPartyFailures = [];
  const consoleErrors = [];

  page.on("pageerror", (error) => pageErrors.push(String(error?.stack || error)));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("requestfailed", (request) => {
    const url = request.url();
    if (url.startsWith(base)) {
      firstPartyFailures.push({ url, type: request.resourceType(), error: request.failure()?.errorText || "failed" });
    }
  });

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
    await page.waitForTimeout(1500);
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
    };
  }).catch(() => ({}));

  await page.screenshot({ path: `${outDir}/${profile.name}.png`, fullPage: true }).catch(() => {});
  const record = { profile: profile.name, status, navigationError, pageErrors, firstPartyFailures, consoleErrors, runtime };
  results.push(record);

  const criticalFailures = firstPartyFailures.filter((item) => ["document", "script", "stylesheet", "xhr", "fetch"].includes(item.type));
  if (status !== 200 || navigationError || pageErrors.length || criticalFailures.length || !runtime.shellVisible || runtime.bodyTextLength < 100 || (runtime.desktopRows + runtime.mobileCards) < 1) {
    failed = true;
  }

  await context.close();
}

await browser.close();
fs.writeFileSync(`${outDir}/result.json`, JSON.stringify({ base, results }, null, 2));
console.log(JSON.stringify({ base, results }, null, 2));
if (failed) process.exit(1);
