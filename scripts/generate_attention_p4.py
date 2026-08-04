#!/usr/bin/env python3
"""P4 Today generator with centralized source-policy enforcement."""
from __future__ import annotations

from typing import Any

import generate_attention_pr3 as base
from contracts.attention_policy import filter_attention_events
from contracts.earnings_reader import EarningsRead, read_earnings_row, read_metrics
from contracts.source_policy import Domain, allows

_ORIGINAL_LOAD_EARNINGS = base.pr2.p0.load_earnings_calendar
_ORIGINAL_BUILD_SECTIONS = base.pr2._build_sections
_LAST_READS: list[EarningsRead] = []
_LAST_EVENT_METRICS: dict[str, Any] = {}


def load_earnings_calendar() -> list[dict[str, Any]]:
    global _LAST_READS
    rows = _ORIGINAL_LOAD_EARNINGS()
    _LAST_READS = [read_earnings_row(row, Domain.TODAY_CATALYST) for row in rows]
    return [read.row for read in _LAST_READS if allows(read.decision)]


def build_sections_with_policy(
    events: list[dict[str, Any]],
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Apply the P4 gate to the complete event set before section construction.

    PR3 combines persisted/generated events with newly discovered and retained
    discovery events immediately before ``_build_sections``. Gating at this
    boundary guarantees every event that can be published is evaluated exactly
    once, including events restored from discovery state.
    """
    global _LAST_EVENT_METRICS
    accepted, _LAST_EVENT_METRICS = filter_attention_events(events)
    return _ORIGINAL_BUILD_SECTIONS(accepted, *args, **kwargs)


def generate() -> dict[str, Any]:
    base.pr2.p0.load_earnings_calendar = load_earnings_calendar
    base.pr2._build_sections = build_sections_with_policy
    output = base.generate()
    earnings_metrics = read_metrics(_LAST_READS)
    allowed_earnings = sum(allows(read.decision) for read in _LAST_READS)
    rejected_earnings = len(_LAST_READS) - allowed_earnings
    contract_metrics = {
        "phase": "P4",
        "read_order": "canonical_first_legacy_fallback",
        "policy_enforced": True,
        **earnings_metrics,
        "allowed_rows": allowed_earnings,
        "rejected_rows": rejected_earnings,
    }
    earnings_health = dict((output.get("source_health") or {}).get("earnings") or {})
    earnings_health.update(contract_metrics)
    output.setdefault("source_health", {})["earnings"] = earnings_health
    output.setdefault("data_quality", {})["earnings_contract_read"] = contract_metrics
    output["data_quality"]["attention_policy_gate"] = {
        "phase": "P4",
        "owner": "scripts/contracts/attention_policy.py",
        **_LAST_EVENT_METRICS,
    }
    for path in base.pr2.p0.ATTENTION_OUT_PATHS:
        base.pr2.p0.save_json(path, output)
    return output


def main() -> None:
    output = generate()
    metrics = output["data_quality"]["earnings_contract_read"]
    gate = output["data_quality"]["attention_policy_gate"]
    print(
        "Generated P4 Today Attention: "
        f"{len(output.get('items') or [])} items / "
        f"{metrics['allowed_rows']} earnings allowed / "
        f"{metrics['rejected_rows']} earnings rejected / "
        f"{gate.get('rejected_events', 0)} events rejected"
    )


if __name__ == "__main__":
    main()
