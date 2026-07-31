#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
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


def chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def ticker_frame(payload: pd.DataFrame | None, symbol: str) -> pd.DataFrame | None:
    if payload is None or payload.empty:
        return None
    if not isinstance(payload.columns, pd.MultiIndex):
        return payload

    wanted = symbol.upper()
    for level in range(payload.columns.nlevels):
        values = {str(value).upper() for value in payload.columns.get_level_values(level)}
        if wanted not in values:
            continue
        try:
            selected = payload.xs(symbol, axis=1, level=level, drop_level=True)
        except KeyError:
            selected = payload.xs(wanted, axis=1, level=level, drop_level=True)
        if isinstance(selected, pd.Series):
            selected = selected.to_frame()
        return selected
    return None


def close_series(payload: pd.DataFrame | None, symbol: str) -> pd.Series:
    frame = ticker_frame(payload, symbol)
    if frame is None or frame.empty:
        return pd.Series(dtype="float64")

    columns = frame.columns
    selected: pd.Series | None = None
    if isinstance(columns, pd.MultiIndex):
        for column in columns:
            if any(str(part).lower() == "close" for part in column):
                selected = frame[column]
                break
    else:
        for column in columns:
            if str(column).lower() == "close":
                selected = frame[column]
                break
    if selected is None:
        return pd.Series(dtype="float64")
    return pd.to_numeric(selected, errors="coerce").dropna()


def index_date(value: Any):
    try:
        return pd.Timestamp(value).date()
    except Exception:
        return None


def row_from_downloads(
    symbol: str,
    intraday: pd.DataFrame | None,
    daily: pd.DataFrame | None,
) -> dict[str, Any]:
    minute_closes = close_series(intraday, symbol)
    daily_closes = close_series(daily, symbol)

    quote_mode = "intraday"
    if len(minute_closes):
        price = num(minute_closes.iloc[-1])
        price_date = index_date(minute_closes.index[-1])
        if len(daily_closes):
            daily_last_date = index_date(daily_closes.index[-1])
            if price_date is not None and daily_last_date == price_date and len(daily_closes) >= 2:
                previous_close = num(daily_closes.iloc[-2])
            else:
                previous_close = num(daily_closes.iloc[-1])
        else:
            previous_close = None
    elif len(daily_closes):
        quote_mode = "daily_close"
        price = num(daily_closes.iloc[-1])
        previous_close = num(daily_closes.iloc[-2]) if len(daily_closes) >= 2 else None
    else:
        raise ValueError("latest market price is unavailable")

    if price is None or price <= 0:
        raise ValueError("latest market price is unavailable")

    day_change = None if previous_close in (None, 0) else price - previous_close
    day_change_pct = (
        None
        if day_change is None or previous_close in (None, 0)
        else day_change / previous_close * 100
    )
    return {
        "ticker": symbol,
        "price": price,
        "previous_close": previous_close,
        "day_change": day_change,
        "day_change_pct": day_change_pct,
        "quote_mode": quote_mode,
    }


def download_batch(
    symbols: list[str],
    *,
    period: str,
    interval: str,
    workers: int,
    timeout_seconds: float,
) -> pd.DataFrame | None:
    try:
        return yf.download(
            tickers=symbols,
            period=period,
            interval=interval,
            group_by="ticker",
            auto_adjust=False,
            actions=False,
            threads=max(1, min(workers, len(symbols))),
            progress=False,
            timeout=timeout_seconds,
            keepna=False,
            prepost=False,
            multi_level_index=True,
        )
    except Exception as exc:
        print(
            f"batch download failed: interval={interval} symbols={len(symbols)} error={exc}",
            flush=True,
        )
        return None


def build_payload(symbols: list[str]) -> dict[str, Any]:
    workers = max(1, min(int(os.environ.get("QUOTE_REFRESH_WORKERS", "16")), 32))
    batch_size = max(10, min(int(os.environ.get("QUOTE_BATCH_SIZE", "80")), 150))
    timeout_seconds = max(1.0, min(float(os.environ.get("QUOTE_REQUEST_TIMEOUT", "8")), 30.0))
    minimum_coverage = float(os.environ.get("QUOTE_MIN_COVERAGE", "0.80"))
    rows_by_symbol: dict[str, dict[str, Any]] = {}
    errors_by_symbol: dict[str, str] = {}

    total_batches = math.ceil(len(symbols) / batch_size) if symbols else 0
    for batch_number, batch in enumerate(chunks(symbols, batch_size), start=1):
        print(
            f"quote batch {batch_number}/{total_batches}: {len(batch)} symbols",
            flush=True,
        )
        intraday = download_batch(
            batch,
            period="2d",
            interval="1m",
            workers=workers,
            timeout_seconds=timeout_seconds,
        )
        daily = download_batch(
            batch,
            period="5d",
            interval="1d",
            workers=workers,
            timeout_seconds=timeout_seconds,
        )
        for symbol in batch:
            try:
                rows_by_symbol[symbol] = row_from_downloads(symbol, intraday, daily)
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
    intraday_count = sum(row.get("quote_mode") == "intraday" for row in rows)
    return {
        "schema_version": "1.2",
        "generated_at": generated_at,
        "market_as_of": generated_at,
        "source": "Yahoo Finance via bounded yfinance multi-ticker download",
        "status": "ok" if coverage >= 0.95 else "partial",
        "row_count": len(rows),
        "requested_count": len(symbols),
        "error_count": len(errors),
        "coverage": round(coverage, 6),
        "intraday_count": intraday_count,
        "workers": workers,
        "batch_size": batch_size,
        "request_timeout_seconds": timeout_seconds,
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
        f"coverage={payload['coverage']:.1%}, intraday={payload['intraday_count']}, "
        f"batch_size={payload['batch_size']}, timeout={payload['request_timeout_seconds']}s"
    )


if __name__ == "__main__":
    main()
