from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

UTC = timezone.utc
DISCOVERY_SOURCES = {"gdelt", "company_ir", "company_press_release", "regulator", "media"}
CONFIRMED_TTL_DAYS = max(1, int(os.environ.get("ATTENTION_CONFIRMED_EVENT_TTL_DAYS", "7")))
REGULATOR_TTL_DAYS = max(CONFIRMED_TTL_DAYS, int(os.environ.get("ATTENTION_REGULATOR_EVENT_TTL_DAYS", "14")))
UNVERIFIED_TTL_DAYS = max(1, int(os.environ.get("ATTENTION_UNVERIFIED_EVENT_TTL_DAYS", "1")))


def parse_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except Exception:
        return None


def event_anchor(event: dict[str, Any]) -> datetime | None:
    source = event.get("source") if isinstance(event.get("source"), dict) else {}
    for value in (event.get("detected_at"), source.get("published_at"), event.get("event_time")):
        parsed = parse_datetime(value)
        if parsed:
            return parsed.astimezone(UTC)
    return None


def retention_days(event: dict[str, Any]) -> int:
    source = event.get("source") if isinstance(event.get("source"), dict) else {}
    if source.get("type") == "regulator" or event.get("event_type") == "regulatory":
        return REGULATOR_TTL_DAYS
    if event.get("verification_status") == "confirmed":
        return CONFIRMED_TTL_DAYS
    return UNVERIFIED_TTL_DAYS


def retain_discovered_events(
    events: list[dict[str, Any]],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Retain active discovery events until a bounded expiry.

    Earnings, SEC and technical events are regenerated from their canonical
    sources every refresh and are deliberately excluded.
    """
    now = (now or datetime.now(UTC)).astimezone(UTC)
    retained: list[dict[str, Any]] = []
    for raw in events:
        if not isinstance(raw, dict):
            continue
        event = dict(raw)
        source = event.get("source") if isinstance(event.get("source"), dict) else {}
        source_type = str(source.get("type") or "")
        event_type = str(event.get("event_type") or "")
        if event_type in {"earnings", "sec_filing", "technical"}:
            continue
        if source_type not in DISCOVERY_SOURCES and event_type != "regulatory":
            continue
        anchor = event_anchor(event)
        if not anchor:
            continue
        explicit_expiry = parse_datetime(event.get("retention_expires_at"))
        expires_at = explicit_expiry.astimezone(UTC) if explicit_expiry else anchor + timedelta(days=retention_days(event))
        if expires_at <= now:
            continue
        event["retention_status"] = "active"
        event["retention_expires_at"] = expires_at.replace(microsecond=0).isoformat()
        event["retention_policy"] = "bounded_discovery_ttl"
        retained.append(event)
    return retained
