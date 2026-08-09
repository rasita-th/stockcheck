"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");

const coordinatorJs = read("site/final-ui-coordinator.js");
const drawerCss = read("site/watchlist-add-drawer.css");
const staticDrawerCss = read("static/watchlist-add-drawer.css");
const appJs = read("site/app.js");
const indexHtml = read("site/index.html");

assert.equal(drawerCss, staticDrawerCss, "Watchlist drawer styles must stay mirrored across site/static");

// This utility surface is a narrower right-edge drawer, not a generic bottom sheet.
for (const token of [
  "#bulkAddSheet.bottom-sheet",
  "width:clamp(360px, 36vw, 520px);",
  "height:100dvh;",
  "inset:0 0 0 auto",
  "border-radius:18px 0 0 18px",
  "translate3d(100%, 0, 0)",
]) {
  assert.ok(drawerCss.includes(token), `Watchlist Add drawer CSS missing: ${token}`);
}

// Parser feedback must use the existing parser contract rather than inventing a second parser.
for (const token of [
  "syncWatchlistAddDrawer",
  "parseTickerList",
  "bulk-parser-feedback",
  "bulk-parsed-symbols",
  "symbols recognized",
  "data-remove-bulk-symbol",
  "watchlist-drawer-actions",
  "bulk-danger-zone",
  "watchlist-add-drawer.css",
]) {
  assert.ok(coordinatorJs.includes(token), `Watchlist Add parser/action hierarchy missing: ${token}`);
}
assert.ok(!coordinatorJs.includes("split(/[\\s,;|、，]+/)"), "Coordinator must not duplicate the ticker parser regex");

// Existing action/data contracts remain the single behavior owner.
for (const token of [
  "function parseTickerList",
  "function addSymbolsBulk",
  "function clearWatchlist",
  "data-import-symbols",
  "data-replace-symbols",
  "data-clear-symbols",
  "data-clear-watchlist",
]) {
  assert.ok(appJs.includes(token) || indexHtml.includes(token), `Existing Watchlist action contract must remain: ${token}`);
}

// Other generic sheets must not be globally converted to drawers. A drawer rule is valid
// only when the selector is explicitly scoped to #bulkAddSheet.
const unscopedDrawerRule = /(^|})\s*\.bottom-sheet\s*\{[^}]*\binset\s*:\s*0\s+0\s+0\s+auto/mi;
assert.ok(!unscopedDrawerRule.test(drawerCss), "Do not convert every bottom sheet into a right drawer");

console.log("watchlist add drawer contract passed");
