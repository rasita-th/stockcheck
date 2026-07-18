from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

UTC = timezone.utc
PRIORITY_RANK = {"Critical": 0, "Risk": 1, "Action": 2, "Watch": 3, "Developing": 4}
DEFAULT_DISCOVERY_RETENTION_DAYS = 7
DISCOVERY_RETENTION_DAYS = {
    "regulatory": 14,
    "litigation": 14,
    "capital_raise": 14,
    "guidance": 10,
    "earnings": 7,
    "corporate_event": 7,
    "contract": 7,
    "management_change": 7,
    "analyst_action": 3,
    "news": 3,
}


def _parse_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except Exception:
        return None


def load_json(path: Path, default: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value
    except Exception:
        return deepcopy(default)


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _primary_event(item: dict[str, Any]) -> dict[str, Any]:
    events = item.get("events") if isinstance(item.get("events"), list) else []
    return events[0] if events and isinstance(events[0], dict) else {}


def item_key(item: dict[str, Any]) -> str:
    event = _primary_event(item)
    event_id = str(event.get("event_id") or "").strip()
    if event_id:
        return event_id
    return ":".join(
        (
            str(item.get("ticker") or "").upper(),
            str(item.get("event_subtype") or event.get("event_subtype") or "event"),
            str(item.get("event_time") or event.get("event_time") or "unknown"),
        )
    )


def discovered_event_key(event: dict[str, Any]) -> str:
    for field in ("event_id", "dedupe_key"):
        value = str(event.get(field) or "").strip()
        if value:
            return value
    source = event.get("source") if isinstance(event.get("source"), dict) else {}
    return ":".join(
        (
            str(event.get("ticker") or "").upper(),
            str(event.get("event_subtype") or event.get("event_type") or "event"),
            str(source.get("url") or event.get("event_time") or event.get("headline") or "unknown"),
        )
    )


def _event_is_resolved(event: dict[str, Any]) -> bool:
    status = str(event.get("resolution_status") or event.get("status") or "").strip().lower()
    return bool(event.get("resolved_at")) or status in {"resolved", "expired", "dismissed", "cancelled"}


def _retention_days(event: dict[str, Any]) -> int:
    event_type = str(event.get("event_type") or "").strip().lower()
    return int(DISCOVERY_RETENTION_DAYS.get(event_type, DEFAULT_DISCOVERY_RETENTION_DAYS))


def retain_active_discovered_events(
    new_events: list[dict[str, Any]],
    old_state: dict[str, Any] | None,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Keep news/regulator events active across refreshes until expiry or resolution.

    Discovery collectors intentionally emit only previously unseen URLs. Their URL
    cursors are not an active-event store, so this state preserves the full event
    while it remains decision-relevant. Expired or explicitly resolved events are
    removed and can then be reported as resolved by the PR3 history layer.
    """

    now = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    old_state = old_state if isinstance(old_state, dict) else {}
    prior_records = old_state.get("events") if isinstance(old_state.get("events"), dict) else {}
    active: dict[str, dict[str, Any]] = {}

    for key, record in prior_records.items():
        if not isinstance(record, dict):
            continue
        event = record.get("event") if isinstance(record.get("event"), dict) else {}
        expires_at = _parse_datetime(record.get("expires_at"))
        if not event or _event_is_resolved(event) or not expires_at or expires_at < now:
            continue
        active[str(key)] = {
            "event": deepcopy(event),
            "first_seen_at": str(record.get("first_seen_at") or now.isoformat()),
            "last_seen_at": str(record.get("last_seen_at") or now.isoformat()),
            "expires_at": expires_at.astimezone(UTC).replace(microsecond=0).isoformat(),
        }

    for event in new_events:
        if not isinstance(event, dict):
            continue
        key = discovered_event_key(event)
        if not key:
            continue
        if _event_is_resolved(event):
            active.pop(key, None)
            continue
        prior = active.get(key) if isinstance(active.get(key), dict) else {}
        first_seen = _parse_datetime(prior.get("first_seen_at")) or now
        prior_expiry = _parse_datetime(prior.get("expires_at"))
        candidate_expiry = now + timedelta(days=_retention_days(event))
        expires_at = max(prior_expiry, candidate_expiry) if prior_expiry else candidate_expiry
        active[key] = {
            "event": deepcopy(event),
            "first_seen_at": first_seen.isoformat(),
            "last_seen_at": now.isoformat(),
            "expires_at": expires_at.astimezone(UTC).replace(microsecond=0).isoformat(),
        }

    ordered_records = dict(
        sorted(
            active.items(),
            key=lambda pair: (
                str((pair[1].get("event") or {}).get("ticker") or ""),
                str(pair[0]),
            ),
        )
    )
    retained_events = [deepcopy(record["event"]) for record in ordered_records.values()]
    next_state = {
        "schema_version": "1.0",
        "updated_at": now.isoformat(),
        "active_count": len(retained_events),
        "events": ordered_records,
    }
    return retained_events, next_state


def _priority_change(current: str, previous: str) -> str:
    current_rank = PRIORITY_RANK.get(current, 9)
    previous_rank = PRIORITY_RANK.get(previous, 9)
    if current_rank < previous_rank:
        return "escalated"
    if current_rank > previous_rank:
        return "eased"
    return "ongoing"


def _change_label(status: str) -> str:
    return {
        "new": "เพิ่มเข้ามาวันนี้",
        "escalated": "สำคัญขึ้นจากรอบก่อน",
        "eased": "ความเร่งด่วนลดลง",
        "updated": "มีข้อมูลใหม่เพิ่ม",
        "ongoing": "ยังต้องติดตามต่อ",
        "resolved": "ออกจากรายการแล้ว",
    }.get(status, "ยังต้องติดตามต่อ")


def _impact_label(change_pct: float | None) -> str:
    if change_pct is None:
        return "ยังไม่มีราคาฐานสำหรับเปรียบเทียบ"
    if abs(change_pct) < 0.5:
        return "ราคายังเปลี่ยนแปลงไม่มาก"
    direction = "ปรับขึ้น" if change_pct > 0 else "ปรับลง"
    return f"ราคาหลังเริ่มติดตาม{direction} {abs(change_pct):.1f}%"


def _event_count(item: dict[str, Any]) -> int:
    return len(item.get("events")) if isinstance(item.get("events"), list) else 0


def _personal_score(item: dict[str, Any], preferences: dict[str, Any]) -> tuple[int, list[str]]:
    score = int(item.get("priority_score") or 0)
    reasons: list[str] = []
    if item.get("portfolio_status") == "holding":
        boost = int(preferences.get("holding_priority_boost") or 0)
        score += boost
        if boost:
            reasons.append(f"หุ้นในพอร์ต +{boost}")
    event_type = str(item.get("event_type") or _primary_event(item).get("event_type") or "")
    event_boosts = preferences.get("event_type_boosts") if isinstance(preferences.get("event_type_boosts"), dict) else {}
    event_boost = int(event_boosts.get(event_type) or 0)
    score += event_boost
    if event_boost:
        reasons.append(f"{event_type} +{event_boost}")
    ticker = str(item.get("ticker") or "").upper()
    ticker_boosts = preferences.get("ticker_boosts") if isinstance(preferences.get("ticker_boosts"), dict) else {}
    ticker_boost = int(ticker_boosts.get(ticker) or 0)
    score += ticker_boost
    if ticker_boost:
        reasons.append(f"{ticker} +{ticker_boost}")
    return score, reasons


def enrich_payload(
    payload: dict[str, Any],
    old_state: dict[str, Any] | None,
    preferences: dict[str, Any] | None,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    now = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    old_state = old_state if isinstance(old_state, dict) else {}
    preferences = preferences if isinstance(preferences, dict) else {}
    previous = old_state.get("items") if isinstance(old_state.get("items"), dict) else {}

    output = deepcopy(payload)
    current_rows: list[dict[str, Any]] = []
    for section in ("items", "technical_watch"):
        rows = output.get(section) if isinstance(output.get(section), list) else []
        for item in rows:
            if not isinstance(item, dict):
                continue
            key = item_key(item)
            prior = previous.get(key) if isinstance(previous.get(key), dict) else {}
            first_seen = _parse_datetime(prior.get("first_seen_at")) or now
            previous_priority = str(prior.get("priority") or "")
            status = "new" if not prior else _priority_change(str(item.get("priority") or ""), previous_priority)
            if prior and status == "ongoing" and _event_count(item) > int(prior.get("event_count") or 0):
                status = "updated"

            baseline_price = prior.get("baseline_price")
            if baseline_price is None:
                baseline_price = item.get("price")
            current_price = item.get("price")
            impact_pct = None
            try:
                baseline = float(baseline_price)
                current = float(current_price)
                if baseline:
                    impact_pct = round((current / baseline - 1) * 100, 2)
            except Exception:
                impact_pct = None

            personal_score, personal_reasons = _personal_score(item, preferences)
            active_days = max(0, (now.date() - first_seen.date()).days)
            item["change"] = {
                "status": status,
                "label_th": _change_label(status),
                "previous_priority": previous_priority or None,
                "first_seen_at": first_seen.isoformat(),
                "active_days": active_days,
            }
            item["impact"] = {
                "baseline_price": baseline_price,
                "current_price": current_price,
                "change_pct": impact_pct,
                "label_th": _impact_label(impact_pct),
            }
            item["personal_priority_score"] = personal_score
            item["personalization_reasons"] = personal_reasons
            item["_history_key"] = key
            current_rows.append(item)

        rows.sort(
            key=lambda item: (
                PRIORITY_RANK.get(str(item.get("priority") or ""), 9),
                -int(item.get("personal_priority_score") or item.get("priority_score") or 0),
                str(item.get("ticker") or ""),
            )
        )

    current_keys = {str(item.get("_history_key") or "") for item in current_rows}
    resolved: list[dict[str, Any]] = []
    for key, prior in previous.items():
        if key in current_keys or not isinstance(prior, dict):
            continue
        resolved.append(
            {
                "history_key": key,
                "ticker": prior.get("ticker"),
                "event_subtype": prior.get("event_subtype"),
                "priority": prior.get("priority"),
                "resolved_at": now.isoformat(),
                "label_th": _change_label("resolved"),
            }
        )
    resolved = (resolved + [row for row in old_state.get("resolved", []) if isinstance(row, dict)])[:20]

    changes_summary = {
        "new": sum(item.get("change", {}).get("status") == "new" for item in current_rows),
        "escalated": sum(item.get("change", {}).get("status") == "escalated" for item in current_rows),
        "updated": sum(item.get("change", {}).get("status") == "updated" for item in current_rows),
        "ongoing": sum(item.get("change", {}).get("status") == "ongoing" for item in current_rows),
        "eased": sum(item.get("change", {}).get("status") == "eased" for item in current_rows),
        "resolved": len(resolved),
    }

    for item in current_rows:
        item.pop("_history_key", None)

    output["contract_version"] = "3.0-attention-workflow"
    output["features"] = {
        **(output.get("features") if isinstance(output.get("features"), dict) else {}),
        "what_changed": True,
        "historical_impact": True,
        "local_review_actions": True,
        "personal_priority": True,
    }
    output["changes_summary"] = changes_summary
    output["recently_resolved"] = resolved[:10]
    output["preferences_applied"] = {
        "holding_priority_boost": int(preferences.get("holding_priority_boost") or 0),
        "event_type_boosts": preferences.get("event_type_boosts") if isinstance(preferences.get("event_type_boosts"), dict) else {},
        "ticker_boosts": preferences.get("ticker_boosts") if isinstance(preferences.get("ticker_boosts"), dict) else {},
    }

    next_items: dict[str, Any] = {}
    for section in ("items", "technical_watch"):
        for item in output.get(section) or []:
            key = item_key(item)
            change = item.get("change") if isinstance(item.get("change"), dict) else {}
            impact = item.get("impact") if isinstance(item.get("impact"), dict) else {}
            next_items[key] = {
                "ticker": item.get("ticker"),
                "event_subtype": item.get("event_subtype"),
                "priority": item.get("priority"),
                "priority_score": item.get("priority_score"),
                "personal_priority_score": item.get("personal_priority_score"),
                "first_seen_at": change.get("first_seen_at") or now.isoformat(),
                "last_seen_at": now.isoformat(),
                "event_count": _event_count(item),
                "baseline_price": impact.get("baseline_price"),
                "current_price": impact.get("current_price"),
            }

    next_state = {
        "schema_version": "1.0",
        "updated_at": now.isoformat(),
        "items": next_items,
        "resolved": resolved,
    }
    return output, next_state
