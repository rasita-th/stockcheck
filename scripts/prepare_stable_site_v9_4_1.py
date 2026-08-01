#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from generate_earnings_radar import generate as generate_earnings_radar
from finnhub_sharded_state import LEGACY_PATH as FINNHUB_LEGACY_PATH
from finnhub_sharded_state import hydrate_state as hydrate_finnhub_state

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
VERSION = "10.7.3"
TECHNICAL_RUNTIME_VERSION = "10.7.6"
STORAGE_GUARD_ASSET = "storage-guard-v10-7-3.js"

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


def inject_storage_guard(html: str, bootstrap_asset: str) -> str:
    html = re.sub(
        rf"\s*<script[^>]+{re.escape(STORAGE_GUARD_ASSET)}[^>]*></script>",
        "",
        html,
        flags=re.I,
    )
    bootstrap_pattern = rf'(\s*<script[^>]+src=["\']{re.escape(bootstrap_asset)}(?:\?[^"\']*)?["\'][^>]*></script>)'
    if re.search(bootstrap_pattern, html, flags=re.I) is None:
        raise SystemExit(f"{bootstrap_asset} script tag is missing; cannot inject storage guard")
    guard = f'<script src="{STORAGE_GUARD_ASSET}?v={VERSION}"></script>'
    return re.sub(
        bootstrap_pattern,
        lambda match: f"\n  {guard}{match.group(1)}",
        html,
        count=1,
        flags=re.I,
    )


def prepare_index(path: Path) -> None:
    html = strip_legacy_markup(path.read_text(encoding="utf-8"))
    for asset in LEGACY_ASSETS:
        html = strip_asset(html, asset)
    for asset in RUNTIME_ASSETS:
        html = cache_bust(html, asset)
    html = inject_storage_guard(html, "app.js")
    html = inject_once(
        html,
        r'\s*<link[^>]+app-shell-v9-4-6\.css[^>]*>',
        f'<link rel="stylesheet" href="app-shell-v9-4-6.css?v={VERSION}">',
        r'</head>',
    )
    html = inject_once(
        html,
        r'\s*<script[^>]+technical-shards-v2\.js[^>]*></script>',
        f'<script src="technical-shards-v2.js?v={TECHNICAL_RUNTIME_VERSION}" defer></script>',
        r'</body>',
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
    html = inject_storage_guard(html, "market.js")
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
    had_legacy = FINNHUB_LEGACY_PATH.exists()
    if not had_legacy:
        hydrate_finnhub_state()
    try:
        os.environ["EARNINGS_RADAR_DAYS_BACK"] = "1"
        os.environ["EARNINGS_RADAR_DAYS_FORWARD"] = "45"
        payload = generate_earnings_radar()
    finally:
        if not had_legacy:
            FINNHUB_LEGACY_PATH.unlink(missing_ok=True)
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


def validate_technical_runtime(data: dict) -> None:
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        raise SystemExit("technical rows are empty; refusing stable deploy")
    nvda = next((row for row in rows if str(row.get("symbol") or row.get("ticker")).upper() == "NVDA"), None)
    if not isinstance(nvda, dict):
        raise SystemExit("technical index is missing NVDA runtime verification row")
    for key in ("close", "ema20", "rsi14"):
        value = nvda.get(key)
        if not isinstance(value, (int, float)):
            raise SystemExit(f"technical NVDA {key} is not numeric")
    if float(nvda["close"]) <= 0:
        raise SystemExit("technical NVDA close is not positive")

    shard_path = SITE / "data" / "technical" / "symbols" / "NVDA.json"
    if not shard_path.exists():
        raise SystemExit("technical NVDA shard is missing; charts would be empty")
    shard = json.loads(shard_path.read_text(encoding="utf-8"))
    series = shard.get("series")
    if shard.get("schema_version") != "2.0" or shard.get("symbol") != "NVDA":
        raise SystemExit("technical NVDA shard contract is invalid")
    if not isinstance(series, list) or len(series) < 30:
        raise SystemExit("technical NVDA shard has insufficient chart history")
    if not isinstance((shard.get("latest") or {}).get("close"), (int, float)):
        raise SystemExit("technical NVDA shard latest close is missing")
    print(f"technical runtime verified: NVDA close={nvda['close']} series={len(series)}")


def validate_data() -> None:
    technical_index = SITE / "data" / "technical" / "index.json"
    if technical_index.exists():
        data = json.loads(technical_index.read_text(encoding="utf-8"))
        rows = data.get("rows")
        if data.get("schema_version") != "2.0" or not isinstance(rows, list) or not rows:
            raise SystemExit("technical/index.json invalid; refusing stable deploy")
        print(f"technical/index.json: {len(rows)} rows")
    else:
        data = json.loads((SITE / "data" / "technical.json").read_text(encoding="utf-8"))
        rows = data.get("rows")
        if not isinstance(rows, list) or not rows:
            raise SystemExit("technical.json is empty; refusing stable deploy")
        print(f"technical.json: {len(rows)} rows")
    validate_technical_runtime(data)

    fundamental = json.loads((SITE / "data" / "fundamental.json").read_text(encoding="utf-8"))
    if not isinstance(fundamental.get("rows"), list):
        raise SystemExit("fundamental.json: rows must be a list")
    print(f"fundamental.json: {len(fundamental['rows'])} rows")
    pulse = SITE / "data" / "market_pulse.json"
    if not pulse.exists() or pulse.stat().st_size < 100:
        raise SystemExit("market_pulse.json missing/empty; refusing stable deploy")
    json.loads(pulse.read_text(encoding="utf-8"))
    radar = SITE / "data" / "earnings_radar.json"
    if not radar.exists() or radar.stat().st_size < 100:
        raise SystemExit("earnings_radar.json missing/empty; refusing stable deploy")
    json.loads(radar.read_text(encoding="utf-8"))


def validate_guard_order(html: str, bootstrap_asset: str, page_name: str) -> None:
    guard_ref = f"{STORAGE_GUARD_ASSET}?v={VERSION}"
    bootstrap_ref = f"{bootstrap_asset}?v={VERSION}"
    guard_position = html.find(guard_ref)
    bootstrap_position = html.find(bootstrap_ref)
    if guard_position < 0 or bootstrap_position < 0 or guard_position > bootstrap_position:
        raise SystemExit(f"storage guard must load before {bootstrap_asset} on {page_name}")


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
    validate_guard_order(index, "app.js", "index.html")
    validate_guard_order(market, "market.js", "market.html")
    guard_path = SITE / STORAGE_GUARD_ASSET
    if not guard_path.exists() or "__stockcheckStorageMode" not in guard_path.read_text(encoding="utf-8"):
        raise SystemExit("storage compatibility guard is missing or invalid")
    if f"technical-shards-v2.js?v={TECHNICAL_RUNTIME_VERSION}" not in index:
        raise SystemExit("technical v2 runtime missing cache-busted reference")
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
