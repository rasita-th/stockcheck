#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "generated"
REQUIRED = ["quote_latest.json", "technical.json", "attention_today.json", "events.json", "health.json"]
PRIORITIES = {"Critical", "Risk", "Action", "Watch", "Developing"}
VERIFICATION = {"confirmed", "estimated", "unverified", "unknown"}


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
        require(item.get("verification_status") in VERIFICATION, f"{prefix} verification_status is invalid")
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
        require(event.get("verification_status") in VERIFICATION, f"{prefix} verification_status is invalid")
        source = event.get("source") or {}
        require(str(source.get("type") or "").lower() != "finnhub", f"{prefix} must not use Finnhub as a source")
        require(bool(source.get("type")), f"{prefix} missing source type")
        if event.get("verification_status") == "confirmed" and source.get("quality") == "primary":
            require(bool(source.get("url")), f"{prefix} confirmed primary source must have a URL")


def main() -> None:
    docs = {name: load(name) for name in REQUIRED}
    require(isinstance(docs["quote_latest.json"].get("rows"), list) and docs["quote_latest.json"]["rows"], "quote_latest rows must be a non-empty list")
    require(isinstance(docs["technical.json"].get("rows"), list) and docs["technical.json"]["rows"], "technical rows must be a non-empty list")
    validate_attention(docs["attention_today.json"])
    validate_events(docs["events.json"])
    require(docs["health.json"].get("status") != "error", "health status is error")
    print("Generated data validation passed")


if __name__ == "__main__":
    main()
