#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "generated"
TARGETS = [ROOT / "site" / "data", ROOT / "static" / "data"]

def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Generated data directory not found: {SOURCE}")
    for target in TARGETS:
        target.mkdir(parents=True, exist_ok=True)
        for src in SOURCE.glob("*.json"):
            shutil.copy2(src, target / src.name)
            print("published", target / src.name)

if __name__ == "__main__":
    main()
