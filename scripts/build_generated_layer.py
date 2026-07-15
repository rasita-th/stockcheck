#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "data" / "generated"
SITE = ROOT / "site" / "data"
STATIC = ROOT / "static" / "data"

MAPPING = {
    ROOT / "site" / "data" / "technical.json": GEN / "technical.json",
    ROOT / "site" / "data" / "scanner.json": GEN / "scanner.json",
    ROOT / "site" / "data" / "attention_today.json": GEN / "attention_today.json",
    ROOT / "site" / "data" / "recommendation_trends.json": GEN / "recommendation_trends.json",
    ROOT / "site" / "data" / "fundamental.json": GEN / "fundamental.json",
    ROOT / "site" / "data" / "market_pulse.json": GEN / "market_pulse.json",
}

def first_existing(*paths: Path) -> Path | None:
    return next((p for p in paths if p.exists() and p.stat().st_size > 0), None)

def main() -> None:
    GEN.mkdir(parents=True, exist_ok=True)
    seeds = {
        "technical.json": first_existing(ROOT/"site/data/technical.json", ROOT/"static/data/technical.json", ROOT/"data/technical.json"),
        "scanner.json": first_existing(ROOT/"site/data/scanner.json", ROOT/"static/data/scanner.json", ROOT/"data/scanner.json"),
        "attention_today.json": first_existing(ROOT/"site/data/attention_today.json", ROOT/"static/data/attention_today.json", ROOT/"data/attention_today.json"),
        "recommendation_trends.json": first_existing(ROOT/"site/data/recommendation_trends.json", ROOT/"static/data/recommendation_trends.json", ROOT/"data/recommendation_trends.json"),
        "fundamental.json": first_existing(ROOT/"site/data/fundamental.json", ROOT/"static/data/fundamental.json", ROOT/"data/fundamental.json"),
        "market_pulse.json": first_existing(ROOT/"site/data/market_pulse.json", ROOT/"static/data/market_pulse.json", ROOT/"data/market_pulse.json"),
    }
    for name, src in seeds.items():
        dst = GEN / name
        if not dst.exists() and src:
            shutil.copy2(src, dst)
            print("seeded", dst, "from", src)

if __name__ == "__main__":
    main()
