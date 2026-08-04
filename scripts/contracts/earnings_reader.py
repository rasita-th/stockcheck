#!/usr/bin/env python3
"""Canonical-first earnings reads with explicit legacy fallback diagnostics.

P3 changes read semantics only. It does not enforce domain rejection; P4 owns the
central policy gate. Consumers receive the canonical decision now so behavior can
be observed before enforcement.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from contracts.source_policy import Decision, Domain, decide, describe_source


@dataclass(frozen=True)
class EarningsRead:
    row: dict[str, Any]
    mode: str
    decision: Decision
    provider: str


def _canonical_source(row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    provenance = row.get("provenance")
    if not isinstance(provenance, list) or not provenance:
        return None
    source = provenance[0]
    if not isinstance(source, Mapping):
        return None
    required = {"provider", "source_class", "evidence_kind", "contract_version"}
    return source if required.issubset(source) else None


def read_earnings_row(row: Mapping[str, Any], domain: Domain | str) -> EarningsRead:
    """Read canonical fields first and fall back visibly to legacy source fields."""
    output = deepcopy(dict(row))
    source = _canonical_source(output)
    mode = "canonical" if source is not None else "legacy_fallback"
    descriptor = describe_source(
        source
        or {
            "provider": output.get("source_type") or output.get("provider") or "unknown",
            "type": output.get("source_type") or output.get("provider") or "unknown",
        }
    )
    try:
        target = Domain(domain)
    except ValueError:
        target = Domain.EARNINGS_RADAR
    canonical_policy = output.get("domain_policy") if isinstance(output.get("domain_policy"), Mapping) else {}
    raw_decision = canonical_policy.get(target.value) if mode == "canonical" else None
    try:
        decision = Decision(str(raw_decision)) if raw_decision is not None else decide(descriptor, target)
    except ValueError:
        decision = Decision.REJECT
    output["source_type"] = str(output.get("source_type") or descriptor.provider).strip().lower()
    output["source_read_mode"] = mode
    output["source_policy_decision"] = decision.value
    return EarningsRead(output, mode, decision, descriptor.provider)


def read_metrics(reads: list[EarningsRead]) -> dict[str, int]:
    return {
        "rows": len(reads),
        "canonical_rows": sum(read.mode == "canonical" for read in reads),
        "legacy_fallback_rows": sum(read.mode == "legacy_fallback" for read in reads),
        "policy_reject_rows": sum(read.decision is Decision.REJECT for read in reads),
    }
