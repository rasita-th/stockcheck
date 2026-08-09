#!/usr/bin/env python3
"""Generate static SEC-first fundamental data for GitHub Pages.

This script is designed for the slower daily/manual GitHub Actions workflow.
It fetches SEC companyfacts + conservative guidance parsing and stores the
result as static JSON. The frequent technical workflow reuses this file.

Outputs identical canonical mirrors:
  data/generated/fundamental.json
  site/data/fundamental.json
  static/data/fundamental.json
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

os.environ["INCLUDE_FUNDAMENTALS"] = "1"
os.environ.setdefault("SCAN_WORKERS", os.environ.get("FUNDAMENTAL_SCAN_WORKERS", "4"))
# Keep guidance robust but configurable from GitHub Actions variables.
os.environ.setdefault("SEC_GUIDANCE_LOOKBACK_DAYS", os.environ.get("SEC_GUIDANCE_LOOKBACK_DAYS", "1460"))
os.environ.setdefault("SEC_GUIDANCE_MAX_FILINGS", os.environ.get("SEC_GUIDANCE_MAX_FILINGS", "40"))
os.environ.setdefault("SEC_GUIDANCE_MAX_DOCUMENTS_PER_FILING", os.environ.get("SEC_GUIDANCE_MAX_DOCUMENTS_PER_FILING", "8"))

ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = ROOT / "site" / "data"
FUNDAMENTAL_PATHS = (
    ROOT / "data" / "generated" / "fundamental.json",
    SITE_DATA / "fundamental.json",
    ROOT / "static" / "data" / "fundamental.json",
)
WATCHLIST = ROOT / "watchlist.txt"
sys.path.insert(0, str(ROOT))

from app import build_analysis  # noqa: E402
from scripts.validate_fundamental_snapshot import validate_candidate, write_mirrors  # noqa: E402


FUNDAMENTAL_KEYS = {
    "fundamentalScore", "fundamentalSignal", "fundamentalReasons", "fundamentalHighlights", "fundamentalSource",
    "latestQuarter", "periodEnd", "filedDate", "filingDate", "accessNumber", "sourceUrl", "earningsDate", "revenue", "revenuePrevQuarter", "revenuePrevQuarterLabel", "revenueYearAgo", "revenueYearAgoLabel",
    "estimatedRevenue", "estimatedRevenueStatus", "revenueSurprisePct", "revenueQoQ", "revenueYoY",
    "netIncome", "netIncomePrevQuarter", "netIncomePrevQuarterLabel", "netIncomeYearAgo", "netIncomeYearAgoLabel",
    "estimatedNetIncome", "profitSurprisePct", "profitQoQ", "profitYoY",
    "eps", "epsPrevQuarter", "epsPrevQuarterLabel", "epsYearAgo", "epsYearAgoLabel", "estimatedEps", "estimatedEpsStatus", "epsSurprisePct", "epsQoQ", "epsYoY",
    "grossProfit", "grossMargin", "operatingIncome", "operatingMargin", "netMargin", "operatingCashFlow", "capex", "freeCashFlow",
    "cash", "totalDebt", "assets", "liabilities", "stockholdersEquity", "debtToEquity",
    "priorCompanyGuidanceRevenuePeriod", "priorCompanyGuidanceRevenue", "priorCompanyGuidanceRevenueLow", "priorCompanyGuidanceRevenueHigh", "actualVsPriorGuidanceRevenuePct",
    "nextCompanyGuidanceRevenue", "nextCompanyGuidanceRevenueLow", "nextCompanyGuidanceRevenueHigh", "nextCompanyGuidanceRevenuePeriod",
    "guidanceHistory", "guidanceDebug", "guidanceScanStats", "guidanceConfidence", "assetType", "dataQuality", "warnings", "tagAudit",
}


def read_watchlist() -> list[str]:
    if not WATCHLIST.exists():
        return ["NVDA", "PLTR", "TSLA", "TSM", "COST", "MSFT", "AMZN", "ORCL", "HOOD", "MSTR"]
    symbols: list[str] = []
    for raw in WATCHLIST.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Support v1-style pasted lists: commas, semicolons, spaces, tabs, or new lines.
        for part in re.split(r"[\s,;]+", line):
            symbol = part.strip().upper()
            if symbol and symbol not in symbols:
                symbols.append(symbol)
    return symbols


def select_post_earnings_symbols(
    watchlist: list[str],
    calendar: dict[str, Any],
    *,
    as_of: dt.date,
    lookback_days: int,
) -> list[str]:
    """Return watchlist tickers with an earnings date in the recent past."""
    allowed = {str(symbol).upper() for symbol in watchlist}
    earliest = as_of - dt.timedelta(days=max(0, int(lookback_days)))
    selected: set[str] = set()
    for item in calendar.get("items") or []:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").upper()
        try:
            earnings_date = dt.date.fromisoformat(str(item.get("earnings_date") or "")[:10])
        except ValueError:
            continue
        if ticker in allowed and earliest <= earnings_date <= as_of:
            selected.add(ticker)
    return [symbol for symbol in watchlist if symbol in selected]


def merge_targeted_snapshot(
    current: dict[str, Any],
    *,
    refreshed_rows: list[dict[str, Any]],
    refreshed_fundamentals: dict[str, dict[str, Any]],
    refreshed_symbols: list[str],
    errors: list[dict[str, str]],
    generated_at: str,
    duration_seconds: float,
) -> dict[str, Any]:
    """Replace only targeted ticker records while retaining full coverage."""
    row_map = {
        str(row.get("symbol") or row.get("ticker") or "").upper(): dict(row)
        for row in current.get("rows") or []
        if isinstance(row, dict)
    }
    for row in refreshed_rows:
        ticker = str(row.get("symbol") or row.get("ticker") or "").upper()
        if ticker:
            row_map[ticker] = row

    fundamentals = dict(current.get("fundamentals") or {})
    fundamentals.update(refreshed_fundamentals)
    targeted = {str(symbol).upper() for symbol in refreshed_symbols}
    retained_errors = [
        item for item in (current.get("errors") or [])
        if isinstance(item, dict) and str(item.get("symbol") or "").upper() not in targeted
    ]
    rows = list(row_map.values())
    rows.sort(key=lambda row: (row.get("fundamentalScore") is not None, row.get("fundamentalScore") or -1), reverse=True)

    payload = dict(current)
    payload.update({
        "generatedAt": generated_at,
        "generatedAtFundamental": generated_at,
        "count": len(rows),
        "rows": rows,
        "fundamentals": fundamentals,
        "errors": retained_errors + errors,
        "mode": "github-pages-hybrid-fundamental-static",
        "dataLayer": "fundamental",
        "refreshMode": "targeted-post-earnings",
        "refreshedSymbols": list(refreshed_symbols),
        "durationSeconds": round(duration_seconds, 2),
        "note": "Static SEC fundamental layer with targeted post-earnings refresh merged into the canonical snapshot.",
    })
    return payload


def set_workflow_output(*, changed: bool, symbols: list[str]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        handle.write(f"changed={'true' if changed else 'false'}\n")
        handle.write(f"symbols={','.join(symbols)}\n")


def pick_fundamental_fields(row: dict[str, Any]) -> dict[str, Any]:
    out = {"symbol": str(row.get("symbol") or "").upper(), "currency": row.get("currency"), "exchange": row.get("exchange"), "instrumentType": row.get("instrumentType")}
    for key in FUNDAMENTAL_KEYS:
        if key in row:
            out[key] = row.get(key)
    return out


def build_one(symbol: str) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    try:
        data = build_analysis(symbol, range_="1y", interval="1d")
        latest_f = pick_fundamental_fields(data.get("latest") or {})
        detail = {
            "symbol": symbol.upper(),
            "latest": latest_f,
            "fundamental": data.get("fundamental") or latest_f,
            "meta": {
                "source": "SEC EDGAR companyfacts + guidance parser",
                "generatedLayer": "fundamental",
            },
        }
        return symbol.upper(), latest_f, detail
    except Exception as exc:  # noqa: BLE001
        return symbol.upper(), None, {"symbol": symbol.upper(), "error": str(exc) or repr(exc) or type(exc).__name__}


def main() -> None:
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    watchlist = read_watchlist()
    refresh_mode = str(os.environ.get("FUNDAMENTAL_REFRESH_MODE") or "full").strip().lower()
    current: dict[str, Any] | None = None
    symbols = list(watchlist)
    if refresh_mode == "targeted-post-earnings":
        current_path = FUNDAMENTAL_PATHS[0]
        current = json.loads(current_path.read_text(encoding="utf-8"))
        calendar_path = ROOT / "data" / "earnings_calendar.json"
        calendar = json.loads(calendar_path.read_text(encoding="utf-8"))
        raw_as_of = str(os.environ.get("FUNDAMENTAL_AS_OF_DATE") or "").strip()
        as_of = dt.date.fromisoformat(raw_as_of) if raw_as_of else dt.datetime.now(dt.timezone.utc).date()
        lookback_days = int(os.environ.get("FUNDAMENTAL_POST_EARNINGS_LOOKBACK_DAYS", "7"))
        symbols = select_post_earnings_symbols(watchlist, calendar, as_of=as_of, lookback_days=lookback_days)
        if not symbols:
            print(f"NO_CHANGES: no watchlist earnings in {lookback_days}-day lookback ending {as_of}")
            set_workflow_output(changed=False, symbols=[])
            return
        print(f"Targeted post-earnings refresh: {', '.join(symbols)}")
    rows: list[dict[str, Any]] = []
    fundamentals: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    started = time.time()
    workers = max(1, min(int(os.environ.get("FUNDAMENTAL_SCAN_WORKERS", "4")), len(symbols) or 1))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(build_one, sym): sym for sym in symbols}
        for future in as_completed(futures):
            sym = futures[future]
            ticker, row, detail = future.result()
            if row:
                rows.append(row)
                fundamentals[ticker] = detail or {"symbol": ticker, "latest": row, "fundamental": row}
                print(f"OK fundamental {ticker}")
            else:
                err = detail if isinstance(detail, dict) else {"symbol": sym, "error": "Unknown error"}
                errors.append({"symbol": str(err.get("symbol") or sym), "error": str(err.get("error") or "Unknown error")})
                print(f"ERR fundamental {sym}: {errors[-1]['error']}")
    rows.sort(key=lambda r: (r.get("fundamentalScore") is not None, r.get("fundamentalScore") or -1), reverse=True)
    generated_at = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    if refresh_mode == "targeted-post-earnings":
        if not rows:
            print("NO_CHANGES: every targeted SEC refresh failed; preserving the current snapshot")
            set_workflow_output(changed=False, symbols=symbols)
            return
        payload = merge_targeted_snapshot(
            current or {},
            refreshed_rows=rows,
            refreshed_fundamentals=fundamentals,
            refreshed_symbols=symbols,
            errors=errors,
            generated_at=generated_at,
            duration_seconds=time.time() - started,
        )
    else:
        payload = {
            "generatedAt": generated_at,
            "generatedAtFundamental": generated_at,
            "count": len(rows),
            "watchlist": watchlist,
            "rows": rows,
            "fundamentals": fundamentals,
            "errors": errors,
            "mode": "github-pages-hybrid-fundamental-static",
            "dataLayer": "fundamental",
            "refreshMode": "full",
            "refreshedSymbols": symbols,
            "durationSeconds": round(time.time() - started, 2),
            "note": "Static SEC fundamental layer. Updated by daily/manual GitHub Actions, then merged with technical.json in the browser.",
        }
    validate_candidate(payload, current)
    write_mirrors(payload, FUNDAMENTAL_PATHS)
    set_workflow_output(changed=True, symbols=symbols)
    print(f"Wrote {len(FUNDAMENTAL_PATHS)} identical Fundamental mirrors with {payload['count']} rows, {len(errors)} errors in {payload['durationSeconds']}s")


if __name__ == "__main__":
    main()
