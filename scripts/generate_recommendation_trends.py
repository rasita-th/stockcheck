#!/usr/bin/env python3
"""Generate Finnhub recommendation trends for Analyst Consensus tab.

This is a static-site safe implementation: the Finnhub key stays in GitHub
Actions secrets, the browser reads only generated JSON.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SITE_DATA_DIR = ROOT / "site" / "data"
STATIC_DATA_DIR = ROOT / "static" / "data"
PORTFOLIO_PATHS = [DATA_DIR / "portfolio.json", SITE_DATA_DIR / "portfolio.json"]
TECHNICAL_PATHS = [SITE_DATA_DIR / "technical.json", DATA_DIR / "technical.json", STATIC_DATA_DIR / "technical.json"]
OUT_PATHS = [DATA_DIR / "recommendation_trends.json", SITE_DATA_DIR / "recommendation_trends.json", STATIC_DATA_DIR / "recommendation_trends.json"]
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "").strip()
OFFLINE_MODE = os.environ.get("STOCKCHECK_ATTENTION_OFFLINE", "").lower() in {"1", "true", "yes"}

CATEGORIES = ["strongBuy", "buy", "hold", "sell", "strongSell"]


def now_ict() -> datetime:
    return datetime.now(timezone(timedelta(hours=7)))


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def tickers_from_portfolio() -> list[str]:
    path = first_existing(PORTFOLIO_PATHS)
    data = load_json(path, []) if path else []
    tickers: list[str] = []
    if isinstance(data, list):
        for row in data:
            if isinstance(row, dict) and row.get("ticker"):
                tickers.append(str(row["ticker"]).strip().upper())
    if tickers:
        return sorted(dict.fromkeys(tickers))

    # Fallback to scanner rows when portfolio config is absent.
    tech_path = first_existing(TECHNICAL_PATHS)
    tech = load_json(tech_path, {}) if tech_path else {}
    rows = tech.get("rows") or []
    for row in rows:
        if isinstance(row, dict):
            t = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
            if t:
                tickers.append(t)
    return sorted(dict.fromkeys(tickers))


def http_json(url: str, timeout: int = 15) -> Any:
    if OFFLINE_MODE:
        return None
    req = urllib.request.Request(url, headers={"User-Agent": "Stock Timing Radar recommendation trends", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize_row(row: dict[str, Any], ticker: str) -> dict[str, Any] | None:
    period = str(row.get("period") or row.get("date") or "")[:10]
    if not period:
        return None
    out = {"period": period[:7], "symbol": str(row.get("symbol") or ticker).upper()}
    total = 0
    for key in CATEGORIES:
        try:
            val = int(row.get(key) or 0)
        except Exception:
            val = 0
        out[key] = max(0, val)
        total += out[key]
    out["total"] = total
    return out if total > 0 else None


def fetch_recommendation_trends(ticker: str) -> tuple[list[dict[str, Any]], str | None]:
    if not FINNHUB_API_KEY:
        return [], "missing_api_key"
    if OFFLINE_MODE:
        return [], "skipped_offline"

    try:
        try:
            import finnhub  # type: ignore
            client = finnhub.Client(api_key=FINNHUB_API_KEY)
            raw = client.recommendation_trends(ticker)
        except ImportError:
            url = f"https://finnhub.io/api/v1/stock/recommendation?symbol={urllib.parse.quote(ticker)}&token={urllib.parse.quote(FINNHUB_API_KEY)}"
            raw = http_json(url) or []
        if not isinstance(raw, list):
            return [], "invalid_response"
        rows = [normalize_row(x, ticker) for x in raw[:6] if isinstance(x, dict)]
        rows = [x for x in rows if x]
        rows.sort(key=lambda x: str(x.get("period", "")))
        return rows, None
    except Exception as exc:
        return [], str(exc)


def main() -> None:
    tickers = tickers_from_portfolio()
    trends: dict[str, list[dict[str, Any]]] = {}
    errors: dict[str, str] = {}
    for ticker in tickers:
        rows, err = fetch_recommendation_trends(ticker)
        if rows:
            trends[ticker] = rows
        elif err:
            errors[ticker] = err
        time.sleep(0.12)

    output = {
        "generated_at": now_ict().replace(microsecond=0).isoformat(),
        "source": "Finnhub recommendation_trends",
        "api_key_present": bool(FINNHUB_API_KEY),
        "count": len(trends),
        "tickers_checked": len(tickers),
        "trends": trends,
        "errors": errors,
    }
    for path in OUT_PATHS:
        save_json(path, output)
    print(f"Generated recommendation trends: {len(trends)} / {len(tickers)} tickers")
    if errors:
        print("Recommendation trend warnings: " + ", ".join(f"{k}:{v}" for k, v in list(errors.items())[:10]))


if __name__ == "__main__":
    main()
