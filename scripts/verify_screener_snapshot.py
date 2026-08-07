#!/usr/bin/env python3
"""Verify the canonical screener snapshot used by overview, filters and alerts."""
from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any


def load(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        raise SystemExit(f"missing or empty file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return value


def symbol_of(row: dict[str, Any]) -> str:
    return str(row.get("ticker") or row.get("symbol") or "").strip().upper()


def number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def parse_time(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith(" UTC"):
            return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def fail(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)



def is_regular_us_market_session(now: datetime) -> bool:
    local = now.astimezone(ZoneInfo("America/New_York"))
    wall_clock = local.timetz().replace(tzinfo=None)
    return (
        local.weekday() < 5
        and time(9, 30) <= wall_clock <= time(16, 30)
    )

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--quotes", type=Path, required=True)
    parser.add_argument("--technical", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--build", type=Path)
    parser.add_argument("--shard", type=Path, action="append", default=[])
    parser.add_argument("--expected-commit", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument("--expected-snapshot-schema", required=True)
    parser.add_argument("--expected-runtime", required=True)
    parser.add_argument(
        "--quote-freshness-policy",
        choices=("always", "market-hours"),
        default="always",
    )
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args()

    snapshot = load(args.snapshot)
    quotes = load(args.quotes)
    technical = load(args.technical)
    runtime = args.runtime.read_text(encoding="utf-8")

    fail(
        snapshot.get("schema_version") == args.expected_snapshot_schema,
        f"snapshot schema is not {args.expected_snapshot_schema}",
    )
    fail(snapshot.get("contract") == "canonical-screener-snapshot", "snapshot contract is invalid")
    rows = snapshot.get("rows")
    fail(isinstance(rows, list) and bool(rows), "snapshot rows are empty")
    fail(snapshot.get("row_count") == len(rows), "snapshot row_count mismatch")
    fail(technical.get("contract") == "canonical-screener-snapshot", "technical mirror is not canonical")
    technical_rows = technical.get("rows")
    fail(isinstance(technical_rows, list) and len(technical_rows) == len(rows), "technical mirror row count differs")

    quote_rows = quotes.get("rows")
    fail(isinstance(quote_rows, list) and bool(quote_rows), "quote_latest rows are empty")
    quote_map = {
        symbol_of(row): row
        for row in quote_rows
        if isinstance(row, dict) and symbol_of(row)
    }
    technical_map = {
        symbol_of(row): row
        for row in technical_rows
        if isinstance(row, dict) and symbol_of(row)
    }

    quote_identity = str(quotes.get("market_as_of") or quotes.get("generated_at") or "")
    fail(bool(quote_identity), "quote_latest timestamp is missing")
    fail(snapshot.get("quote_generated_at") == quote_identity, "snapshot does not identify the deployed quote generation")
    baseline_identity = str(technical.get("technical_generated_at") or technical.get("generatedAtTechnical") or technical.get("generatedAt") or "")
    fail(snapshot.get("technical_generated_at") == baseline_identity, "snapshot technical baseline identity mismatch")

    seen: set[str] = set()
    live_count = 0
    price_mismatches: list[str] = []
    mirror_mismatches: list[str] = []
    invalid_rows: list[str] = []
    indicator_counts = {key: 0 for key in ("ema5", "ema20", "ema89", "ema200", "rsi14")}

    for item in rows:
        fail(isinstance(item, dict), "snapshot contains a non-object row")
        symbol = symbol_of(item)
        fail(bool(symbol), "snapshot row is missing symbol")
        fail(symbol not in seen, f"duplicate snapshot symbol: {symbol}")
        seen.add(symbol)

        status = item.get("snapshotStatus")
        if status not in {"live_quote", "technical_fallback"}:
            invalid_rows.append(f"{symbol}:status")
        for key in ("price", "close", "rsi14", "score"):
            if number(item.get(key)) is None:
                invalid_rows.append(f"{symbol}:{key}")
        if not str(item.get("signal") or "").strip():
            invalid_rows.append(f"{symbol}:signal")

        for indicator in indicator_counts:
            indicator_value = number(item.get(indicator))
            if indicator_value is not None:
                indicator_counts[indicator] += 1
                if indicator.startswith("ema"):
                    distance = number(item.get(f"pctVs{indicator.upper().replace('EMA', 'Ema')}"))
                    if distance is None:
                        invalid_rows.append(f"{symbol}:pctVs{indicator}")

        mirrored = technical_map.get(symbol)
        if not isinstance(mirrored, dict):
            mirror_mismatches.append(f"{symbol}:missing")
        else:
            for key in ("price", "close", "score", "signal", "snapshotStatus", "quoteGeneratedAt"):
                if mirrored.get(key) != item.get(key):
                    mirror_mismatches.append(f"{symbol}:{key}")

        if status == "live_quote":
            live_count += 1
            quote = quote_map.get(symbol)
            if not isinstance(quote, dict):
                price_mismatches.append(f"{symbol}:missing_quote")
            else:
                price = number(item.get("price"))
                quoted = number(quote.get("price"))
                if price is None or quoted is None or abs(price - quoted) > 0.0001:
                    price_mismatches.append(f"{symbol}:{price}!={quoted}")

    fail(not invalid_rows, f"invalid canonical rows: {invalid_rows[:12]}")
    fail(not mirror_mismatches, f"snapshot/technical mirror mismatch: {mirror_mismatches[:12]}")
    fail(not price_mismatches, f"snapshot/quote mismatch: {price_mismatches[:12]}")

    computed_coverage = live_count / len(rows)
    declared_coverage = number(snapshot.get("live_quote_coverage"))
    fail(declared_coverage is not None, "snapshot live_quote_coverage missing")
    fail(abs(computed_coverage - declared_coverage) <= 0.000001, "snapshot live quote coverage identity mismatch")
    fail(computed_coverage >= 0.80, f"snapshot live quote coverage too low: {computed_coverage:.1%}")

    indicator_coverage = {key: count / len(rows) for key, count in indicator_counts.items()}
    minimum_indicator_coverage = {
        "ema5": 0.95,
        "ema20": 0.95,
        "ema89": 0.85,
        "ema200": 0.75,
        "rsi14": 0.95,
    }
    for key, minimum in minimum_indicator_coverage.items():
        fail(
            indicator_coverage[key] >= minimum,
            f"{key} market coverage too low: {indicator_coverage[key]:.1%} < {minimum:.1%}",
        )

    quote_time = parse_time(quote_identity)
    snapshot_time = parse_time(snapshot.get("generated_at") or snapshot.get("generatedAt"))
    fail(quote_time is not None, "quote generation timestamp is invalid")
    fail(snapshot_time is not None, "snapshot generation timestamp is invalid")
    now = datetime.now(timezone.utc)
    quote_age_minutes = (now - quote_time.astimezone(timezone.utc)).total_seconds() / 60.0
    snapshot_age_minutes = (now - snapshot_time.astimezone(timezone.utc)).total_seconds() / 60.0
    ttl = int(snapshot.get("stale_after_minutes") or 0)
    fail(ttl > 0, "snapshot TTL is invalid")
    fail(quote_age_minutes >= -5, f"quote timestamp is too far in the future: {quote_age_minutes:.1f}m")
    fail(snapshot_age_minutes >= -5, f"snapshot timestamp is too far in the future: {snapshot_age_minutes:.1f}m")
    enforce_freshness = (
        args.quote_freshness_policy == "always"
        or is_regular_us_market_session(now)
    )
    if enforce_freshness:
        fail(quote_age_minutes <= ttl, f"deployed quotes are stale: {quote_age_minutes:.1f}m > {ttl}m")
        fail(snapshot_age_minutes <= ttl, f"snapshot is stale: {snapshot_age_minutes:.1f}m > {ttl}m")

    runtime_tokens = (
        "data/screener_snapshot.json",
        "function snapshotIsFresh",
        "function mapCanonicalScreenerRow",
        "function buildCanonicalAlertItems",
        "function projectSeriesToSnapshot",
        "data/technical/symbols/",
    )
    missing_tokens = [token for token in runtime_tokens if token not in runtime]
    fail(not missing_tokens, f"runtime is missing canonical screener tokens: {missing_tokens}")

    shard_summary: dict[str, int] = {}
    for shard_path in args.shard:
        shard = load(shard_path)
        symbol = str(shard.get("symbol") or "").upper()
        series = shard.get("series")
        fail(shard.get("schema_version") == "2.0" and bool(symbol), f"invalid shard: {shard_path}")
        fail(isinstance(series, list) and len(series) >= 30, f"{symbol} shard has insufficient series")
        fail(symbol in seen, f"{symbol} shard is not represented in canonical snapshot")
        shard_summary[symbol] = len(series)

    build_identity: dict[str, Any] = {}
    if args.build:
        build = load(args.build)
        expected = str(args.expected_commit or "").strip()
        if expected:
            fail(build.get("source_commit") == expected, "production build commit does not match verified commit")
        fail(build.get("technical_asset_version") == args.expected_runtime, "production runtime version mismatch")
        build_identity = {
            "source_commit": build.get("source_commit"),
            "run_id": build.get("run_id"),
            "technical_asset_version": build.get("technical_asset_version"),
        }

    summary = {
        "schema_version": "1.0",
        "contract": "verified-canonical-screener",
        "row_count": len(rows),
        "quote_row_count": len(quote_rows),
        "live_quote_count": live_count,
        "live_quote_coverage": round(computed_coverage, 6),
        "indicator_coverage": {key: round(value, 6) for key, value in indicator_coverage.items()},
        "quote_age_minutes": round(quote_age_minutes, 2),
        "quote_freshness_policy": args.quote_freshness_policy,
        "freshness_enforced": enforce_freshness,
        "snapshot_age_minutes": round(snapshot_age_minutes, 2),
        "stale_after_minutes": ttl,
        "runtime_version": args.expected_runtime,
        "sample_shards": shard_summary,
        "build": build_identity,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.summary_output:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
