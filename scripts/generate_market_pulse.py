#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_PATHS = [
    ROOT / "data" / "market_universe.json",
    ROOT / "site" / "data" / "market_universe.json",
    ROOT / "static" / "data" / "market_universe.json",
]
OUTPUT_DIRS = [ROOT / "data", ROOT / "site" / "data", ROOT / "static" / "data"]


def load_universe() -> dict[str, list[dict[str, str]]]:
    for path in UNIVERSE_PATHS:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    raise SystemExit("market_universe.json not found")


def pct_change(series: pd.Series, sessions: int) -> float | None:
    series = series.dropna()
    if len(series) <= sessions:
        return None
    old = float(series.iloc[-sessions - 1])
    new = float(series.iloc[-1])
    if old == 0:
        return None
    return (new / old - 1.0) * 100.0


def ytd_change(series: pd.Series) -> float | None:
    series = series.dropna()
    if series.empty:
        return None
    current_year = series.index[-1].year
    ytd = series[series.index.year == current_year]
    if len(ytd) < 2:
        return None
    first = float(ytd.iloc[0])
    last = float(ytd.iloc[-1])
    if first == 0:
        return None
    return (last / first - 1.0) * 100.0


def safe_round(value: Any, digits: int = 2) -> float | None:
    try:
        n = float(value)
        if not math.isfinite(n):
            return None
        return round(n, digits)
    except Exception:
        return None


def fetch_prices(symbols: list[str]) -> pd.DataFrame:
    data = yf.download(
        tickers=" ".join(symbols),
        period="1y",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=True,
        group_by="column",
    )
    if data.empty:
        raise SystemExit("No market pulse price data returned")
    if isinstance(data.columns, pd.MultiIndex):
        if "Close" in data.columns.get_level_values(0):
            return data["Close"]
        if "Adj Close" in data.columns.get_level_values(0):
            return data["Adj Close"]
    if "Close" in data.columns:
        return data[["Close"]].rename(columns={"Close": symbols[0]})
    raise SystemExit("Could not locate Close prices in yfinance response")


def build_rows(items: list[dict[str, str]], closes: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        symbol = item["symbol"]
        if symbol not in closes.columns:
            continue
        series = closes[symbol].dropna()
        if series.empty:
            continue
        row = dict(item)
        row.update({
            "price": safe_round(series.iloc[-1]),
            "day_pct": safe_round(pct_change(series, 1)),
            "week_pct": safe_round(pct_change(series, 5)),
            "month_pct": safe_round(pct_change(series, 21)),
            "ytd_pct": safe_round(ytd_change(series)),
            "as_of": series.index[-1].strftime("%Y-%m-%d"),
        })
        rows.append(row)
    return rows


def rank_rows(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: (r.get(key) is not None, r.get(key) or -9999), reverse=True)


def build_today_pulse(sectors: list[dict[str, Any]], themes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    for group, rows in (("sector", sectors), ("theme", themes)):
        for row in rows:
            score = abs(row.get("day_pct") or 0) * 1.2 + abs(row.get("week_pct") or 0) * 0.6
            direction = "inflow" if (row.get("week_pct") or 0) > 0 else "outflow"
            candidates.append({
                "symbol": row.get("symbol"),
                "label": row.get("label"),
                "group": group,
                "direction": direction,
                "day_pct": row.get("day_pct"),
                "week_pct": row.get("week_pct"),
                "month_pct": row.get("month_pct"),
                "score": round(score, 2),
            })
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:10]


def save_all(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    for directory in OUTPUT_DIRS:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "market_pulse.json"
        path.write_text(text + "\n", encoding="utf-8")
        print("wrote", path)


def main() -> None:
    universe = load_universe()
    all_items = sum((universe.get(key, []) for key in ("global_markets", "us_sectors", "themes")), [])
    symbols = list(dict.fromkeys(item["symbol"] for item in all_items))
    closes = fetch_prices(symbols)

    global_rows = build_rows(universe.get("global_markets", []), closes)
    sector_rows = build_rows(universe.get("us_sectors", []), closes)
    theme_rows = build_rows(universe.get("themes", []), closes)

    payload = {
        "version": "9.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Yahoo Finance via yfinance; ETF proxies for relative market performance",
        "global_markets": rank_rows(global_rows, "ytd_pct"),
        "us_sectors": rank_rows(sector_rows, "week_pct"),
        "themes": rank_rows(theme_rows, "week_pct"),
        "today_pulse": build_today_pulse(sector_rows, theme_rows),
        "breadth": {
            "sectors_positive_day": sum(1 for r in sector_rows if (r.get("day_pct") or 0) > 0),
            "sectors_positive_week": sum(1 for r in sector_rows if (r.get("week_pct") or 0) > 0),
            "sector_count": len(sector_rows),
        },
    }
    save_all(payload)


if __name__ == "__main__":
    main()
