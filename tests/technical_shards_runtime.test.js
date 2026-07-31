"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const runtime = fs.readFileSync(path.join(root, "site", "technical-shards-v2.js"), "utf8");

let fetchCount = 0;
let renderCount = 0;
const state = {
  staticMode: true,
  staticLoaded: true,
  selected: "CIFR",
  staticPayloads: { technical: { __technicalV2: true } },
  quotes: {
    NVDA: {
      latest: { pe: 44.1 },
      fundamental: { revenue: 130000000000 },
    },
    CIFR: {
      latest: { pe: 31.2 },
      fundamental: { revenue: 151000000 },
    },
  },
};

const shard = {
  schema_version: "2.0",
  symbol: "CIFR",
  latest: { symbol: "CIFR", close: 22.79, ema20: 21.89, rsi14: 51.71 },
  series: [
    { date: "2026-07-30", close: 24.08 },
    { date: "2026-07-31", close: 22.79 },
  ],
  meta: { source: "runtime-test" },
};

const context = {
  console,
  window: {},
  __state: state,
  __fetchStaticLayer: async () => ({ rows: [] }),
  __loadStaticData: async () => {},
  __currentQuoteFor: (symbol) => state.quotes[symbol] || null,
  __renderAll: () => { renderCount += 1; },
  __fetch: async (url) => {
    fetchCount += 1;
    assert.match(url, /data\/technical\/symbols\/CIFR\.json/);
    return {
      ok: true,
      status: 200,
      text: async () => JSON.stringify(shard),
    };
  },
};
vm.createContext(context);
vm.runInContext(`
  var state = globalThis.__state;
  var fetchStaticLayer = globalThis.__fetchStaticLayer;
  var loadStaticData = globalThis.__loadStaticData;
  var currentQuoteFor = globalThis.__currentQuoteFor;
  var renderAll = globalThis.__renderAll;
  var fetch = globalThis.__fetch;
  ${runtime}
  globalThis.__runtimeCurrentQuoteFor = currentQuoteFor;
`, context, { filename: "technical-shards-v2.js" });

(async () => {
  const tableQuote = context.__runtimeCurrentQuoteFor("NVDA");
  assert.equal(tableQuote.fundamental.revenue, 130000000000);
  assert.equal(fetchCount, 0, "rendering a non-selected table row must not fetch its shard");

  const summary = context.__runtimeCurrentQuoteFor("CIFR");
  assert.equal(summary.fundamental.revenue, 151000000);

  const loaded = await context.window.StockcheckTechnicalV2.loadTechnicalShard("CIFR");
  assert.equal(fetchCount, 1, "selected summary-only quote must fetch its technical shard once");
  assert.equal(loaded.series.length, 2);
  assert.equal(loaded.latest.close, 22.79);
  assert.equal(loaded.latest.pe, 31.2, "technical merge must preserve existing latest fields");
  assert.equal(loaded.fundamental.revenue, 151000000, "technical merge must preserve fundamentals");
  assert.equal(loaded.__technicalV2Loaded, true);
  assert.equal(renderCount, 1, "chart data arrival must rerender the detail view");

  const cached = await context.window.StockcheckTechnicalV2.loadTechnicalShard("CIFR");
  assert.equal(cached.series.length, 2);
  assert.equal(fetchCount, 1, "loaded series must be cached for the page session");

  console.log("technical shard runtime test passed: only selected CIFR upgraded to series");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
