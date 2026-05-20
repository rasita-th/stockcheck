#!/usr/bin/env python3
"""v8.3.0 Analyst Consensus cache queue.

Runs safely every 15 minutes. It does NOT refresh every ticker every run.
It refreshes only missing/stale US tickers under one small budget.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIRS = [ROOT / "data", ROOT / "site" / "data", ROOT / "static" / "data"]

API_KEY = os.environ.get("FINNHUB_API_KEY", "").strip()
MAX_CALLS = int(os.environ.get("ANALYST_CONSENSUS_MAX_CALLS_PER_RUN", "3"))
TTL_HOURS = float(os.environ.get("ANALYST_CONSENSUS_TTL_HOURS", "168"))
MIN_DELAY_SECONDS = float(os.environ.get("FINNHUB_MIN_DELAY_SECONDS", "0.35"))

NON_US_SUFFIXES = (
    ".BK", ".SET", ".TO", ".V", ".CN", ".L", ".HK", ".SS", ".SZ",
    ".KS", ".KQ", ".T", ".AX", ".PA", ".DE", ".SW", ".MI", ".AS",
    ".ST", ".OL", ".CO"
)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def load_json(path: Path, fallback: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"::warning::Could not read {path}: {exc}")
    return fallback

def save_json_all(name: str, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    for d in DATA_DIRS:
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(text + "\n", encoding="utf-8")
        print("wrote", d / name)

def normalize_ticker(raw: Any) -> str:
    t = str(raw or "").strip().upper().replace("$", "")
    return t if re.match(r"^[A-Z0-9.\-]{1,18}$", t) else ""

def is_us_ticker(ticker: str) -> bool:
    if not ticker:
        return False
    if any(ticker.endswith(s) for s in NON_US_SUFFIXES):
        return False
    return True

def parse_dt(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def age_hours(raw: Any) -> float | None:
    dt = parse_dt(raw)
    if not dt:
        return None
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600

def load_ticker_universe() -> list[str]:
    tickers: list[str] = []
    for name in ("technical.json", "scanner.json"):
        for d in [ROOT / "site" / "data", ROOT / "static" / "data", ROOT / "data"]:
            data = load_json(d / name, {})
            rows = data.get("rows") if isinstance(data, dict) else []
            if isinstance(rows, list):
                for r in rows:
                    if isinstance(r, dict):
                        t = normalize_ticker(r.get("ticker") or r.get("symbol"))
                        if t and is_us_ticker(t):
                            tickers.append(t)
    wl = ROOT / "watchlist.txt"
    if wl.exists():
        for token in re.split(r"[\s,;|]+", wl.read_text(encoding="utf-8")):
            t = normalize_ticker(token)
            if t and is_us_ticker(t):
                tickers.append(t)
    seen = set()
    out = []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out

def load_existing_cache() -> dict[str, Any]:
    for d in DATA_DIRS:
        p = d / "recommendation_trends.json"
        data = load_json(p, None)
        if isinstance(data, dict):
            return data
    return {
        "generated_at": now_iso(),
        "source": "finnhub_recommendation_trends",
        "items": {},
        "diagnostics": {}
    }

def entry_rows(entry: Any) -> list[Any]:
    if isinstance(entry, list):
        return entry
    if isinstance(entry, dict):
        if isinstance(entry.get("rows"), list):
            return entry["rows"]
        if isinstance(entry.get("data"), list):
            return entry["data"]
        if isinstance(entry.get("trend"), list):
            return entry["trend"]
    return []

def entry_updated_at(entry: Any) -> Any:
    if isinstance(entry, dict):
        return entry.get("updated_at") or entry.get("generated_at") or entry.get("last_success")
    return None

def needs_refresh(ticker: str, cache: dict[str, Any]) -> bool:
    items = cache.setdefault("items", {})
    entry = items.get(ticker) or cache.get(ticker)
    if not entry:
        return True
    if not entry_rows(entry):
        return True
    hours = age_hours(entry_updated_at(entry))
    return hours is None or hours >= TTL_HOURS

def fetch_recommendation(ticker: str) -> list[dict[str, Any]]:
    if not API_KEY:
        raise RuntimeError("FINNHUB_API_KEY is missing")
    url = "https://finnhub.io/api/v1/stock/recommendation?" + urllib.parse.urlencode({
        "symbol": ticker,
        "token": API_KEY
    })
    with urllib.request.urlopen(url, timeout=20) as res:
        raw = res.read().decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, list):
        return []
    rows = []
    for r in data:
        if isinstance(r, dict):
            rows.append({
                "symbol": ticker,
                "period": r.get("period"),
                "strongBuy": r.get("strongBuy"),
                "buy": r.get("buy"),
                "hold": r.get("hold"),
                "sell": r.get("sell"),
                "strongSell": r.get("strongSell"),
            })
    return rows

def main() -> None:
    cache = load_existing_cache()
    cache.setdefault("items", {})
    cache["source"] = "finnhub_recommendation_trends"
    cache["generated_at"] = now_iso()
    cache["ttl_hours"] = TTL_HOURS

    tickers = load_ticker_universe()
    queue = [t for t in tickers if needs_refresh(t, cache)]

    diagnostics = {
        "checked_tickers": len(tickers),
        "queue_size": len(queue),
        "max_calls_this_run": MAX_CALLS,
        "api_enabled": bool(API_KEY),
        "refreshed": [],
        "errors": [],
        "updated_at": now_iso(),
    }

    if not API_KEY:
        diagnostics["errors"].append("FINNHUB_API_KEY missing; no calls made")
        cache["diagnostics"] = diagnostics
        save_json_all("recommendation_trends.json", cache)
        return

    calls = 0
    for ticker in queue:
        if calls >= MAX_CALLS:
            break
        try:
            rows = fetch_recommendation(ticker)
            cache["items"][ticker] = {
                "ticker": ticker,
                "updated_at": now_iso(),
                "rows": rows,
                "status": "ok" if rows else "empty"
            }
            diagnostics["refreshed"].append(ticker)
            calls += 1
            time.sleep(MIN_DELAY_SECONDS)
        except Exception as exc:
            diagnostics["errors"].append(f"{ticker}: {exc}")
            cache["items"][ticker] = {
                "ticker": ticker,
                "updated_at": now_iso(),
                "rows": entry_rows(cache["items"].get(ticker)),
                "status": "error",
                "error": str(exc)
            }

    diagnostics["calls_made"] = calls
    cache["diagnostics"] = diagnostics

    for t, entry in list(cache.get("items", {}).items()):
        cache[t] = entry

    save_json_all("recommendation_trends.json", cache)
    print("Analyst consensus refresh done:", diagnostics)

if __name__ == "__main__":
    main()
