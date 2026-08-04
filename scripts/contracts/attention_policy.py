#!/usr/bin/env python3
"""Centralized fail-closed policy gate for Today Attention events."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from contracts.source_policy import Decision, Domain, allows, decide, describe_source


@dataclass(frozen=True)
class AttentionPolicyResult:
    allowed: bool
    decision: Decision
    provider: str
    domain: Domain
    reason: str


def _canonical_source(event: Mapping[str, Any]) -> Mapping[str, Any] | None:
    provenance = event.get("provenance")
    if isinstance(provenance, list) and provenance and isinstance(provenance[0], Mapping):
        return provenance[0]
    source = event.get("source")
    return source if isinstance(source, Mapping) else None


def evaluate_attention_event(event: Mapping[str, Any]) -> AttentionPolicyResult:
    """Evaluate one event using source capability, never a provider blacklist."""
    event_type = str(event.get("event_type") or "").strip().lower()
    domain = Domain.TECHNICAL_WATCH if event_type == "technical" else Domain.TODAY_CATALYST
    descriptor = describe_source(_canonical_source(event))
    decision = decide(descriptor, domain)
    return AttentionPolicyResult(
        allowed=allows(decision),
        decision=decision,
        provider=descriptor.provider,
        domain=domain,
        reason=f"{descriptor.source_class.value}/{descriptor.evidence_kind.value} -> {decision.value}",
    )


def filter_attention_events(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        result = evaluate_attention_event(event)
        if result.allowed:
            event["attention_policy_decision"] = result.decision.value
            accepted.append(event)
        else:
            rejected.append(
                {
                    "event_id": str(event.get("event_id") or ""),
                    "ticker": str(event.get("ticker") or ""),
                    "provider": result.provider,
                    "reason": result.reason,
                }
            )
    metrics = {
        "policy_enforced": True,
        "evaluated_events": len(accepted) + len(rejected),
        "accepted_events": len(accepted),
        "rejected_events": len(rejected),
        "reject_reasons": rejected[:25],
    }
    return accepted, metrics
