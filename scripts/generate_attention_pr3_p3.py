#!/usr/bin/env python3
"""P3 canonical-first dual-read adapter for Today Attention."""
from __future__ import annotations
from collections import Counter
from typing import Any

import generate_attention_pr3 as pr3
from contracts.source_policy import Domain, describe_source, decide

READ_METRICS: Counter[str] = Counter()
p0 = pr3.pr2.p0
_ORIGINAL_LOAD = p0.load_earnings_calendar
_ORIGINAL_GENERATE = pr3.generate


def load_earnings_calendar() -> list[dict[str, Any]]:
    rows = _ORIGINAL_LOAD()
    output: list[dict[str, Any]] = []
    READ_METRICS.clear()
    for row in rows:
        item = dict(row)
        provenance = item.get("provenance")
        policy = item.get("domain_policy")
        if isinstance(provenance, list) and provenance and isinstance(provenance[0], dict) and isinstance(policy, dict) and Domain.TODAY_CATALYST.value in policy:
            descriptor = describe_source(provenance[0])
            item["source_type"] = descriptor.provider
            item["source_class"] = descriptor.source_class.value
            item["evidence_kind"] = descriptor.evidence_kind.value
            item["domain_decision"] = str(policy[Domain.TODAY_CATALYST.value])
            verification = item.get("verification") if isinstance(item.get("verification"), dict) else {}
            item["verification_level"] = verification.get("level")
            item["contract_read_path"] = "canonical"
            READ_METRICS["canonical_rows"] += 1
        else:
            descriptor = describe_source({"type": item.get("source_type") or "unknown"})
            item["source_class"] = descriptor.source_class.value
            item["evidence_kind"] = descriptor.evidence_kind.value
            item["domain_decision"] = decide(descriptor, Domain.TODAY_CATALYST).value
            item["contract_read_path"] = "legacy_fallback"
            READ_METRICS["legacy_fallback_rows"] += 1
        output.append(item)
    return output


def generate() -> dict[str, Any]:
    payload = _ORIGINAL_GENERATE()
    payload["contract_read_metrics"] = {
        "canonical_rows": READ_METRICS["canonical_rows"],
        "legacy_fallback_rows": READ_METRICS["legacy_fallback_rows"],
        "fallback_active": READ_METRICS["legacy_fallback_rows"] > 0,
        "policy": "canonical provenance/domain_policy first; legacy source_type fallback is temporary and observable",
    }
    for path in p0.ATTENTION_OUT_PATHS:
        p0.save_json(path, payload)
    return payload


p0.load_earnings_calendar = load_earnings_calendar

if __name__ == "__main__":
    result = generate()
    print(f"Generated P3 Attention with {result['contract_read_metrics']['legacy_fallback_rows']} legacy fallback rows")
