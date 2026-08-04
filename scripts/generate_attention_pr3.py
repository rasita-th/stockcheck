#!/usr/bin/env python3
"""PR3 generator for the Today Attention workflow.

PR3 builds on the catalyst-first PR2 contract and adds:
- official regulator-page discovery
- change tracking versus the previous successful run
- price impact since an item first entered Today
- configurable personal priority scores
- persistence for active discovered news/regulator events
"""
from __future__ import annotations

import os
from typing import Any

import generate_attention_pr2 as pr2
from attention_pr3 import enrich_payload, retain_active_discovered_events
from attention_sources import collect_news_events, collect_regulator_events

REGULATOR_CONFIG_PATH = pr2.p0.DATA_DIR / "regulator_sources.json"
REGULATOR_STATE_PATH = pr2.p0.STATE_DIR / "regulators.json"
PR3_STATE_PATH = pr2.p0.STATE_DIR / "pr3_attention.json"
DISCOVERED_EVENTS_STATE_PATH = pr2.p0.STATE_DIR / "pr3_discovered_events.json"
PREFERENCES_PATH = pr2.p0.DATA_DIR / "attention_preferences.json"
REGULATORS_ENABLED = os.environ.get("ATTENTION_REGULATORS_ENABLED", "1").lower() in {"1", "true", "yes"}


def _technical_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "risk": sum(1 for item in rows if item.get("event_subtype") == "technical_risk"),
        "setup": sum(1 for item in rows if item.get("event_subtype") == "technical_setup"),
        "total": len(rows),
    }


def _attention_eligible_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Exclude discovery-only Finnhub rows from the verified Attention contract."""
    eligible: list[dict[str, Any]] = []
    for event in events:
        source = event.get("source") if isinstance(event.get("source"), dict) else {}
        if str(source.get("type") or "").strip().lower() == "finnhub":
            continue
        eligible.append(event)
    return eligible


def _first_number(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = pr2.p0.to_float(row.get(key))
        if value is not None:
            return value
    return None


def _hydrate_technical_watch_metrics(
    rows: list[dict[str, Any]],
    technical_map: dict[str, dict[str, Any]],
) -> int:
    """Fill legacy/incomplete Attention events from the canonical technical row.

    Older Attention artifacts may contain the correct ticker and volume but omit
    RSI and EMA-distance fields, or carry placeholder zeroes. The current UI reads
    event-level snake_case fields, while the canonical scanner uses camelCase.
    Hydrate only technical events, preserve valid event values, and use the latest
    canonical scanner row as the authoritative fallback.
    """
    repaired = 0
    for item in rows:
        ticker = str(item.get("ticker") or "").strip().upper()
        source_row = technical_map.get(ticker)
        events = item.get("events") if isinstance(item.get("events"), list) else []
        if not ticker or not isinstance(source_row, dict) or not events:
            continue
        event = next(
            (row for row in events if isinstance(row, dict) and row.get("event_type") == "technical"),
            None,
        )
        if not isinstance(event, dict):
            continue

        canonical = {
            "technical_score": _first_number(source_row, "score", "technical_score"),
            "rsi14": _first_number(source_row, "rsi14", "rsi", "RSI14"),
            "pct_vs_ema20": _first_number(source_row, "pctVsEma20", "pct_vs_ema20"),
            "pct_vs_ema200": _first_number(source_row, "pctVsEma200", "pct_vs_ema200"),
            "volume_ratio20": _first_number(
                source_row,
                "volumeRatio20",
                "relativeVolume",
                "relVolume",
                "volumeRatio",
            ),
        }
        signal = str(source_row.get("signal") or source_row.get("technical_signal") or "").strip()
        if signal:
            canonical["technical_signal"] = signal

        changed = False
        for key, value in canonical.items():
            if value is None or value == "":
                continue
            current = event.get(key)
            current_number = pr2.p0.to_float(current) if key != "technical_signal" else None
            missing = current in (None, "")
            placeholder_zero = (
                key in {"pct_vs_ema20", "pct_vs_ema200"}
                and current_number == 0.0
                and float(value) != 0.0
                and pr2.p0.to_float(event.get("rsi14")) is None
            )
            if missing or placeholder_zero:
                event[key] = value
                changed = True

        item["relative_volume"] = canonical.get("volume_ratio20") or item.get("relative_volume")
        if changed:
            event["technical_metrics_source"] = "canonical_technical_snapshot"
            repaired += 1
    return repaired


def generate() -> dict[str, Any]:
    old_discovered_state = pr2.p0.load_json(DISCOVERED_EVENTS_STATE_PATH, {}) or {}
    base_output = pr2.p0.generate()
    portfolio = pr2.p0.load_portfolio()
    portfolio_map = {stock["ticker"]: stock for stock in portfolio}
    technical_map = pr2.p0.load_technical_rows()
    contexts = pr2._technical_contexts(technical_map, portfolio_map)
    registry = pr2.p0.load_json(pr2.REGISTRY_PATH, {}) or {}

    old_news_state = pr2.p0.load_json(pr2.NEWS_STATE_PATH, {}) or {}
    news_result = collect_news_events(
        portfolio=portfolio,
        registry=registry,
        old_state=old_news_state,
        enabled=pr2.NEWS_ENABLED,
    )

    regulator_config = pr2.p0.load_json(REGULATOR_CONFIG_PATH, {}) or {}
    old_regulator_state = pr2.p0.load_json(REGULATOR_STATE_PATH, {}) or {}
    regulator_result = collect_regulator_events(
        portfolio=portfolio,
        registry=registry,
        config=regulator_config,
        old_state=old_regulator_state,
        enabled=REGULATORS_ENABLED,
    )

    retention_now = pr2.p0.now_utc().replace(microsecond=0)
    newly_discovered_events = news_result.events + regulator_result.events
    active_discovered_events, next_discovered_state = retain_active_discovered_events(
        newly_discovered_events,
        old_discovered_state,
        now=retention_now,
    )

    merged_events, catalyst_items, technical_watch, technical_fill_count = pr2._build_sections(
        _attention_eligible_events(pr2._load_events()) + active_discovered_events,
        portfolio,
        technical_map,
        portfolio_map,
        contexts,
    )
    technical_metric_repair_count = _hydrate_technical_watch_metrics(technical_watch, technical_map)

    source_health = dict(base_output.get("source_health") or {})
    source_health.pop("news", None)
    source_health.update(news_result.health)
    source_health.update(regulator_result.health)
    errors = (
        [row for row in base_output.get("errors", []) if isinstance(row, dict)]
        + news_result.errors
        + regulator_result.errors
    )
    summary = {
        label: sum(1 for item in catalyst_items if item.get("priority") == label)
        for label in ("Critical", "Risk", "Action", "Watch", "Developing")
    }
    generated_at = retention_now.isoformat()

    output = dict(base_output)
    output.update(
        {
            "contract_version": "2.2-catalyst-first",
            "updated_at": generated_at,
            "features": {
                **(base_output.get("features") or {}),
                "free_news_discovery": pr2.NEWS_ENABLED,
                "official_regulator_sources": REGULATORS_ENABLED,
                "discovered_event_retention": True,
                "technical_watch": True,
                "technical_scan_fill": technical_fill_count > 0,
                "technical_metric_hydration": True,
                "thai_friendly_ui": True,
            },
            "total_events": len(merged_events),
            "coverage_status": pr2._coverage_status(source_health),
            "summary": summary,
            "technical_summary": _technical_summary(technical_watch),
            "source_health": source_health,
            "items": catalyst_items,
            "technical_watch": technical_watch,
            "errors": errors,
        }
    )
    output["data_quality"] = {
        **(base_output.get("data_quality") or {}),
        "news_contract": "additive fields only; legacy P0 fields preserved",
        "news_policy": "GDELT is discovery-only; unverified reports are capped at Watch",
        "regulator_policy": "official regulator pages are primary discovery sources and still require confident company matching",
        "discovered_event_retention": "active news and regulator events persist across refreshes until explicit resolution or event-type TTL expiry",
        "newly_discovered_event_count": len(newly_discovered_events),
        "active_discovered_event_count": len(active_discovered_events),
        "event_deduplication": "ticker + normalized subtype + time window + headline similarity",
        "attention_policy": "company catalysts remain above technical-only context",
        "technical_policy": "technical-only rows remain in technical_watch and never fill the main catalyst list",
        "technical_fill_count": technical_fill_count,
        "technical_metric_repair_count": technical_metric_repair_count,
        "technical_metrics_source": "canonical technical.json row fills incomplete legacy Attention events",
        "technical_watch_minimum": pr2.TECHNICAL_WATCH_MIN,
        "technical_max_age_days": pr2.MAX_TECHNICAL_AGE_DAYS,
    }

    old_pr3_state = pr2.p0.load_json(PR3_STATE_PATH, {}) or {}
    preferences = pr2.p0.load_json(PREFERENCES_PATH, {}) or {}
    output, next_pr3_state = enrich_payload(output, old_pr3_state, preferences, now=retention_now)

    event_output = {
        "schema_version": "1.0",
        "contract_version": "1.3-pr3",
        "generated_at": output.get("updated_at") or generated_at,
        "row_count": len(merged_events),
        "events": merged_events,
    }
    for path in pr2.p0.ATTENTION_OUT_PATHS:
        pr2.p0.save_json(path, output)
    for path in pr2.p0.EVENT_OUT_PATHS:
        pr2.p0.save_json(path, event_output)

    if pr2.NEWS_ENABLED:
        pr2.p0.save_json(pr2.NEWS_STATE_PATH, news_result.state)
    if REGULATORS_ENABLED:
        pr2.p0.save_json(REGULATOR_STATE_PATH, regulator_result.state)
    pr2.p0.save_json(DISCOVERED_EVENTS_STATE_PATH, next_discovered_state)
    pr2.p0.save_json(PR3_STATE_PATH, next_pr3_state)
    return output


def main() -> None:
    output = generate()
    changes = output.get("changes_summary") or {}
    quality = output.get("data_quality") if isinstance(output.get("data_quality"), dict) else {}
    print(
        "Generated PR3 Today workflow: "
        f"{len(output.get('items') or [])} catalysts / "
        f"{len(output.get('technical_watch') or [])} technical watch / "
        f"{changes.get('new', 0)} new / {changes.get('escalated', 0)} escalated / "
        f"{quality.get('active_discovered_event_count', 0)} retained discovered events"
    )


if __name__ == "__main__":
    main()
