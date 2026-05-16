#!/usr/bin/env python3
"""Generate fast technical data for GitHub Pages.

This script is designed for the 15-minute GitHub Actions workflow.
It intentionally disables SEC fundamentals so the frequent workflow stays fast.

Outputs:
  site/data/technical.json
  site/data/scanner.json  (compatibility pointer for older UI)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

# Disable heavy fundamentals before importing app.py.
os.environ["INCLUDE_FUNDAMENTALS"] = "0"
os.environ.setdefault("SCAN_WORKERS", os.environ.get("TECHNICAL_SCAN_WORKERS", "8"))

ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = ROOT / "site" / "data"
WATCHLIST = ROOT / "watchlist.txt"
sys.path.insert(0, str(ROOT))

from app import scan_symbols  # noqa: E402


def read_watchlist() -> list[str]:
    if not WATCHLIST.exists():
        return ["NVDA", "PLTR", "TSLA", "TSM", "COST", "MSFT", "AMZN", "ORCL", "HOOD", "MSTR"]
    symbols: list[str] = []
    for raw in WATCHLIST.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Support v1-style pasted lists: commas, semicolons, spaces, tabs, or new lines.
        for part in re.split(r"[\s,;]+", line):
            symbol = part.strip().upper()
            if symbol and symbol not in symbols:
                symbols.append(symbol)
    return symbols


def main() -> None:
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    symbols = read_watchlist()
    range_ = os.environ.get("TECHNICAL_RANGE", "1y")
    interval = os.environ.get("TECHNICAL_INTERVAL", "1d")
    started = time.time()
    payload = scan_symbols(symbols, range_=range_, interval=interval)
    payload.update({
        "mode": "github-pages-hybrid-technical",
        "dataLayer": "technical",
        "generatedAtTechnical": payload.get("generatedAt"),
        "range": range_,
        "interval": interval,
        "note": "Technical layer generated frequently by GitHub Actions. Fundamental fields are merged client-side from fundamental.json.",
        "durationSeconds": round(time.time() - started, 2),
    })
    out = SITE_DATA / "technical.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # Keep scanner.json for backward compatibility with older static UI.
    scanner = dict(payload)
    scanner["mode"] = "github-pages-hybrid-technical-compat-scanner"
    (SITE_DATA / "scanner.json").write_text(json.dumps(scanner, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {out} with {len(payload.get('rows', []))} rows, {len(payload.get('errors', []))} errors in {payload['durationSeconds']}s")


if __name__ == "__main__":
    main()
