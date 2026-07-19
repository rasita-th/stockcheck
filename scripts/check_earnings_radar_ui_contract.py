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

if site_js and static_js and site_js != static_js:
    errors.append("site/static mismatch: earnings-radar-pr4.js")
if site_css and static_css and site_css != static_css:
    errors.append("site/static mismatch: earnings-radar-pr4.css")

for token in (
    "PERSONAL_STORAGE",
    "loadPersonalTickers",
    "personaliseItem",
    "personalisedItems",
    "source_relation",
    'window.addEventListener("stockcheck:portfolio-change"',
    'window.addEventListener("storage"',
    "state.personalTickers.size",
):
    if token not in site_js:
        errors.append(f"missing local portfolio personalization: {token}")

for token in (
    'const VERSION = "10.7.1"',
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
    "เกี่ยวข้องกับหุ้นของคุณ",
    "หุ้นในพอร์ตใกล้ประกาศ",
    "StockcheckCompanyLogo",
    "tickerMark",
):
    if token not in site_js:
        errors.append(f"Earnings Radar runtime missing: {token}")

for token in (
    ".er-radar",
    ".er-stat-grid",
    ".er-calendar",
    ".er-table-wrap",
    ".er-mobile-list",
    ".er-relation-portfolio",
    ".er-relation-related",
    ".er-dialog",
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
    window = payload.get("window") if isinstance(payload.get("window"), dict) else {}
    if int(window.get("days_forward") or 0) < 45:
        errors.append(f"earnings radar publish window is shorter than 45 days: {relative}")

if errors:
    print("Earnings Radar UI contract failed:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    raise SystemExit(1)
print("Earnings Radar UI contract passed")
