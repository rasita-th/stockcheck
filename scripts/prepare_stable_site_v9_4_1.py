#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from generate_earnings_radar import generate as generate_earnings_radar

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
VERSION = "10.7.1"

LEGACY_ASSETS = (
    "nav-fix-v9-2.css", "nav-fix-v9-2.js",
    "scanner-dashboard.css", "scanner-dashboard.js",
    "scanner-dashboard-v9-3-5.css", "scanner-dashboard-v9-3-5.js",
    "scanner-layout-v9-3-1.css", "scanner-layout-v9-3-1.js",
    "scanner-layout-v9-3-2.css", "scanner-layout-v9-3-2.js",
    "scanner-layout-v9-3-5.css", "scanner-layout-v9-3-5.js",
    "scanner-layout-v9-3-7.css", "scanner-layout-v9-3-7.js",
    "shared-app-shell-v9-3-3.css", "shared-app-shell-v9-3-3.js",
    "shared-app-shell-v9-3-4.css", "shared-app-shell-v9-3-4.js",
    "shared-app-shell-v9-3-6.css", "shared-app-shell-v9-3-6.js",
    "thai-time-v9-3-3.js", "thai-time-v9-3-4.js",
    "mobile-nav-v9-4-2.css", "runtime-guard-v9-4-1.js",
    "desktop-layout-v9-4-3.css",
    "app-shell-v9-4-6.css", "app-shell-v9-4-6.js",
)

RUNTIME_ASSETS = (
    "styles.css",
    "app.js",
    "notification-phase2.css",
    "notification-phase2.js",
    "final-ui-coordinator.css",
    "final-ui-coordinator.js",
    "memo-only-fix.css",
    "memo-only-fix.js",
)


def strip_asset(html: str, asset: str) -> str:
    html = re.sub(rf"\s*<link[^>]+{re.escape(asset)}[^>]*>", "", html, flags=re.I)
    html = re.sub(rf"\s*<script[^>]+{re.escape(asset)}[^>]*></script>", "", html, flags=re.I)
    return html


def strip_legacy_markup(html: str) -> str:
    html = re.sub(r"\s*<style[^>]+id=[\"']market-pulse-launch-style[\"'][^>]*>.*?</style>", "", html, flags=re.I | re.S)
    html = re.sub(r"\s*<a[^>]+class=[\"'][^\"']*market-pulse-launch[^\"']*[\"'][^>]*>.*?</a>", "", html, flags=re.I | re.S)
    return html


def cache_bust(html: str, asset: str) -> str:
    return re.sub(rf'({re.escape(asset)})(?:\?[^"\']*)?', rf'\1?v={VERSION}', html, flags=re.I)


def inject_once(html: str, pattern: str, tag: str, before: str) -> str:
    html = re.sub(pattern, "", html, flags=re.I)
    return re.sub(before, f"\n  {tag}\n{before}", html, count=1, flags=re.I)


def prepare_index(path: Path) -> None:
    html = strip_legacy_markup(path.read_text(encoding="utf-8"))
    for asset in LEGACY_ASSETS:
        html = strip_asset(html, asset)
    for asset in RUNTIME_ASSETS:
        html = cache_bust(html, asset)
    html = inject_once(
        html,
        r'\s*<link[^>]+app-shell-v9-4-6\.css[^>]*>',
        f'<link rel="stylesheet" href="app-shell-v9-4-6.css?v={VERSION}">',
        r'</head>',
    )
    html = inject_once(
        html,
        r'\s*<script[^>]+app-shell-v9-4-6\.js[^>]*></script>',
        f'<script src="app-shell-v9-4-6.js?v={VERSION}" defer></script>',
        r'</body>',
    )
    path.write_text(html, encoding="utf-8")


def prepare_market(path: Path) -> None:
    html = strip_legacy_markup(path.read_text(encoding="utf-8"))
    for asset in LEGACY_ASSETS:
        html = strip_asset(html, asset)
    html = cache_bust(html, "market.css")
    html = cache_bust(html, "market.js")
    clean_nav = (
        '<nav class="topnav" aria-label="Primary">'
        '<a href="index.html#scanner">Scanner</a>'
        '<a href="index.html#today">Today</a>'
        '<a href="index.html#memo">Memo</a>'
        '<a class="active" href="market.html" aria-current="page">Market Pulse</a>'
        '</nav>'
    )
    html = re.sub(r'<nav[^>]*class=["\']topnav["\'][^>]*>.*?</nav>', clean_nav, html, count=1, flags=re.I | re.S)
    html = inject_once(
        html,
        r'\s*<link[^>]+app-shell-v9-4-6\.css[^>]*>',
        f'<link rel="stylesheet" href="app-shell-v9-4-6.css?v={VERSION}">',
        r'</head>',
    )
    path.write_text(html, encoding="utf-8")


def prepare_earnings_radar() -> None:
    # This is a deterministic projection of repository state and makes no API
    # calls. Rebuilding it here guarantees every Pages artifact carries the
    # same 45-day contract even when a bot-generated data commit has not yet
    # triggered another Pages run.
    os.environ["EARNINGS_RADAR_DAYS_BACK"] = "1"
    os.environ["EARNINGS_RADAR_DAYS_FORWARD"] = "45"
    payload = generate_earnings_radar()
    window = payload.get("window") if isinstance(payload.get("window"), dict) else {}
    coverage = payload.get("coverage") if isinstance(payload.get("coverage"), dict) else {}
    if int(window.get("days_forward") or 0) < 45:
        raise SystemExit("earnings_radar.json is not a 45-day contract")
    if int(coverage.get("market_source_rows") or 0) <= int(coverage.get("portfolio_total") or 0):
        raise SystemExit("earnings_radar.json is not market-wide")
    print(
        "Prepared Earnings Radar: "
        f"{coverage.get('published_rows', 0)} published rows / "
        f"{coverage.get('market_source_rows', 0)} market-source rows"
    )


def validate_data() -> None:
    for name in ("technical.json", "fundamental.json"):
        path = SITE / "data" / name
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get("rows")
        if not isinstance(rows, list):
            raise SystemExit(f"{name}: rows must be a list")
        if name == "technical.json" and not rows:
            raise SystemExit("technical.json is empty; refusing stable deploy")
        print(f"{name}: {len(rows)} rows")
    pulse = SITE / "data" / "market_pulse.json"
    if not pulse.exists() or pulse.stat().st_size < 100:
        raise SystemExit("market_pulse.json missing/empty; refusing stable deploy")
    json.loads(pulse.read_text(encoding="utf-8"))
    radar = SITE / "data" / "earnings_radar.json"
    if not radar.exists() or radar.stat().st_size < 100:
        raise SystemExit("earnings_radar.json missing/empty; refusing stable deploy")
    json.loads(radar.read_text(encoding="utf-8"))


def validate_clean_html() -> None:
    index = (SITE / "index.html").read_text(encoding="utf-8")
    market = (SITE / "market.html").read_text(encoding="utf-8")
    forbidden = ("scanner-dashboard", "scanner-layout-v9-3", "shared-app-shell-v9-3", "nav-fix-v9-2", "thai-time-v9-3", "runtime-guard-v9-4-1", "mobile-nav-v9-4-2")
    for token in forbidden:
        if token in index or token in market:
            raise SystemExit(f"legacy runtime remains in Pages artifact: {token}")
    for token in ("Scanner", "Today", "Memo", "Market Pulse"):
        if token not in market:
            raise SystemExit(f"market navigation missing: {token}")
    for token in ('id="marketBriefing"', 'data-pulse-mode="balanced"', 'data-pulse-mode="portfolio"', 'id="pulseSummaryList"'):
        if token not in market:
            raise SystemExit(f"market briefing contract missing: {token}")
    for asset in RUNTIME_ASSETS:
        if f"{asset}?v={VERSION}" not in index:
            raise SystemExit(f"runtime asset missing cache-busted reference: {asset}")
    for asset in ("market.css", "market.js"):
        if f"{asset}?v={VERSION}" not in market:
            raise SystemExit(f"market asset missing cache-busted reference: {asset}")


def main() -> None:
    prepare_index(SITE / "index.html")
    prepare_market(SITE / "market.html")
    prepare_earnings_radar()
    validate_data()
    validate_clean_html()
    print(f"Prepared clean single-runtime Pages artifact v{VERSION}")


if __name__ == "__main__":
    main()
