"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(root, "site", "app.js"), "utf8");

function extractFunction(name) {
  const marker = `function ${name}(`;
  const start = source.indexOf(marker);
  assert.notEqual(start, -1, `${name} must exist in the Memo runtime`);
  const declarationStart = source.slice(start - 6, start) === "async " ? start - 6 : start;
  const bodyStart = source.indexOf("{", start);
  let depth = 0;
  for (let index = bodyStart; index < source.length; index += 1) {
    if (source[index] === "{") depth += 1;
    if (source[index] === "}") depth -= 1;
    if (depth === 0) return source.slice(declarationStart, index + 1);
  }
  throw new Error(`unterminated function: ${name}`);
}

let apiFetchCount = 0;
const context = {
  console,
  state: {
    watchlist: ["NVDA"],
    rows: [
      { symbol: "NVDA", close: 223.98, snapshotStatus: "live_quote" },
      { symbol: "HOOD", close: 150.44, snapshotStatus: "live_quote" },
    ],
  },
  memoTicker: (value) => String(value || "").trim().toUpperCase(),
  memoToNum: (value) => {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  },
  mapRow: (row) => ({ ticker: row.symbol, price: row.close, raw: row }),
  trendFromStock: () => "Uptrend",
  trendFromQuote: () => "Unknown",
  calcPctChange: (current, note) => ((current - note) / note) * 100,
  calcFromTarget: (current, target) => ((current - target) / target) * 100,
  isMemoAlertReached: () => false,
  fetchJson: async () => {
    apiFetchCount += 1;
    throw new Error("GitHub Pages does not expose /api/quote");
  },
  URLSearchParams,
};
vm.createContext(context);
vm.runInContext(`
  ${extractFunction("canonicalStockForMemoTicker")}
  ${extractFunction("enrichMemo")}
  ${extractFunction("fetchMemoPrice")}
  globalThis.__canonicalStockForMemoTicker = canonicalStockForMemoTicker;
  globalThis.__enrichMemo = enrichMemo;
  globalThis.__fetchMemoPrice = fetchMemoPrice;
`, context, { filename: "memo-canonical-price-runtime.js" });

(async () => {
  const hood = context.__canonicalStockForMemoTicker("hood");
  assert.equal(hood.ticker, "HOOD");
  assert.equal(hood.price, 150.44, "Memo must search the full canonical snapshot, not only the watchlist");

  const hydrated = context.__enrichMemo({ ticker: "HOOD", currentPrice: null, notePrice: 140, targetPrice: 160, status: "Watchlist" });
  assert.equal(hydrated.currentPrice, 150.44, "an existing Memo must hydrate during render without a manual refresh");

  const refreshed = await context.__fetchMemoPrice("HOOD");
  assert.equal(refreshed.price, 150.44);
  assert.equal(refreshed.source, "canonical_screener_snapshot");
  assert.equal(apiFetchCount, 0, "a canonical price must not fall through to the unavailable Pages API");

  console.log("memo canonical price runtime test passed");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
