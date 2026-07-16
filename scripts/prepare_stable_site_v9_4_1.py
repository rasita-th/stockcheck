#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
VERSION = "9.4.6"

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
    html = cache_bust(html, "styles.css")
    html = cache_bust(html, "app.js")
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


def main() -> None:
    prepare_index(SITE / "index.html")
    prepare_market(SITE / "market.html")
    validate_data()
    validate_clean_html()
    print(f"Prepared clean single-runtime Pages artifact v{VERSION}")


if __name__ == "__main__":
    main()
