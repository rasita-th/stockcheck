#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ATTENTION = ROOT / "data" / "generated" / "attention_today.json"
EVENTS = ROOT / "data" / "generated" / "events.json"

VALID_CHANGE_STATUS = {"new", "escalated", "eased", "updated", "ongoing"}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: root must be an object")
    return data


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    attention = load(ATTENTION)
    events_doc = load(EVENTS)
    require(str(attention.get("contract_version") or "").startswith("3.0"), "PR3 payload must use contract 3.0")

    features = attention.get("features") if isinstance(attention.get("features"), dict) else {}
    for key in (
        "what_changed",
        "historical_impact",
        "local_review_actions",
        "personal_priority",
        "discovered_event_retention",
    ):
        require(features.get(key) is True, f"PR3 feature missing: {key}")

    changes = attention.get("changes_summary") if isinstance(attention.get("changes_summary"), dict) else {}
    for key in ("new", "escalated", "updated", "ongoing", "eased", "resolved"):
        require(isinstance(changes.get(key), int), f"changes_summary.{key} must be an integer")

    require(isinstance(attention.get("recently_resolved"), list), "recently_resolved must be a list")
    require(isinstance(attention.get("preferences_applied"), dict), "preferences_applied must be an object")

    rows = []
    for section in ("items", "technical_watch"):
        section_rows = attention.get(section) if isinstance(attention.get(section), list) else []
        rows.extend(section_rows)
        for item in section_rows:
            ticker = item.get("ticker")
            change = item.get("change") if isinstance(item.get("change"), dict) else {}
            impact = item.get("impact") if isinstance(item.get("impact"), dict) else {}
            require(change.get("status") in VALID_CHANGE_STATUS, f"invalid PR3 change status: {ticker}")
            require(bool(change.get("label_th")), f"PR3 Thai change label missing: {ticker}")
            require(isinstance(change.get("active_days"), int) and change["active_days"] >= 0, f"PR3 active_days invalid: {ticker}")
            require("baseline_price" in impact and "current_price" in impact and "change_pct" in impact, f"PR3 impact contract missing: {ticker}")
            require(bool(impact.get("label_th")), f"PR3 impact Thai label missing: {ticker}")
            require(isinstance(item.get("personal_priority_score"), int), f"personal priority score missing: {ticker}")
            require(isinstance(item.get("personalization_reasons"), list), f"personalization reasons missing: {ticker}")

    source_health = attention.get("source_health") if isinstance(attention.get("source_health"), dict) else {}
    if features.get("official_regulator_sources"):
        require("regulators" in source_health, "regulator source health missing")
    retention_health = source_health.get("discovered_event_retention")
    require(isinstance(retention_health, dict), "discovered event retention health missing")
    require(retention_health.get("status") == "ok", "discovered event retention health is not ok")
    require(isinstance(retention_health.get("retained_events"), int), "retained event count must be an integer")
    for key in ("confirmed_ttl_days", "regulator_ttl_days", "unverified_ttl_days"):
        require(isinstance(retention_health.get(key), int) and retention_health[key] > 0, f"retention health missing {key}")

    quality = attention.get("data_quality") if isinstance(attention.get("data_quality"), dict) else {}
    require(bool(quality.get("discovery_retention_policy")), "discovery retention policy missing")

    regulator_dedupe: set[str] = set()
    for event in events_doc.get("events") or []:
        source = event.get("source") if isinstance(event.get("source"), dict) else {}
        if source.get("type") != "regulator":
            continue
        event_id = str(event.get("event_id") or "")
        require(event.get("verification_status") == "confirmed", f"regulator event must be confirmed: {event_id}")
        require(source.get("quality") == "primary" and bool(source.get("url")), f"regulator event lacks official URL: {event_id}")
        require(bool(event.get("regulator")), f"regulator agency key missing: {event_id}")
        require(event.get("entity_confidence") in {"high", "medium"}, f"regulator company match is not confident: {event_id}")
        dedupe_key = str(event.get("dedupe_key") or "")
        require(dedupe_key and dedupe_key not in regulator_dedupe, f"duplicate regulator event: {event_id}")
        regulator_dedupe.add(dedupe_key)
        if event.get("retention_status") == "active":
            require(bool(event.get("retention_expires_at")), f"retained regulator event lacks expiry: {event_id}")

    print(
        f"PR3 validation passed: {len(rows)} active items, "
        f"{len(regulator_dedupe)} regulator events, "
        f"{retention_health.get('retained_events')} retained"
    )


if __name__ == "__main__":
    main()
