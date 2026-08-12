from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from .common import build_registry_entry, http_bytes, http_json, utc_now
from .discovery import collect_gdelt, collect_ir


@dataclass
class NewsCollectionResult:
    events: list[dict[str, Any]]
    state: dict[str, Any]
    health: dict[str, Any]
    errors: list[dict[str, str]]


def collect_news_events(portfolio: list[dict[str, Any]], registry: dict[str, Any] | None, old_state: dict[str, Any] | None, enabled: bool, fetch_json: Callable[[str], dict[str, Any] | None] = http_json, fetch_bytes_fn: Callable[[str], bytes | None] = http_bytes, now: datetime | None = None) -> NewsCollectionResult:
    now, registry, old_state = now or utc_now(), registry if isinstance(registry, dict) else {}, old_state if isinstance(old_state, dict) else {}
    defaults = registry.get("defaults") if isinstance(registry.get("defaults"), dict) else {}
    overrides = registry.get("items") if isinstance(registry.get("items"), dict) else {}
    if not enabled:
        return NewsCollectionResult([], old_state, {"news": {"status": "disabled", "source": "Free news discovery", "note": "Feature flag ATTENTION_NEWS_ENABLED is off."}, "ir": {"status": "disabled", "checked": 0, "source": "Company IR/RSS"}, "gdelt": {"status": "disabled", "checked": 0, "source": "GDELT DOC 2.0"}}, [])
    all_entries = [build_registry_entry(stock, overrides.get(str(stock.get("ticker") or "").upper(), {})) for stock in portfolio]
    not_applicable = sum(bool(entry.get("ticker") and entry.get("disabled")) for entry in all_entries)
    entries = [entry for entry in all_entries if entry.get("ticker") and not entry.get("disabled")]
    if not entries:
        return NewsCollectionResult([], old_state, {"news": {"status": "partial", "source": "Free news discovery", "note": "No enabled source-registry entries."}}, [])
    batch_size = max(1, int(os.environ.get("ATTENTION_NEWS_BATCH_SIZE", defaults.get("batch_size", 10))))
    configured = sum(bool(entry.get("ir_urls") or entry.get("ir_feeds")) for entry in entries)
    registry_coverage = {
        "applicable": len(entries),
        "configured": configured,
        "missing": len(entries) - configured,
        "not_applicable": not_applicable,
    }
    cursor = int(old_state.get("cursor") or 0) % len(entries)
    batch = [entries[(cursor + index) % len(entries)] for index in range(min(batch_size, len(entries)))]
    old_tickers = old_state.get("tickers") if isinstance(old_state.get("tickers"), dict) else {}
    next_tickers, events, errors = dict(old_tickers), [], []
    ir_ok = ir_partial = ir_error = gdelt_ok = gdelt_unavailable = 0
    for entry in batch:
        ticker = entry["ticker"]
        ticker_state = old_tickers.get(ticker) if isinstance(old_tickers.get(ticker), dict) else {}
        ir_events, ir_state, ir_status, ir_message = collect_ir(entry, ticker_state.get("ir") if isinstance(ticker_state.get("ir"), dict) else {}, fetch_bytes_fn, now, int(defaults.get("ir_bootstrap_hours", 6)))
        gdelt_events, gdelt_state, gdelt_status, gdelt_message = collect_gdelt(entry, ticker_state.get("gdelt") if isinstance(ticker_state.get("gdelt"), dict) else {}, fetch_json, now, str(defaults.get("gdelt_timespan", "24h")), int(defaults.get("gdelt_maxrecords", 20)), int(defaults.get("gdelt_bootstrap_hours", 6)))
        events.extend(ir_events + gdelt_events)
        next_tickers[ticker] = {"ir": ir_state, "gdelt": gdelt_state}
        ir_ok += ir_status == "ok"; ir_partial += ir_status == "partial"; ir_error += ir_status == "error"
        gdelt_ok += gdelt_status == "ok"; gdelt_unavailable += gdelt_status != "ok"
        if ir_message: errors.append({"source": "ir", "ticker": ticker, "message": ir_message})
    ir_status = "ok" if ir_ok and not ir_error and not ir_partial else "partial" if ir_ok or ir_partial else "error"
    gdelt_status = "ok" if gdelt_ok and not gdelt_unavailable else "partial" if gdelt_ok else "optional_unavailable"
    # GDELT is discovery-only. Verified IR coverage owns the actionable news health.
    overall = ir_status
    next_state = {"schema_version": "1.0", "updated_at": now.isoformat(), "cursor": (cursor + len(batch)) % len(entries), "tickers": next_tickers}
    health = {"news": {"status": overall, "source": "Verified company IR discovery", "checked": len(batch), "accepted_events": len(events)}, "ir": {"status": ir_status, "source": "Company IR/RSS", "checked": len(batch), "ok": ir_ok, "partial": ir_partial, "errors": ir_error, "registry": registry_coverage}, "gdelt": {"status": gdelt_status, "source": "GDELT DOC 2.0", "role": "discovery_only", "checked": len(batch), "ok": gdelt_ok, "unavailable": gdelt_unavailable, "note": "Optional secondary discovery does not downgrade verified-source coverage."}}
    return NewsCollectionResult(events, next_state, health, errors)
