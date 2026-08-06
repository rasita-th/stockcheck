#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "data" / "generated" / "source_freshness.json"
TIMESTAMP_FIELDS = (
    "regularMarketTime", "marketTime", "market_time", "latestTradingDay",
    "asOf", "as_of", "date", "datetime", "timestamp", "time",
)


def parse_market_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).date()
        except (OverflowError, OSError, ValueError):
            return None
    raw = str(value).strip()
    if raw.isdigit() and len(raw) >= 10:
        try:
            stamp = float(raw)
            if stamp > 10_000_000_000:
                stamp /= 1000
            return datetime.fromtimestamp(stamp, tz=timezone.utc).date()
        except (OverflowError, OSError, ValueError):
            return None
    try:
        return datetime.fromisoformat(raw.replace(" UTC", "+00:00").replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            continue
    return None


def previous_business_day(day: date) -> date:
    candidate = day
    while candidate.weekday() >= 5:
        candidate = candidate.fromordinal(candidate.toordinal() - 1)
    return candidate


def business_day_lag(observed: date, expected: date) -> int:
    if observed >= expected:
        return 0
    lag = 0
    cursor = observed
    while cursor < expected:
        cursor = cursor.fromordinal(cursor.toordinal() + 1)
        if cursor.weekday() < 5:
            lag += 1
    return lag


def extract_row_date(row: dict[str, Any]) -> date | None:
    for field in TIMESTAMP_FIELDS:
        parsed = parse_market_date(row.get(field))
        if parsed:
            return parsed
    latest = row.get("latest")
    if isinstance(latest, dict):
        for field in TIMESTAMP_FIELDS:
            parsed = parse_market_date(latest.get(field))
            if parsed:
                return parsed
    return None


def inspect(
    payload: dict[str, Any],
    *,
    now: datetime,
    max_business_day_lag: int,
    min_coverage: float,
    max_stale_ratio: float = 0.0,
) -> dict[str, Any]:
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    expected = previous_business_day(now.date())
    observed: list[tuple[str, date]] = []
    missing: list[str] = []
    stale: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or row.get("ticker") or "UNKNOWN").upper()
        market_date = extract_row_date(row)
        if not market_date:
            missing.append(symbol)
            continue
        observed.append((symbol, market_date))
        lag = business_day_lag(market_date, expected)
        if lag > max_business_day_lag:
            stale.append({"symbol": symbol, "market_date": market_date.isoformat(), "business_day_lag": lag})
    total = len(rows)
    coverage = (len(observed) / total) if total else 0.0
    stale_ratio = (len(stale) / len(observed)) if observed else 1.0
    stale_within_tolerance = bool(stale) and stale_ratio <= max_stale_ratio
    if total == 0:
        status = "invalid"
    elif coverage < min_coverage:
        status = "source_partial"
    elif stale and not stale_within_tolerance:
        status = "source_stale"
    else:
        status = "fresh"
    dates = [item[1] for item in observed]
    return {
        "schema_version": "1.0",
        "status": status,
        "checked_at": now.astimezone(timezone.utc).isoformat(),
        "expected_market_date": expected.isoformat(),
        "max_business_day_lag": max_business_day_lag,
        "max_stale_ratio": max_stale_ratio,
        "row_count": total,
        "timestamp_coverage": round(coverage, 4),
        "stale_ratio": round(stale_ratio, 4),
        "stale_within_tolerance": stale_within_tolerance,
        "oldest_market_date": min(dates).isoformat() if dates else None,
        "newest_market_date": max(dates).isoformat() if dates else None,
        "missing_timestamp_count": len(missing),
        "missing_timestamp_symbols": missing[:50],
        "stale_count": len(stale),
        "stale_symbols": stale[:100],
    }


def ratio(value: str) -> float:
    parsed = float(value)
    if not 0.0 <= parsed <= 1.0:
        raise argparse.ArgumentTypeError("ratio must be between 0 and 1")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--max-business-day-lag", type=int, default=1)
    parser.add_argument("--min-coverage", type=ratio, default=0.80)
    parser.add_argument("--max-stale-ratio", type=ratio, default=0.0)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    payload = json.loads((ROOT / args.path).read_text(encoding="utf-8"))
    result = inspect(
        payload,
        now=datetime.now(timezone.utc),
        max_business_day_lag=args.max_business_day_lag,
        min_coverage=args.min_coverage,
        max_stale_ratio=args.max_stale_ratio,
    )
    report = Path(args.report)
    if not report.is_absolute():
        report = ROOT / report
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    rejected = {"invalid", "source_stale"}
    if not args.allow_partial:
        rejected.add("source_partial")
    if result["status"] in rejected:
        raise SystemExit(f"STALE_SOURCE_MARKET_DATA: {result['status']}")


if __name__ == "__main__":
    main()
