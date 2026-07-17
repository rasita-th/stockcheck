#!/usr/bin/env python3
from __future__ import annotations

import tempfile
from pathlib import Path

from publish_generated_data import EXCLUDED, publishable_files


def main() -> None:
    assert "market_pulse.json" in EXCLUDED
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp)
        for name in ("technical.json", "health.json", "market_pulse.json"):
            (source / name).write_text("{}\n", encoding="utf-8")
        names = [path.name for path in publishable_files(source)]
        assert names == ["health.json", "technical.json"], names
        assert "market_pulse.json" not in names
    print("Generic publisher exclusion test passed")


if __name__ == "__main__":
    main()
