#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

LEGACY_ASSETS = (
    "nav-fix-v9-2.css",
    "nav-fix-v9-2.js",
    "scanner-dashboard.css",
    "scanner-dashboard.js",
    "scanner-dashboard-v9-3-5.css",
    "scanner-dashboard-v9-3-5.js",
    "scanner-layout-v9-3-1.css",
    "scanner-layout-v9-3-1.js",
    "scanner-layout-v9-3-2.css",
    "scanner-layout-v9-3-2.js",
    "scanner-layout-v9-3-5.css",
    "scanner-layout-v9-3-5.js",
    "scanner-layout-v9-3-7.css",
    "scanner-layout-v9-3-7.js",
    "shared-app-shell-v9-3-3.css",
    "shared-app-shell-v9-3-3.js",
    "shared-app-shell-v9-3-4.css",
    "shared-app-shell-v9-3-4.js",
    "shared-app-shell-v9-3-6.css",
    "shared-app-shell-v9-3-6.js",
    "thai-time-v9-3-3.js",
    "thai-time-v9-3-4.js",
)


def strip_asset(html: str, asset: str) -> str:
    html = re.sub(rf"\s*<link[^>]+{re.escape(asset)}[^>]*>", "", html, flags=re.I)
    html = re.sub(rf"\s*<script[^>]+{re.escape(asset)}[^>]*></script>", "", html, flags=re.I)
    return html


def cache_bust(html: str, asset: str, version: str) -> str:
    return re.sub(
        rf'({re.escape(asset)})(?:\?[^"\']*)?',
        rf'\1?v={version}',
        html,
        flags=re.I,
    )


def ensure_runtime_guard(html: str) -> str:
    tag = '<script src="runtime-guard-v9-4-1.js?v=9.4.1" defer></script>'
    html = re.sub(r"\s*<script[^>]+runtime-guard-v9-4-1\.js[^>]*></script>", "", html, flags=re.I)
    return re.sub(r"</body>", f"\n  {tag}\n</body>", html, count=1, flags=re.I)


def prepare_index(path: Path) -> None:
    html = path.read_text(encoding="utf-8")
    for asset in LEGACY_ASSETS:
        html = strip_asset(html, asset)
    html = cache_bust(html, "styles.css", "9.4.1")
    html = cache_bust(html, "app.js", "9.4.1")
    html = ensure_runtime_guard(html)
    path.write_text(html, encoding="utf-8")


def prepare_market(path: Path) -> None:
    html = path.read_text(encoding="utf-8")
    for asset in LEGACY_ASSETS:
        html = strip_asset(html, asset)
    html = cache_bust(html, "market.css", "9.4.1")
    html = cache_bust(html, "market.js", "9.4.1")
    if 'href="index.html#memo"' not in html:
        html = re.sub(
            r'(<nav[^>]*class="topnav"[^>]*>.*?<a[^>]+href="index\.html#today"[^>]*>Today</a>)',
            r'\1<a href="index.html#memo">Memo</a>',
            html,
            count=1,
            flags=re.I | re.S,
        )
    html = ensure_runtime_guard(html)
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


def main() -> None:
    prepare_index(SITE / "index.html")
    prepare_market(SITE / "market.html")
    validate_data()
    print("Prepared stable v9.4.1 Pages artifact")


if __name__ == "__main__":
    main()
