#!/usr/bin/env python3
"""Unified, dual-key Finnhub pipeline for Stockcheck.

Coordinates Finnhub scheduling/caching while preserving existing public JSON
contracts. Secrets are read from the environment and never written to output.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIRS = [ROOT / "data", ROOT / "site" / "data", ROOT / "static" / "data"]
PRIVATE_DIR = ROOT / "data" / "finnhub"
STATE_PATH = PRIVATE_DIR / "state.json"
SNAPSHOT_PATH = PRIVATE_DIR / "snapshot.json"
SCHEMA_VERSION = "1.0.0"
LEGACY_CALENDAR_VERSION = "2.0"
NON_US_SUFFIXES = (
    ".BK", ".SET", ".BKK", ".TO", ".V", ".CN", ".L", ".HK", ".SS", ".SZ",
    ".KS", ".KQ", ".T", ".AX", ".PA", ".DE", ".SW", ".MI", ".AS", ".ST",
    ".OL", ".CO", ".SI",
)


@dataclass(frozen=True)
class EndpointPolicy:
    role: str
    ttl_hours: float
    method: str
    normalizer: str
    per_run_cap: int


ENDPOINTS: dict[str, EndpointPolicy] = {
    "company_earnings": EndpointPolicy("events", 24.0, "company_earnings", "earnings", 20),
    "eps_estimates": EndpointPolicy("events", 24.0, "company_eps_estimates", "list", 14),
    "revenue_estimates": EndpointPolicy("events", 24.0, "company_revenue_estimates", "list", 14),
    "recommendation_trends": EndpointPolicy("analyst", 24.0, "recommendation_trends", "recommendations", 24),
    "price_target": EndpointPolicy("analyst", 72.0, "price_target", "dict", 16),
    "company_profile": EndpointPolicy("analyst", 720.0, "company_profile2", "dict", 4),
    "basic_financials": EndpointPolicy("analyst", 168.0, "company_basic_financials", "dict", 8),
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().replace(microsecond=0).isoformat()


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists() and path.stat().st_size:
            return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"::warning::Could not read {path}: {exc}")
    return default


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def save_public(name: str, payload: Any) -> None:
    for folder in PUBLIC_DIRS:
        save_json(folder / name, payload)


def clean_ticker(value: Any) -> str:
    ticker = str(value or "").strip().upper().replace("$", "")
    if not ticker or any(ticker.endswith(suffix) for suffix in NON_US_SUFFIXES):
        return ""
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")
    return ticker if len(ticker) <= 18 and set(ticker) <= allowed else ""


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return [row for row in payload["rows"] if isinstance(row, dict)]
    return []


def load_universe() -> list[str]:
    candidates = [
        ROOT / "data" / "portfolio.json",
        ROOT / "site" / "data" / "portfolio.json",
        ROOT / "static" / "data" / "portfolio.json",
        ROOT / "data" / "technical.json",
        ROOT / "site" / "data" / "technical.json",
        ROOT / "static" / "data" / "technical.json",
    ]
    ordered: list[str] = []
    seen: set[str] = set()
    for path in candidates:
        payload = load_json(path, [] if path.name == "portfolio.json" else {})
        rows = payload if isinstance(payload, list) else _rows_from_payload(payload)
        for row in rows:
            ticker = clean_ticker(row.get("ticker") or row.get("symbol"))
            if ticker and ticker not in seen:
                seen.add(ticker)
                ordered.append(ticker)
    return ordered


def default_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": now_iso(),
        "endpoints": {name: {} for name in ENDPOINTS},
        "batch": {},
        "runs": [],
    }


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    state = load_json(path, {})
    if not isinstance(state, dict):
        state = {}
    base = default_state()
    if isinstance(state.get("endpoints"), dict):
        for name in ENDPOINTS:
            if isinstance(state["endpoints"].get(name), dict):
                base["endpoints"][name] = state["endpoints"][name]
    if isinstance(state.get("batch"), dict):
        base["batch"] = state["batch"]
    if isinstance(state.get("runs"), list):
        base["runs"] = state["runs"][-19:]
    return base


def is_due(entry: Any, ttl_hours: float, current: datetime | None = None) -> bool:
    if not isinstance(entry, dict):
        return True
    checked = parse_dt(entry.get("updated_at"))
    if checked is None:
        return True
    current = current or now_utc()
    return (current - checked).total_seconds() >= ttl_hours * 3600


def due_tickers(state: dict[str, Any], endpoint: str, universe: Iterable[str]) -> list[str]:
    policy = ENDPOINTS[endpoint]
    bucket = state.setdefault("endpoints", {}).setdefault(endpoint, {})
    unique = sorted({ticker for ticker in universe if clean_ticker(ticker)})

    def rank(ticker: str) -> tuple[int, float, str]:
        entry = bucket.get(ticker)
        checked = parse_dt(entry.get("updated_at")) if isinstance(entry, dict) else None
        if checked is None:
            return (0, 0.0, ticker)
        age = (now_utc() - checked).total_seconds()
        return (1, -age, ticker)

    return [ticker for ticker in sorted(unique, key=rank) if is_due(bucket.get(ticker), policy.ttl_hours)]


def safe_number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def normalize_earnings(payload: Any) -> list[dict[str, Any]]:
    rows = payload if isinstance(payload, list) else []
    output: list[dict[str, Any]] = []
    for row in rows[:12]:
        if not isinstance(row, dict):
            continue
        output.append({
            "period": row.get("period") or row.get("quarter"),
            "actual": safe_number(row.get("actual")),
            "estimate": safe_number(row.get("estimate")),
            "surprise": safe_number(row.get("surprise")),
            "surprisePercent": safe_number(row.get("surprisePercent")),
            "symbol": clean_ticker(row.get("symbol")),
        })
    return output


def normalize_recommendations(payload: Any) -> list[dict[str, Any]]:
    rows = payload if isinstance(payload, list) else []
    output: list[dict[str, Any]] = []
    for row in rows[:12]:
        if not isinstance(row, dict):
            continue
        output.append({
            "period": row.get("period"),
            "strongBuy": int(row.get("strongBuy") or 0),
            "buy": int(row.get("buy") or 0),
            "hold": int(row.get("hold") or 0),
            "sell": int(row.get("sell") or 0),
            "strongSell": int(row.get("strongSell") or 0),
            "symbol": clean_ticker(row.get("symbol")),
        })
    return sorted(output, key=lambda row: str(row.get("period") or ""))[-8:]


def normalize_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        payload = payload["data"]
    return [row for row in payload if isinstance(row, dict)][:24] if isinstance(payload, list) else []


def normalize_dict(payload: Any) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) else {}


NORMALIZERS: dict[str, Callable[[Any], Any]] = {
    "earnings": normalize_earnings,
    "recommendations": normalize_recommendations,
    "list": normalize_list,
    "dict": normalize_dict,
}


def client_for(role: str):
    if role == "events":
        key = os.getenv("FINNHUB_API_KEY_EVENTS", "").strip() or os.getenv("FINNHUB_API_KEY", "").strip()
    else:
        key = (
            os.getenv("FINNHUB_API_KEY_ANALYST", "").strip()
            or os.getenv("FINNHUB_API_KEY_2", "").strip()
            or os.getenv("FINNHUB_API_KEY", "").strip()
        )
    if not key:
        return None
    import finnhub  # type: ignore
    return finnhub.Client(api_key=key)


def endpoint_call(client: Any, endpoint: str, ticker: str) -> Any:
    policy = ENDPOINTS[endpoint]
    method = getattr(client, policy.method, None)
    if method is None:
        raise RuntimeError(f"finnhub client does not support {policy.method}")
    if endpoint == "company_earnings":
        return method(ticker, limit=8)
    if endpoint in {"eps_estimates", "revenue_estimates"}:
        return method(ticker, freq="quarterly")
    if endpoint == "company_profile":
        return method(symbol=ticker)
    if endpoint == "basic_financials":
        return method(ticker, "all")
    return method(ticker)


def update_ticker_endpoints(
    state: dict[str, Any], role: str, universe: list[str], client: Any,
    max_calls: int, delay_seconds: float,
) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {"role": role, "calls_used": 0, "refreshed": {}, "errors": [], "missing_key": client is None}
    if client is None or max_calls <= 0:
        return diagnostics
    role_endpoints = [name for name, policy in ENDPOINTS.items() if policy.role == role]
    remaining_endpoint = {name: ENDPOINTS[name].per_run_cap for name in role_endpoints}
    queues = {name: due_tickers(state, name, universe) for name in role_endpoints}
    while diagnostics["calls_used"] < max_calls:
        progressed = False
        for endpoint in role_endpoints:
            if diagnostics["calls_used"] >= max_calls:
                break
            if remaining_endpoint[endpoint] <= 0 or not queues[endpoint]:
                continue
            progressed = True
            ticker = queues[endpoint].pop(0)
            remaining_endpoint[endpoint] -= 1
            diagnostics["calls_used"] += 1
            try:
                raw = endpoint_call(client, endpoint, ticker)
                data = NORMALIZERS[ENDPOINTS[endpoint].normalizer](raw)
                state["endpoints"][endpoint][ticker] = {
                    "status": "ok" if data else "empty",
                    "updated_at": now_iso(),
                    "data": data,
                }
                diagnostics["refreshed"].setdefault(endpoint, []).append(ticker)
            except Exception as exc:
                diagnostics["errors"].append(f"{endpoint}:{ticker}:{exc}")
                old = state["endpoints"][endpoint].get(ticker)
                if not isinstance(old, dict):
                    state["endpoints"][endpoint][ticker] = {
                        "status": "error", "updated_at": now_iso(), "data": None, "error": str(exc)
                    }
                else:
                    old["last_error_at"] = now_iso()
                    old["last_error"] = str(exc)
            if delay_seconds > 0:
                time.sleep(delay_seconds)
        if not progressed:
            break
    return diagnostics


def update_earnings_calendar(state: dict[str, Any], client: Any, days_back: int = 7, days_forward: int = 45) -> dict[str, Any]:
    existing = state.setdefault("batch", {}).get("earnings_calendar")
    ttl = float(os.getenv("FINNHUB_CALENDAR_TTL_HOURS", "3"))
    if not is_due(existing, ttl):
        return {"status": "fresh", "calls_used": 0}
    if client is None:
        return {"status": "missing_key", "calls_used": 0}
    start = date.today() - timedelta(days=days_back)
    end = date.today() + timedelta(days=days_forward)
    try:
        raw = client.earnings_calendar(_from=start.isoformat(), to=end.isoformat(), symbol="", international=False)
        rows = raw.get("earningsCalendar") if isinstance(raw, dict) else []
        rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
        state["batch"]["earnings_calendar"] = {
            "status": "ok" if rows else "empty",
            "updated_at": now_iso(),
            "window": {"from": start.isoformat(), "to": end.isoformat(), "international": False},
            "data": rows,
        }
        return {"status": "ok" if rows else "empty", "calls_used": 1, "row_count": len(rows)}
    except Exception as exc:
        if isinstance(existing, dict):
            existing["last_error_at"] = now_iso()
            existing["last_error"] = str(exc)
        return {"status": "error", "calls_used": 1, "error": str(exc)}


def calendar_hour(value: Any) -> str | None:
    return {"amc": "after_market", "bmo": "before_market", "dmh": "during_market"}.get(str(value or "").lower())


def finnhub_calendar_items(state: dict[str, Any], universe: set[str]) -> list[dict[str, Any]]:
    batch = state.get("batch", {}).get("earnings_calendar", {})
    rows = batch.get("data") if isinstance(batch, dict) else []
    items: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        ticker = clean_ticker(row.get("symbol"))
        event_date = str(row.get("date") or "")
        if not ticker or ticker not in universe or not event_date:
            continue
        quarter = row.get("quarter")
        year = row.get("year")
        items.append({
            "ticker": ticker,
            "earnings_date": event_date,
            "fiscal_quarter": f"Q{quarter} {year}" if quarter and year else None,
            "status": "estimated",
            "time": calendar_hour(row.get("hour")),
            "event_time": None,
            "source_type": "finnhub",
            "source_url": None,
            "confirmed_at": None,
            "confidence": "medium",
            "eps_actual": safe_number(row.get("epsActual")),
            "eps_estimate": safe_number(row.get("epsEstimate")),
            "revenue_actual": safe_number(row.get("revenueActual")),
            "revenue_estimate": safe_number(row.get("revenueEstimate")),
            "note": "Finnhub earnings calendar; company IR/SEC confirmation takes precedence.",
        })
    return items


def merge_earnings_items(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(item: dict[str, Any]) -> tuple[str, str]:
        return clean_ticker(item.get("ticker") or item.get("symbol")), str(item.get("earnings_date") or item.get("date") or "")
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for item in incoming:
        if isinstance(item, dict) and all(key(item)):
            merged[key(item)] = item
    for item in existing:
        if not isinstance(item, dict) or not all(key(item)):
            continue
        current = merged.get(key(item))
        official = str(item.get("status") or "").lower() == "confirmed" or str(item.get("source_type") or "").lower() in {"company_ir", "sec", "regulator"}
        if official or current is None:
            merged[key(item)] = item
    return sorted(merged.values(), key=lambda item: (str(item.get("earnings_date") or "9999"), str(item.get("ticker") or "")))


def public_contracts(state: dict[str, Any], universe: list[str]) -> dict[str, dict[str, Any]]:
    generated = now_iso()
    rec_entries = state.get("endpoints", {}).get("recommendation_trends", {})
    recommendation_items: dict[str, Any] = {}
    for ticker, entry in rec_entries.items():
        if isinstance(entry, dict):
            recommendation_items[ticker] = {
                "ticker": ticker,
                "updated_at": entry.get("updated_at"),
                "status": entry.get("status"),
                "rows": entry.get("data") if isinstance(entry.get("data"), list) else [],
            }
    recommendation = {
        "schema_version": "1.1.0", "generated_at": generated,
        "source": "finnhub_recommendation_trends", "items": recommendation_items,
        "ttl_hours": ENDPOINTS["recommendation_trends"].ttl_hours,
    }
    recommendation.update(recommendation_items)
    earnings_entries = state.get("endpoints", {}).get("company_earnings", {})
    eps = {
        "schema_version": "1.1.0", "generated_at": generated,
        "source": "Finnhub company_earnings unified cache", "api_key_present": None,
        "surprises": {
            ticker: entry.get("data") if isinstance(entry, dict) and isinstance(entry.get("data"), list) else []
            for ticker, entry in earnings_entries.items()
        },
        "_cache": {"fetched_at": {ticker: entry.get("updated_at") for ticker, entry in earnings_entries.items() if isinstance(entry, dict)}},
        "_meta": {"version": SCHEMA_VERSION, "policy": "Last-known-good cache; unified events key; US tickers only."},
    }
    old_calendar = load_json(ROOT / "data" / "earnings_calendar.json", {})
    old_items = old_calendar.get("items") if isinstance(old_calendar, dict) and isinstance(old_calendar.get("items"), list) else []
    calendar = {
        "schema_version": LEGACY_CALENDAR_VERSION, "updated_at": generated,
        "items": merge_earnings_items(old_items, finnhub_calendar_items(state, set(universe))),
        "policy": "Company IR/SEC confirmed dates override Finnhub estimates. Missing values remain null and are never fabricated.",
    }
    feature_endpoints = {
        endpoint: entries for endpoint, entries in state.get("endpoints", {}).items()
        if endpoint in ENDPOINTS and isinstance(entries, dict)
    }
    features = {
        "schema_version": SCHEMA_VERSION, "generated_at": generated, "source": "finnhub",
        "features": feature_endpoints, "batch": state.get("batch", {}),
        "contract": {"optional_fields": True, "last_known_good": True, "secrets_exposed": False},
    }
    return {
        "recommendation_trends.json": recommendation,
        "eps_surprises.json": eps,
        "earnings_calendar.json": calendar,
        "finnhub_features.json": features,
    }


def write_outputs(state: dict[str, Any], universe: list[str]) -> None:
    state["schema_version"] = SCHEMA_VERSION
    state["updated_at"] = now_iso()
    save_json(STATE_PATH, state)
    contracts = public_contracts(state, universe)
    save_json(SNAPSHOT_PATH, {
        "schema_version": SCHEMA_VERSION, "generated_at": now_iso(),
        "endpoint_counts": {endpoint: len(entries) for endpoint, entries in state.get("endpoints", {}).items() if isinstance(entries, dict)},
        "batch_status": {name: payload.get("status") for name, payload in state.get("batch", {}).items() if isinstance(payload, dict)},
    })
    for name, payload in contracts.items():
        save_public(name, payload)


def validate_no_secret(payload: Any, secrets: Iterable[str]) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    for secret in secrets:
        if secret and secret in text:
            raise RuntimeError("API key leaked into generated payload")


def run(mode: str, state_path: Path = STATE_PATH) -> dict[str, Any]:
    state = load_state(state_path)
    universe = load_universe()
    delay = float(os.getenv("FINNHUB_MIN_DELAY_SECONDS", "1.25"))
    events_budget = min(50, max(0, int(os.getenv("FINNHUB_EVENTS_MAX_CALLS_PER_RUN", "48"))))
    analyst_budget = min(50, max(0, int(os.getenv("FINNHUB_ANALYST_MAX_CALLS_PER_RUN", "48"))))
    diagnostics: dict[str, Any] = {"mode": mode, "started_at": now_iso(), "universe_count": len(universe)}
    if mode in {"events", "all"}:
        events_client = client_for("events")
        diagnostics["calendar"] = update_earnings_calendar(state, events_client)
        ticker_budget = max(0, events_budget - int(diagnostics["calendar"].get("calls_used", 0)))
        diagnostics["events"] = update_ticker_endpoints(state, "events", universe, events_client, ticker_budget, delay)
    if mode in {"analyst", "all"}:
        analyst_client = client_for("analyst")
        diagnostics["analyst"] = update_ticker_endpoints(state, "analyst", universe, analyst_client, analyst_budget, delay)
    diagnostics["completed_at"] = now_iso()
    state.setdefault("runs", []).append(diagnostics)
    state["runs"] = state["runs"][-20:]
    write_outputs(state, universe)
    validate_no_secret(state, [
        os.getenv("FINNHUB_API_KEY_EVENTS", ""), os.getenv("FINNHUB_API_KEY_ANALYST", ""),
        os.getenv("FINNHUB_API_KEY", ""), os.getenv("FINNHUB_API_KEY_2", ""),
    ])
    return diagnostics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("events", "analyst", "all", "publish-only"), default="all")
    args = parser.parse_args()
    if args.mode == "publish-only":
        state = load_state()
        universe = load_universe()
        write_outputs(state, universe)
        result = {"mode": args.mode, "published_at": now_iso(), "universe_count": len(universe)}
    else:
        result = run(args.mode)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
