#!/usr/bin/env python3
"""P5 canonical-only wrapper for the Earnings Radar generator."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import generate_earnings_radar as base
from contracts.earnings_contract import enrich_earnings_item
from contracts.earnings_reader import EarningsRead, read_earnings_row, read_metrics
from contracts.source_policy import Domain, allows


def _canonicalize_market_state(state: dict[str, Any]) -> tuple[dict[str, Any], list[EarningsRead]]:
    canonical_state = deepcopy(state if isinstance(state, dict) else {})
    batch = canonical_state.get("batch") if isinstance(canonical_state.get("batch"), dict) else {}
    calendar = batch.get("earnings_calendar") if isinstance(batch.get("earnings_calendar"), dict) else {}
    raw_rows = calendar.get("data") if isinstance(calendar.get("data"), list) else []
    reads: list[EarningsRead] = []
    allowed_rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        canonical = enrich_earnings_item({**raw, "source_type": "finnhub", "status": raw.get("status") or "estimated"})
        read = read_earnings_row(canonical, Domain.EARNINGS_RADAR)
        reads.append(read)
        if allows(read.decision):
            allowed_rows.append(raw)
    canonical_calendar = dict(calendar)
    canonical_calendar["data"] = allowed_rows
    canonical_batch = dict(batch)
    canonical_batch["earnings_calendar"] = canonical_calendar
    canonical_state["batch"] = canonical_batch
    return canonical_state, reads


def build_payload(state: dict[str, Any], calendar: dict[str, Any], portfolio_payload: Any, relevance_payload: Any, **kwargs: Any) -> dict[str, Any]:
    raw_rows = calendar.get("items") if isinstance(calendar, dict) and isinstance(calendar.get("items"), list) else []
    calendar_reads = [read_earnings_row(row, Domain.EARNINGS_RADAR) for row in raw_rows if isinstance(row, dict)]
    canonical_calendar = dict(calendar or {})
    canonical_calendar["items"] = [read.row for read in calendar_reads if allows(read.decision)]
    canonical_state, state_reads = _canonicalize_market_state(state)
    all_reads = state_reads + calendar_reads
    payload = base.build_payload(canonical_state, canonical_calendar, portfolio_payload, relevance_payload, **kwargs)
    payload["source_contract"] = {
        "phase": "P5",
        "read_order": "canonical_only",
        "policy_enforced": True,
        "legacy_fallback_retired": True,
        "state_rows": len(state_reads),
        "calendar_rows": len(calendar_reads),
        **read_metrics(all_reads),
    }
    payload.setdefault("policy", {})["source_policy_phase"] = "P5 canonical-only policy enforcement"
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
    print(f"Generated P5 earnings radar: {payload['coverage']['published_rows']} rows / {metrics['canonical_rows']} canonical / 0 legacy fallback")


if __name__ == "__main__":
    main()
