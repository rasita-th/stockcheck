#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "generated"
REQUIRED = ["quote_latest.json", "technical.json", "attention_today.json", "events.json", "health.json"]
PRIORITIES = {"Critical", "Risk", "Action", "Watch", "Developing"}
VERIFICATION = {"confirmed", "estimated", "unverified", "unknown"}
DRAWDOWN_STATUSES = {"complete", "partial-history", "unavailable"}
DRAWDOWN_FLAT_KEYS = (
    "drawdownCurrentPct",
    "drawdownMaxPct",
    "drawdownDaysSincePeak",
    "drawdownAsOf",
    "drawdownStatus",
)


def load(name: str) -> dict[str, Any]:
    path = DATA / name
    if not path.exists() or path.stat().st_size == 0:
        raise SystemExit(f"Missing or empty generated data file: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path} root must be an object")
    return data


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def symbol_of(row: dict[str, Any]) -> str:
    return str(row.get("ticker") or row.get("symbol") or "").strip().upper()


def finite_number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def validate_drawdown_row(row: dict[str, Any], symbol: str) -> bool:
    metric = row.get("drawdown")
    require(isinstance(metric, dict), f"{symbol} drawdown payload missing")
    require(str(metric.get("schemaVersion") or "") == "1.0", f"{symbol} drawdown schema must be 1.0")

    status = str(metric.get("status") or "")
    require(status in DRAWDOWN_STATUSES, f"{symbol} drawdown status invalid")
    require(str(metric.get("window") or "") == "up-to-756-sessions", f"{symbol} drawdown window invalid")
    require(str(metric.get("source") or "") == "adjusted_close_then_close", f"{symbol} drawdown source invalid")

    flattened = {
        "drawdownCurrentPct": metric.get("currentPct"),
        "drawdownMaxPct": metric.get("maxPct"),
        "drawdownDaysSincePeak": metric.get("daysSincePeak"),
        "drawdownAsOf": metric.get("asOf"),
        "drawdownStatus": metric.get("status"),
    }
    for key, expected in flattened.items():
        require(row.get(key) == expected, f"{symbol} {key} differs from drawdown payload")

    if status in {"complete", "partial-history"}:
        current = finite_number(metric.get("currentPct"))
        maximum = finite_number(metric.get("maxPct"))
        observations = metric.get("observations")
        days_since_peak = metric.get("daysSincePeak")
        require(current is not None and maximum is not None, f"{symbol} drawdown percentages are invalid")
        require(-100.0 <= maximum <= current <= 0.0, f"{symbol} drawdown percentage domain is invalid")
        require(isinstance(observations, int) and observations >= 2, f"{symbol} drawdown observations invalid")
        require(isinstance(days_since_peak, int) and days_since_peak >= 0, f"{symbol} daysSincePeak invalid")
        require(bool(metric.get("asOf")), f"{symbol} drawdown asOf missing")
        return True

    require(metric.get("currentPct") is None, f"{symbol} unavailable drawdown must not expose currentPct")
    require(metric.get("maxPct") is None, f"{symbol} unavailable drawdown must not expose maxPct")
    require(row.get("drawdownCurrentPct") is None, f"{symbol} unavailable drawdown must not flatten to zero")
    return False


def validate_screener_snapshot(
    data: dict[str, Any],
    quotes: dict[str, Any],
    technical: dict[str, Any],
) -> None:
    schema = str(data.get("schema_version") or "")
    require(schema in {"1.0", "1.1"}, "screener snapshot schema must be 1.0 or 1.1")
    require(data.get("contract") == "canonical-screener-snapshot", "screener snapshot contract is invalid")
    rows = data.get("rows")
    require(isinstance(rows, list) and bool(rows), "screener snapshot rows must be non-empty")
    require(data.get("row_count") == len(rows), "screener snapshot row_count mismatch")
    require(float(data.get("live_quote_coverage") or 0) >= 0.80, "screener snapshot quote coverage is below 80%")
    require(int(data.get("stale_after_minutes") or 0) > 0, "screener snapshot TTL is invalid")

    if schema == "1.1":
        require(str(data.get("drawdown_schema_version") or "") == "1.0", "drawdown schema version must be 1.0")
        declared_count = data.get("drawdown_available_count")
        declared_coverage = finite_number(data.get("drawdown_coverage"))
        require(isinstance(declared_count, int) and declared_count >= 0, "drawdown available count is invalid")
        require(declared_coverage is not None and 0.0 <= declared_coverage <= 1.0, "drawdown coverage is invalid")

    technical_rows = technical.get("rows")
    require(isinstance(technical_rows, list) and bool(technical_rows), "canonical technical rows must be non-empty")
    require(
        technical.get("contract") == "canonical-screener-snapshot",
        "technical.json must declare canonical-screener-snapshot when the snapshot exists",
    )
    require(len(technical_rows) == len(rows), "canonical technical and screener row counts differ")

    quote_map = {
        symbol_of(row): row
        for row in quotes.get("rows", [])
        if isinstance(row, dict) and symbol_of(row)
    }
    technical_map = {
        symbol_of(row): row
        for row in technical_rows
        if isinstance(row, dict) and symbol_of(row)
    }
    seen: set[str] = set()
    drawdown_available = 0

    for index, row in enumerate(rows):
        require(isinstance(row, dict), f"screener row {index} must be an object")
        symbol = symbol_of(row)
        require(bool(symbol), f"screener row {index} missing symbol")
        require(symbol not in seen, f"duplicate screener symbol: {symbol}")
        seen.add(symbol)
        require(row.get("snapshotStatus") in {"live_quote", "technical_fallback"}, f"{symbol} snapshot status invalid")

        mirrored = technical_map.get(symbol)
        require(isinstance(mirrored, dict), f"{symbol} missing from canonical technical mirror")
        for key in ("price", "close", "score", "signal", "snapshotStatus"):
            require(mirrored.get(key) == row.get(key), f"{symbol} {key} differs between snapshot and technical mirror")

        if schema == "1.1":
            if validate_drawdown_row(row, symbol):
                drawdown_available += 1
            for key in ("drawdown", *DRAWDOWN_FLAT_KEYS):
                require(mirrored.get(key) == row.get(key), f"{symbol} {key} differs between snapshot and technical mirror")

        if row.get("snapshotStatus") == "live_quote":
            quote = quote_map.get(symbol)
            require(isinstance(quote, dict), f"{symbol} live row missing quote source")
            require(abs(float(row.get("price")) - float(quote.get("price"))) <= 0.0001, f"{symbol} snapshot price does not match quote_latest")
            for key in ("pctVsEma5", "pctVsEma20", "pctVsEma89", "pctVsEma200"):
                require(row.get(key) is None or isinstance(row.get(key), (int, float)), f"{symbol} {key} is invalid")

    if schema == "1.1":
        computed_coverage = drawdown_available / len(rows)
        require(data.get("drawdown_available_count") == drawdown_available, "drawdown available count mismatch")
        declared_coverage = float(data.get("drawdown_coverage"))
        require(abs(computed_coverage - declared_coverage) <= 0.000001, "drawdown coverage identity mismatch")
        require(computed_coverage >= 0.80, f"drawdown coverage is below 80%: {computed_coverage:.1%}")


def validate_attention(data: dict[str, Any]) -> None:
    require(str(data.get("schema_version", "")).startswith("2.0"), "attention_today must use P0 schema 2.0")
    require(data.get("data_quality", {}).get("free_sources_only") is True, "attention_today must declare free_sources_only=true")
    require(isinstance(data.get("source_health"), dict), "attention_today source_health must be an object")
    require(data.get("coverage_status") in {"complete", "partial"}, "attention_today coverage_status is invalid")
    items = data.get("items")
    require(isinstance(items, list), "attention_today items must be a list")
    max_items = int(data.get("data_quality", {}).get("max_attention_items", 7))
    require(len(items) <= max_items, f"attention_today exceeds max item count ({max_items})")
    seen_tickers: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"attention item {index}"
        require(isinstance(item, dict), f"{prefix} must be an object")
        ticker = str(item.get("ticker") or "")
        require(bool(ticker), f"{prefix} missing ticker")
        require(ticker not in seen_tickers, f"duplicate attention ticker: {ticker}")
        seen_tickers.add(ticker)
        require(item.get("priority") in PRIORITIES, f"{prefix} has invalid priority")
        require(isinstance(item.get("priority_score"), int), f"{prefix} priority_score must be an integer")
        require(isinstance(item.get("why_today"), list) and item["why_today"], f"{prefix} why_today must be a non-empty list")
        require(item.get("verification_status") in VERIFICATION, f"{prefix} has invalid verification status")
        require(isinstance(item.get("events"), list) and item["events"], f"{prefix} events must be a non-empty list")
        source = item.get("source") or {}
        require(str(source.get("type") or "").lower() != "finnhub", f"{prefix} must not use Finnhub as a source")
        if item.get("verification_status") == "confirmed" and source.get("quality") == "primary":
            require(bool(source.get("url")), f"{prefix} confirmed primary event must have a source URL")


def validate_events(data: dict[str, Any]) -> None:
    events = data.get("events")
    require(isinstance(events, list), "events.json events must be a list")
    require(data.get("row_count") == len(events), "events.json row_count mismatch")
    seen: set[str] = set()
    for index, event in enumerate(events):
        prefix = f"event {index}"
        require(isinstance(event, dict), f"{prefix} must be an object")
        event_id = str(event.get("event_id") or "")
        require(bool(event_id), f"{prefix} missing event_id")
        require(event_id not in seen, f"duplicate event_id: {event_id}")
        seen.add(event_id)
        require(bool(event.get("ticker")), f"{prefix} missing ticker")
        require(bool(event.get("event_type")), f"{prefix} missing event_type")
        require(bool(event.get("event_subtype")), f"{prefix} missing event_subtype")
        require(event.get("verification_status") in VERIFICATION, f"{prefix} has invalid verification status")
        source = event.get("source") or {}
        require(str(source.get("type") or "").lower() != "finnhub", f"{prefix} must not use Finnhub as a source")
        require(bool(source.get("type")), f"{prefix} missing source type")
        if event.get("verification_status") == "confirmed" and source.get("quality") == "primary":
            require(bool(source.get("url")), f"{prefix} confirmed primary source must have a source URL")


def main() -> None:
    docs = {name: load(name) for name in REQUIRED}
    quote = docs["quote_latest.json"]
    technical = docs["technical.json"]
    require(isinstance(quote.get("rows"), list) and quote["rows"], "quote_latest rows must be a non-empty list")
    require(isinstance(technical.get("rows"), list) and technical["rows"], "technical rows must be a non-empty list")

    snapshot_path = DATA / "screener_snapshot.json"
    canonical_declared = technical.get("contract") == "canonical-screener-snapshot"
    if canonical_declared or snapshot_path.exists():
        validate_screener_snapshot(load("screener_snapshot.json"), quote, technical)
    else:
        print("Legacy/offline fixture: canonical screener snapshot not declared; compatibility validation only")

    validate_attention(docs["attention_today.json"])
    validate_events(docs["events.json"])
    require(docs["health.json"].get("status") != "error", "health status is error")
    print("Generated data validation passed")


if __name__ == "__main__":
    main()
