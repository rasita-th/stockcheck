#!/usr/bin/env python3
"""Validate Drawdown additions on canonical screener snapshot schema 1.1."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"{path}: root must be an object")
    return payload


def symbol_of(row: dict[str, Any]) -> str:
    return str(row.get("symbol") or row.get("ticker") or "").strip().upper()


def finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def fail(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--technical", type=Path, required=True)
    parser.add_argument("--compat-output", type=Path, required=True)
    args = parser.parse_args()

    snapshot = load(args.snapshot)
    technical = load(args.technical)
    rows = snapshot.get("rows")
    technical_rows = technical.get("rows")

    fail(snapshot.get("schema_version") == "1.1", "snapshot schema is not 1.1")
    fail(snapshot.get("drawdown_schema_version") == "1.0", "drawdown schema is not 1.0")
    fail(isinstance(rows, list) and bool(rows), "snapshot rows are empty")
    fail(isinstance(technical_rows, list) and len(technical_rows) == len(rows), "technical mirror row count differs")

    technical_map = {
        symbol_of(row): row
        for row in technical_rows
        if isinstance(row, dict) and symbol_of(row)
    }
    available = 0
    invalid: list[str] = []
    mirror_mismatches: list[str] = []

    for row in rows:
        if not isinstance(row, dict):
            invalid.append("non-object-row")
            continue
        symbol = symbol_of(row)
        metric = row.get("drawdown")
        if not symbol or not isinstance(metric, dict):
            invalid.append(f"{symbol or '?'}:missing-drawdown")
            continue
        status = metric.get("status")
        if status in {"complete", "partial-history"}:
            available += 1
            current = finite(metric.get("currentPct"))
            maximum = finite(metric.get("maxPct"))
            observations = metric.get("observations")
            days_since_peak = metric.get("daysSincePeak")
            if current is None or maximum is None or not (-100.0 <= maximum <= current <= 0.0):
                invalid.append(f"{symbol}:domain")
            if not isinstance(observations, int) or observations < 2:
                invalid.append(f"{symbol}:observations")
            if not isinstance(days_since_peak, int) or days_since_peak < 0:
                invalid.append(f"{symbol}:days-since-peak")
            if not str(metric.get("asOf") or ""):
                invalid.append(f"{symbol}:as-of")
        elif status != "unavailable":
            invalid.append(f"{symbol}:status")

        flattened = {
            "drawdownCurrentPct": metric.get("currentPct"),
            "drawdownMaxPct": metric.get("maxPct"),
            "drawdownDaysSincePeak": metric.get("daysSincePeak"),
            "drawdownAsOf": metric.get("asOf"),
            "drawdownStatus": metric.get("status"),
        }
        for key, expected in flattened.items():
            if row.get(key) != expected:
                invalid.append(f"{symbol}:{key}")

        mirrored = technical_map.get(symbol)
        if not isinstance(mirrored, dict):
            mirror_mismatches.append(f"{symbol}:missing")
        else:
            for key in ("drawdown", *flattened.keys()):
                if mirrored.get(key) != row.get(key):
                    mirror_mismatches.append(f"{symbol}:{key}")

    declared_available = snapshot.get("drawdown_available_count")
    declared_coverage = finite(snapshot.get("drawdown_coverage"))
    computed_coverage = available / len(rows)
    fail(declared_available == available, "drawdown available count mismatch")
    fail(declared_coverage is not None and abs(declared_coverage - computed_coverage) <= 0.000001, "drawdown coverage mismatch")
    fail(computed_coverage >= 0.80, f"drawdown coverage too low: {computed_coverage:.1%}")
    fail(not invalid, f"invalid drawdown rows: {invalid[:12]}")
    fail(not mirror_mismatches, f"drawdown mirror mismatch: {mirror_mismatches[:12]}")

    compat = dict(snapshot)
    compat["schema_version"] = "1.0"
    args.compat_output.parent.mkdir(parents=True, exist_ok=True)
    args.compat_output.write_text(json.dumps(compat, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Drawdown snapshot verified: {available}/{len(rows)} rows ({computed_coverage:.1%})")


if __name__ == "__main__":
    main()
