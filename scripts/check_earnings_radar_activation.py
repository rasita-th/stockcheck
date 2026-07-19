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


loader = read("site/memo-only-fix.js")
styles = read("site/memo-only-fix.css")
deploy = read(".github/workflows/deploy-pages.yml")

for token in (
    'earnings-radar-pr4.js?v=10.5.1',
    "loadEarningsRadar",
    'loadScript("attention-pr4.js?v=10.4.3", "attentionPr4Loader", loadEarningsRadar)',
):
    if token not in loader:
        errors.append(f"production loader missing: {token}")
if 'earnings-radar-pr4.css?v=10.5.1' not in styles:
    errors.append("production stylesheet does not import Earnings Radar 10.5.1")

for token in (
    'TODAY_DEPLOY_VERSION: "10.5.5"',
    "node --check site/earnings-radar-pr4.js",
    "test -s site/earnings-radar-pr4.js",
    "test -s site/earnings-radar-pr4.css",
    "test -s site/data/earnings_radar.json",
    "earnings-radar-pr4.js?smoke=",
    "earnings-radar-pr4.css?smoke=",
    "earnings_radar.json?smoke=",
    "StockcheckEarningsRadarP4",
    "earnings_radar_schema",
    "earnings_published_rows",
):
    if token not in deploy:
        errors.append(f"Pages activation guard missing: {token}")

for relative in (
    "data/generated/earnings_radar.json",
    "site/data/earnings_radar.json",
    "static/data/earnings_radar.json",
):
    path = ROOT / relative
    if not path.exists():
        errors.append(f"missing activation data: {relative}")
        continue
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"invalid activation data {relative}: {exc}")
        continue
    window = payload.get("window") if isinstance(payload.get("window"), dict) else {}
    coverage = payload.get("coverage") if isinstance(payload.get("coverage"), dict) else {}
    if int(window.get("days_forward") or 0) < 45:
        errors.append(f"activation data is not a 45-day contract: {relative}")
    if int(coverage.get("market_source_rows") or 0) <= int(coverage.get("portfolio_total") or 0):
        errors.append(f"activation data is not market-wide: {relative}")

if errors:
    print("Earnings Radar activation contract failed:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    raise SystemExit(1)
print("Earnings Radar activation contract passed")

