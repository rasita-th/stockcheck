"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const runtime = fs.readFileSync(path.join(root, "site", "technical-shards-v2.js"), "utf8");

let shardFetchCount = 0;
let snapshotFetchCount = 0;
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

const snapshot = {
  schema_version: "1.0",
  contract: "canonical-screener-snapshot",
  generated_at: new Date().toISOString(),
  stale_after_minutes: 30,
  rows: [
    {
      symbol: "AMD",
      close: 493.23,
      price: 493.23,
      regularMarketPrice: 493.23,
      dayPct: 0.6592,
      snapshotStatus: "live_quote",
    },
    {
      symbol: "CIFR",
      close: 22.645,
      price: 22.645,
      regularMarketPrice: 22.645,
      dayPct: -0.64,
      score: 81,
      signal: "BUY ZONE / Trend Confirmed",
      snapshotStatus: "live_quote",
    },
  ],
};

const shard = {
  schema_version: "2.0",
  symbol: "CIFR",
  latest: { symbol: "CIFR", close: 22.79, ema20: 21.89, rsi14: 51.71 },
  series: [
    { date: "2026-07-30", close: 24.08, high: 24.5, low: 23.5 },
    { date: "2026-07-31", close: 22.79, high: 24.53, low: 21.98 },
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
  __mapRow: (row) => ({ price: row.close, dayPct: null, ticker: row.symbol }),
  __buildAlertItems: () => [{ id: "live-alert" }],
  __toNum: (value) => {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  },
  __renderAll: () => { renderCount += 1; },
  __fetch: async (url) => {
    if (/data\/screener_snapshot\.json/.test(url)) {
      snapshotFetchCount += 1;
      return {
        ok: true,
        status: 200,
        text: async () => JSON.stringify(snapshot),
      };
    }
    if (/data\/technical\/symbols\/CIFR\.json/.test(url)) {
      shardFetchCount += 1;
      return {
        ok: true,
        status: 200,
        text: async () => JSON.stringify(shard),
      };
    }
    throw new Error(`unexpected fetch: ${url}`);
  },
};
vm.createContext(context);
vm.runInContext(`
  var state = globalThis.__state;
  var fetchStaticLayer = globalThis.__fetchStaticLayer;
  var loadStaticData = globalThis.__loadStaticData;
  var currentQuoteFor = globalThis.__currentQuoteFor;
  var mapRow = globalThis.__mapRow;
  var buildAlertItems = globalThis.__buildAlertItems;
  var toNum = globalThis.__toNum;
  var renderAll = globalThis.__renderAll;
  var fetch = globalThis.__fetch;
  ${runtime}
  globalThis.__runtimeFetchStaticLayer = fetchStaticLayer;
  globalThis.__runtimeCurrentQuoteFor = currentQuoteFor;
  globalThis.__runtimeMapRow = mapRow;
  globalThis.__runtimeBuildAlertItems = buildAlertItems;
`, context, { filename: "technical-shards-v2.js" });

(async () => {
  const technical = await context.__runtimeFetchStaticLayer("technical");
  assert.equal(snapshotFetchCount, 1, "screener must load the canonical snapshot first");
  assert.equal(technical.__screenerSnapshot, true);
  assert.equal(technical.__screenerFresh, true);
  assert.equal(technical.rows[0].price, 493.23);

  const mapped = context.__runtimeMapRow(technical.rows[0]);
  assert.equal(mapped.price, 493.23, "canonical live price must override technical close");
  assert.equal(mapped.dayPct, 0.6592, "canonical day change must reach screener and alerts");
  assert.equal(mapped.screenerSnapshotFresh, true);
  assert.equal(context.__runtimeBuildAlertItems().length, 1, "fresh snapshot may produce alerts");

  const tableQuote = context.__runtimeCurrentQuoteFor("NVDA");
  assert.equal(tableQuote.fundamental.revenue, 130000000000);
  assert.equal(shardFetchCount, 0, "rendering a non-selected table row must not fetch its shard");

  const summary = context.__runtimeCurrentQuoteFor("CIFR");
  assert.equal(summary.fundamental.revenue, 151000000);

  const loaded = await context.window.StockcheckTechnicalV2.loadTechnicalShard("CIFR");
  assert.equal(shardFetchCount, 1, "selected summary-only quote must fetch its technical shard once");
  assert.equal(loaded.series.length, 2);
  assert.equal(loaded.latest.close, 22.645, "detail header must retain canonical live price");
  assert.equal(loaded.series.at(-1).close, 22.645, "last chart candle must project canonical live price");
  assert.equal(loaded.series.at(-1).__snapshotProjected, true);
  assert.equal(loaded.latest.score, 81, "detail score must match screener snapshot");
  assert.equal(loaded.latest.pe, 31.2, "technical merge must preserve existing latest fields");
  assert.equal(loaded.fundamental.revenue, 151000000, "technical merge must preserve fundamentals");
  assert.equal(loaded.__technicalV2Loaded, true);
  assert.equal(renderCount, 1, "chart data arrival must rerender the detail view");

  const cached = await context.window.StockcheckTechnicalV2.loadTechnicalShard("CIFR");
  assert.equal(cached.series.length, 2);
  assert.equal(shardFetchCount, 1, "loaded series must be cached for the page session");

  context.window.StockcheckTechnicalV2.getSnapshot().generated_at = "2020-01-01T00:00:00Z";
  assert.equal(context.window.StockcheckTechnicalV2.snapshotIsFresh(), false);
  assert.equal(context.__runtimeBuildAlertItems().length, 0, "stale snapshot must suppress technical alerts");

  console.log("canonical screener runtime test passed: live overview + consistent lazy detail + stale alert gate");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
