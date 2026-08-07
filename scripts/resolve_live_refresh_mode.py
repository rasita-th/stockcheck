#!/usr/bin/env python3
"""Resolve quote-only versus full technical refresh without conflating timestamps."""
from __future__ import annotations

import json
import os
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

try:
    from scripts.check_data_freshness import parse_timestamp
except ModuleNotFoundError:  # Direct execution via ``python scripts/...``.
    from check_data_freshness import parse_timestamp


MARKET_TZ = ZoneInfo("America/New_York")
FULL_REFRESH_LEAD_MINUTES = 45.0


def resolve_refresh_mode(
    *,
    now: datetime,
    event_name: str,
    event_schedule: str,
    requested_full: bool,
    technical_payload: dict[str, Any],
) -> dict[str, Any]:
    local_now = now.astimezone(MARKET_TZ)
    market_open = local_now.weekday() < 5 and time(9, 25) <= local_now.time() <= time(16, 20)
    scheduled_full = event_name == "schedule" and event_schedule == "35 21 * * 1-5"
    force_fast = event_name in {"workflow_dispatch", "push"}

    technical_stamp = technical_payload.get("generatedAtTechnical")
    technical_age_minutes: float | None = None
    if technical_stamp:
        try:
            technical_time = parse_timestamp(technical_stamp)
            technical_age_minutes = (local_now.astimezone(timezone.utc) - technical_time).total_seconds() / 60
        except (TypeError, ValueError):
            technical_age_minutes = None

    stale_market_baseline = market_open and (
        technical_age_minutes is None or technical_age_minutes >= FULL_REFRESH_LEAD_MINUTES
    )
    full_technical = requested_full or scheduled_full or stale_market_baseline
    run_refresh = market_open or force_fast or full_technical

    if requested_full:
        full_reason = "manual_full_refresh"
    elif scheduled_full:
        full_reason = "scheduled_after_close_refresh"
    elif stale_market_baseline:
        full_reason = "stale_market_hours_baseline"
    else:
        full_reason = "fast_quote_refresh"

    return {
        "run_refresh": run_refresh,
        "market_open": market_open,
        "full_technical": full_technical,
        "full_reason": full_reason,
        "technical_age_minutes": technical_age_minutes,
        "now": local_now.isoformat(),
    }


def main() -> None:
    path = Path(os.environ.get("TECHNICAL_DATA_PATH", "site/data/technical.json"))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    result = resolve_refresh_mode(
        now=datetime.now(MARKET_TZ),
        event_name=os.environ.get("EVENT_NAME", ""),
        event_schedule=os.environ.get("EVENT_SCHEDULE", ""),
        requested_full=os.environ.get("FULL_TECHNICAL_INPUT", "false").lower() == "true",
        technical_payload=payload if isinstance(payload, dict) else {},
    )
    for key, value in result.items():
        if isinstance(value, bool):
            value = "true" if value else "false"
        elif value is None:
            value = "unknown"
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
