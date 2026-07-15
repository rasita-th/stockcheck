#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST = ROOT / "watchlist.txt"
OUT = ROOT / "data" / "generated" / "quote_latest.json"

def read_watchlist() -> list[str]:
    if not WATCHLIST.exists():
        return ["NVDA", "PLTR", "TSLA", "MSFT", "AMZN", "HOOD"]
    out: list[str] = []
    for raw in WATCHLIST.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        for token in re.split(r"[\s,;|]+", line):
            t = token.strip().upper()
            if t and t not in out:
                out.append(t)
    return out

def num(v: Any) -> float | None:
    try:
        n = float(v)
        return n if n == n else None
    except Exception:
        return None

def main() -> None:
    symbols = read_watchlist()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for symbol in symbols:
        try:
            t = yf.Ticker(symbol)
            fi = t.fast_info
            price = num(getattr(fi, "last_price", None))
            prev = num(getattr(fi, "previous_close", None))
            if price is None:
                hist = t.history(period="2d", interval="1m", auto_adjust=False)
                if not hist.empty:
                    price = num(hist["Close"].dropna().iloc[-1])
            if prev is None:
                hist_d = t.history(period="5d", interval="1d", auto_adjust=False)
                closes = hist_d["Close"].dropna() if not hist_d.empty else []
                if len(closes) >= 2:
                    prev = num(closes.iloc[-2])
            day_abs = None if price is None or prev in (None, 0) else price - prev
            day_pct = None if day_abs is None or prev in (None, 0) else day_abs / prev * 100
            rows.append({
                "ticker": symbol,
                "price": price,
                "previous_close": prev,
                "day_change": day_abs,
                "day_change_pct": day_pct,
            })
        except Exception as exc:
            errors.append({"ticker": symbol, "error": str(exc)})

    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_as_of": datetime.now(timezone.utc).isoformat(),
        "source": "Yahoo Finance via yfinance",
        "status": "ok" if rows else "error",
        "row_count": len(rows),
        "error_count": len(errors),
        "stale_after_minutes": 30,
        "rows": rows,
        "errors": errors,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} with {len(rows)} rows and {len(errors)} errors")

if __name__ == "__main__":
    main()
