#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
STATIC = ROOT / "static"
ASSETS = (
    "attention-p0.js",
    "attention-p0.css",
    "attention-pr3.js",
    "attention-pr3.css",
    "today-view-isolation.css",
    "memo-only-fix.js",
    "memo-only-fix.css",
)


def main() -> None:
    STATIC.mkdir(parents=True, exist_ok=True)
    for name in ASSETS:
        source = SITE / name
        target = STATIC / name
        if not source.exists():
            raise SystemExit(f"Missing Today asset: {source}")
        shutil.copyfile(source, target)
        print(f"Synced {name}")


if __name__ == "__main__":
    main()
