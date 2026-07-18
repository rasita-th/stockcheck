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
MIN_ATTENTION_ITEMS = max(0, min(p0.MAX_ITEMS, int(os.environ.get("ATTENTION_MIN_ITEMS", "3"))))
MAX_TECHNICAL_AGE_DAYS = max(0, int(os.environ.get("ATTENTION_TECHNICAL_MAX_AGE_DAYS", "3")))


def _load_events() -> list[dict[str, Any]]:
    raw = p0.load_json(p0.GENERATED_DIR / "events.json", {}) or {}
    rows = raw.get("events") if isinstance(raw, dict) else []
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _coverage_status(source_health: dict[str, Any]) -> str:
    degraded = {"partial", "unavailable", "error"}
    return "partial" if any(str((value or {}).get("status") or "unknown") in degraded for value in source_health.values() if isinstance(value, dict)) else "complete"


def _scan_date(row: dict[str, Any]) -> Any:
    for key in ("regularMarketTime", "date", "dataDate", "asOfDate"):
        parsed = p0.parse_date(row.get(key))
        if parsed:
            return parsed
    return None


def _technical_scan_candidates(portfolio: list[dict[str, Any]], technical_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Build objective, recent technical context when event sources are quiet.

    These are not recommendations. They are selected from the monitored portfolio
    using the scanner's existing score and signal, and stale rows are rejected.
    """
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
        direction = "weakest" if risk_side else "strongest"
        urgency = "today" if age_days == 0 else "developing"
        rsi = p0.to_float(row.get("rsi14"))
        pct_ema20 = p0.to_float(row.get("pctVsEma20"))
        pct_ema200 = p0.to_float(row.get("pctVsEma200"))
        volume_ratio = p0.to_float(row.get("volumeRatio20"))
        detail_parts = [f"score {score:.0f}/100", signal]
        if rsi is not None:
            detail_parts.append(f"RSI {rsi:.1f}")
        if pct_ema20 is not None:
            detail_parts.append(f"{pct_ema20:+.1f}% vs EMA20")
        if pct_ema200 is not None:
            detail_parts.append(f"{pct_ema200:+.1f}% vs EMA200")
        if volume_ratio is not None:
            detail_parts.append(f"volume {volume_ratio:.2f}x 20-day average")
        why = f"Latest technical scan dated {scan_date.isoformat()}: " + ", ".join(detail_parts) + "."
        summary = f"This is one of the {direction} recent technical scans in the monitored portfolio; it is context, not a recommendation."
        source = {
            "type": "technical_json",
            "quality": "internal",
            "url": "data/technical.json",
            "published_at": scan_date.isoformat(),
        }
        event = {
            "event_id": f"technical:{ticker}:{subtype}:{scan_date.isoformat()}",
            "ticker": ticker,
            "event_type": "technical",
            "event_subtype": subtype,
            "headline": f"Latest technical scan · {score:.0f}/100",
            "summary": summary,
            "why_today": why,
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


def _add_technical_fill(
    events: list[dict[str, Any]],
    portfolio: list[dict[str, Any]],
    technical_map: dict[str, dict[str, Any]],
    portfolio_map: dict[str, dict[str, Any]],
    contexts: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    merged = deduplicate_events(events)
    current_items = p0.aggregate_items(merged, portfolio_map, contexts)
    needed = max(0, MIN_ATTENTION_ITEMS - len(current_items))
    if needed == 0:
        return merged, 0
    existing_tickers = {str(item.get("ticker") or "").upper() for item in current_items}
    selected: list[dict[str, Any]] = []
    for event in _technical_scan_candidates(portfolio, technical_map):
        ticker = str(event.get("ticker") or "").upper()
        if not ticker or ticker in existing_tickers:
            continue
        selected.append(event)
        existing_tickers.add(ticker)
        if len(selected) >= needed:
            break
    return deduplicate_events(merged + selected), len(selected)


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
    merged_events, technical_fill_count = _add_technical_fill(
        _load_events() + news_result.events,
        portfolio,
        technical_map,
        portfolio_map,
        contexts,
    )
    items = _enforce_unverified_cap(p0.aggregate_items(merged_events, portfolio_map, contexts))

    source_health = dict(base_output.get("source_health") or {})
    source_health.pop("news", None)
    source_health.update(news_result.health)
    errors = [row for row in base_output.get("errors", []) if isinstance(row, dict)] + news_result.errors
    summary = {label: sum(1 for item in items if item.get("priority") == label) for label in ("Critical", "Risk", "Action", "Watch", "Developing")}

    output = dict(base_output)
    output.update({
        "contract_version": "2.1-additive",
        "features": {
            **(base_output.get("features") or {}),
            "free_news_discovery": NEWS_ENABLED,
            "technical_scan_fill": technical_fill_count > 0,
        },
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
        "technical_policy": "event triggers first; when fewer than the configured minimum are found, fill only with the strongest recent scanner rows and label them as technical context",
        "technical_fill_count": technical_fill_count,
        "minimum_attention_items": MIN_ATTENTION_ITEMS,
        "technical_max_age_days": MAX_TECHNICAL_AGE_DAYS,
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
