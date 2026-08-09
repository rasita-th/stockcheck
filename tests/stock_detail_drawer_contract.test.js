"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");

const coordinatorJs = read("site/final-ui-coordinator.js");
const coordinatorCss = read("site/final-ui-coordinator.css");
const appJs = read("site/app.js");

// Drawer geometry: this is an edge-anchored surface, not a centered modal.
for (const token of [
  "inset: 0 0 0 auto;",
  "width: clamp(760px, 62vw, 1180px);",
  "height: 100dvh;",
  "border-radius: 18px 0 0 18px;",
  "transform: translate3d(100%, 0, 0);",
  "transform: translate3d(0, 0, 0);",
]) {
  assert.ok(coordinatorCss.includes(token), `Stock Detail drawer CSS missing: ${token}`);
}
assert.ok(!coordinatorCss.includes("inset: 5vh max(24px, 4vw) auto auto;"), "legacy floating modal inset must be removed");

// Decision surface: the top of the drawer must be grouped into real decision zones.
for (const token of [
  "syncStockDetailDecisionSurface",
  "stock-detail-decision-grid",
  "detail-decision-price",
  "detail-decision-context",
  "detail-score-dial",
  "detail-decision-metrics",
  "rangePositionPct",
  "52-week position",
]) {
  assert.ok(coordinatorJs.includes(token), `Stock Detail decision-surface runtime missing: ${token}`);
}

// Motion + responsive interaction contracts.
for (const token of [
  "DRAWER_TRANSITION_MS",
  "mobile-detail-drag-handle",
  "#mobileDetailModal.full-modal",
]) {
  assert.ok(coordinatorJs.includes(token) || coordinatorCss.includes(token), `Stock Detail responsive drawer contract missing: ${token}`);
}

// Do not trade away existing functional content for the redesign.
for (const token of [
  'data-detail-tab="technical"',
  'data-detail-tab="setup"',
  'data-detail-tab="fundamental"',
  'data-detail-tab="playbook"',
  'chartPanel("RSI(14)"',
  'chartPanel("MACD(12,26,9)"',
  'chartPanel("VOL(5,10)"',
  "priceChartPanel(s)",
]) {
  assert.ok(appJs.includes(token), `Existing Stock Detail behavior must remain available: ${token}`);
}

console.log("stock detail drawer contract passed");
