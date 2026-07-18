#!/usr/bin/env python3
"""PR2/PR3 additive adapter for catalyst-first Today Attention.

The P0 generator remains the legacy-compatible event producer. This adapter:
- adds free news/IR discovery
- preserves source verification and deduplication
- separates company/fundamental catalysts from technical-only context
- keeps technical watch items recent, objective and clearly secondary
"""
from __future__ import annotations

import os
from typing import Any

import generate_attention_p0 as p0
from attention_sources import collect_news_events, deduplicate_events

REGISTRY_PATH = p0.DATA_DIR / "source_registry.json"
NEWS_STATE_PATH = p0.STATE_DIR / "news.json"
NEWS_ENABLED = os.environ.get("ATTENTION_NEWS_ENABLED", "0").lower() in {"1", "true", "yes"}
TECHNICAL_WATCH_MIN = max(0, min(p0.MAX_ITEMS, int(os.environ.get("ATTENTION_TECHNICAL_WATCH_MIN", "3"))))
MAX_TECHNICAL_AGE_DAYS = max(0, int(os.environ.get("ATTENTION_TECHNICAL_MAX_AGE_DAYS", "3")))


def _load_events() -> list[dict[str, Any]]:
    raw = p0.load_json(p0.GENERATED_DIR / "events.json", {}) or {}
    rows = raw.get("events") if isinstance(raw, dict) else []
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _coverage_status(source_health: dict[str, Any]) -> str:
    degraded = {"partial", "unavailable", "error"}
    return "partial" if any(
        str((value or {}).get("status") or "unknown") in degraded
        for value in source_health.values()
        if isinstance(value, dict)
    ) else "complete"


def _first_ratio(row: dict[str, Any] | None) -> float | None:
    row = row if isinstance(row, dict) else {}
    for key in ("relativeVolume", "relVolume", "volumeRatio", "volumeRatio20"):
        value = p0.to_float(row.get(key))
        if value is not None:
            return value
    return None


def _technical_contexts(
    technical_map: dict[str, dict[str, Any]],
    portfolio_map: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    contexts: dict[str, dict[str, Any]] = {}
    for ticker in portfolio_map:
        row = technical_map.get(ticker)
        context = p0.price_context(row)
        context["relative_volume"] = _first_ratio(row)
        contexts[ticker] = context
    return contexts


def _restore_internal_verification(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for event in events:
        source = event.get("source") if isinstance(event.get("source"), dict) else {}
        if event.get("event_type") == "technical" and source.get("quality") == "internal":
            event["verification_status"] = "confirmed"
            event["verification_level"] = "confirmed_internal"
            event["verification_reason"] = "Derived directly from the repository's latest technical.json row."
    return events


def _dedupe_with_provenance(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _restore_internal_verification(deduplicate_events(events))


def _scan_date(row: dict[str, Any]) -> Any:
    for key in ("regularMarketTime", "date", "dataDate", "asOfDate"):
        parsed = p0.parse_date(row.get(key))
        if parsed:
            return parsed
    return None


def _technical_scan_candidates(
    portfolio: list[dict[str, Any]],
    technical_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create recent technical-only watch events from the existing scanner output."""
    today = p0.now_et().date()
    detected_at = p0.now_utc().replace(microsecond=0).isoformat()
    ranked: list[tuple[tuple[int, float, float, str], dict[str, Any]]] = []

    for stock in portfolio:
        ticker = str(stock.get("ticker") or "").upper()
        row = technical_map.get(ticker) if ticker else None
        if not isinstance(row, dict):
            continue

        score = p0.to_float(row.get("score"))
        scan_date = _scan_date(row)
        signal = str(row.get("signal") or "").strip()
        if score is None or scan_date is None or not signal:
            continue

        age_days = (today - scan_date).days
        if age_days < 0 or age_days > MAX_TECHNICAL_AGE_DAYS:
            continue

        strength = abs(score - 50.0)
        if score >= 85 or score <= 35:
            bucket, materiality = 0, "medium"
        elif score >= 75 or score <= 45:
            bucket, materiality = 1, "low"
        else:
            bucket, materiality = 2, "low"

        risk_side = score < 50
        subtype = "technical_risk" if risk_side else "technical_setup"
        urgency = "today" if age_days == 0 else "developing"
        rsi = p0.to_float(row.get("rsi14"))
        pct_ema20 = p0.to_float(row.get("pctVsEma20"))
        pct_ema200 = p0.to_float(row.get("pctVsEma200"))
        volume_ratio = _first_ratio(row)
        source = {
            "type": "technical_json",
            "quality": "internal",
            "url": "data/technical.json",
            "published_at": scan_date.isoformat(),
        }

        detail_parts = [f"score {score:.0f}/100", signal]
        if rsi is not None:
            detail_parts.append(f"RSI {rsi:.1f}")
        if pct_ema20 is not None:
            detail_parts.append(f"{pct_ema20:+.1f}% vs EMA20")
        if pct_ema200 is not None:
            detail_parts.append(f"{pct_ema200:+.1f}% vs EMA200")
        if volume_ratio is not None:
            detail_parts.append(f"volume {volume_ratio:.2f}x 20-day average")

        event = {
            "event_id": f"technical:{ticker}:{subtype}:{scan_date.isoformat()}",
            "ticker": ticker,
            "event_type": "technical",
            "event_subtype": subtype,
            "headline": f"Latest technical scan · {score:.0f}/100",
            "summary": "Technical context from the latest market scan; this is not a recommendation.",
            "why_today": f"Latest technical scan dated {scan_date.isoformat()}: " + ", ".join(detail_parts) + ".",
            "materiality": materiality,
            "urgency": urgency,
            "event_time": scan_date.isoformat(),
            "detected_at": detected_at,
            "verification_status": "confirmed",
            "verification_level": "confirmed_internal",
            "verification_reason": "Derived directly from the repository's latest technical.json row.",
            "source": source,
            "source_chain": [source],
            "technical_score": score,
            "technical_signal": signal,
            "scan_age_days": age_days,
            "rsi14": rsi,
            "pct_vs_ema20": pct_ema20,
            "pct_vs_ema200": pct_ema200,
            "volume_ratio20": volume_ratio,
        }
        rank = (bucket, -strength, -(volume_ratio or 0.0), ticker)
        ranked.append((rank, event))

    ranked.sort(key=lambda row: row[0])
    return [event for _, event in ranked]


def _enforce_unverified_cap(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Unverified public news is never allowed above Watch."""
    priority_order = {"Critical": 0, "Risk": 1, "Action": 2, "Watch": 3, "Developing": 4}
    for item in items:
        events = item.get("events") if isinstance(item.get("events"), list) else []
        primary = events[0] if events else {}
        if primary.get("verification_status") == "unverified" and item.get("priority") in {"Critical", "Risk", "Action"}:
            item["priority"] = "Watch"
            item["priority_score"] = min(int(item.get("priority_score") or 0), 51)
            item["severity"] = "medium"
    items.sort(key=lambda item: (
        priority_order.get(str(item.get("priority")), 9),
        -int(item.get("priority_score") or 0),
        str(item.get("ticker") or ""),
    ))
    return items[: p0.MAX_ITEMS]


def _is_catalyst_item(item: dict[str, Any]) -> bool:
    events = item.get("events") if isinstance(item.get("events"), list) else []
    return any(str(event.get("event_type") or "") != "technical" for event in events)


def _build_sections(
    events: list[dict[str, Any]],
    portfolio: list[dict[str, Any]],
    technical_map: dict[str, dict[str, Any]],
    portfolio_map: dict[str, dict[str, Any]],
    contexts: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], int]:
    """Return normalized events, catalyst-first items and a separate technical watch."""
    merged = _dedupe_with_provenance(events)
    all_items = _enforce_unverified_cap(p0.aggregate_items(merged, portfolio_map, contexts))
    catalyst_items = [item for item in all_items if _is_catalyst_item(item)]
    technical_items = [item for item in all_items if not _is_catalyst_item(item)]

    existing_tickers = {str(item.get("ticker") or "").upper() for item in all_items}
    needed = max(0, TECHNICAL_WATCH_MIN - len(technical_items))
    selected: list[dict[str, Any]] = []
    for event in _technical_scan_candidates(portfolio, technical_map):
        ticker = str(event.get("ticker") or "").upper()
        if not ticker or ticker in existing_tickers:
            continue
        selected.append(event)
        existing_tickers.add(ticker)
        if len(selected) >= needed:
            break

    if selected:
        merged = _dedupe_with_provenance(merged + selected)
        all_items = _enforce_unverified_cap(p0.aggregate_items(merged, portfolio_map, contexts))
        catalyst_items = [item for item in all_items if _is_catalyst_item(item)]
        technical_items = [item for item in all_items if not _is_catalyst_item(item)]

    return merged, catalyst_items[: p0.MAX_ITEMS], technical_items[: p0.MAX_ITEMS], len(selected)


def generate() -> dict[str, Any]:
    base_output = p0.generate()
    portfolio = p0.load_portfolio()
    portfolio_map = {stock["ticker"]: stock for stock in portfolio}
    technical_map = p0.load_technical_rows()
    contexts = _technical_contexts(technical_map, portfolio_map)
    registry = p0.load_json(REGISTRY_PATH, {}) or {}
    old_news_state = p0.load_json(NEWS_STATE_PATH, {}) or {}

    news_result = collect_news_events(
        portfolio=portfolio,
        registry=registry,
        old_state=old_news_state,
        enabled=NEWS_ENABLED,
    )

    merged_events, catalyst_items, technical_watch, technical_fill_count = _build_sections(
        _load_events() + news_result.events,
        portfolio,
        technical_map,
        portfolio_map,
        contexts,
    )

    source_health = dict(base_output.get("source_health") or {})
    source_health.pop("news", None)
    source_health.update(news_result.health)
    errors = [row for row in base_output.get("errors", []) if isinstance(row, dict)] + news_result.errors
    summary = {
        label: sum(1 for item in catalyst_items if item.get("priority") == label)
        for label in ("Critical", "Risk", "Action", "Watch", "Developing")
    }
    technical_summary = {
        "risk": sum(1 for item in technical_watch if item.get("event_subtype") == "technical_risk"),
        "setup": sum(1 for item in technical_watch if item.get("event_subtype") == "technical_setup"),
        "total": len(technical_watch),
    }
    generated_at = p0.now_utc().replace(microsecond=0).isoformat()

    output = dict(base_output)
    output.update({
        "contract_version": "2.2-catalyst-first",
        "updated_at": generated_at,
        "features": {
            **(base_output.get("features") or {}),
            "free_news_discovery": NEWS_ENABLED,
            "technical_watch": True,
            "technical_scan_fill": technical_fill_count > 0,
            "thai_friendly_ui": True,
        },
        "total_events": len(merged_events),
        "coverage_status": _coverage_status(source_health),
        "summary": summary,
        "technical_summary": technical_summary,
        "source_health": source_health,
        "items": catalyst_items,
        "technical_watch": technical_watch,
        "errors": errors,
    })
    output["data_quality"] = {
        **(base_output.get("data_quality") or {}),
        "news_contract": "additive fields only; legacy P0 fields preserved",
        "news_policy": "GDELT is discovery-only; unverified reports are capped at Watch",
        "event_deduplication": "ticker + normalized subtype + time window + headline similarity",
        "source_registry_schema": str(registry.get("schema_version") or "unknown"),
        "attention_policy": "earnings, SEC filings, company events and verified news are shown before technical-only context",
        "technical_policy": "technical-only rows live in a separate technical_watch section and never fill the main catalyst list",
        "technical_fill_count": technical_fill_count,
        "technical_watch_minimum": TECHNICAL_WATCH_MIN,
        "technical_max_age_days": MAX_TECHNICAL_AGE_DAYS,
        "relative_volume_policy": "only dimensionless ratio fields are exposed",
        "internal_verification_policy": "repository-generated technical rows are confirmed-internal and are not shown as external sources",
    }

    event_output = {
        "schema_version": "1.0",
        "contract_version": "1.2-catalyst-first",
        "generated_at": generated_at,
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
        "Generated catalyst-first attention list: "
        f"{len(output.get('items') or [])} catalysts / "
        f"{len(output.get('technical_watch') or [])} technical watch / "
        f"{output.get('total_events')} events"
    )


if __name__ == "__main__":
    main()
