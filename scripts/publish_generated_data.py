#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "generated"
TARGETS = [ROOT / "site" / "data", ROOT / "static" / "data"]

# Files with their own validated production workflow must never be republished
# by the generic generated-data layer. Market Pulse is written only by
# refresh-market-pulse-v9-2.yml at 08:00 and 20:00 ICT.
EXCLUDED = {"market_pulse.json"}


def publishable_files(source: Path = SOURCE) -> list[Path]:
    return sorted(path for path in source.glob("*.json") if path.name not in EXCLUDED)


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Generated data directory not found: {SOURCE}")
    for target in TARGETS:
        target.mkdir(parents=True, exist_ok=True)
        for src in publishable_files():
            shutil.copy2(src, target / src.name)
            print("published", target / src.name)
        for name in sorted(EXCLUDED):
            if (SOURCE / name).exists():
                print("skipped dedicated-pipeline file", name)


if __name__ == "__main__":
    main()
