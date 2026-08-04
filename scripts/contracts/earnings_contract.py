#!/usr/bin/env python3
"""Backward-compatible canonical provenance for earnings contracts.

P2 is an additive dual-write phase: every legacy earnings field is preserved,
while canonical identity, provenance, verification and domain-policy fields are
written alongside it. Consumers continue to read legacy fields until the P3
dual-read migration.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping

from contracts.source_policy import (
    CONTRACT_VERSION as SOURCE_POLICY_CONTRACT_VERSION,
    Decision,
    Domain,
    EvidenceKind,
    SourceClass,
    decide,
    describe_source,
)

EARNINGS_ITEM_CONTRACT_VERSION = "1.0.0"
CONFIRMED_STATUSES = {"confirmed", "reported", "call_pending"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalized(value: Any) -> str:
    return str(value or "").strip().lower()


def _ticker(item: Mapping[str, Any]) -> str:
    return str(item.get("ticker") or item.get("symbol") or "").strip().upper()


def _earnings_date(item: Mapping[str, Any]) -> str:
    return str(item.get("earnings_date") or item.get("date") or "").strip()[:10]


def _legacy_source(item: Mapping[str, Any]) -> dict[str, Any]:
    source = item.get("source") if isinstance(item.get("source"), Mapping) else {}
    return {
        **dict(source),
        "provider": (
            source.get("provider")
            or source.get("type")
            or item.get("source_type")
            or item.get("provider")
            or "unknown"
        ),
        "type": source.get("type") or item.get("source_type") or item.get("provider") or "unknown",
    }


def _existing_provenance(item: Mapping[str, Any]) -> dict[str, Any] | None:
    rows = item.get("provenance")
    if not isinstance(rows, list) or not rows:
        return None
    first = rows[0]
    return dict(first) if isinstance(first, Mapping) else None


def _verification_level(status: str, source_class: SourceClass, evidence_kind: EvidenceKind) -> str:
    if status in CONFIRMED_STATUSES and source_class is SourceClass.PRIMARY:
        return "confirmed"
    if evidence_kind is EvidenceKind.MARKET_ESTIMATE:
        return "estimated"
    if evidence_kind is EvidenceKind.PUBLIC_REPORT:
        return "unverified"
    if source_class is SourceClass.INTERNAL:
        return "confirmed_internal"
    return "unknown"


def enrich_earnings_item(
    item: Mapping[str, Any],
    *,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Return an enriched copy without changing or deleting legacy fields."""
    output = deepcopy(dict(item))
    existing = _existing_provenance(output)
    descriptor = describe_source(existing or _legacy_source(output))
    ticker = _ticker(output)
    event_date = _earnings_date(output)
    status = _normalized(output.get("status")) or "estimated"
    source_url = (
        (existing or {}).get("source_url")
        or output.get("source_url")
        or ((output.get("source") or {}).get("url") if isinstance(output.get("source"), Mapping) else None)
    )
    source_retrieved_at = (
        (existing or {}).get("retrieved_at")
        or retrieved_at
        or output.get("updated_at")
        or output.get("confirmed_at")
        or None
    )
    verification_level = _verification_level(status, descriptor.source_class, descriptor.evidence_kind)
    confirmed_by = [descriptor.provider] if verification_level == "confirmed" else []

    output["contract_version"] = EARNINGS_ITEM_CONTRACT_VERSION
    output["identity"] = {
        "event_id": f"earnings:{ticker}:{event_date}" if ticker and event_date else "",
        "ticker": ticker,
        "earnings_date": event_date,
    }
    output["provenance"] = [
        {
            **descriptor.as_dict(),
            "source_url": source_url,
            "retrieved_at": source_retrieved_at,
        }
    ]
    output["verification"] = {
        "level": verification_level,
        "status": status,
        "confirmed_by": confirmed_by,
    }
    output["domain_policy"] = {
        domain.value: decide(descriptor, domain).value
        for domain in Domain
    }
    return output


def enrich_earnings_document(
    payload: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Dual-write canonical fields into every item of a legacy calendar document."""
    output = deepcopy(dict(payload))
    timestamp = generated_at or str(output.get("updated_at") or "") or _now_iso()
    rows = output.get("items")
    items = [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []
    output["items"] = [enrich_earnings_item(row, retrieved_at=timestamp) for row in items]
    output["item_contract_version"] = EARNINGS_ITEM_CONTRACT_VERSION
    output["source_policy_contract_version"] = SOURCE_POLICY_CONTRACT_VERSION
    features = output.get("features") if isinstance(output.get("features"), Mapping) else {}
    output["features"] = {
        **dict(features),
        "canonical_provenance": True,
        "legacy_fields_preserved": True,
        "dual_write": True,
    }
    output["contract_metrics"] = {
        "item_count": len(output["items"]),
        "canonical_provenance_rows": sum(bool(row.get("provenance")) for row in output["items"]),
        "unknown_source_rows": sum(
            row.get("domain_policy", {}).get(Domain.EARNINGS_RADAR.value) == Decision.REJECT.value
            for row in output["items"]
        ),
    }
    return output
