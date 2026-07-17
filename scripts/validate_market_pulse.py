#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REQUIRED = {
    "global_markets": 3,
    "us_indices": 3,
    "us_sectors": 8,
    "themes": 5,
}
REQUIRED_MODES = ("balanced", "portfolio", "action", "news", "risk")


def is_text(value: Any, minimum: int = 1) -> bool:
    return isinstance(value, str) and len(value.strip()) >= minimum


def validate_narrative(data: dict[str, Any], problems: list[str]) -> None:
    narrative = data.get("narrative")
    if not isinstance(narrative, dict):
        problems.append("narrative: missing/not an object")
        return
    if narrative.get("default_mode") not in REQUIRED_MODES:
        problems.append("narrative.default_mode: invalid")
    if narrative.get("regime") not in {"risk-on", "mixed", "risk-off"}:
        problems.append("narrative.regime: invalid")
    if narrative.get("risk_level") not in {"contained", "moderate", "elevated"}:
        problems.append("narrative.risk_level: invalid")
    refresh = narrative.get("refresh_window_hours")
    if not isinstance(refresh, (int, float)) or not 1 <= float(refresh) <= 48:
        problems.append("narrative.refresh_window_hours: must be between 1 and 48")
    sources = narrative.get("sources")
    if not isinstance(sources, list) or not sources:
        problems.append("narrative.sources: missing/empty")
    elif any(not isinstance(source, dict) or not is_text(source.get("label")) for source in sources):
        problems.append("narrative.sources: each source needs a label")

    modes = narrative.get("modes")
    if not isinstance(modes, dict):
        problems.append("narrative.modes: missing/not an object")
        return
    for key in REQUIRED_MODES:
        mode = modes.get(key)
        if not isinstance(mode, dict):
            problems.append(f"narrative.modes.{key}: missing/not an object")
            continue
        if not is_text(mode.get("headline"), 8):
            problems.append(f"narrative.modes.{key}.headline: too short/missing")
        if not is_text(mode.get("deck"), 8):
            problems.append(f"narrative.modes.{key}.deck: too short/missing")
        summary = mode.get("summary")
        if not isinstance(summary, list) or not 5 <= len(summary) <= 10:
            problems.append(f"narrative.modes.{key}.summary: need 5-10 lines")
        elif any(not is_text(line, 8) for line in summary):
            problems.append(f"narrative.modes.{key}.summary: invalid line")
        for bucket in ("positive", "watch", "risk"):
            value = mode.get(bucket)
            if not isinstance(value, list):
                problems.append(f"narrative.modes.{key}.{bucket}: must be a list")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="data/market_pulse.json")
    parser.add_argument("--min-ok-rate", type=float, default=0.75)
    args = parser.parse_args()
    path = Path(args.path)
    if not path.exists() or path.stat().st_size < 100:
        raise SystemExit(f"invalid or missing JSON: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"cannot parse {path}: {exc}")
    if not isinstance(data, dict):
        raise SystemExit("root must be an object")

    problems: list[str] = []
    for timestamp_key in ("generated_at", "next_refresh_at"):
        value = data.get(timestamp_key)
        if not is_text(value):
            problems.append(f"{timestamp_key}: missing")
            continue
        try:
            datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            problems.append(f"{timestamp_key}: invalid ISO timestamp")

    total = ok = 0
    for key, minimum in REQUIRED.items():
        rows = data.get(key)
        if not isinstance(rows, list):
            problems.append(f"{key}: missing/not a list")
            continue
        if len(rows) < minimum:
            problems.append(f"{key}: {len(rows)} rows, need >= {minimum}")
        for row in rows:
            total += 1
            if not isinstance(row, dict):
                continue
            status = str(row.get("status", "ok")).lower()
            has_identity = bool(row.get("symbol") or row.get("ticker") or row.get("name") or row.get("label"))
            numeric_value = any(
                isinstance(row.get(field), (int, float)) and math.isfinite(row[field])
                for field in ("price", "close", "change_pct", "return_1d", "value")
            )
            if status == "ok" and has_identity and numeric_value:
                ok += 1
    rate = ok / total if total else 0.0
    if rate < args.min_ok_rate:
        problems.append(f"valid row rate {rate:.1%}, need >= {args.min_ok_rate:.0%}")

    validate_narrative(data, problems)
    if problems:
        raise SystemExit("validation failed: " + "; ".join(problems))
    print(
        json.dumps(
            {
                "path": str(path),
                "rows": total,
                "ok": ok,
                "ok_rate": round(rate, 4),
                "groups": {key: len(data[key]) for key in REQUIRED},
                "narrative_modes": list(REQUIRED_MODES),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
