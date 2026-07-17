#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED_FILES = (
    "index.html",
    "styles.css",
    "app.js",
    "market.html",
    "market.css",
    "market.js",
    "data/technical.json",
    "data/fundamental.json",
)

LEGACY_TOKENS = (
    "scanner-dashboard-v9-3",
    "scanner-layout-v9-3",
    "nav-fix-v9-2",
)

REQUIRED_NAV = ("Scanner", "Today", "Memo", "Market Pulse")


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def validate_json(path: Path, require_rows: bool) -> int:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"{path}: invalid JSON: {exc}")
    rows = data.get("rows")
    if not isinstance(rows, list):
        fail(f"{path}: rows must be a list")
    if require_rows and not rows:
        fail(f"{path}: rows are empty")
    return len(rows)


def duplicate_ids(html: str) -> list[str]:
    ids = re.findall(r'\bid=["\']([^"\']+)["\']', html, flags=re.I)
    return sorted({item for item in ids if ids.count(item) > 1})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="site")
    args = parser.parse_args()

    site = Path(args.site)
    if not site.is_dir():
        fail(f"site directory not found: {site}")

    for rel in REQUIRED_FILES:
        path = site / rel
        if not path.is_file() or path.stat().st_size == 0:
            fail(f"missing or empty file: {path}")

    index = (site / "index.html").read_text(encoding="utf-8")
    market = (site / "market.html").read_text(encoding="utf-8")

    duplicates = duplicate_ids(index)
    if duplicates:
        fail(f"duplicate IDs in index.html: {', '.join(duplicates)}")

    for token in LEGACY_TOKENS:
        if token in index:
            fail(f"legacy runtime reference found in index.html: {token}")

    combined = index + "\n" + market
    for label in REQUIRED_NAV:
        if label not in combined:
            fail(f"navigation label missing: {label}")

    technical_count = validate_json(site / "data/technical.json", True)
    fundamental_count = validate_json(site / "data/fundamental.json", False)

    print("PASS")
    print(f"technical rows: {technical_count}")
    print(f"fundamental rows: {fundamental_count}")
    print("navigation labels: Scanner, Today, Memo, Market Pulse")


if __name__ == "__main__":
    main()
