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
const intervals = [];
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
  schema_version: "1.1",
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
      drawdown: {
        schemaVersion: "1.0",
        status: "complete",
        currentPct: -8.5,
        maxPct: -31.2,
        daysSincePeak: 21,
        observations: 251,
        asOf: "2026-08-07",
      },
      drawdownCurrentPct: -8.5,
      drawdownMaxPct: -31.2,
      drawdownDaysSincePeak: 21,
      drawdownAsOf: "2026-08-07",
      drawdownStatus: "complete",
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
let servedSnapshot = snapshot;

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
  __mergeStaticPayloads: (technical) => {
    state.rows = technical.rows;
  },
  setInterval: (callback, delay) => {
    intervals.push({ callback, delay });
    return intervals.length;
  },
  __fetch: async (url) => {
    if (/data\/screener_snapshot\.json/.test(url)) {
      snapshotFetchCount += 1;
      return {
        ok: true,
        status: 200,
        text: async () => JSON.stringify(servedSnapshot),
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
  var mergeStaticPayloads = globalThis.__mergeStaticPayloads;
  var fetch = globalThis.__fetch;
  ${runtime}
  globalThis.__runtimeFetchStaticLayer = fetchStaticLayer;
  globalThis.__runtimeCurrentQuoteFor = currentQuoteFor;
  globalThis.__runtimeMapRow = mapRow;
  globalThis.__runtimeBuildAlertItems = buildAlertItems;
`, context, { filename: "technical-shards-v2.js" });

(async () => {
  const technical = await context.__runtimeFetchStaticLayer("technical");
  assert.equal(snapshotFetchCount, 1, "schema 1.1 snapshot must activate without a reload loop");
  assert.equal(technical.__screenerSnapshot, true);
  assert.equal(technical.__screenerFresh, true);
  assert.equal(technical.rows[0].price, 493.23);
  assert.equal(context.window.StockcheckTechnicalV2.version, "10.7.9");
  assert.equal(context.window.StockcheckTechnicalV2.snapshotSchema, "1.1");

  const mapped = context.__runtimeMapRow(technical.rows[0]);
  assert.equal(mapped.price, 493.23, "canonical live price must override technical close");
  assert.equal(mapped.dayPct, 0.6592, "canonical day change must reach screener and alerts");
  assert.equal(mapped.drawdown.currentPct, -8.5, "canonical drawdown must reach the UI row model");
  assert.equal(mapped.drawdown.daysSincePeak, 21, "row model must retain drawdown context");
  assert.equal(context.window.StockcheckTechnicalV2.drawdownFor("AMD").currentPct, -8.5, "Drawdown UI must read the mapped row metric");
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

  const fridayCloseSnapshot = {
    ...snapshot,
    generated_at: "2026-08-07T19:55:00Z",
  };
  const mondayPreOpen = new Date("2026-08-10T13:00:00Z");
  const mondayMarketOpen = new Date("2026-08-10T15:00:00Z");
  assert.equal(
    context.window.StockcheckTechnicalV2.freshnessState(fridayCloseSnapshot, mondayPreOpen).status,
    "latest-completed-session",
    "Friday close must remain usable before Monday opens",
  );
  assert.equal(
    context.window.StockcheckTechnicalV2.freshnessState(fridayCloseSnapshot, mondayMarketOpen).status,
    "stale",
    "Friday data must stop driving alerts once Monday is open",
  );

  const laborDay = new Date("2026-09-07T15:00:00Z");
  const preHolidaySnapshot = { ...snapshot, generated_at: "2026-09-04T19:55:00Z" };
  assert.equal(
    context.window.StockcheckTechnicalV2.freshnessState(preHolidaySnapshot, laborDay).status,
    "latest-completed-session",
    "the last completed session must remain usable on a US market holiday",
  );
  assert.equal(
    context.window.StockcheckTechnicalV2.freshnessState({ rows: [] }, mondayPreOpen).status,
    "unavailable",
    "invalid contracts must fail closed",
  );

  context.window.StockcheckTechnicalV2.getSnapshot().generated_at = "2020-01-01T00:00:00Z";
  assert.equal(context.window.StockcheckTechnicalV2.snapshotIsFresh(), false);
  assert.equal(context.__runtimeBuildAlertItems().length, 0, "stale snapshot must suppress technical alerts");

  const refreshTimer = intervals.find((entry) => entry.delay === 5 * 60 * 1000);
  assert.ok(refreshTimer, "runtime must poll the canonical snapshot every five minutes");
  servedSnapshot = {
    ...snapshot,
    generated_at: new Date(Date.now() + 60_000).toISOString(),
    rows: snapshot.rows.map((row) => row.symbol === "CIFR" ? { ...row, price: 23.5, close: 23.5 } : row),
  };
  const rendersBeforeRefresh = renderCount;
  await refreshTimer.callback();
  assert.equal(context.window.StockcheckTechnicalV2.getSnapshot().rows[1].price, 23.5);
  assert.equal(state.rows[1].price, 23.5, "newer snapshot must replace the canonical application rows");
  assert.equal(context.__runtimeBuildAlertItems().length, 1, "the open tab must recover alerts after a fresh publish");
  assert.ok(renderCount > rendersBeforeRefresh, "new snapshot must rerender the open page");

  const activeIdentity = context.window.StockcheckTechnicalV2.getSnapshot();
  const rendersBeforeWarmRefresh = renderCount;
  await refreshTimer.callback();
  assert.equal(context.window.StockcheckTechnicalV2.getSnapshot(), activeIdentity, "equal identity must not replace warm-cache state");
  assert.equal(renderCount, rendersBeforeWarmRefresh, "equal identity must not cause a redundant application rerender");

  console.log("canonical screener runtime test passed: schema 1.1 + single fetch + live overview + lazy detail");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
