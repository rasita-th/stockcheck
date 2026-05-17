#!/usr/bin/env python3
"""Shared Finnhub call scheduler for Stock Timing Radar.

Keeps generated-data workflows from calling the same ticker on every run.
The browser never sees API keys; this file only writes public call metadata.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIRS = [ROOT / "data", ROOT / "site" / "data", ROOT / "static" / "data"]
STATE_NAME = "finnhub_call_state.json"
TECHNICAL_PATHS = [ROOT / "site" / "data" / "technical.json", ROOT / "data" / "technical.json", ROOT / "static" / "data" / "technical.json"]
PORTFOLIO_PATHS = [ROOT / "data" / "portfolio.json", ROOT / "site" / "data" / "portfolio.json", ROOT / "static" / "data" / "portfolio.json"]

NON_US_SUFFIXES = {
    "BK", "SET", "BKK", "HK", "SS", "SZ", "TO", "V", "L", "PA", "DE", "F", "MI", "MC", "AS", "SW",
    "SI", "AX", "KS", "KQ", "T", "TW", "TWO", "OL", "ST", "CO", "HE", "IR", "SA", "JO", "MX",
}
US_EXCHANGES = {"NASDAQ", "NYSE", "NYSEARCA", "AMEX", "ARCA", "NMS", "NYQ", "NCM", "NGM", "ASE", "NAS"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_ict_iso() -> str:
    return datetime.now(timezone(timedelta(hours=7))).isoformat(timespec="seconds")


def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def first_existing(paths: list[Path]) -> Path | None:
    return next((p for p in paths if p.exists()), None)


def normalize_ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def suffix_of(ticker: str) -> str:
    if "." not in ticker:
        return ""
    return ticker.rsplit(".", 1)[-1].upper()


def is_us_eligible(ticker: str, meta: dict[str, Any] | None = None) -> bool:
    ticker = normalize_ticker(ticker)
    if not ticker:
        return False
    suffix = suffix_of(ticker)
    if suffix in NON_US_SUFFIXES:
        return False
    meta = meta or {}
    exch = normalize_ticker(meta.get("exchange") or meta.get("market") or meta.get("mic") or meta.get("exchangeCode"))
    country = normalize_ticker(meta.get("country") or meta.get("region"))
    if country and country not in {"US", "USA", "UNITED STATES"}:
        return False
    if exch and exch not in US_EXCHANGES:
        return False
    return True


def load_ticker_meta() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in PORTFOLIO_PATHS:
        data = load_json(path, [])
        if isinstance(data, list):
            for row in data:
                if isinstance(row, dict):
                    ticker = normalize_ticker(row.get("ticker") or row.get("symbol"))
                    if ticker:
                        out.setdefault(ticker, {}).update(row)
    tech_path = first_existing(TECHNICAL_PATHS)
    tech = load_json(tech_path, {}) if tech_path else {}
    rows = tech.get("rows") if isinstance(tech, dict) else []
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                ticker = normalize_ticker(row.get("ticker") or row.get("symbol"))
                if ticker:
                    out.setdefault(ticker, {}).update(row)
    return out


def load_state() -> dict[str, Any]:
    path = first_existing([d / STATE_NAME for d in DATA_DIRS])
    state = load_json(path, {}) if path else {}
    if not isinstance(state, dict):
        state = {}
    state.setdefault("version", "8.3.0")
    state.setdefault("updated_at", now_ict_iso())
    state.setdefault("endpoints", {})
    state.setdefault("skipped_non_us", {})
    state.setdefault("last_batches", {})
    return state


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = now_ict_iso()
    for folder in DATA_DIRS:
        save_json(folder / STATE_NAME, state)


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        raw = str(value).replace("Z", "+00:00")
        d = datetime.fromisoformat(raw)
        if not d.tzinfo:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return None


def select_batch(endpoint: str, tickers: list[str], batch_size: int | None = None, min_hours: float | None = None) -> tuple[list[str], dict[str, Any]]:
    meta = load_ticker_meta()
    state = load_state()
    endpoint_state = state.setdefault("endpoints", {}).setdefault(endpoint, {})
    batch_size = int(batch_size if batch_size is not None else os.environ.get("FINNHUB_BATCH_SIZE", "25"))
    min_hours = float(min_hours if min_hours is not None else os.environ.get("FINNHUB_MIN_REFRESH_HOURS", "24"))
    now = now_utc()

    unique: list[str] = []
    seen: set[str] = set()
    skipped: list[str] = []
    for ticker in tickers:
        ticker = normalize_ticker(ticker)
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        if not is_us_eligible(ticker, meta.get(ticker, {})):
            skipped.append(ticker)
            continue
        unique.append(ticker)

    def sort_key(ticker: str) -> tuple[int, float, str]:
        last = parse_dt((endpoint_state.get(ticker) or {}).get("last_checked_at"))
        if last is None:
            return (0, 0, ticker)
        age_hours = (now - last).total_seconds() / 3600
        return (1, -age_hours, ticker)

    due: list[str] = []
    for ticker in sorted(unique, key=sort_key):
        last = parse_dt((endpoint_state.get(ticker) or {}).get("last_checked_at"))
        if last is not None and ((now - last).total_seconds() / 3600) < min_hours:
            continue
        due.append(ticker)
        if batch_size > 0 and len(due) >= batch_size:
            break

    state["skipped_non_us"][endpoint] = skipped
    state["last_batches"][endpoint] = {"selected_at": now_ict_iso(), "tickers": due, "batch_size": batch_size, "min_hours": min_hours, "eligible_count": len(unique), "skipped_non_us_count": len(skipped)}
    save_state(state)
    return due, state


def mark_checked(endpoint: str, tickers: list[str], status: str = "ok", extra: dict[str, Any] | None = None) -> None:
    state = load_state()
    endpoint_state = state.setdefault("endpoints", {}).setdefault(endpoint, {})
    stamp = now_utc().isoformat(timespec="seconds")
    for ticker in sorted({normalize_ticker(t) for t in tickers if normalize_ticker(t)}):
        endpoint_state[ticker] = {"last_checked_at": stamp, "status": status, **(extra or {})}
    save_state(state)


def merge_public_json(file_name: str, key: str) -> dict[str, Any]:
    path = first_existing([d / file_name for d in DATA_DIRS])
    data = load_json(path, {}) if path else {}
    if not isinstance(data, dict):
        data = {}
    if not isinstance(data.get(key), dict):
        data[key] = {}
    return data
