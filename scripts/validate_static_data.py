#!/usr/bin/env python3
"""Validate static data files before GitHub Pages deployment.

This is intentionally lightweight: the goal is to fail loudly when a workflow
would deploy malformed JSON or a missing data layer, instead of leaving the UI
blank and making the problem look like a render bug.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = ROOT / "site" / "data"

REQUIRED_FILES = ["technical.json", "fundamental.json"]
ATTENTION_PRIORITIES = {"Critical", "Risk", "Action", "Watch", "Developing"}
EARNINGS_STATUSES = {"confirmed", "estimated", "reported", "call_pending"}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing required static data file: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def validate_layer(name: str, data: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    rows = data.get("rows")
    if not isinstance(rows, list):
        raise SystemExit(f"{name}: rows must be a list")
    errors = data.get("errors", [])
    if errors is not None and not isinstance(errors, list):
        raise SystemExit(f"{name}: errors must be a list if present")
    if name == "technical" and len(rows) == 0:
        raise SystemExit("technical: rows is empty; refusing to deploy a blank scanner")
    if name == "fundamental" and len(rows) == 0:
        warnings.append("fundamental rows is empty; the UI will show a visible warning")
    if not (data.get("generatedAt") or data.get("generatedAtTechnical") or data.get("generatedAtFundamental")):
        warnings.append(f"{name} has no generatedAt timestamp")
    return warnings


def validate_earnings_calendar(path: Path) -> None:
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc

    if isinstance(payload, list):
        rows = payload
        schema_version = "legacy"
    elif isinstance(payload, dict):
        schema_version = str(payload.get("schema_version") or "2.0")
        rows = payload.get("items")
        if not isinstance(rows, list):
            raise SystemExit("earnings_calendar: schema object must contain an items list")
    else:
        raise SystemExit("earnings_calendar: root must be a list or schema object")

    for row in rows:
        if not isinstance(row, dict):
            raise SystemExit("earnings_calendar: each row must be an object")
        if not row.get("ticker") or not (row.get("earnings_date") or row.get("date")):
            raise SystemExit("earnings_calendar: ticker and earnings date are required")
        status = str(row.get("status") or "estimated").lower()
        if status not in EARNINGS_STATUSES:
            raise SystemExit(f"earnings_calendar: unsupported status {status!r}")
        if status == "confirmed":
            source_url = row.get("source_url") or row.get("url")
            source_type = str(row.get("source_type") or row.get("source") or "").lower()
            if not source_url or source_type not in {"company_ir", "sec", "company", "primary"}:
                raise SystemExit("earnings_calendar: confirmed rows require a primary source URL")
    print(f"earnings_calendar: schema {schema_version}, {len(rows)} rows")


def validate_attention(path: Path, all_warnings: list[str]) -> None:
    if not path.exists():
        return
    attention = load_json(path)
    items = attention.get("items", [])
    if not isinstance(items, list):
        raise SystemExit("attention_today: items must be a list")
    if len(items) > 7:
        raise SystemExit(f"attention_today: expected at most 7 items, found {len(items)}")
    if not attention.get("updated_at"):
        all_warnings.append("attention_today has no updated_at timestamp")

    technical = load_json(SITE_DATA / "technical.json")
    rows = technical.get("rows") or []
    by_ticker = {str(r.get("ticker") or r.get("symbol") or "").upper(): r for r in rows if isinstance(r, dict)}

    for item in items:
        if not isinstance(item, dict):
            raise SystemExit("attention_today: each item must be an object")
        ticker = str(item.get("ticker") or "").upper()
        if not ticker:
            raise SystemExit("attention_today: ticker is required")

        priority = item.get("priority")
        if priority is not None and priority not in ATTENTION_PRIORITIES:
            raise SystemExit(f"attention_today: {ticker} has unsupported priority {priority!r}")

        events = item.get("events")
        if events is not None:
            if not isinstance(events, list):
                raise SystemExit(f"attention_today: {ticker} events must be a list")
            event_ids: set[str] = set()
            for event in events:
                if not isinstance(event, dict):
                    raise SystemExit(f"attention_today: {ticker} event must be an object")
                event_id = str(event.get("event_id") or "")
                if not event_id:
                    raise SystemExit(f"attention_today: {ticker} event_id is required")
                if event_id in event_ids:
                    raise SystemExit(f"attention_today: {ticker} duplicate event_id {event_id}")
                event_ids.add(event_id)
                source = event.get("source")
                if not isinstance(source, dict) or not source.get("type"):
                    raise SystemExit(f"attention_today: {ticker} event source is required")
                if event.get("verification_status") == "confirmed" and source.get("quality") == "primary" and not source.get("url"):
                    raise SystemExit(f"attention_today: {ticker} confirmed primary event lacks source URL")

        # Legacy technical-trigger compatibility. New P0 items can omit primary_trigger.
        primary_trigger = item.get("primary_trigger")
        if primary_trigger in {"price_move", "buy_zone", "trim_zone"} and item.get("price") is None:
            raise SystemExit(f"attention_today: {ticker} technical trigger lacks price")
        if primary_trigger == "price_move" and item.get("day_change_pct") is None:
            raise SystemExit(f"attention_today: {ticker} price_move trigger lacks day_change_pct")
        if primary_trigger == "buy_zone":
            distance = item.get("buy_zone_distance_pct")
            try:
                if not (-10.01 <= float(distance) <= 5.01):
                    raise SystemExit(f"attention_today: {ticker} buy_zone distance outside valid range: {distance}")
            except (TypeError, ValueError):
                raise SystemExit(f"attention_today: {ticker} buy_zone item lacks valid buy_zone_distance_pct")
        if primary_trigger == "trim_zone":
            distance = item.get("trim_zone_distance_pct")
            try:
                if not (-3.01 <= float(distance) <= 10.01):
                    raise SystemExit(f"attention_today: {ticker} trim_zone distance outside valid range: {distance}")
            except (TypeError, ValueError):
                raise SystemExit(f"attention_today: {ticker} trim_zone item lacks valid trim_zone_distance_pct")

        row = by_ticker.get(ticker)
        if not row:
            continue
        if item.get("price") is not None:
            try:
                attention_price = float(item.get("price"))
                scanner_price = float(row.get("price") or row.get("regularMarketPrice"))
                if scanner_price and abs(attention_price - scanner_price) / abs(scanner_price) > 0.02:
                    raise SystemExit(
                        f"attention_today: {ticker} price mismatch with technical.json "
                        f"({attention_price} vs {scanner_price})"
                    )
            except (TypeError, ValueError):
                pass
        if item.get("day_change_pct") is not None:
            try:
                attention_change = float(item.get("day_change_pct"))
                scanner_change = float(row.get("dayPct"))
                if abs(attention_change - scanner_change) > 0.25:
                    raise SystemExit(
                        f"attention_today: {ticker} day_change_pct mismatch with technical.json "
                        f"({attention_change} vs {scanner_change})"
                    )
            except (TypeError, ValueError):
                pass

    print(f"attention_today: {len(items)} items")


def main() -> None:
    all_warnings: list[str] = []
    for file_name in REQUIRED_FILES:
        data = load_json(SITE_DATA / file_name)
        all_warnings.extend(validate_layer(file_name.replace(".json", ""), data))

    scanner_path = SITE_DATA / "scanner.json"
    if scanner_path.exists():
        load_json(scanner_path)

    validate_earnings_calendar(SITE_DATA / "earnings_calendar.json")
    validate_attention(SITE_DATA / "attention_today.json", all_warnings)

    for warning in all_warnings:
        print(f"::warning::{warning}")
    print("Static data validation passed")


if __name__ == "__main__":
    main()
