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


def main() -> None:
    all_warnings: list[str] = []
    for file_name in REQUIRED_FILES:
        data = load_json(SITE_DATA / file_name)
        all_warnings.extend(validate_layer(file_name.replace(".json", ""), data))
    scanner_path = SITE_DATA / "scanner.json"
    if scanner_path.exists():
        load_json(scanner_path)
    earnings_calendar_path = SITE_DATA / "earnings_calendar.json"
    if earnings_calendar_path.exists():
        try:
            earnings_calendar = json.loads(earnings_calendar_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in {earnings_calendar_path}: {exc}") from exc
        if not isinstance(earnings_calendar, list):
            raise SystemExit("earnings_calendar: root must be a list")
        for row in earnings_calendar:
            if not isinstance(row, dict):
                raise SystemExit("earnings_calendar: each row must be an object")
            if not row.get("ticker") or not row.get("earnings_date"):
                raise SystemExit("earnings_calendar: ticker and earnings_date are required")

    attention_path = SITE_DATA / "attention_today.json"
    if attention_path.exists():
        attention = load_json(attention_path)
        if not isinstance(attention.get("items", []), list):
            raise SystemExit("attention_today: items must be a list")
        if not attention.get("updated_at"):
            all_warnings.append("attention_today has no updated_at timestamp")
        # Guardrail: attention cards must not contradict scanner data.
        # If a ticker exists in technical.json, price and day change should be
        # sourced from that same row. Otherwise the attention radar can become
        # misleading even when the UI renders correctly.
        technical = load_json(SITE_DATA / "technical.json")
        rows = technical.get("rows") or []
        by_ticker = {str(r.get("ticker") or r.get("symbol") or "").upper(): r for r in rows if isinstance(r, dict)}
        for item in attention.get("items", []):
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker") or "").upper()
            technical_trigger = item.get("primary_trigger") in {"price_move", "buy_zone", "trim_zone"}
            if technical_trigger and (item.get("price") is None or item.get("day_change_pct") is None):
                raise SystemExit(f"attention_today: {ticker} technical trigger lacks price/day_change_pct")
            if item.get("primary_trigger") == "buy_zone":
                d = item.get("buy_zone_distance_pct")
                try:
                    if not (-10.01 <= float(d) <= 5.01):
                        raise SystemExit(f"attention_today: {ticker} buy_zone distance outside valid range: {d}")
                except (TypeError, ValueError):
                    raise SystemExit(f"attention_today: {ticker} buy_zone item lacks valid buy_zone_distance_pct")
            if item.get("primary_trigger") == "trim_zone":
                d = item.get("trim_zone_distance_pct")
                try:
                    if not (-3.01 <= float(d) <= 10.01):
                        raise SystemExit(f"attention_today: {ticker} trim_zone distance outside valid range: {d}")
                except (TypeError, ValueError):
                    raise SystemExit(f"attention_today: {ticker} trim_zone item lacks valid trim_zone_distance_pct")
            row = by_ticker.get(ticker)
            if not row:
                continue
            try:
                ap = float(item.get("price"))
                sp = float(row.get("price") or row.get("regularMarketPrice"))
                if sp and abs(ap - sp) / abs(sp) > 0.02:
                    raise SystemExit(f"attention_today: {ticker} price mismatch with technical.json ({ap} vs {sp})")
            except (TypeError, ValueError):
                pass
            try:
                ac = float(item.get("day_change_pct"))
                sc = float(row.get("dayPct"))
                if abs(ac - sc) > 0.25:
                    raise SystemExit(f"attention_today: {ticker} day_change_pct mismatch with technical.json ({ac} vs {sc})")
            except (TypeError, ValueError):
                pass
    for warning in all_warnings:
        print(f"::warning::{warning}")
    print("Static data validation passed")


if __name__ == "__main__":
    main()
