#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "data" / "generated"


def first_existing(*paths: Path) -> Path | None:
    return next((path for path in paths if path.exists() and path.stat().st_size > 0), None)


def main() -> None:
    GEN.mkdir(parents=True, exist_ok=True)
    seeds = {
        "technical.json": first_existing(ROOT / "site/data/technical.json", ROOT / "static/data/technical.json", ROOT / "data/technical.json"),
        "scanner.json": first_existing(ROOT / "site/data/scanner.json", ROOT / "static/data/scanner.json", ROOT / "data/scanner.json"),
        "attention_today.json": first_existing(ROOT / "site/data/attention_today.json", ROOT / "static/data/attention_today.json", ROOT / "data/attention_today.json"),
        "events.json": first_existing(ROOT / "site/data/events.json", ROOT / "static/data/events.json", ROOT / "data/events.json"),
        "recommendation_trends.json": first_existing(ROOT / "site/data/recommendation_trends.json", ROOT / "static/data/recommendation_trends.json", ROOT / "data/recommendation_trends.json"),
        "fundamental.json": first_existing(ROOT / "site/data/fundamental.json", ROOT / "static/data/fundamental.json", ROOT / "data/fundamental.json"),
        "market_pulse.json": first_existing(ROOT / "site/data/market_pulse.json", ROOT / "static/data/market_pulse.json", ROOT / "data/market_pulse.json"),
    }
    for name, source in seeds.items():
        destination = GEN / name
        if not destination.exists() and source:
            shutil.copy2(source, destination)
            print("seeded", destination, "from", source)


if __name__ == "__main__":
    main()
