#!/usr/bin/env python3
"""P3 canonical-first wrapper for the Earnings Radar generator."""
from __future__ import annotations

from typing import Any

import generate_earnings_radar as base
from contracts.earnings_reader import read_earnings_row, read_metrics
from contracts.source_policy import Domain


def build_payload(
    state: dict[str, Any],
    calendar: dict[str, Any],
    portfolio_payload: Any,
    relevance_payload: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    raw_rows = calendar.get("items") if isinstance(calendar, dict) and isinstance(calendar.get("items"), list) else []
    reads = [read_earnings_row(row, Domain.EARNINGS_RADAR) for row in raw_rows if isinstance(row, dict)]
    canonical_calendar = dict(calendar or {})
    canonical_calendar["items"] = [read.row for read in reads]
    payload = base.build_payload(state, canonical_calendar, portfolio_payload, relevance_payload, **kwargs)
    payload["source_contract"] = {
        "read_order": "canonical_first_legacy_fallback",
        "policy_enforced": False,
        **read_metrics(reads),
    }
    payload.setdefault("policy", {})["source_policy_phase"] = (
        "P3 observes canonical domain decisions; P4 will enforce the centralized gate"
    )
    return payload


def generate() -> dict[str, Any]:
    payload = build_payload(
        base.load_json(base.STATE_PATH, {}),
        base.load_json(base.CALENDAR_PATH, {}),
        base.load_json(base.PORTFOLIO_PATH, []),
        base.load_json(base.RELEVANCE_PATH, {}),
        days_back=int(base.os.getenv("EARNINGS_RADAR_DAYS_BACK", "1")),
        days_forward=int(base.os.getenv("EARNINGS_RADAR_DAYS_FORWARD", "14")),
    )
    for path in base.OUTPUT_PATHS:
        base.save_json(path, payload)
    return payload


def main() -> None:
    payload = generate()
    metrics = payload["source_contract"]
    print(
        "Generated P3 earnings radar: "
        f"{payload['coverage']['published_rows']} rows / "
        f"{metrics['canonical_rows']} canonical / "
        f"{metrics['legacy_fallback_rows']} legacy fallback"
    )


if __name__ == "__main__":
    main()
