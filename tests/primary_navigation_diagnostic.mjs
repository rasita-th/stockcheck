import { chromium } from "playwright";

const base = (process.env.PRODUCTION_URL || "http://127.0.0.1:8000/").replace(/\/?$/, "/");
const mode = process.env.BLOCK_RUNTIME || "none";

const blockPatterns = {
  drawdown: /drawdown-screener-v10-9\.js/i,
  "memo-only": /memo-only-fix\.js/i,
  "final-ui": /final-ui-coordinator\.js/i,
  "attention-p0": /attention-p0\.js/i,
  "attention-pr3": /attention-pr3\.js/i,
  "attention-pr4": /attention-pr4\.js/i,
};

console.log(`[diag] mode=${mode} launch`);
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const errors = [];

page.on("console", (message) => {
  const text = message.text();
  if (message.type() === "error" || message.type() === "warning") {
    console.log(`[diag] browser-${message.type()}: ${text}`);
  }
});
page.on("pageerror", (error) => {
  errors.push(String(error?.stack || error));
  console.log(`[diag] pageerror: ${String(error?.stack || error)}`);
});

const pattern = blockPatterns[mode];
if (pattern) {
  await page.route("**/*", async (route) => {
    const url = route.request().url();
    if (pattern.test(url)) {
      console.log(`[diag] blocked ${url}`);
      await route.abort();
      return;
    }
    await route.continue();
  });
}

console.log(`[diag] goto ${base}`);
const response = await page.goto(`${base}?primary_nav_diag=${Date.now()}&mode=${encodeURIComponent(mode)}`, {
  waitUntil: "domcontentloaded",
  timeout: 30000,
});
console.log(`[diag] index status=${response?.status()}`);
await page.waitForSelector(".app-shell", { state: "visible", timeout: 15000 });
await page.waitForSelector('.app-mode-nav [data-app-view="attention"]', { state: "visible", timeout: 15000 });
console.log("[diag] nav ready");

const before = await page.evaluate(() => ({
  bodyClass: document.body.className,
  viewVersion: window.__stockcheckPrimaryNavVersion || window.StockRadarShellV946?.version || null,
  scripts: [...document.scripts].map((script) => script.src).filter(Boolean).map((src) => src.split("/").pop()),
  attentionPages: [...document.querySelectorAll(".attention-page")].map((node) => ({ id: node.id, cls: node.className })),
}));
console.log(`[diag] before=${JSON.stringify(before)}`);

console.log("[diag] before Today click");
await page.locator('.app-mode-nav [data-app-view="attention"]').click({ timeout: 10000, noWaitAfter: true });
console.log("[diag] after Today click");

await new Promise((resolve) => setTimeout(resolve, 500));
console.log("[diag] before post-click evaluate");
const after = await page.evaluate(() => ({
  bodyClass: document.body.className,
  memo: document.body.classList.contains("memo-active"),
  attention: document.body.classList.contains("attention-active"),
  visibleAttention: [...document.querySelectorAll(".attention-page")].filter((node) => {
    const style = getComputedStyle(node);
    const rect = node.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  }).map((node) => node.id),
}));
console.log(`[diag] after=${JSON.stringify(after)}`);

if (!after.attention || after.memo || after.visibleAttention.length === 0) {
  throw new Error(`Today state invalid in mode ${mode}: ${JSON.stringify(after)}`);
}

console.log(`[diag] mode=${mode} PASS errors=${errors.length}`);
await context.close();
await browser.close();
