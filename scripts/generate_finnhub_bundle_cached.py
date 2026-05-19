#!/usr/bin/env python3
"""v8.2.12 Unified Finnhub budget manager.

One workflow run should not let three independent scripts spend Finnhub quota
blindly. This bundle coordinates these Finnhub endpoints under one global budget:

- financials_reported(symbol, freq="quarterly") for the fundamental resolver; default TTL 30 days
- company_earnings(symbol, limit=5) for EPS surprise / resolver
- recommendation_trends(symbol) for analyst consensus

Security: FINNHUB_API_KEY is read only from environment / GitHub Actions Secret.
No key is written to JSON or browser-visible files.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIRS = [ROOT / "data", ROOT / "site" / "data", ROOT / "static" / "data"]
CACHE_PATHS = [d / "finnhub_bundle_cache.json" for d in DATA_DIRS]
REC_PATHS = [d / "recommendation_trends.json" for d in DATA_DIRS]
EPS_PATHS = [d / "eps_surprises.json" for d in DATA_DIRS]

API_KEY = os.environ.get("FINNHUB_API_KEY", "").strip()
OFFLINE = os.environ.get("STOCKCHECK_OFFLINE", "").lower() in {"1", "true", "yes"}

TOTAL_MAX_CALLS = int(os.environ.get("FINNHUB_BUNDLE_MAX_CALLS_PER_RUN", "30"))
ENDPOINT_MAX = {
    "financials": int(os.environ.get("FINNHUB_FINANCIALS_MAX_CALLS_PER_RUN", "10")),
    "earnings": int(os.environ.get("FINNHUB_EPS_MAX_CALLS_PER_RUN", "10")),
    "recommendations": int(os.environ.get("FINNHUB_REC_MAX_CALLS_PER_RUN", "10")),
}
TTL_HOURS = {
    "financials": float(os.environ.get("FINNHUB_FINANCIALS_TTL_HOURS", "720")),
    "earnings": float(os.environ.get("FINNHUB_EPS_TTL_HOURS", "168")),
    "recommendations": float(os.environ.get("FINNHUB_REC_TTL_HOURS", "168")),
}
MIN_DELAY_SECONDS = float(os.environ.get("FINNHUB_MIN_DELAY_SECONDS", "0.25"))

NON_US_PATTERNS = [
    ".BK", ".SET", ".BK-R", ".TO", ".V", ".CN", ".L", ".HK", ".SS", ".SZ", ".KS", ".KQ",
    ".T", ".AX", ".PA", ".DE", ".SW", ".MI", ".AS", ".ST", ".OL", ".CO",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        raw = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def hours_since(value: Any) -> float | None:
    dt = parse_dt(value)
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"::warning::Could not read {path}: {exc}")
        return fallback


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False), encoding="utf-8")


def save_all(paths: list[Path], data: Any) -> None:
    for p in paths:
        save_json(p, data)


def first_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None


def is_us_ticker(ticker: str) -> bool:
    t = str(ticker or "").strip().upper()
    if not t:
        return False
    if any(t.endswith(suffix) for suffix in NON_US_PATTERNS):
        return False
    if t.startswith("^"):
        return False
    # US common-ish tickers: AAPL, BRK-B, BRK.B, GOOG, RKLB, ASTS.
    return bool(re.fullmatch(r"[A-Z0-9]{1,6}([.-][A-Z0-9]{1,4})?", t))


def ticker_sort_key(ticker: str, cache: dict[str, Any]) -> tuple[int, float, str]:
    # Missing cache first, then stalest first.
    oldest = 0.0
    missing_count = 0
    fetched = cache.setdefault("_cache", {}).setdefault("fetched_at", {})
    for endpoint in ("financials", "earnings", "recommendations"):
        ts = fetched.get(endpoint, {}).get(ticker)
        h = hours_since(ts)
        if h is None:
            missing_count += 1
            oldest = max(oldest, 999999.0)
        else:
            oldest = max(oldest, h)
    return (-missing_count, -oldest, ticker)


def portfolio_tickers() -> list[str]:
    # Prefer portfolio/watchlist config sources without touching watchlist.txt.
    candidates = [ROOT / "data" / "portfolio.json", ROOT / "site" / "data" / "portfolio.json", ROOT / "static" / "data" / "portfolio.json"]
    path = first_existing(candidates)
    tickers: list[str] = []
    if path:
        raw = load_json(path, [])
        if isinstance(raw, list):
            for row in raw:
                if isinstance(row, dict):
                    t = str(row.get("ticker") or row.get("symbol") or "").upper().strip()
                    if t and is_us_ticker(t):
                        tickers.append(t)
    # Include tickers from generated technical/fundamental rows as backup.
    for rel in ["site/data/technical.json", "data/technical.json", "site/data/fundamental.json", "data/fundamental.json"]:
        raw = load_json(ROOT / rel, {})
        rows = raw.get("rows") if isinstance(raw, dict) else []
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    t = str(row.get("ticker") or row.get("symbol") or "").upper().strip()
                    if t and is_us_ticker(t):
                        tickers.append(t)
    seen = set()
    out = []
    for t in tickers:
        if t not in seen:
            out.append(t); seen.add(t)
    return out


def default_cache() -> dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "version": "8.2.12",
        "financials": {},
        "earnings": {},
        "recommendations": {},
        "_cache": {"fetched_at": {"financials": {}, "earnings": {}, "recommendations": {}}},
        "_meta": {},
    }


def load_bundle_cache() -> dict[str, Any]:
    path = first_existing(CACHE_PATHS)
    data = load_json(path, {}) if path else {}
    if not isinstance(data, dict):
        data = {}
    base = default_cache()
    for key in ["financials", "earnings", "recommendations"]:
        if isinstance(data.get(key), dict):
            base[key] = data[key]
    if isinstance(data.get("_cache"), dict):
        base["_cache"] = data["_cache"]
    base.setdefault("_cache", {}).setdefault("fetched_at", {})
    for endpoint in ["financials", "earnings", "recommendations"]:
        base["_cache"].setdefault("fetched_at", {}).setdefault(endpoint, {})
    return base


class Budget:
    def __init__(self) -> None:
        self.total = TOTAL_MAX_CALLS
        self.endpoint_left = dict(ENDPOINT_MAX)
        self.used: dict[str, int] = {"financials": 0, "earnings": 0, "recommendations": 0}
        self.failed: dict[str, list[str]] = {"financials": [], "earnings": [], "recommendations": []}
        self.skipped_fresh: dict[str, int] = {"financials": 0, "earnings": 0, "recommendations": 0}
        self.skipped_budget: dict[str, int] = {"financials": 0, "earnings": 0, "recommendations": 0}
        self.refreshed: dict[str, list[str]] = {"financials": [], "earnings": [], "recommendations": []}

    def can_call(self, endpoint: str) -> bool:
        return self.total > 0 and self.endpoint_left.get(endpoint, 0) > 0

    def spend(self, endpoint: str, ticker: str) -> None:
        self.total -= 1
        self.endpoint_left[endpoint] = self.endpoint_left.get(endpoint, 0) - 1
        self.used[endpoint] = self.used.get(endpoint, 0) + 1
        self.refreshed.setdefault(endpoint, []).append(ticker)
        if MIN_DELAY_SECONDS > 0:
            time.sleep(MIN_DELAY_SECONDS)


BUDGET = Budget()
CACHE = load_bundle_cache()
CLIENT: Any = None
RESOLVER: Any = None


def cache_fresh(endpoint: str, ticker: str) -> bool:
    data = CACHE.get(endpoint_map(endpoint), {}).get(ticker)
    ts = CACHE.setdefault("_cache", {}).setdefault("fetched_at", {}).setdefault(endpoint, {}).get(ticker)
    h = hours_since(ts)
    if h is None:
        return False
    if h > TTL_HOURS[endpoint]:
        return False
    # Empty recommendation/earnings arrays can be valid, but if the key is absent it is not fresh.
    return ticker in CACHE.get(endpoint_map(endpoint), {})


def endpoint_map(endpoint: str) -> str:
    return {"financials": "financials", "earnings": "earnings", "recommendations": "recommendations"}[endpoint]


def mark(endpoint: str, ticker: str) -> None:
    CACHE.setdefault("_cache", {}).setdefault("fetched_at", {}).setdefault(endpoint, {})[ticker] = now_iso()


def normalize_financial_rows(raw_data: Any) -> list[dict[str, Any]]:
    raw_rows = raw_data.get("data") if isinstance(raw_data, dict) else []
    if not isinstance(raw_rows, list) or RESOLVER is None:
        return []
    rows = [RESOLVER.normalize_finnhub_report(r) for r in raw_rows if isinstance(r, dict)]
    rows = [r for r in rows if r.get("periodEnd")]
    rows.sort(key=RESOLVER.period_sort_key, reverse=True)
    return rows


def normalize_earnings(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out = []
    for r in raw[:8]:
        if isinstance(r, dict):
            out.append({
                "period": r.get("period") or r.get("quarter"),
                "actual": r.get("actual"),
                "estimate": r.get("estimate"),
                "surprise": r.get("surprise"),
                "surprisePercent": r.get("surprisePercent"),
                "symbol": str(r.get("symbol") or "").upper(),
            })
    return out


def normalize_recommendations(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    rows = []
    for r in raw[:12]:
        if not isinstance(r, dict):
            continue
        rows.append({
            "period": r.get("period"),
            "strongBuy": r.get("strongBuy", 0) or 0,
            "buy": r.get("buy", 0) or 0,
            "hold": r.get("hold", 0) or 0,
            "sell": r.get("sell", 0) or 0,
            "strongSell": r.get("strongSell", 0) or 0,
            "symbol": str(r.get("symbol") or "").upper(),
        })
    rows.sort(key=lambda x: str(x.get("period") or ""))
    return rows[-8:]


def cached_call(endpoint: str, ticker: str, call_fn, normalize_fn):
    ticker = ticker.upper()
    bucket = endpoint_map(endpoint)
    if cache_fresh(endpoint, ticker):
        BUDGET.skipped_fresh[endpoint] += 1
        return CACHE.get(bucket, {}).get(ticker, [])
    if not CLIENT or OFFLINE or not API_KEY:
        return CACHE.get(bucket, {}).get(ticker, [])
    if not BUDGET.can_call(endpoint):
        BUDGET.skipped_budget[endpoint] += 1
        return CACHE.get(bucket, {}).get(ticker, [])
    try:
        raw = call_fn()
        data = normalize_fn(raw)
        CACHE.setdefault(bucket, {})[ticker] = data
        mark(endpoint, ticker)
        BUDGET.spend(endpoint, ticker)
        return data
    except Exception as exc:
        BUDGET.failed.setdefault(endpoint, []).append(f"{ticker}: {exc}")
        print(f"::warning::Finnhub {endpoint} failed for {ticker}: {exc}")
        return CACHE.get(bucket, {}).get(ticker, [])


def patched_financials(client: Any, ticker: str) -> list[dict[str, Any]]:
    return cached_call("financials", ticker, lambda: CLIENT.financials_reported(symbol=ticker, freq="quarterly"), normalize_financial_rows)


def patched_earnings(client: Any, ticker: str) -> list[dict[str, Any]]:
    return cached_call("earnings", ticker, lambda: CLIENT.company_earnings(ticker, limit=5), normalize_earnings)


def refresh_recommendations(tickers: list[str]) -> None:
    for ticker in tickers:
        cached_call("recommendations", ticker, lambda t=ticker: CLIENT.recommendation_trends(t), normalize_recommendations)


def write_recommendations_output() -> None:
    data = {
        "generated_at": now_iso(),
        "source": "Finnhub recommendation_trends cached by unified budget manager",
        "api_key_present": bool(API_KEY),
        "trends": CACHE.get("recommendations", {}),
        "_cache": {"fetched_at": CACHE.get("_cache", {}).get("fetched_at", {}).get("recommendations", {})},
        "_meta": {
            "version": "8.2.12",
            "finnhub_status": "missing_api_key" if not API_KEY else "loaded",
            "ttl_hours": TTL_HOURS["recommendations"],
            "global_budget_per_run": TOTAL_MAX_CALLS,
            "endpoint_budget_per_run": ENDPOINT_MAX["recommendations"],
            "calls_used": BUDGET.used["recommendations"],
            "refreshed": BUDGET.refreshed["recommendations"],
            "skipped_fresh_count": BUDGET.skipped_fresh["recommendations"],
            "skipped_budget_count": BUDGET.skipped_budget["recommendations"],
            "failed": BUDGET.failed["recommendations"],
            "policy": "One global Finnhub budget shared by financials, EPS surprise, and recommendation trends; unique US tickers only; skip .BK/non-US.",
        },
    }
    save_all(REC_PATHS, data)


def write_eps_output() -> None:
    data = {
        "generated_at": now_iso(),
        "source": "Finnhub company_earnings cached by unified budget manager",
        "api_key_present": bool(API_KEY),
        "surprises": CACHE.get("earnings", {}),
        "_cache": {"fetched_at": CACHE.get("_cache", {}).get("fetched_at", {}).get("earnings", {})},
        "_meta": {
            "version": "8.2.12",
            "finnhub_status": "missing_api_key" if not API_KEY else "loaded",
            "ttl_hours": TTL_HOURS["earnings"],
            "global_budget_per_run": TOTAL_MAX_CALLS,
            "endpoint_budget_per_run": ENDPOINT_MAX["earnings"],
            "calls_used": BUDGET.used["earnings"],
            "refreshed": BUDGET.refreshed["earnings"],
            "skipped_fresh_count": BUDGET.skipped_fresh["earnings"],
            "skipped_budget_count": BUDGET.skipped_budget["earnings"],
            "failed": BUDGET.failed["earnings"],
            "policy": "Shared Finnhub budget; company_earnings cache is also used by fundamental resolver EPS surprise.",
        },
    }
    save_all(EPS_PATHS, data)


def write_bundle_cache(tickers: list[str]) -> None:
    CACHE["generated_at"] = now_iso()
    CACHE["version"] = "8.2.11"
    CACHE["_meta"] = {
        "api_key_present": bool(API_KEY),
        "offline": OFFLINE,
        "checked_tickers": len(tickers),
        "ttl_hours": TTL_HOURS,
        "global_budget_per_run": TOTAL_MAX_CALLS,
        "endpoint_budget_per_run": ENDPOINT_MAX,
        "calls_used_total": sum(BUDGET.used.values()),
        "calls_used_by_endpoint": BUDGET.used,
        "refreshed": BUDGET.refreshed,
        "skipped_fresh": BUDGET.skipped_fresh,
        "skipped_budget": BUDGET.skipped_budget,
        "failed": BUDGET.failed,
        "policy": "v8.2.12: One global Finnhub quota envelope. Fundamental financials default to 30-day TTL; EPS/recommendation default to 7-day TTL. Fast price refresh never calls these endpoints.",
    }
    save_all(CACHE_PATHS, CACHE)


def patch_resolver() -> None:
    global RESOLVER
    import generate_fundamental_resolver as resolver  # type: ignore
    RESOLVER = resolver
    resolver.fetch_finnhub_financials = patched_financials
    resolver.fetch_finnhub_earnings = patched_earnings


def init_client() -> None:
    global CLIENT
    if API_KEY and not OFFLINE:
        try:
            import finnhub  # type: ignore
            CLIENT = finnhub.Client(api_key=API_KEY)
        except Exception as exc:
            CLIENT = None
            print(f"::warning::Finnhub client unavailable: {exc}")
    else:
        if not API_KEY:
            print("::warning::FINNHUB_API_KEY missing; preserving Finnhub caches")


def main() -> None:
    tickers = portfolio_tickers()
    tickers = sorted(tickers, key=lambda t: ticker_sort_key(t, CACHE))
    init_client()
    patch_resolver()

    print("Finnhub unified budget manager v8.2.12")
    print(f"- API key present: {bool(API_KEY)}")
    print(f"- Tickers checked: {len(tickers)}")
    print(f"- Global max calls this run: {TOTAL_MAX_CALLS}")
    print(f"- Endpoint caps: {ENDPOINT_MAX}")

    # Fundamental resolver will use patched cached financials/company_earnings.
    RESOLVER.main()

    # Recommendation trends use the remaining shared budget.
    refresh_recommendations(tickers)

    write_recommendations_output()
    write_eps_output()
    write_bundle_cache(tickers)

    print("Finnhub bundle complete")
    print(f"- Calls used total: {sum(BUDGET.used.values())}/{TOTAL_MAX_CALLS}")
    print(f"- Calls used by endpoint: {BUDGET.used}")
    print(f"- Skipped fresh: {BUDGET.skipped_fresh}")
    print(f"- Skipped budget: {BUDGET.skipped_budget}")
    for endpoint, failures in BUDGET.failed.items():
        if failures:
            print(f"- {endpoint} failures: {len(failures)}")


if __name__ == "__main__":
    main()
