#!/usr/bin/env python3
"""Validate Fundamental ownership, monotonic freshness and canonical mirrors."""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


class FundamentalContractError(ValueError):
    pass


def parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    try:
        if raw.endswith(" UTC"):
            return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def period_key(row: dict[str, Any]) -> tuple[int, int, str]:
    period = str(row.get("periodEnd") or "")[:10]
    quarter = str(row.get("latestQuarter") or "")
    match = re.search(r"Q([1-4])\s*(20\d{2})", quarter, flags=re.I)
    if match:
        return (int(match.group(2)), int(match.group(1)), period)
    return (0, 0, period)


def rows_by_ticker(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise FundamentalContractError("rows must be a non-empty list")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise FundamentalContractError("every row must be an object")
        ticker = str(row.get("ticker") or row.get("symbol") or "").upper()
        if not ticker or ticker in result:
            raise FundamentalContractError(f"invalid or duplicate ticker: {ticker!r}")
        result[ticker] = row
    return result


def validate_candidate(candidate: dict[str, Any], current: dict[str, Any] | None = None) -> dict[str, Any]:
    candidate_rows = rows_by_ticker(candidate)
    stamp = parse_timestamp(candidate.get("generatedAtFundamental") or candidate.get("generatedAt"))
    if stamp is None:
        raise FundamentalContractError("candidate timestamp is missing or invalid")
    if candidate.get("count") != len(candidate_rows):
        raise FundamentalContractError("count does not match rows")
    fundamentals = candidate.get("fundamentals")
    if not isinstance(fundamentals, dict) or not set(candidate_rows).issubset({str(k).upper() for k in fundamentals}):
        raise FundamentalContractError("fundamentals map does not cover every row")

    regressions: list[str] = []
    if current:
        current_rows = rows_by_ticker(current)
        current_stamp = parse_timestamp(current.get("generatedAtFundamental") or current.get("generatedAt"))
        if current_stamp and stamp < current_stamp:
            raise FundamentalContractError("candidate generatedAtFundamental is older than production")
        for ticker in sorted(set(current_rows) & set(candidate_rows)):
            before = period_key(current_rows[ticker])
            after = period_key(candidate_rows[ticker])
            if before[:2] != (0, 0) and after[:2] != (0, 0) and after[:2] < before[:2]:
                regressions.append(f"{ticker}:{current_rows[ticker].get('latestQuarter')}->{candidate_rows[ticker].get('latestQuarter')}")
            elif before[2] and after[2] and after[2] < before[2]:
                regressions.append(f"{ticker}:{before[2]}->{after[2]}")
        minimum = max(1, int(len(current_rows) * 0.95))
        if len(candidate_rows) < minimum:
            raise FundamentalContractError(f"candidate coverage fell from {len(current_rows)} to {len(candidate_rows)} rows")
    if regressions:
        raise FundamentalContractError("ticker reporting period regressed: " + ", ".join(regressions[:20]))
    return {"row_count": len(candidate_rows), "generated_at": stamp.isoformat(), "period_regressions": 0}


def validate_mirrors(paths: Iterable[Path]) -> None:
    paths = list(paths)
    if not paths:
        raise FundamentalContractError("no mirror paths supplied")
    canonical = paths[0].read_bytes()
    for path in paths[1:]:
        if path.read_bytes() != canonical:
            raise FundamentalContractError(f"mirror mismatch: {path} vs {paths[0]}")


def write_mirrors(payload: dict[str, Any], paths: Iterable[Path]) -> None:
    encoded = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(encoded)
        os.replace(temporary, path)


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FundamentalContractError(f"{path}: root must be an object")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--current", type=Path)
    parser.add_argument("--mirror", action="append", type=Path, default=[])
    args = parser.parse_args()
    result = validate_candidate(load(args.candidate), load(args.current) if args.current and args.current.exists() else None)
    if args.mirror:
        validate_mirrors([args.candidate, *args.mirror])
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
