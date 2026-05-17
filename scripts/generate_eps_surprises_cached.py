#!/usr/bin/env python3
"""Generate Finnhub EPS surprise cache with unique ticker throttling."""
from __future__ import annotations

from typing import Any

from finnhub_cache_utils import (
    ROOT, api_key, call_budget, get_finnhub_client, is_fresh, load_json,
    mark_fetched, now_iso, portfolio_tickers, save_json_all
)

OUT_PATHS = [ROOT / "data" / "eps_surprises.json", ROOT / "site" / "data" / "eps_surprises.json", ROOT / "static" / "data" / "eps_surprises.json"]
TTL_HOURS = float(__import__('os').environ.get("FINNHUB_EPS_TTL_HOURS", "168"))
MAX_CALLS = call_budget(35, "FINNHUB_EPS_MAX_CALLS_PER_RUN")


def normalize(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    out = []
    for r in rows[:8]:
        if not isinstance(r, dict):
            continue
        out.append({
            "period": r.get("period") or r.get("quarter"),
            "actual": r.get("actual"),
            "estimate": r.get("estimate"),
            "surprise": r.get("surprise"),
            "surprisePercent": r.get("surprisePercent"),
            "symbol": str(r.get("symbol") or "").upper(),
        })
    return out


def main() -> None:
    existing = load_json(OUT_PATHS[1], {}) if OUT_PATHS[1].exists() else load_json(OUT_PATHS[0], {})
    if not isinstance(existing, dict): existing = {}
    data = {
        "generated_at": now_iso(),
        "source": "Finnhub company_earnings cached",
        "api_key_present": bool(api_key()),
        "surprises": existing.get("surprises") if isinstance(existing.get("surprises"), dict) else {},
        "_cache": existing.get("_cache") if isinstance(existing.get("_cache"), dict) else {"fetched_at": {}},
        "_meta": {"version":"8.2.10", "ttl_hours":TTL_HOURS, "max_calls_per_run":MAX_CALLS, "policy":"unique US tickers only; skip .BK/non-US; preserve cached data"},
    }
    client = get_finnhub_client()
    tickers = portfolio_tickers()
    if not client:
        data["_meta"].update({"finnhub_status":"missing_api_key", "checked_tickers":tickers})
        save_json_all(OUT_PATHS, data)
        print("::warning::FINNHUB_API_KEY missing; preserving EPS surprise cache")
        return
    calls_left = MAX_CALLS
    refreshed=[]; skipped=[]; failed=[]
    for ticker in tickers:
        if is_fresh(data, ticker, TTL_HOURS, "surprises"):
            skipped.append(ticker); continue
        if calls_left <= 0: break
        try:
            rows = normalize(client.company_earnings(ticker, limit=5))
            data["surprises"][ticker] = rows
            mark_fetched(data, ticker)
            refreshed.append(ticker); calls_left -= 1
        except Exception as exc:
            failed.append(ticker)
            print(f"::warning::company_earnings failed for {ticker}: {exc}")
    data["_meta"].update({"finnhub_status":"loaded", "checked_count":len(tickers), "refreshed":refreshed, "skipped_fresh_count":len(skipped), "skipped_fresh_sample":skipped[:40], "failed":failed, "calls_used":len(refreshed), "tracked_count":len(data["surprises"])})
    save_json_all(OUT_PATHS, data)
    print(f"EPS surprise cache: refreshed {len(refreshed)}, skipped fresh {len(skipped)}, tracked {len(data['surprises'])}")

if __name__ == "__main__":
    main()
