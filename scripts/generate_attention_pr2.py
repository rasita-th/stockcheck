#!/usr/bin/env python3
"""PR2 additive adapter for free news discovery and source verification.

The underlying P0 generator remains the legacy-compatible contract owner. This
adapter runs P0 first, adds news/IR events, deduplicates across source types and
writes the same 2.0-p0 payload with additive PR2 metadata.
"""
from __future__ import annotations

import os
from typing import Any

import generate_attention_p0 as p0
from attention_sources import collect_news_events, deduplicate_events

REGISTRY_PATH = p0.DATA_DIR / "source_registry.json"
NEWS_STATE_PATH = p0.STATE_DIR / "news.json"
NEWS_ENABLED = os.environ.get("ATTENTION_NEWS_ENABLED", "0").lower() in {"1", "true", "yes"}


def _load_events() -> list[dict[str, Any]]:
    raw = p0.load_json(p0.GENERATED_DIR / "events.json", {}) or {}
    rows = raw.get("events") if isinstance(raw, dict) else []
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _coverage_status(source_health: dict[str, Any]) -> str:
    degraded = {"partial", "unavailable", "error"}
    return "partial" if any(str((value or {}).get("status") or "unknown") in degraded for value in source_health.values() if isinstance(value, dict)) else "complete"


def _enforce_unverified_cap(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Unverified news is never allowed above Watch without another primary event."""
    priority_order = {"Critical": 0, "Risk": 1, "Action": 2, "Watch": 3, "Developing": 4}
    for item in items:
        events = item.get("events") if isinstance(item.get("events"), list) else []
        primary = events[0] if events else {}
        if primary.get("verification_status") == "unverified" and item.get("priority") in {"Critical", "Risk", "Action"}:
            item["priority"] = "Watch"
            item["priority_score"] = min(int(item.get("priority_score") or 0), 51)
            item["severity"] = "medium"
    items.sort(key=lambda item: (priority_order.get(str(item.get("priority")), 9), -int(item.get("priority_score") or 0), str(item.get("ticker") or "")))
    return items[: p0.MAX_ITEMS]


def generate() -> dict[str, Any]:
    base_output = p0.generate()
    portfolio = p0.load_portfolio()
    portfolio_map = {stock["ticker"]: stock for stock in portfolio}
    technical_map = p0.load_technical_rows()
    contexts = {ticker: p0.price_context(technical_map.get(ticker)) for ticker in portfolio_map}
    registry = p0.load_json(REGISTRY_PATH, {}) or {}
    old_news_state = p0.load_json(NEWS_STATE_PATH, {}) or {}

    news_result = collect_news_events(
        portfolio=portfolio,
        registry=registry,
        old_state=old_news_state,
        enabled=NEWS_ENABLED,
    )
    merged_events = deduplicate_events(_load_events() + news_result.events)
    items = _enforce_unverified_cap(p0.aggregate_items(merged_events, portfolio_map, contexts))

    source_health = dict(base_output.get("source_health") or {})
    source_health.pop("news", None)
    source_health.update(news_result.health)
    errors = [row for row in base_output.get("errors", []) if isinstance(row, dict)] + news_result.errors
    summary = {label: sum(1 for item in items if item.get("priority") == label) for label in ("Critical", "Risk", "Action", "Watch", "Developing")}

    output = dict(base_output)
    output.update({
        "contract_version": "2.1-additive",
        "features": {**(base_output.get("features") or {}), "free_news_discovery": NEWS_ENABLED},
        "total_events": len(merged_events),
        "coverage_status": _coverage_status(source_health),
        "summary": summary,
        "source_health": source_health,
        "items": items,
        "errors": errors,
    })
    output["data_quality"] = {
        **(base_output.get("data_quality") or {}),
        "news_contract": "additive fields only; legacy P0 fields preserved",
        "news_policy": "GDELT is discovery-only; unverified reports are capped at Watch",
        "event_deduplication": "ticker + normalized subtype + time window + headline similarity",
        "source_registry_schema": str(registry.get("schema_version") or "unknown"),
    }

    event_output = {
        "schema_version": "1.0",
        "contract_version": "1.1-additive",
        "generated_at": output.get("updated_at"),
        "row_count": len(merged_events),
        "events": merged_events,
    }
    for path in p0.ATTENTION_OUT_PATHS:
        p0.save_json(path, output)
    for path in p0.EVENT_OUT_PATHS:
        p0.save_json(path, event_output)
    if NEWS_ENABLED:
        p0.save_json(NEWS_STATE_PATH, news_result.state)
    return output


def main() -> None:
    output = generate()
    print(
        "Generated PR2 attention list: "
        f"{len(output.get('items') or [])} items / {output.get('total_events')} events / "
        f"news={'enabled' if NEWS_ENABLED else 'disabled'}"
    )


if __name__ == "__main__":
    main()
