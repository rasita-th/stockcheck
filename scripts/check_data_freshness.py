#!/usr/bin/env python3
"""Fail a producer when its generated dataset is missing, empty, or stale."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp is missing")
    raw = value.strip()
    if raw.endswith(" UTC"):
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resolve_timestamp(payload: dict[str, Any], fields: list[str]) -> tuple[str, datetime]:
    for field in fields:
        value = payload.get(field)
        if value not in (None, ""):
            return field, parse_timestamp(value)
    raise ValueError(f"none of the timestamp fields are present: {', '.join(fields)}")


def resolve_row_count(payload: dict[str, Any]) -> int:
    rows = payload.get("rows")
    if isinstance(rows, list):
        return len(rows)
    for field in ("count", "row_count"):
        value = payload.get(field)
        if isinstance(value, int):
            return value
    raise ValueError("dataset has no rows list or integer count/row_count")


def validate(
    path: Path,
    timestamp_fields: list[str],
    max_age_minutes: float,
    min_rows: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"dataset does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("dataset root must be a JSON object")
    field, timestamp = resolve_timestamp(payload, timestamp_fields)
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_minutes = (current - timestamp).total_seconds() / 60
    if age_minutes < -5:
        raise ValueError(f"dataset timestamp is {abs(age_minutes):.1f} minutes in the future")
    if age_minutes > max_age_minutes:
        raise ValueError(
            f"STALE_GENERATED_DATA: {path} {field}={timestamp.isoformat()} "
            f"age={age_minutes:.1f}m limit={max_age_minutes:.1f}m"
        )
    row_count = resolve_row_count(payload)
    if row_count < min_rows:
        raise ValueError(f"INSUFFICIENT_GENERATED_ROWS: {path} rows={row_count} minimum={min_rows}")
    return {
        "path": str(path),
        "timestamp_field": field,
        "timestamp": timestamp.isoformat(),
        "age_minutes": round(age_minutes, 1),
        "row_count": row_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--timestamp-field", action="append", required=True, dest="timestamp_fields")
    parser.add_argument("--max-age-minutes", type=float, default=30)
    parser.add_argument("--min-rows", type=int, default=1)
    args = parser.parse_args()
    try:
        result = validate(args.path, args.timestamp_fields, args.max_age_minutes, args.min_rows)
    except (ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
