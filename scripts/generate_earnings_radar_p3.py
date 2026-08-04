#!/usr/bin/env python3
"""P3 canonical-first dual-read adapter for Earnings Radar."""
from __future__ import annotations
from collections import Counter
from typing import Any
import generate_earnings_radar as radar
from contracts.source_policy import Domain, describe_source, decide

READ_METRICS: Counter[str] = Counter()
_ORIGINAL_NORMALIZE_OFFICIAL_ROW = radar.normalize_official_row
_ORIGINAL_BUILD_PAYLOAD = radar.build_payload


def _canonical_source(row: dict[str, Any]) -> tuple[str, str, str] | None:
    provenance = row.get("provenance")
    policy = row.get("domain_policy")
    if not isinstance(provenance, list) or not provenance or not isinstance(provenance[0], dict):
        return None
    if not isinstance(policy, dict) or Domain.EARNINGS_RADAR.value not in policy:
        return None
    descriptor = describe_source(provenance[0])
    return descriptor.provider, descriptor.source_class.value, descriptor.evidence_kind.value


def normalize_official_row(row: dict[str, Any]) -> dict[str, Any] | None:
    item = _ORIGINAL_NORMALIZE_OFFICIAL_ROW(row)
    if item is None:
        return None
    canonical = _canonical_source(row)
    if canonical is not None:
        provider, source_class, evidence_kind = canonical
        item["source_type"] = provider
        item["source_class"] = source_class
        item["evidence_kind"] = evidence_kind
        item["domain_decision"] = str(row["domain_policy"][Domain.EARNINGS_RADAR.value])
        verification = row.get("verification") if isinstance(row.get("verification"), dict) else {}
        item["verification_level"] = verification.get("level")
        item["contract_read_path"] = "canonical"
        READ_METRICS["canonical_rows"] += 1
    else:
        descriptor = describe_source({"type": row.get("source_type") or "unknown"})
        item["source_class"] = descriptor.source_class.value
        item["evidence_kind"] = descriptor.evidence_kind.value
        item["domain_decision"] = decide(descriptor, Domain.EARNINGS_RADAR).value
        item["verification_level"] = "confirmed" if item.get("status") == "confirmed" else "estimated"
        item["contract_read_path"] = "legacy_fallback"
        READ_METRICS["legacy_fallback_rows"] += 1
    return item


def build_payload(*args: Any, **kwargs: Any) -> dict[str, Any]:
    READ_METRICS.clear()
    payload = _ORIGINAL_BUILD_PAYLOAD(*args, **kwargs)
    payload["contract_read_metrics"] = {
        "canonical_rows": READ_METRICS["canonical_rows"],
        "legacy_fallback_rows": READ_METRICS["legacy_fallback_rows"],
        "fallback_active": READ_METRICS["legacy_fallback_rows"] > 0,
        "policy": "canonical provenance/domain_policy first; legacy source_type fallback is temporary and observable",
    }
    return payload


radar.normalize_official_row = normalize_official_row
radar.build_payload = build_payload

if __name__ == "__main__":
    radar.main()
