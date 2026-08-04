#!/usr/bin/env python3
"""Canonical-only earnings reads after legacy-fallback retirement (P5)."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from contracts.source_policy import Decision, Domain, describe_source


class CanonicalEarningsContractError(ValueError):
    """Raised when an earnings row does not satisfy the canonical P5 contract."""


@dataclass(frozen=True)
class EarningsRead:
    row: dict[str, Any]
    mode: str
    decision: Decision
    provider: str


def _canonical_source(row: Mapping[str, Any]) -> Mapping[str, Any]:
    provenance = row.get("provenance")
    if not isinstance(provenance, list) or not provenance:
        raise CanonicalEarningsContractError("earnings row requires non-empty canonical provenance")
    source = provenance[0]
    if not isinstance(source, Mapping):
        raise CanonicalEarningsContractError("earnings provenance[0] must be an object")
    required = {"provider", "source_class", "evidence_kind", "contract_version"}
    missing = sorted(required.difference(source))
    if missing:
        raise CanonicalEarningsContractError(
            "earnings provenance missing canonical fields: " + ", ".join(missing)
        )
    return source


def read_earnings_row(row: Mapping[str, Any], domain: Domain | str) -> EarningsRead:
    """Read canonical provenance and policy only; legacy-only rows fail closed."""
    output = deepcopy(dict(row))
    source = _canonical_source(output)
    descriptor = describe_source(source)
    try:
        target = Domain(domain)
    except ValueError as exc:
        raise CanonicalEarningsContractError(f"unknown earnings target domain: {domain}") from exc

    canonical_policy = output.get("domain_policy")
    if not isinstance(canonical_policy, Mapping):
        raise CanonicalEarningsContractError("earnings row requires canonical domain_policy")
    raw_decision = canonical_policy.get(target.value)
    if raw_decision is None:
        raise CanonicalEarningsContractError(
            f"earnings domain_policy missing decision for {target.value}"
        )
    try:
        decision = Decision(str(raw_decision))
    except ValueError as exc:
        raise CanonicalEarningsContractError(
            f"invalid earnings policy decision for {target.value}: {raw_decision}"
        ) from exc

    # Preserve the legacy projection field for external backward compatibility,
    # but it is no longer read to determine identity or eligibility.
    output["source_type"] = str(output.get("source_type") or descriptor.provider).strip().lower()
    output["source_read_mode"] = "canonical"
    output["source_policy_decision"] = decision.value
    return EarningsRead(output, "canonical", decision, descriptor.provider)


def read_metrics(reads: list[EarningsRead]) -> dict[str, int]:
    return {
        "rows": len(reads),
        "canonical_rows": len(reads),
        "legacy_fallback_rows": 0,
        "policy_reject_rows": sum(read.decision is Decision.REJECT for read in reads),
    }
