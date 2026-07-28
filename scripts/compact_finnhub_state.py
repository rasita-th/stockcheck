#!/usr/bin/env python3
"""Compact Finnhub cache and regenerate bounded public contracts.

This is intentionally a post-generation migration layer. Producers remain read-only
and run this before building the immutable production artifact.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "finnhub" / "state.json"
PUBLIC_DIRS = (ROOT / "data", ROOT / "site" / "data", ROOT / "static" / "data")
FEATURE_NAME = "finnhub_features.json"
MAX_ANNUAL_ROWS = 5
MAX_QUARTERLY_ROWS = 8
REMOVED_TICKER_GRACE_DAYS = 30

BASIC_METRICS = {
    "52WeekHigh", "52WeekLow", "beta", "currentRatio", "grossMarginTTM",
    "netProfitMarginTTM", "operatingMarginTTM", "peBasicExclExtraTTM",
    "pbAnnual", "psTTM", "roeTTM", "roaTTM", "totalDebtToEquityAnnual",
    "revenueGrowthTTMYoy", "epsGrowthTTMYoy",
}
SERIES_METRICS = {
    "revenue", "netIncome", "eps", "grossMargin", "operatingMargin",
    "freeCashFlow", "totalDebt", "totalEquity",
}


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def clean_ticker(value: Any) -> str:
    ticker = str(value or "").strip().upper().replace("$", "")
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")
    return ticker if ticker and len(ticker) <= 18 and set(ticker) <= allowed else ""


def load_universe() -> set[str]:
    universe: set[str] = set()
    for path in (ROOT / "data" / "portfolio.json", ROOT / "data" / "technical.json"):
        payload = load_json(path, [])
        rows = payload if isinstance(payload, list) else payload.get("rows", []) if isinstance(payload, dict) else []
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict):
                ticker = clean_ticker(row.get("ticker") or row.get("symbol"))
                if ticker:
                    universe.add(ticker)
    return universe


def parse_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def finite_number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return int(number) if number.is_integer() else number


def compact_series(series: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(series, dict):
        return {}
    output: dict[str, list[dict[str, Any]]] = {}
    limits = {"annual": MAX_ANNUAL_ROWS, "quarterly": MAX_QUARTERLY_ROWS}
    for cadence, limit in limits.items():
        source = series.get(cadence)
        cadence_output: list[dict[str, Any]] = []
        if isinstance(source, dict):
            for metric, rows in source.items():
                if metric not in SERIES_METRICS or not isinstance(rows, list):
                    continue
                normalized = []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    period = row.get("period") or row.get("year") or row.get("quarter")
                    value = finite_number(row.get("v", row.get("value")))
                    if period and value is not None:
                        normalized.append({"metric": metric, "period": str(period), "value": value})
                cadence_output.extend(sorted(normalized, key=lambda item: item["period"])[-limit:])
        elif isinstance(source, list):
            for row in source:
                if not isinstance(row, dict):
                    continue
                metric = str(row.get("metric") or "")
                period = row.get("period")
                value = finite_number(row.get("v", row.get("value")))
                if metric in SERIES_METRICS and period and value is not None:
                    cadence_output.append({"metric": metric, "period": str(period), "value": value})
            cadence_output = sorted(cadence_output, key=lambda item: item["period"])[-limit:]
        if cadence_output:
            output[cadence] = cadence_output
    return output


def compact_basic_financials(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    metrics = payload.get("metric") if isinstance(payload.get("metric"), dict) else {}
    compact_metrics = {
        key: value
        for key in sorted(BASIC_METRICS)
        if (value := finite_number(metrics.get(key))) is not None
    }
    result: dict[str, Any] = {}
    symbol = clean_ticker(payload.get("symbol"))
    if symbol:
        result["symbol"] = symbol
    if compact_metrics:
        result["metric"] = compact_metrics
    series = compact_series(payload.get("series"))
    if series:
        result["series"] = series
    return result


def compact_entry(endpoint: str, entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    data = entry.get("data")
    if endpoint == "basic_financials":
        data = compact_basic_financials(data)
    elif isinstance(data, list):
        data = data[:24]
    elif isinstance(data, dict):
        data = dict(data)
    elif data is not None:
        data = None
    result = {
        "status": str(entry.get("status") or ("ok" if data else "empty")),
        "updated_at": entry.get("updated_at"),
        "data": data,
    }
    if result["status"] == "error":
        error = str(entry.get("error") or entry.get("last_error") or "")[:500]
        if error:
            result["last_error"] = error
            result["last_error_at"] = entry.get("last_error_at") or entry.get("updated_at")
    return result


def compact_state(state: Any, universe: set[str]) -> dict[str, Any]:
    if not isinstance(state, dict):
        state = {}
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=REMOVED_TICKER_GRACE_DAYS)
    endpoints_out: dict[str, dict[str, Any]] = {}
    endpoints = state.get("endpoints") if isinstance(state.get("endpoints"), dict) else {}
    for endpoint, entries in endpoints.items():
        if not isinstance(entries, dict):
            continue
        bucket: dict[str, Any] = {}
        for raw_ticker, entry in entries.items():
            ticker = clean_ticker(raw_ticker)
            if not ticker:
                continue
            updated = parse_time(entry.get("updated_at")) if isinstance(entry, dict) else None
            if universe and ticker not in universe and (updated is None or updated < cutoff):
                continue
            compacted = compact_entry(endpoint, entry)
            if compacted is not None:
                bucket[ticker] = compacted
        endpoints_out[endpoint] = bucket
    batch = state.get("batch") if isinstance(state.get("batch"), dict) else {}
    batch_out: dict[str, Any] = {}
    for name, entry in batch.items():
        if not isinstance(entry, dict):
            continue
        compacted = {key: entry.get(key) for key in ("status", "updated_at", "window") if key in entry}
        rows = entry.get("data")
        if isinstance(rows, list):
            compacted["data"] = rows[:500]
        batch_out[name] = compacted
    return {
        "schema_version": str(state.get("schema_version") or "1.0.0"),
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "endpoints": endpoints_out,
        "batch": batch_out,
        "runs": (state.get("runs") if isinstance(state.get("runs"), list) else [])[-20:],
    }


def public_projection(state: dict[str, Any], universe: set[str]) -> dict[str, Any]:
    features: dict[str, dict[str, Any]] = {}
    for endpoint, entries in state.get("endpoints", {}).items():
        if not isinstance(entries, dict):
            continue
        projected: dict[str, Any] = {}
        for ticker, entry in entries.items():
            if universe and ticker not in universe:
                continue
            if not isinstance(entry, dict):
                continue
            projected[ticker] = {
                "status": entry.get("status"),
                "updated_at": entry.get("updated_at"),
                "data": entry.get("data"),
            }
        features[endpoint] = projected
    return {
        "schema_version": "1.1.0",
        "generated_at": state.get("updated_at"),
        "source": "finnhub",
        "features": features,
        "contract": {
            "optional_fields": True,
            "last_known_good": True,
            "secrets_exposed": False,
            "bounded_payload": True,
        },
    }


def encoded(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def atomic_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encoded(payload))
    os.replace(temporary, path)


def run(write: bool) -> dict[str, Any]:
    original = load_json(STATE_PATH, {})
    universe = load_universe()
    compacted = compact_state(original, universe)
    projection = public_projection(compacted, universe)
    before_state = STATE_PATH.stat().st_size if STATE_PATH.exists() else 0
    before_feature = (ROOT / "data" / FEATURE_NAME).stat().st_size if (ROOT / "data" / FEATURE_NAME).exists() else 0
    result = {
        "state_before_bytes": before_state,
        "state_after_bytes": len(encoded(compacted)),
        "features_before_bytes": before_feature,
        "features_after_bytes": len(encoded(projection)),
        "universe_count": len(universe),
        "write": write,
    }
    if write:
        atomic_write(STATE_PATH, compacted)
        for directory in PUBLIC_DIRS:
            atomic_write(directory / FEATURE_NAME, projection)
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    run(write=args.write)


if __name__ == "__main__":
    main()
