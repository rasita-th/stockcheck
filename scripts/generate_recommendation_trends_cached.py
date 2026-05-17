#!/usr/bin/env python3
"""Generate Finnhub recommendation trends with per-ticker cache.

- Unique US tickers only; skips .BK and other non-US suffixes.
- Refreshes only stale/missing symbols.
- Preserves old data for symbols not refreshed in this run.
- Does not expose FINNHUB_API_KEY; reads it from GitHub Actions secrets.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from finnhub_cache_utils import (
    ROOT, api_key, call_budget, get_finnhub_client, is_fresh, load_json,
    mark_fetched, now_iso, portfolio_tickers, save_json_all
)

OUT_PATHS = [ROOT / "data" / "recommendation_trends.json", ROOT / "site" / "data" / "recommendation_trends.json", ROOT / "static" / "data" / "recommendation_trends.json"]
TTL_HOURS = float(__import__('os').environ.get("FINNHUB_REC_TTL_HOURS", "168"))  # 7 days
MAX_CALLS = call_budget(35, "FINNHUB_REC_MAX_CALLS_PER_RUN")


def normalize_rows(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append({
            "period": row.get("period"),
            "strongBuy": int(row.get("strongBuy") or 0),
            "buy": int(row.get("buy") or 0),
            "hold": int(row.get("hold") or 0),
            "sell": int(row.get("sell") or 0),
            "strongSell": int(row.get("strongSell") or 0),
            "symbol": str(row.get("symbol") or "").upper(),
        })
    return sorted(out, key=lambda r: str(r.get("period") or ""))[-12:]


def main() -> None:
    existing = load_json(OUT_PATHS[1], {}) if OUT_PATHS[1].exists() else load_json(OUT_PATHS[0], {})
    if not isinstance(existing, dict):
        existing = {}
    data = {
        "generated_at": now_iso(),
        "source": "Finnhub recommendation_trends cached",
        "api_key_present": bool(api_key()),
        "trends": existing.get("trends") if isinstance(existing.get("trends"), dict) else {},
        "_cache": existing.get("_cache") if isinstance(existing.get("_cache"), dict) else {"fetched_at": {}},
        "_meta": {
            "version": "8.2.10",
            "ttl_hours": TTL_HOURS,
            "max_calls_per_run": MAX_CALLS,
            "policy": "unique US tickers only; skip .BK/non-US; preserve cached data",
        },
    }
    trends = data["trends"]
    tickers = portfolio_tickers()
    client = get_finnhub_client()
    refreshed: list[str] = []
    skipped_fresh: list[str] = []
    missing_or_failed: list[str] = []

    if not client:
        data["_meta"]["finnhub_status"] = "missing_api_key"
        data["_meta"]["checked_tickers"] = tickers
        save_json_all(OUT_PATHS, data)
        print("::warning::FINNHUB_API_KEY missing; preserving existing recommendation trends cache")
        return

    calls_left = MAX_CALLS
    for ticker in tickers:
        if is_fresh(data, ticker, TTL_HOURS, "trends"):
            skipped_fresh.append(ticker)
            continue
        if calls_left <= 0:
            break
        try:
            rows = normalize_rows(client.recommendation_trends(ticker))
            trends[ticker] = rows
            mark_fetched(data, ticker)
            refreshed.append(ticker)
            calls_left -= 1
        except Exception as exc:
            missing_or_failed.append(ticker)
            print(f"::warning::recommendation_trends failed for {ticker}: {exc}")

    data["_meta"].update({
        "finnhub_status": "loaded",
        "checked_count": len(tickers),
        "refreshed": refreshed,
        "skipped_fresh_count": len(skipped_fresh),
        "skipped_fresh_sample": skipped_fresh[:40],
        "failed": missing_or_failed,
        "calls_used": len(refreshed),
        "calls_left": max(0, calls_left),
        "tracked_count": len(trends),
    })
    save_json_all(OUT_PATHS, data)
    print(f"Recommendation trends cache: refreshed {len(refreshed)}, skipped fresh {len(skipped_fresh)}, tracked {len(trends)}")


if __name__ == "__main__":
    main()
