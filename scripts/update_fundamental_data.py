#!/usr/bin/env python3
"""Generate static SEC-first fundamental data for GitHub Pages.

This script is designed for the slower daily/manual GitHub Actions workflow.
It fetches SEC companyfacts + conservative guidance parsing and stores the
result as static JSON. The frequent technical workflow reuses this file.

Outputs:
  site/data/fundamental.json
"""
from __future__ import annotations

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
WATCHLIST = ROOT / "watchlist.txt"
sys.path.insert(0, str(ROOT))

from app import build_analysis  # noqa: E402


FUNDAMENTAL_KEYS = {
    "fundamentalScore", "fundamentalSignal", "fundamentalReasons", "fundamentalHighlights", "fundamentalSource",
    "latestQuarter", "earningsDate", "revenue", "revenuePrevQuarter", "revenuePrevQuarterLabel", "revenueYearAgo", "revenueYearAgoLabel",
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
    symbols = read_watchlist()
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
    payload = {
        "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "generatedAtFundamental": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "count": len(rows),
        "watchlist": symbols,
        "rows": rows,
        "fundamentals": fundamentals,
        "errors": errors,
        "mode": "github-pages-hybrid-fundamental-static",
        "dataLayer": "fundamental",
        "durationSeconds": round(time.time() - started, 2),
        "note": "Static SEC fundamental layer. Updated by daily/manual GitHub Actions, then merged with technical.json in the browser.",
    }
    out = SITE_DATA / "fundamental.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {out} with {len(rows)} rows, {len(errors)} errors in {payload['durationSeconds']}s")


if __name__ == "__main__":
    main()
