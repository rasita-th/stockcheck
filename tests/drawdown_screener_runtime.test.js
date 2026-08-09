"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const runtime = fs.readFileSync(path.join(root, "site", "drawdown-screener-v10-9.js"), "utf8");

let drawdownCell = null;
const row = {
  dataset: { select: "NVDA" },
  classList: { toggle() {} },
  querySelector(selector) {
    if (selector === "td, th") return { textContent: "100" };
    if (selector === "[data-drawdown-cell]") return drawdownCell;
    return null;
  },
  append(cell) { drawdownCell = cell; },
};
const table = {
  querySelector(selector) {
    if (selector === "thead tr") return { querySelector: () => ({}) };
    return null;
  },
  querySelectorAll(selector) { return selector === "tbody tr" ? [row] : []; },
};

const document = {
  readyState: "complete",
  documentElement: { dataset: {} },
  body: {},
  addEventListener() {},
  querySelector(selector) { return selector === "#technicalTable" ? table : null; },
  querySelectorAll() { return []; },
  createElement() { return { dataset: {}, className: "", textContent: "", title: "" }; },
};

const context = {
  console,
  document,
  window: {
    StockcheckTechnicalV2: {
      drawdownFor(ticker) {
        return ticker === "NVDA"
          ? { status: "complete", currentPct: -8.5, daysSincePeak: 21, asOf: "2026-08-07" }
          : null;
      },
    },
    addEventListener() {},
  },
  localStorage: { getItem: () => null, setItem() {} },
  fetch: async () => ({ ok: true, json: async () => ({ rows: [] }) }),
  MutationObserver: class { observe() {} },
  requestAnimationFrame(callback) { callback(); return 1; },
  cancelAnimationFrame() {},
};

vm.createContext(context);
vm.runInContext(runtime, context, { filename: "drawdown-screener-v10-9.js" });

setImmediate(() => {
  try {
    assert.ok(drawdownCell, "Drawdown renderer must decorate the canonical Scanner row");
    assert.equal(drawdownCell.textContent, "-8.5%", "canonical JSON metric must not render as an em dash");
    assert.equal(document.documentElement.dataset.drawdownScreener, "10.9.1");
    console.log("drawdown screener runtime test passed: mapped canonical metric renders in the table");
  } catch (error) {
    console.error(error);
    process.exitCode = 1;
  }
});
