#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ATTENTION = ROOT / "data" / "generated" / "attention_today.json"
EVENTS = ROOT / "data" / "generated" / "events.json"
GOLDEN = ROOT / "tests" / "golden" / "attention_today_v2_0.json"


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: root must be an object")
    return data


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def validate_legacy_contract(current: dict[str, Any], golden: dict[str, Any]) -> None:
    for field in golden:
        require(field in current, f"attention_today lost legacy top-level field: {field}")
    current_items = current.get("items") or []
    if current_items:
        golden_item = (golden.get("items") or [{}])[0]
        for field in golden_item:
            require(field in current_items[0], f"attention item lost legacy field: {field}")


def main() -> None:
    attention = load(ATTENTION)
    events_doc = load(EVENTS)
    golden = load(GOLDEN)
    validate_legacy_contract(attention, golden)
    features = attention.get("features") if isinstance(attention.get("features"), dict) else {}
    source_health = attention.get("source_health") if isinstance(attention.get("source_health"), dict) else {}
    if features.get("free_news_discovery"):
        for key in ("news", "ir", "gdelt"):
            require(key in source_health, f"PR2 source health missing: {key}")
    seen_dedupe: set[str] = set()
    for event in events_doc.get("events") or []:
        source_type = str((event.get("source") or {}).get("type") or "")
        if source_type not in {"gdelt", "company_ir"}:
            continue
        for field in ("dedupe_key", "entity_confidence", "verification_level", "verification_reason", "source_chain"):
            require(field in event, f"PR2 event missing {field}: {event.get('event_id')}")
        require(isinstance(event.get("source_chain"), list) and event["source_chain"], f"PR2 event source_chain is empty: {event.get('event_id')}")
        dedupe_key = str(event.get("dedupe_key") or "")
        require(dedupe_key not in seen_dedupe, f"duplicate PR2 dedupe_key: {dedupe_key}")
        seen_dedupe.add(dedupe_key)
        if event.get("verification_status") == "confirmed":
            require(any((source or {}).get("quality") == "primary" and (source or {}).get("url") for source in event["source_chain"]), f"confirmed PR2 event lacks primary source: {event.get('event_id')}")
    for item in attention.get("items") or []:
        events = item.get("events") if isinstance(item.get("events"), list) else []
        if events and events[0].get("verification_status") == "unverified":
            require(item.get("priority") in {"Watch", "Developing"}, f"unverified item exceeds Watch: {item.get('ticker')}")
    print("PR2 attention validation passed")


if __name__ == "__main__":
    main()
