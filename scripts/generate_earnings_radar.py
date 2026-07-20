#!/usr/bin/env python3
"""Build the PR4 market-wide earnings radar contract.

The existing ``earnings_calendar.json`` remains unchanged for backward
compatibility.  This generator reads the full Finnhub batch calendar from the
private repository state, overlays company-confirmed calendar entries, and
publishes a compact UI-ready contract for a short decision window.

No estimates are fabricated. Missing provider values stay ``null`` and
confirmed Company IR / SEC rows always override Finnhub estimates for the same
symbol and date.
"""
from __future__ import annotations

import json
import math
import os
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "finnhub" / "state.json"
CALENDAR_PATH = ROOT / "data" / "earnings_calendar.json"
PORTFOLIO_PATH = ROOT / "data" / "portfolio.json"
RELEVANCE_PATH = ROOT / "data" / "earnings_relevance.json"
OUTPUT_PATHS = (
    ROOT / "data" / "generated" / "earnings_radar.json",
    ROOT / "site" / "data" / "earnings_radar.json",
    ROOT / "static" / "data" / "earnings_radar.json",
)
SCHEMA_VERSION = "1.0"
VALID_RELATIONS = {"portfolio", "related", "coverage", "market"}
VALID_TIMES = {"before_market", "during_market", "after_market", "unknown"}
OFFICIAL_SOURCES = {"company_ir", "sec", "regulator", "company_press_release"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


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


def clean_ticker(value: Any) -> str:
    ticker = str(value or "").strip().upper().replace("$", "")
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")
    return ticker if ticker and len(ticker) <= 18 and set(ticker) <= allowed else ""


def safe_number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except (TypeError, ValueError):
        return None


def normalize_time(value: Any) -> str:
    raw = str(value or "").strip().lower()
    mapped = {
        "amc": "after_market",
        "after_market": "after_market",
        "after market": "after_market",
        "bmo": "before_market",
        "before_market": "before_market",
        "before market": "before_market",
        "dmh": "during_market",
        "during_market": "during_market",
        "during market": "during_market",
    }.get(raw, "unknown")
    return mapped if mapped in VALID_TIMES else "unknown"


def portfolio_map(payload: Any) -> dict[str, dict[str, Any]]:
    rows = payload if isinstance(payload, list) else []
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = clean_ticker(row.get("ticker") or row.get("symbol"))
        if ticker:
            output[ticker] = dict(row)
    return output


def profile_map(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    endpoints = state.get("endpoints") if isinstance(state.get("endpoints"), dict) else {}
    entries = endpoints.get("company_profile") if isinstance(endpoints.get("company_profile"), dict) else {}
    output: dict[str, dict[str, Any]] = {}
    for ticker, entry in entries.items():
        ticker = clean_ticker(ticker)
        data = entry.get("data") if isinstance(entry, dict) and isinstance(entry.get("data"), dict) else {}
        if ticker and data:
            output[ticker] = data
    return output


def coverage_set(state: dict[str, Any], portfolio: dict[str, dict[str, Any]]) -> set[str]:
    covered = set(portfolio)
    endpoints = state.get("endpoints") if isinstance(state.get("endpoints"), dict) else {}
    for entries in endpoints.values():
        if not isinstance(entries, dict):
            continue
        covered.update(clean_ticker(ticker) for ticker in entries)
    covered.discard("")
    return covered


def latest_universe_count(state: dict[str, Any], covered: set[str]) -> int:
    runs = state.get("runs") if isinstance(state.get("runs"), list) else []
    for run in reversed(runs):
        if not isinstance(run, dict):
            continue
        value = run.get("universe_count")
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed >= 0:
            return max(parsed, len(covered))
    return len(covered)


def relation_config(payload: Any) -> dict[str, dict[str, Any]]:
    rows = payload.get("relations") if isinstance(payload, dict) and isinstance(payload.get("relations"), dict) else {}
    output: dict[str, dict[str, Any]] = {}
    for ticker, row in rows.items():
        ticker = clean_ticker(ticker)
        if not ticker or not isinstance(row, dict):
            continue
        related_to = sorted({clean_ticker(value) for value in row.get("related_to", []) if clean_ticker(value)})
        output[ticker] = {
            "related_to": related_to,
            "reason_th": str(row.get("reason_th") or "เกี่ยวข้องกับธีมหรือห่วงโซ่มูลค่าของหุ้นในพอร์ต"),
        }
    return output


def raw_market_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    batch = state.get("batch") if isinstance(state.get("batch"), dict) else {}
    calendar = batch.get("earnings_calendar") if isinstance(batch.get("earnings_calendar"), dict) else {}
    rows = calendar.get("data") if isinstance(calendar.get("data"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def normalize_market_row(row: dict[str, Any]) -> dict[str, Any] | None:
    ticker = clean_ticker(row.get("symbol") or row.get("ticker"))
    event_date = parse_date(row.get("date") or row.get("earnings_date"))
    if not ticker or event_date is None:
        return None
    quarter = row.get("quarter")
    year = row.get("year")
    return {
        "ticker": ticker,
        "earnings_date": event_date.isoformat(),
        "fiscal_quarter": f"Q{quarter} {year}" if quarter and year else None,
        "status": "estimated",
        "confidence": "medium",
        "time": normalize_time(row.get("hour") or row.get("time")),
        "event_time": None,
        "source_type": "finnhub",
        "source_url": None,
        "eps_actual": safe_number(row.get("epsActual") if "epsActual" in row else row.get("eps_actual")),
        "eps_estimate": safe_number(row.get("epsEstimate") if "epsEstimate" in row else row.get("eps_estimate")),
        "revenue_actual": safe_number(row.get("revenueActual") if "revenueActual" in row else row.get("revenue_actual")),
        "revenue_estimate": safe_number(row.get("revenueEstimate") if "revenueEstimate" in row else row.get("revenue_estimate")),
        "note": None,
    }


def normalize_official_row(row: dict[str, Any]) -> dict[str, Any] | None:
    ticker = clean_ticker(row.get("ticker") or row.get("symbol"))
    event_date = parse_date(row.get("earnings_date") or row.get("date"))
    if not ticker or event_date is None:
        return None
    source_type = str(row.get("source_type") or "").strip().lower() or "unknown"
    status = str(row.get("status") or "estimated").strip().lower()
    return {
        "ticker": ticker,
        "earnings_date": event_date.isoformat(),
        "fiscal_quarter": row.get("fiscal_quarter"),
        "status": status,
        "confidence": row.get("confidence") or ("high" if source_type in OFFICIAL_SOURCES else "medium"),
        "time": normalize_time(row.get("time")),
        "event_time": row.get("event_time"),
        "source_type": source_type,
        "source_url": row.get("source_url"),
        "eps_actual": safe_number(row.get("eps_actual")),
        "eps_estimate": safe_number(row.get("eps_estimate")),
        "revenue_actual": safe_number(row.get("revenue_actual")),
        "revenue_estimate": safe_number(row.get("revenue_estimate")),
        "note": row.get("note"),
    }


def merge_calendar_rows(market_rows: Iterable[dict[str, Any]], official_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in market_rows:
        item = normalize_market_row(raw)
        if item:
            merged[(item["ticker"], item["earnings_date"])] = item
    for raw in official_rows:
        item = normalize_official_row(raw)
        if not item:
            continue
        key = (item["ticker"], item["earnings_date"])
        current = merged.get(key, {})
        official = item["status"] == "confirmed" or item["source_type"] in OFFICIAL_SOURCES
        if official or not current:
            # Keep provider estimates when the official row confirms only the date.
            merged[key] = {
                **current,
                **{field: value for field, value in item.items() if value is not None},
            }
        else:
            merged[key] = {
                **item,
                **{field: value for field, value in current.items() if value is not None},
            }
    return sorted(merged.values(), key=lambda item: (item["earnings_date"], item["ticker"]))


def classify_relation(
    ticker: str,
    portfolio: dict[str, dict[str, Any]],
    covered: set[str],
    relations: dict[str, dict[str, Any]],
) -> tuple[str, list[str], str | None]:
    if ticker in portfolio:
        return "portfolio", [ticker], "หุ้นที่อยู่ในพอร์ต"
    relation = relations.get(ticker)
    related_to = [value for value in (relation or {}).get("related_to", []) if value in portfolio]
    if related_to:
        return "related", related_to, str((relation or {}).get("reason_th") or "เกี่ยวข้องกับหุ้นในพอร์ต")
    if ticker in covered:
        return "coverage", [], "หุ้นที่อยู่ใน coverage universe"
    return "market", [], None


def decorate_item(
    item: dict[str, Any],
    today: date,
    portfolio: dict[str, dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    covered: set[str],
    relations: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    ticker = item["ticker"]
    portfolio_row = portfolio.get(ticker, {})
    profile = profiles.get(ticker, {})
    relation, related_to, reason = classify_relation(ticker, portfolio, covered, relations)
    event_date = parse_date(item["earnings_date"])
    days_from_today = (event_date - today).days if event_date else None
    market_cap = safe_number(profile.get("marketCapitalization"))
    relation_weight = {"portfolio": 1000, "related": 700, "coverage": 400, "market": 0}[relation]
    confirmed_weight = 100 if item.get("status") == "confirmed" else 0
    timing_weight = max(0, 30 - abs(days_from_today or 0))
    return {
        **item,
        "name": portfolio_row.get("name") or profile.get("name") or profile.get("ticker") or ticker,
        "exchange": portfolio_row.get("exchange") or profile.get("exchange"),
        "industry": profile.get("finnhubIndustry"),
        "logo_url": profile.get("logo"),
        "market_cap_millions": market_cap,
        "relation": relation,
        "related_to": related_to,
        "relation_reason_th": reason,
        "portfolio_role": portfolio_row.get("role"),
        "days_from_today": days_from_today,
        "is_today": days_from_today == 0,
        "priority_score": relation_weight + confirmed_weight + timing_weight,
    }


def count_summary(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    rows = list(rows)
    times = Counter(str(row.get("time") or "unknown") for row in rows)
    relations = Counter(str(row.get("relation") or "market") for row in rows)
    return {
        "total": len(rows),
        "before_market": times["before_market"],
        "during_market": times["during_market"],
        "after_market": times["after_market"],
        "unknown": times["unknown"],
        "portfolio": relations["portfolio"],
        "related": relations["related"],
        "coverage": relations["coverage"],
        "market": relations["market"],
        "confirmed": sum(row.get("status") == "confirmed" for row in rows),
        "estimated": sum(row.get("status") != "confirmed" for row in rows),
    }


def build_payload(
    state: dict[str, Any],
    legacy_calendar: dict[str, Any],
    portfolio_payload: Any,
    relevance_payload: Any,
    *,
    today: date | None = None,
    days_back: int = 1,
    days_forward: int = 14,
) -> dict[str, Any]:
    today = today or now_utc().date()
    start = today - timedelta(days=max(0, days_back))
    end = today + timedelta(days=max(0, days_forward))
    portfolio = portfolio_map(portfolio_payload)
    profiles = profile_map(state)
    covered = coverage_set(state, portfolio)
    relations = relation_config(relevance_payload)
    market_rows = raw_market_rows(state)
    official_rows = legacy_calendar.get("items") if isinstance(legacy_calendar, dict) and isinstance(legacy_calendar.get("items"), list) else []
    merged = merge_calendar_rows(market_rows, official_rows)
    market_window_keys = {
        (item["ticker"], item["earnings_date"])
        for raw in market_rows
        if (item := normalize_market_row(raw)) is not None
        and (event_date := parse_date(item["earnings_date"])) is not None
        and start <= event_date <= end
    }
    official_window_keys = {
        (item["ticker"], item["earnings_date"])
        for raw in official_rows
        if isinstance(raw, dict)
        and (item := normalize_official_row(raw)) is not None
        and (event_date := parse_date(item["earnings_date"])) is not None
        and start <= event_date <= end
    }
    decorated = [
        decorate_item(item, today, portfolio, profiles, covered, relations)
        for item in merged
        if (event_date := parse_date(item.get("earnings_date"))) is not None and start <= event_date <= end
    ]
    decorated.sort(key=lambda item: (item["earnings_date"], -int(item["priority_score"]), item["ticker"]))

    day_rows: list[dict[str, Any]] = []
    cursor = start
    while cursor <= end:
        rows = [item for item in decorated if item["earnings_date"] == cursor.isoformat()]
        day_rows.append({"date": cursor.isoformat(), **count_summary(rows)})
        cursor += timedelta(days=1)

    today_rows = [item for item in decorated if item["earnings_date"] == today.isoformat()]
    batch = state.get("batch") if isinstance(state.get("batch"), dict) else {}
    batch_calendar = batch.get("earnings_calendar") if isinstance(batch.get("earnings_calendar"), dict) else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc().replace(microsecond=0).isoformat(),
        "market_timezone": "America/New_York",
        "display_timezone": "Asia/Bangkok",
        "selected_date": today.isoformat(),
        "window": {
            "from": start.isoformat(),
            "to": end.isoformat(),
            "days_back": max(0, days_back),
            "days_forward": max(0, days_forward),
            "provider_window": batch_calendar.get("window"),
        },
        "summary": count_summary(today_rows),
        "daily_summary": day_rows,
        "coverage": {
            "portfolio_total": len(portfolio),
            "coverage_universe_total": latest_universe_count(state, covered),
            "market_source_rows": len(market_rows),
            "market_window_rows": len(market_window_keys),
            "published_rows": len(decorated),
            "official_overlay_additions": len(official_window_keys - market_window_keys),
            "profile_names_known": sum(bool(item.get("name") and item.get("name") != item.get("ticker")) for item in decorated),
            "estimate_rows": sum(item.get("eps_estimate") is not None or item.get("revenue_estimate") is not None for item in decorated),
            "official_rows": sum(item.get("status") == "confirmed" for item in decorated),
        },
        "items": decorated,
        "policy": {
            "legacy_calendar_unchanged": True,
            "market_wide_source": "Finnhub earnings calendar batch",
            "official_override": "Company IR / SEC confirmed rows override provider estimates for the same ticker and date",
            "missing_values": "Missing EPS, revenue, company name and event time remain null or ticker-only; values are never fabricated",
            "relevance": "Portfolio relations are explicit and auditable through data/earnings_relevance.json",
        },
    }


def generate() -> dict[str, Any]:
    payload = build_payload(
        load_json(STATE_PATH, {}),
        load_json(CALENDAR_PATH, {}),
        load_json(PORTFOLIO_PATH, []),
        load_json(RELEVANCE_PATH, {}),
        days_back=int(os.getenv("EARNINGS_RADAR_DAYS_BACK", "1")),
        days_forward=int(os.getenv("EARNINGS_RADAR_DAYS_FORWARD", "14")),
    )
    for path in OUTPUT_PATHS:
        save_json(path, payload)
    return payload


def main() -> None:
    payload = generate()
    summary = payload["summary"]
    coverage = payload["coverage"]
    print(
        "Generated earnings radar: "
        f"{summary['total']} today / {coverage['published_rows']} window rows / "
        f"{coverage['market_source_rows']} market-source rows"
    )


if __name__ == "__main__":
    main()
