#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
VERSION = "9.4.5"

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
    "thai-time-v9-3-3.js", "thai-time-v9-3-4.js",
    "desktop-layout-v9-4-3.css",
)


def strip_asset(html: str, asset: str) -> str:
    html = re.sub(rf"\s*<link[^>]+{re.escape(asset)}[^>]*>", "", html, flags=re.I)
    html = re.sub(rf"\s*<script[^>]+{re.escape(asset)}[^>]*></script>", "", html, flags=re.I)
    return html


def cache_bust(html: str, asset: str) -> str:
    return re.sub(rf'({re.escape(asset)})(?:\?[^"\']*)?', rf'\1?v={VERSION}', html, flags=re.I)


def inject_once(html: str, pattern: str, tag: str, before: str) -> str:
    html = re.sub(pattern, "", html, flags=re.I)
    return re.sub(before, f"\n  {tag}\n{before}", html, count=1, flags=re.I)


def prepare_index(path: Path) -> None:
    html = path.read_text(encoding="utf-8")
    for asset in LEGACY_ASSETS:
        html = strip_asset(html, asset)
    for asset in ("styles.css", "app.js", "shared-app-shell-v9-3-6.css", "shared-app-shell-v9-3-6.js"):
        html = cache_bust(html, asset)
    html = inject_once(
        html,
        r'\s*<link[^>]+mobile-nav-v9-4-2\.css[^>]*>',
        f'<link rel="stylesheet" href="mobile-nav-v9-4-2.css?v={VERSION}">',
        r'</head>',
    )
    html = inject_once(
        html,
        r'\s*<script[^>]+runtime-guard-v9-4-1\.js[^>]*></script>',
        f'<script src="runtime-guard-v9-4-1.js?v={VERSION}" defer></script>',
        r'</body>',
    )
    path.write_text(html, encoding="utf-8")


def prepare_market(path: Path) -> None:
    html = path.read_text(encoding="utf-8")
    for asset in LEGACY_ASSETS:
        html = strip_asset(html, asset)
    for asset in ("market.css", "market.js", "shared-app-shell-v9-3-6.css", "shared-app-shell-v9-3-6.js"):
        html = cache_bust(html, asset)
    html = inject_once(
        html,
        r'\s*<script[^>]+runtime-guard-v9-4-1\.js[^>]*></script>',
        f'<script src="runtime-guard-v9-4-1.js?v={VERSION}" defer></script>',
        r'</body>',
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


def main() -> None:
    prepare_index(SITE / "index.html")
    prepare_market(SITE / "market.html")
    validate_data()
    print(f"Prepared source-level recovery v{VERSION} Pages artifact")


if __name__ == "__main__":
    main()
