#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST = ROOT / "watchlist.txt"
OUT_PATHS = (
    ROOT / "data" / "generated" / "quote_latest.json",
    ROOT / "site" / "data" / "quote_latest.json",
    ROOT / "static" / "data" / "quote_latest.json",
)


def read_watchlist() -> list[str]:
    if not WATCHLIST.exists():
        return ["NVDA", "PLTR", "TSLA", "MSFT", "AMZN", "HOOD"]
    out: list[str] = []
    for raw in WATCHLIST.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        for token in re.split(r"[\s,;|]+", line):
            ticker = token.strip().upper()
            if ticker and ticker not in out:
                out.append(ticker)
    return out


def num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def fetch_symbol(symbol: str) -> dict[str, Any]:
    ticker = yf.Ticker(symbol)
    fast_info = ticker.fast_info
    price = num(getattr(fast_info, "last_price", None))
    previous_close = num(getattr(fast_info, "previous_close", None))

    if price is None:
        minute_history = ticker.history(period="2d", interval="1m", auto_adjust=False)
        if not minute_history.empty:
            closes = minute_history["Close"].dropna()
            if len(closes):
                price = num(closes.iloc[-1])

    if previous_close is None:
        daily_history = ticker.history(period="5d", interval="1d", auto_adjust=False)
        closes = daily_history["Close"].dropna() if not daily_history.empty else []
        if len(closes) >= 2:
            previous_close = num(closes.iloc[-2])

    if price is None or price <= 0:
        raise ValueError("latest market price is unavailable")

    day_change = None if previous_close in (None, 0) else price - previous_close
    day_change_pct = None if day_change is None or previous_close in (None, 0) else day_change / previous_close * 100
    return {
        "ticker": symbol,
        "price": price,
        "previous_close": previous_close,
        "day_change": day_change,
        "day_change_pct": day_change_pct,
    }


def build_payload(symbols: list[str]) -> dict[str, Any]:
    workers = max(1, min(int(os.environ.get("QUOTE_REFRESH_WORKERS", "16")), 32, len(symbols) or 1))
    minimum_coverage = float(os.environ.get("QUOTE_MIN_COVERAGE", "0.80"))
    rows_by_symbol: dict[str, dict[str, Any]] = {}
    errors_by_symbol: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="quote") as executor:
        futures = {executor.submit(fetch_symbol, symbol): symbol for symbol in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                rows_by_symbol[symbol] = future.result()
            except Exception as exc:
                errors_by_symbol[symbol] = str(exc)

    rows = [rows_by_symbol[symbol] for symbol in symbols if symbol in rows_by_symbol]
    errors = [
        {"ticker": symbol, "error": errors_by_symbol[symbol]}
        for symbol in symbols
        if symbol in errors_by_symbol
    ]
    coverage = len(rows) / len(symbols) if symbols else 0.0
    if coverage < minimum_coverage:
        raise SystemExit(
            f"quote coverage below minimum: {len(rows)}/{len(symbols)} "
            f"({coverage:.1%} < {minimum_coverage:.1%})"
        )

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "schema_version": "1.1",
        "generated_at": generated_at,
        "market_as_of": generated_at,
        "source": "Yahoo Finance via concurrent yfinance fast_info",
        "status": "ok" if coverage >= 0.95 else "partial",
        "row_count": len(rows),
        "requested_count": len(symbols),
        "error_count": len(errors),
        "coverage": round(coverage, 6),
        "workers": workers,
        "stale_after_minutes": 30,
        "rows": rows,
        "errors": errors,
    }


def write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    print(f"wrote {path}")


def main() -> None:
    symbols = read_watchlist()
    if not symbols:
        raise SystemExit("watchlist is empty")
    payload = build_payload(symbols)
    for path in OUT_PATHS:
        write_atomic(path, payload)
    print(
        f"quote refresh: {payload['row_count']}/{payload['requested_count']} rows, "
        f"coverage={payload['coverage']:.1%}, workers={payload['workers']}"
    )


if __name__ == "__main__":
    main()
