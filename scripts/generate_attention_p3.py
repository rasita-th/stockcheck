#!/usr/bin/env python3
"""P3 canonical-first wrapper for the PR3 Today Attention generator."""
from __future__ import annotations

from typing import Any

import generate_attention_pr3 as base
from contracts.earnings_reader import EarningsRead, read_earnings_row, read_metrics
from contracts.source_policy import Domain

_ORIGINAL_LOAD_EARNINGS = base.pr2.p0.load_earnings_calendar
_LAST_READS: list[EarningsRead] = []


def load_earnings_calendar() -> list[dict[str, Any]]:
    global _LAST_READS
    rows = _ORIGINAL_LOAD_EARNINGS()
    _LAST_READS = [read_earnings_row(row, Domain.TODAY_CATALYST) for row in rows]
    return [read.row for read in _LAST_READS]


def generate() -> dict[str, Any]:
    base.pr2.p0.load_earnings_calendar = load_earnings_calendar
    output = base.generate()
    metrics = read_metrics(_LAST_READS)
    earnings_health = dict((output.get("source_health") or {}).get("earnings") or {})
    earnings_health.update(
        {
            "read_order": "canonical_first_legacy_fallback",
            "policy_enforced": False,
            **metrics,
        }
    )
    output.setdefault("source_health", {})["earnings"] = earnings_health
    output.setdefault("data_quality", {})["earnings_contract_read"] = {
        "phase": "P3",
        "read_order": "canonical_first_legacy_fallback",
        "policy_enforced": False,
        **metrics,
    }
    for path in base.pr2.p0.ATTENTION_OUT_PATHS:
        base.pr2.p0.save_json(path, output)
    return output


def main() -> None:
    output = generate()
    metrics = output["data_quality"]["earnings_contract_read"]
    print(
        "Generated P3 Today Attention: "
        f"{len(output.get('items') or [])} items / "
        f"{metrics['canonical_rows']} canonical / "
        f"{metrics['legacy_fallback_rows']} legacy fallback"
    )


if __name__ == "__main__":
    main()
