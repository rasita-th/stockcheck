#!/usr/bin/env python3
"""Verify that a Finnhub event refresh reached GitHub Pages and Today PR3."""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain an object")
    return payload


def fetch_json(base_url: str, relative: str) -> dict[str, Any]:
    nonce = str(time.time_ns())
    url = f"{base_url.rstrip('/')}/{relative.lstrip('/')}?verify={urllib.parse.quote(nonce)}"
    request = urllib.request.Request(
        url,
        headers={"Cache-Control": "no-cache", "User-Agent": "stockcheck-deploy-verifier"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{relative} must contain an object")
    return payload


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def timestamp_at_least(actual: Any, expected: Any) -> bool:
    actual_dt, expected_dt = parse_dt(actual), parse_dt(expected)
    return bool(actual_dt and expected_dt and actual_dt >= expected_dt)


def portfolio_tickers(payload: Any) -> set[str]:
    rows = payload if isinstance(payload, list) else []
    return {
        str(row.get("ticker") or row.get("symbol") or "").upper()
        for row in rows
        if isinstance(row, dict) and (row.get("ticker") or row.get("symbol"))
    }


def validate_linkage(
    calendar: dict[str, Any], attention: dict[str, Any], features: dict[str, Any], portfolio: set[str]
) -> dict[str, int]:
    calendar_items = calendar.get("items")
    attention_items = attention.get("items")
    if not isinstance(calendar_items, list):
        raise RuntimeError("earnings_calendar.json items must be a list")
    if not isinstance(attention_items, list):
        raise RuntimeError("attention_today.json items must be a list")
    if not str(attention.get("contract_version") or "").startswith("3.0"):
        raise RuntimeError("deployed Today payload is not PR3 contract 3.0")

    batch = features.get("batch") if isinstance(features.get("batch"), dict) else {}
    earnings_batch = (
        batch.get("earnings_calendar")
        if isinstance(batch.get("earnings_calendar"), dict)
        else {}
    )
    batch_rows = earnings_batch.get("data") if isinstance(earnings_batch.get("data"), list) else []
    if earnings_batch.get("status") != "ok" or not batch_rows:
        raise RuntimeError("deployed Finnhub earnings batch is not healthy or contains no rows")

    today = date.today()
    due: set[str] = set()
    for row in calendar_items:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or row.get("symbol") or "").upper()
        event_date = parse_date(row.get("earnings_date") or row.get("date"))
        if not ticker or ticker not in portfolio or event_date is None:
            continue
        status = str(row.get("status") or "estimated").lower()
        days = (event_date - today).days
        if 0 <= days <= 1 or (status in {"reported", "call_pending"} and -1 <= days <= 1):
            due.add(ticker)

    surfaced: set[str] = set()
    for item in attention_items:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").upper()
        events = item.get("events") if isinstance(item.get("events"), list) else []
        if any(
            isinstance(event, dict) and event.get("event_type") == "earnings"
            for event in events
        ):
            surfaced.add(ticker)

    missing = sorted(due - surfaced)
    if missing:
        raise RuntimeError(
            "earnings due within one day are missing from Today UI: " + ", ".join(missing)
        )

    return {
        "batch_rows": len(batch_rows),
        "portfolio_calendar_rows": sum(
            1
            for row in calendar_items
            if isinstance(row, dict)
            and str(row.get("ticker") or "").upper() in portfolio
        ),
        "due_tickers": len(due),
        "surfaced_due_tickers": len(due & surfaced),
        "today_items": len(attention_items),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://rasita2644-star.github.io/stockcheck")
    parser.add_argument("--attempts", type=int, default=36)
    parser.add_argument("--sleep-seconds", type=float, default=10)
    args = parser.parse_args()

    expected_features = load_json(ROOT / "site/data/finnhub_features.json")
    expected_attention = load_json(ROOT / "site/data/attention_today.json")
    portfolio_payload = json.loads(
        (ROOT / "site/data/portfolio.json").read_text(encoding="utf-8")
    )
    portfolio = portfolio_tickers(portfolio_payload)
    expected_feature_time = expected_features.get("generated_at")
    expected_attention_time = expected_attention.get("updated_at")

    last_error: Exception | None = None
    for attempt in range(1, max(1, args.attempts) + 1):
        try:
            features = fetch_json(args.base_url, "data/finnhub_features.json")
            calendar = fetch_json(args.base_url, "data/earnings_calendar.json")
            attention = fetch_json(args.base_url, "data/attention_today.json")
            if not timestamp_at_least(features.get("generated_at"), expected_feature_time):
                raise RuntimeError("Pages still serves an older Finnhub feature snapshot")
            if not timestamp_at_least(attention.get("updated_at"), expected_attention_time):
                raise RuntimeError("Pages still serves an older Today snapshot")
            summary = validate_linkage(calendar, attention, features, portfolio)
            print(json.dumps({"status": "verified", "attempt": attempt, **summary}, indent=2))
            return
        except Exception as exc:
            last_error = exc
            print(f"verification attempt {attempt} failed: {exc}")
            if attempt < args.attempts:
                time.sleep(max(0, args.sleep_seconds))
    raise SystemExit(f"Finnhub/Today deployment verification failed: {last_error}")


if __name__ == "__main__":
    main()
