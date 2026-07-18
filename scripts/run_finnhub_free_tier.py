#!/usr/bin/env python3
"""Free-tier-safe runtime adapter for the unified Finnhub pipeline.

Finnhub exposes earnings calendar, earnings surprises and recommendation trends
on the free tier, while EPS/revenue estimate endpoints and price target require
premium access. This adapter disables premium calls by default, preserves
last-known-good cache entries on provider errors, and derives upcoming estimates
from the free market-wide earnings calendar.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date, timedelta
from typing import Any

import finnhub_pipeline as pipeline

PREMIUM_FLAGS = {
    "eps_estimates": "FINNHUB_ENABLE_PREMIUM_ESTIMATES",
    "revenue_estimates": "FINNHUB_ENABLE_PREMIUM_ESTIMATES",
    "price_target": "FINNHUB_ENABLE_PREMIUM_PRICE_TARGET",
}


def env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def configure_endpoints() -> dict[str, str]:
    skipped: dict[str, str] = {}
    for endpoint, flag in PREMIUM_FLAGS.items():
        if endpoint in pipeline.ENDPOINTS and not env_true(flag):
            pipeline.ENDPOINTS.pop(endpoint, None)
            skipped[endpoint] = f"premium_disabled:{flag}"
    return skipped


def provider_error(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("error", "Error Message", "message"):
        value = payload.get(key)
        if value and str(value).strip():
            return str(value).strip()
    return None


def classify_error(exc: Exception | str) -> str:
    text = str(exc).lower()
    if "429" in text or "rate limit" in text or "too many requests" in text:
        return "rate_limited"
    if "401" in text or "unauthorized" in text or "invalid api" in text:
        return "unauthorized"
    if "403" in text or "premium" in text or "forbidden" in text or "access denied" in text:
        return "premium_required"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    return "provider_error"


def record_failure(bucket: dict[str, Any], ticker: str, exc: Exception) -> None:
    entry = bucket.get(ticker)
    if not isinstance(entry, dict):
        entry = {"status": "error", "data": None}
        bucket[ticker] = entry
    entry["last_attempt_at"] = pipeline.now_iso()
    entry["last_error_at"] = pipeline.now_iso()
    entry["last_error"] = str(exc)
    entry["last_error_type"] = classify_error(exc)
    # Keep updated_at from the last good response so failed rows remain due.
    if entry.get("data") in (None, {}, []):
        entry["status"] = "error"


def safe_update_ticker_endpoints(
    state: dict[str, Any], role: str, universe: list[str], client: Any,
    max_calls: int, delay_seconds: float,
) -> dict[str, Any]:
    endpoints = [name for name, policy in pipeline.ENDPOINTS.items() if policy.role == role]
    diagnostics: dict[str, Any] = {
        "role": role,
        "calls_used": 0,
        "refreshed": {},
        "errors": [],
        "missing_key": client is None,
        "enabled_endpoints": endpoints,
    }
    if client is None or max_calls <= 0:
        return diagnostics
    caps = {name: pipeline.ENDPOINTS[name].per_run_cap for name in endpoints}
    queues = {name: pipeline.due_tickers(state, name, universe) for name in endpoints}
    while diagnostics["calls_used"] < max_calls:
        progressed = False
        for endpoint in endpoints:
            if diagnostics["calls_used"] >= max_calls:
                break
            if caps[endpoint] <= 0 or not queues[endpoint]:
                continue
            progressed = True
            ticker = queues[endpoint].pop(0)
            caps[endpoint] -= 1
            diagnostics["calls_used"] += 1
            bucket = state["endpoints"][endpoint]
            try:
                raw = pipeline.endpoint_call(client, endpoint, ticker)
                error = provider_error(raw)
                if error:
                    raise RuntimeError(error)
                data = pipeline.NORMALIZERS[pipeline.ENDPOINTS[endpoint].normalizer](raw)
                bucket[ticker] = {
                    "status": "ok" if data else "empty",
                    "updated_at": pipeline.now_iso(),
                    "last_attempt_at": pipeline.now_iso(),
                    "data": data,
                }
                diagnostics["refreshed"].setdefault(endpoint, []).append(ticker)
            except Exception as exc:
                record_failure(bucket, ticker, exc)
                diagnostics["errors"].append({
                    "endpoint": endpoint,
                    "ticker": ticker,
                    "type": classify_error(exc),
                    "message": str(exc),
                })
            if delay_seconds > 0:
                time.sleep(delay_seconds)
        if not progressed:
            break
    return diagnostics


def safe_update_earnings_calendar(
    state: dict[str, Any], client: Any, days_back: int = 7, days_forward: int = 35,
) -> dict[str, Any]:
    existing = state.setdefault("batch", {}).get("earnings_calendar")
    ttl = float(os.getenv("FINNHUB_CALENDAR_TTL_HOURS", "3"))
    if not pipeline.is_due(existing, ttl):
        rows = existing.get("data") if isinstance(existing, dict) else []
        return {"status": "fresh", "calls_used": 0, "row_count": len(rows or [])}
    if client is None:
        return {"status": "missing_key", "calls_used": 0}
    start = date.today() - timedelta(days=days_back)
    end = date.today() + timedelta(days=days_forward)
    try:
        payload = client.earnings_calendar(
            _from=start.isoformat(), to=end.isoformat(), symbol="", international=False
        )
        error = provider_error(payload)
        if error:
            raise RuntimeError(error)
        rows = payload.get("earningsCalendar") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise RuntimeError("earningsCalendar response is missing a list")
        rows = [row for row in rows if isinstance(row, dict)]
        if not rows:
            raise RuntimeError("earningsCalendar returned no rows; preserving last-known-good data")
        state["batch"]["earnings_calendar"] = {
            "status": "ok",
            "updated_at": pipeline.now_iso(),
            "last_attempt_at": pipeline.now_iso(),
            "window": {"from": start.isoformat(), "to": end.isoformat(), "international": False},
            "data": rows,
        }
        return {"status": "ok", "calls_used": 1, "row_count": len(rows)}
    except Exception as exc:
        if not isinstance(existing, dict):
            existing = {"status": "error", "data": []}
            state["batch"]["earnings_calendar"] = existing
        existing["last_attempt_at"] = pipeline.now_iso()
        existing["last_error_at"] = pipeline.now_iso()
        existing["last_error"] = str(exc)
        existing["last_error_type"] = classify_error(exc)
        return {
            "status": "error",
            "calls_used": 1,
            "error": str(exc),
            "error_type": classify_error(exc),
        }


def derive_calendar_estimates(calendar: dict[str, Any]) -> dict[str, Any]:
    rows = calendar.get("items") if isinstance(calendar, dict) else []
    output: dict[str, Any] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or str(row.get("source_type") or "").lower() != "finnhub":
            continue
        ticker = str(row.get("ticker") or "").upper()
        event_date = str(row.get("earnings_date") or "")
        if not ticker or not event_date:
            continue
        candidate = {
            "earnings_date": event_date,
            "eps_estimate": row.get("eps_estimate"),
            "revenue_estimate": row.get("revenue_estimate"),
            "eps_actual": row.get("eps_actual"),
            "revenue_actual": row.get("revenue_actual"),
            "time": row.get("time"),
            "source": "finnhub_earnings_calendar",
            "updated_at": row.get("updated_at"),
        }
        current = output.get(ticker)
        if current is None or event_date < str(current.get("earnings_date") or "9999"):
            output[ticker] = candidate
    return output


def enrich_feature_contracts() -> None:
    for folder in pipeline.PUBLIC_DIRS:
        feature_path = folder / "finnhub_features.json"
        calendar_path = folder / "earnings_calendar.json"
        features = pipeline.load_json(feature_path, {})
        calendar = pipeline.load_json(calendar_path, {})
        if not isinstance(features, dict):
            features = {}
        features["calendar_estimates"] = derive_calendar_estimates(calendar)
        features["plan"] = {
            "default": "free_tier_safe",
            "premium_endpoints_opt_in": sorted(PREMIUM_FLAGS),
            "last_known_good": True,
        }
        pipeline.save_json(feature_path, features)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("events", "analyst", "all"), default="all")
    args = parser.parse_args()
    skipped = configure_endpoints()
    pipeline.update_ticker_endpoints = safe_update_ticker_endpoints
    pipeline.update_earnings_calendar = safe_update_earnings_calendar
    diagnostics = pipeline.run(args.mode)
    diagnostics["premium_skipped"] = skipped
    enrich_feature_contracts()
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))
    errors: list[Any] = []
    for section in ("events", "analyst"):
        block = diagnostics.get(section)
        if isinstance(block, dict):
            errors.extend(block.get("errors") or [])
    if errors:
        print(f"::warning::Finnhub completed with {len(errors)} endpoint errors; cached data was preserved")


if __name__ == "__main__":
    main()
