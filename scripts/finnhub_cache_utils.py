#!/usr/bin/env python3
"""Shared Finnhub cache helpers for Stock Timing Radar v8.2.10.

Purpose: avoid calling Finnhub repeatedly for the same ticker.  These helpers
skip non-US symbols such as .BK, dedupe tickers, preserve existing generated
JSON, and refresh only stale/missing tickers within a configurable per-run
budget.
"""
from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIRS = [ROOT / "data", ROOT / "site" / "data", ROOT / "static" / "data"]
US_EXCHANGES = {"US", "NMS", "NYQ", "NAS", "NASDAQ", "NYSE", "AMEX", "BATS", "ARCX", "OTC"}
NON_US_SUFFIXES = (".BK", ".SET", ".BKK", ".L", ".TO", ".V", ".AX", ".HK", ".SI", ".T", ".KS", ".KQ", ".SS", ".SZ")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        raw = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def age_hours(value: Any) -> float | None:
    dt = parse_dt(value)
    if not dt:
        return None
    return (now_utc() - dt).total_seconds() / 3600


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"::warning::Could not read {path}: {exc}")
        return fallback


def save_json_all(paths: list[Path], data: Any) -> None:
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False), encoding="utf-8")


def first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def clean_ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def is_us_symbol(ticker: str, exchange: Any = None) -> bool:
    t = clean_ticker(ticker)
    if not t:
        return False
    if any(t.endswith(sfx) for sfx in NON_US_SUFFIXES):
        return False
    if re.search(r"[^A-Z0-9.\-]", t):
        return False
    # Do not spend API calls on preferred/warrant/local suffixes by default.
    if "." in t and not t.endswith((".A", ".B")):
        return False
    exch = clean_ticker(exchange)
    if exch and exch not in US_EXCHANGES:
        return False
    return True


def portfolio_tickers() -> list[str]:
    tickers: list[tuple[str, Any]] = []
    for path in [ROOT / "data" / "portfolio.json", ROOT / "site" / "data" / "portfolio.json", ROOT / "static" / "data" / "portfolio.json"]:
        rows = load_json(path, [])
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    tickers.append((clean_ticker(row.get("ticker") or row.get("symbol")), row.get("exchange") or row.get("market")))
    # Also use current scanner rows, but never let these overwrite portfolio order.
    for path in [ROOT / "site" / "data" / "technical.json", ROOT / "data" / "technical.json", ROOT / "static" / "data" / "technical.json"]:
        data = load_json(path, {})
        rows = data.get("rows") if isinstance(data, dict) else []
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    tickers.append((clean_ticker(row.get("ticker") or row.get("symbol")), row.get("exchange") or row.get("market")))
    seen = set()
    out = []
    for t, exch in tickers:
        if not t or t in seen:
            continue
        if not is_us_symbol(t, exch):
            continue
        seen.add(t)
        out.append(t)
    return out


def cache_meta(data: dict[str, Any]) -> dict[str, Any]:
    meta = data.get("_cache") if isinstance(data.get("_cache"), dict) else {}
    return meta


def symbol_fetched_at(data: dict[str, Any], ticker: str) -> str | None:
    meta = cache_meta(data)
    fetched = meta.get("fetched_at") if isinstance(meta.get("fetched_at"), dict) else {}
    return fetched.get(ticker)


def is_fresh(data: dict[str, Any], ticker: str, ttl_hours: float, collection_key: str) -> bool:
    coll = data.get(collection_key) if isinstance(data.get(collection_key), dict) else {}
    if ticker not in coll:
      return False
    h = age_hours(symbol_fetched_at(data, ticker))
    return h is not None and h <= ttl_hours


def call_budget(default: int, env_name: str) -> int:
    raw = os.environ.get(env_name)
    try:
        n = int(raw) if raw else default
        return max(0, n)
    except Exception:
        return default


def api_key() -> str:
    return os.environ.get("FINNHUB_API_KEY", "").strip()


def get_finnhub_client():
    key = api_key()
    if not key:
        return None
    import finnhub  # type: ignore
    return finnhub.Client(api_key=key)


def mark_fetched(data: dict[str, Any], ticker: str) -> None:
    data.setdefault("_cache", {}).setdefault("fetched_at", {})[ticker] = now_iso()


def safe_number(value: Any) -> float | None:
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except Exception:
        return None
