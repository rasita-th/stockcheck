#!/usr/bin/env python3
"""Canonical source provenance and domain-eligibility policy.

This module is intentionally not wired into production generators yet. It defines
and tests the contract that later migration PRs will adopt through dual-write and
dual-read phases.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

CONTRACT_VERSION = "1.0.0"


class SourceClass(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    DISCOVERY = "discovery"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


class EvidenceKind(StrEnum):
    OFFICIAL_RECORD = "official_record"
    COMPANY_DISCLOSURE = "company_disclosure"
    PUBLIC_REPORT = "public_report"
    MARKET_ESTIMATE = "market_estimate"
    INTERNAL_SIGNAL = "internal_signal"
    UNKNOWN = "unknown"


class Domain(StrEnum):
    EARNINGS_RADAR = "earnings_radar"
    TODAY_CATALYST = "today_catalyst"
    TECHNICAL_WATCH = "technical_watch"


class Decision(StrEnum):
    ALLOW = "allow"
    ALLOW_ESTIMATED = "allow_estimated"
    ALLOW_UNVERIFIED = "allow_unverified"
    ALLOW_INTERNAL_ONLY = "allow_internal_only"
    REJECT = "reject"


@dataclass(frozen=True)
class SourceDescriptor:
    provider: str
    source_class: SourceClass
    evidence_kind: EvidenceKind
    contract_version: str = CONTRACT_VERSION

    def as_dict(self) -> dict[str, str]:
        return {
            "contract_version": self.contract_version,
            "provider": self.provider,
            "source_class": self.source_class.value,
            "evidence_kind": self.evidence_kind.value,
        }


_LEGACY_SOURCE_MAP: dict[str, tuple[SourceClass, EvidenceKind]] = {
    "company_ir": (SourceClass.PRIMARY, EvidenceKind.COMPANY_DISCLOSURE),
    "company_press_release": (SourceClass.PRIMARY, EvidenceKind.COMPANY_DISCLOSURE),
    "company": (SourceClass.PRIMARY, EvidenceKind.COMPANY_DISCLOSURE),
    "primary": (SourceClass.PRIMARY, EvidenceKind.COMPANY_DISCLOSURE),
    "sec": (SourceClass.PRIMARY, EvidenceKind.OFFICIAL_RECORD),
    "regulator": (SourceClass.PRIMARY, EvidenceKind.OFFICIAL_RECORD),
    "technical_json": (SourceClass.INTERNAL, EvidenceKind.INTERNAL_SIGNAL),
    "internal": (SourceClass.INTERNAL, EvidenceKind.INTERNAL_SIGNAL),
    "finnhub": (SourceClass.DISCOVERY, EvidenceKind.MARKET_ESTIMATE),
    "gdelt": (SourceClass.DISCOVERY, EvidenceKind.PUBLIC_REPORT),
    "news": (SourceClass.DISCOVERY, EvidenceKind.PUBLIC_REPORT),
    "rss": (SourceClass.DISCOVERY, EvidenceKind.PUBLIC_REPORT),
    "curated": (SourceClass.SECONDARY, EvidenceKind.MARKET_ESTIMATE),
}


def _normalized(value: Any) -> str:
    return str(value or "").strip().lower()


def _enum_value(enum_type: type[StrEnum], value: Any, fallback: StrEnum) -> StrEnum:
    try:
        return enum_type(_normalized(value))
    except ValueError:
        return fallback


def describe_source(source: Mapping[str, Any] | None) -> SourceDescriptor:
    """Normalize canonical provenance fields or migrate a legacy source object.

    Explicit canonical fields win. Missing or invalid fields fail closed as
    ``unknown`` instead of being inferred from a quality label alone.
    """
    source = source if isinstance(source, Mapping) else {}
    provider = _normalized(source.get("provider") or source.get("type")) or "unknown"

    if source.get("source_class") is not None or source.get("evidence_kind") is not None:
        source_class = _enum_value(SourceClass, source.get("source_class"), SourceClass.UNKNOWN)
        evidence_kind = _enum_value(EvidenceKind, source.get("evidence_kind"), EvidenceKind.UNKNOWN)
        return SourceDescriptor(
            provider=provider,
            source_class=SourceClass(source_class),
            evidence_kind=EvidenceKind(evidence_kind),
        )

    source_class, evidence_kind = _LEGACY_SOURCE_MAP.get(
        provider,
        (SourceClass.UNKNOWN, EvidenceKind.UNKNOWN),
    )
    return SourceDescriptor(
        provider=provider,
        source_class=source_class,
        evidence_kind=evidence_kind,
    )


def decide(descriptor: SourceDescriptor, domain: Domain | str) -> Decision:
    """Return the fail-closed eligibility decision for a target domain."""
    try:
        target = Domain(domain)
    except ValueError:
        return Decision.REJECT

    if descriptor.source_class is SourceClass.UNKNOWN or descriptor.evidence_kind is EvidenceKind.UNKNOWN:
        return Decision.REJECT

    if target is Domain.EARNINGS_RADAR:
        if descriptor.evidence_kind in {EvidenceKind.OFFICIAL_RECORD, EvidenceKind.COMPANY_DISCLOSURE}:
            return Decision.ALLOW
        if descriptor.evidence_kind is EvidenceKind.MARKET_ESTIMATE and descriptor.source_class in {
            SourceClass.PRIMARY,
            SourceClass.SECONDARY,
            SourceClass.DISCOVERY,
        }:
            return Decision.ALLOW_ESTIMATED
        return Decision.REJECT

    if target is Domain.TODAY_CATALYST:
        if descriptor.evidence_kind in {EvidenceKind.OFFICIAL_RECORD, EvidenceKind.COMPANY_DISCLOSURE}:
            return Decision.ALLOW
        if descriptor.evidence_kind is EvidenceKind.PUBLIC_REPORT and descriptor.source_class in {
            SourceClass.SECONDARY,
            SourceClass.DISCOVERY,
        }:
            return Decision.ALLOW_UNVERIFIED
        return Decision.REJECT

    if target is Domain.TECHNICAL_WATCH:
        if descriptor.source_class is SourceClass.INTERNAL and descriptor.evidence_kind is EvidenceKind.INTERNAL_SIGNAL:
            return Decision.ALLOW_INTERNAL_ONLY
        return Decision.REJECT

    return Decision.REJECT


def allows(decision: Decision) -> bool:
    return decision is not Decision.REJECT
