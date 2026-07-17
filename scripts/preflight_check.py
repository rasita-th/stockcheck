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

FORBIDDEN_ARTIFACT_TOKENS = (
    "scanner-dashboard",
    "scanner-layout-v9-3",
    "shared-app-shell-v9-3",
    "nav-fix-v9-2",
    "thai-time-v9-3",
    "runtime-guard-v9-4-1",
    "mobile-nav-v9-4-2",
)

REQUIRED_NAV_LABELS = ("Scanner", "Today", "Memo", "Market Pulse")


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def validate_json(path: Path, require_rows: bool) -> int:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"{path}: invalid JSON: {exc}")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        fail(f"{path}: rows must be a list")
    if require_rows and not rows:
        fail(f"{path}: rows are empty")
    return len(rows)


def duplicate_ids(html: str) -> list[str]:
    ids = re.findall(r'\bid=["\']([^"\']+)["\']', html, flags=re.I)
    counts: dict[str, int] = {}
    for value in ids:
        counts[value] = counts.get(value, 0) + 1
    return sorted(value for value, count in counts.items() if count > 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the prepared GitHub Pages artifact")
    parser.add_argument("--site", default="site", help="Prepared site directory")
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
    combined = index + "\n" + market

    duplicates = duplicate_ids(index)
    if duplicates:
        fail(f"duplicate IDs in prepared index.html: {', '.join(duplicates)}")

    for token in FORBIDDEN_ARTIFACT_TOKENS:
        if token in combined:
            fail(f"legacy runtime remains in prepared artifact: {token}")

    for label in REQUIRED_NAV_LABELS:
        if label not in combined:
            fail(f"navigation label missing from prepared artifact: {label}")

    technical_count = validate_json(site / "data/technical.json", require_rows=True)
    fundamental_count = validate_json(site / "data/fundamental.json", require_rows=False)

    print("PASS: prepared Pages artifact")
    print(f"technical rows: {technical_count}")
    print(f"fundamental rows: {fundamental_count}")
    print("navigation: Scanner, Today, Memo, Market Pulse")


if __name__ == "__main__":
    main()
