#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []


def read(path: str) -> str:
    target = ROOT / path
    if not target.exists():
        errors.append(f"missing: {path}")
        return ""
    return target.read_text(encoding="utf-8")


site_js = read("site/earnings-radar-pr4.js")
static_js = read("static/earnings-radar-pr4.js")
site_css = read("site/earnings-radar-pr4.css")
static_css = read("static/earnings-radar-pr4.css")
site_guard = read("site/earnings-radar-error-guard.js")
static_guard = read("static/earnings-radar-error-guard.js")
loader = read("site/memo-only-fix.js")

for label, site_text, static_text in (
    ("earnings-radar-pr4.js", site_js, static_js),
    ("earnings-radar-pr4.css", site_css, static_css),
    ("earnings-radar-error-guard.js", site_guard, static_guard),
):
    if site_text and static_text and site_text != static_text:
        errors.append(f"site/static mismatch: {label}")

for token in (
    'const VERSION = "10.5.0"',
    'const DATA_URL = "data/earnings_radar.json"',
    "chooseInitialDate",
    "daily_summary",
    "data-er-date-input",
    "data-er-filter",
    "data-er-export",
    "data-er-details",
    "data-er-load-more",
    "StockcheckEarningsRadarP4",
    "Earnings Radar",
    "Earnings Calendar",
    "เกี่ยวข้องกับพอร์ตคุณ",
    "หุ้นในพอร์ตใกล้ประกาศ",
):
    if token not in site_js:
        errors.append(f"Earnings Radar runtime missing: {token}")

for token in (
    'const VERSION = "10.5.1"',
    "ยังเปิด Earnings Radar ไม่ได้",
    "data-er-error-retry",
    "StockcheckEarningsRadarErrorGuard",
    "ensureVisibleError",
):
    if token not in site_guard:
        errors.append(f"Earnings Radar error guard missing: {token}")
if 'earnings-radar-error-guard.js?v=10.5.1' not in loader:
    errors.append("production loader does not load the Earnings Radar error guard")

for token in (
    ".er-radar",
    ".er-stat-grid",
    ".er-calendar",
    ".er-table-wrap",
    ".er-mobile-list",
    ".er-relation-portfolio",
    ".er-relation-related",
    ".er-dialog",
    ".er-error",
):
    if token not in site_css:
        errors.append(f"Earnings Radar stylesheet missing: {token}")

for forbidden in (
    "146",
    "327 / 408",
    "technical_json",
    "Unverified report",
    "👑",
    "📈",
    "📅",
    "sparkline",
):
    if forbidden.lower() in site_js.lower():
        errors.append(f"Earnings Radar contains hard-coded/decorative token: {forbidden}")

if "<svg" not in site_js:
    errors.append("Earnings Radar must use the shared line-icon vocabulary")
if "Blob([" not in site_js or "text/csv" not in site_js:
    errors.append("Earnings Radar CSV export is missing")
if "MutationObserver" not in site_js:
    errors.append("Earnings Radar must reattach after PR4 rerenders")

optional_fields = (
    "eps_actual",
    "eps_estimate",
    "revenue_actual",
    "revenue_estimate",
    "source_url",
)
for relative in (
    "data/generated/earnings_radar.json",
    "site/data/earnings_radar.json",
    "static/data/earnings_radar.json",
):
    path = ROOT / relative
    if not path.exists():
        errors.append(f"missing data contract: {relative}")
        continue
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"invalid data contract {relative}: {exc}")
        continue
    if not isinstance(payload, dict) or not str(payload.get("schema_version") or "").startswith("1.0"):
        errors.append(f"unsupported earnings radar schema: {relative}")
        continue
    window = payload.get("window") if isinstance(payload.get("window"), dict) else {}
    coverage = payload.get("coverage") if isinstance(payload.get("coverage"), dict) else {}
    if int(window.get("days_forward") or 0) < 45:
        errors.append(f"earnings radar publish window is shorter than 45 days: {relative}")
    if int(coverage.get("market_rows_in_window") or 0) <= 0:
        errors.append(f"earnings radar has no in-window market rows: {relative}")
    if coverage.get("provider_window_overlaps_publish_window") is not True:
        errors.append(f"earnings radar does not prove provider-window overlap: {relative}")
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            errors.append(f"earnings radar item is not an object: {relative}")
            continue
        for field in optional_fields:
            if field not in item:
                errors.append(f"earnings radar optional field missing ({field}): {relative} {item.get('ticker')}")

if errors:
    print("Earnings Radar UI contract failed:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    raise SystemExit(1)
print("Earnings Radar UI contract passed")
