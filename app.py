#!/usr/bin/env python3
"""
Stock Timing Radar
A lightweight local web app for scanning stocks by EMA/RSI setup.

Run:
  python app.py
Then open:
  http://localhost:8787

Data source:
  Yahoo Finance chart endpoint, fetched server-side to avoid browser CORS issues.
  Symbols use Yahoo format, e.g. NVDA, PLTR, TSM, COST, 0700.HK, PTT.BK.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import math
import os
import shutil
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
import ssl

try:
    import certifi
    ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())
except Exception:
    pass
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

PORT = int(os.environ.get("PORT", "8787"))
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "120"))
HTTP_VERBOSE_LOG = os.environ.get("STOCK_RADAR_HTTP_LOG", "0").lower() in {"1", "true", "yes", "verbose"}

def _load_local_env_files() -> None:
    """Tiny .env/key-file loader for IDLE use. No third-party dotenv needed."""
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for raw in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_local_env_files()

ALPHA_VANTAGE_DAILY_LIMIT = int(os.environ.get("ALPHA_VANTAGE_DAILY_LIMIT", "25"))
ALPHA_VANTAGE_CACHE_DIR = BASE_DIR / ".alpha_vantage_cache"
ALPHA_VANTAGE_QUOTA_FILE = BASE_DIR / ".alpha_vantage_quota.json"
ALPHA_VANTAGE_CACHE_DIR.mkdir(exist_ok=True)


# In-memory cache: key -> (timestamp, payload)
CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}

# Small caches for no-key fundamental data sources.
QUOTE_V7_CACHE: Dict[str, Dict[str, Any]] = {}
SEC_TICKER_CACHE: Optional[Dict[str, Any]] = None
SEC_FACTS_CACHE: Dict[str, Dict[str, Any]] = {}


DEFAULT_WATCHLIST = [
    "NVDA", "PLTR", "TSLA", "TSM", "COST", "MSFT", "AMZN", "ORCL", "HOOD", "MSTR"
]
WATCHLIST_FILE = BASE_DIR / "watchlist.txt"
SCAN_WORKERS = int(os.environ.get("SCAN_WORKERS", "8"))
INCLUDE_FUNDAMENTALS = os.environ.get("INCLUDE_FUNDAMENTALS", "1") != "0"

# SEC-first fundamental V1. Keep this as a separate Python module so it can
# be opened and run in IDLE independently before touching the web UI.
try:
    from sec_v1_fundamentals import build_fundamental_sec_v1
except Exception as _sec_v1_import_error:  # noqa: BLE001
    build_fundamental_sec_v1 = None  # type: ignore[assignment]
    SEC_V1_IMPORT_ERROR = str(_sec_v1_import_error)
else:
    SEC_V1_IMPORT_ERROR = None


def read_watchlist_file() -> List[str]:
    if not WATCHLIST_FILE.exists():
        return list(DEFAULT_WATCHLIST)
    symbols: List[str] = []
    for raw in WATCHLIST_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        for part in line.replace(";", ",").split(","):
            symbol = part.strip().upper()
            if symbol and symbol not in symbols:
                symbols.append(symbol)
    return symbols or list(DEFAULT_WATCHLIST)


@dataclass
class Candle:
    ts: int
    date: str
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[int]


def _http_get_text(url: str, timeout: int = 20) -> str:
    """Fetch text with browser-like headers. Some data endpoints reject bare Python requests."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            ),
            "Accept": "application/json,text/csv,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9,th;q=0.8",
            "Connection": "close",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _http_get_json(url: str, timeout: int = 20) -> Dict[str, Any]:
    raw = _http_get_text(url, timeout=timeout)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        preview = raw[:180].replace("\n", " ").strip()
        raise RuntimeError(f"Market data returned non-JSON response: {preview}") from exc


def _range_to_period1(range_: str) -> int:
    days = {
        "1mo": 45,
        "3mo": 120,
        "6mo": 220,
        "1y": 420,
        "2y": 760,
        "5y": 1900,
        "10y": 3800,
        "ytd": 420,
        "max": 8000,
    }.get(range_, 420)
    return int(time.time()) - days * 24 * 60 * 60


def _stooq_symbol(symbol: str) -> str:
    """Best-effort Stooq fallback. Works mainly for US tickers."""
    s = symbol.strip().lower().replace("-", ".")
    if "." not in s:
        s = f"{s}.us"
    return s


def stooq_chart(symbol: str, range_: str = "1y") -> Dict[str, Any]:
    stooq_symbol = _stooq_symbol(symbol)
    url = f"https://stooq.com/q/d/l/?s={urllib.parse.quote(stooq_symbol)}&i=d"
    raw = _http_get_text(url)
    if "No data" in raw or not raw.strip():
        raise RuntimeError(f"No fallback data from Stooq for {symbol}")

    rows = list(csv.DictReader(io.StringIO(raw)))
    if not rows:
        raise RuntimeError(f"No fallback rows from Stooq for {symbol}")

    start_date = dt.datetime.utcfromtimestamp(_range_to_period1(range_)).date()
    parsed = []
    for row in rows:
        try:
            date_obj = dt.date.fromisoformat(row["Date"])
            if date_obj < start_date:
                continue
            parsed.append({
                "date": date_obj,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(float(row.get("Volume") or 0)),
            })
        except Exception:
            continue

    if len(parsed) < 30:
        raise RuntimeError(f"Not enough fallback history from Stooq for {symbol}")

    timestamps = [int(dt.datetime.combine(r["date"], dt.time()).replace(tzinfo=dt.timezone.utc).timestamp()) for r in parsed]
    quote = {
        "open": [r["open"] for r in parsed],
        "high": [r["high"] for r in parsed],
        "low": [r["low"] for r in parsed],
        "close": [r["close"] for r in parsed],
        "volume": [r["volume"] for r in parsed],
    }
    latest = parsed[-1]
    return {
        "chart": {
            "result": [{
                "timestamp": timestamps,
                "indicators": {"quote": [quote]},
                "meta": {
                    "currency": "USD",
                    "exchangeName": "Stooq fallback",
                    "fullExchangeName": "Stooq fallback",
                    "instrumentType": "EQUITY",
                    "regularMarketPrice": latest["close"],
                    "regularMarketTime": timestamps[-1],
                },
            }],
            "error": None,
        }
    }


def yahoo_chart(symbol: str, range_: str = "1y", interval: str = "1d") -> Dict[str, Any]:
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("Missing ticker symbol")

    allowed_ranges = {"1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}
    allowed_intervals = {"1d", "1wk", "1mo"}
    if range_ not in allowed_ranges:
        range_ = "1y"
    if interval not in allowed_intervals:
        interval = "1d"

    cache_key = f"{symbol}:{range_}:{interval}"
    cached = CACHE.get(cache_key)
    if cached and time.time() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    encoded_symbol = urllib.parse.quote(symbol, safe="")
    urls = [
        (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}"
            f"?range={urllib.parse.quote(range_)}&interval={urllib.parse.quote(interval)}"
            "&includePrePost=false&events=div%2Csplits"
        ),
        (
            f"https://query2.finance.yahoo.com/v8/finance/chart/{encoded_symbol}"
            f"?range={urllib.parse.quote(range_)}&interval={urllib.parse.quote(interval)}"
            "&includePrePost=false&events=div%2Csplits"
        ),
    ]

    last_error = None
    for url in urls:
        try:
            payload = _http_get_json(url)
            CACHE[cache_key] = (time.time(), payload)
            return payload
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(0.2)

    # Fallback works best for US tickers like NVDA, MSFT, TSLA. Non-US symbols may still fail.
    try:
        payload = stooq_chart(symbol, range_)
        CACHE[cache_key] = (time.time(), payload)
        return payload
    except Exception as fallback_exc:  # noqa: BLE001
        base_msg = str(last_error) or repr(last_error)
        fallback_msg = str(fallback_exc) or repr(fallback_exc)
        raise RuntimeError(f"Yahoo failed: {base_msg}; fallback failed: {fallback_msg}") from fallback_exc


def epoch_to_date(ts: int) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def parse_candles(payload: Dict[str, Any]) -> Tuple[List[Candle], Dict[str, Any]]:
    chart = payload.get("chart", {})
    errors = chart.get("error")
    if errors:
        raise RuntimeError(errors.get("description") or str(errors))

    results = chart.get("result") or []
    if not results:
        raise RuntimeError("No data returned from market data source")

    result = results[0]
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    meta = result.get("meta") or {}

    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    candles: List[Candle] = []
    for i, ts in enumerate(timestamps):
        close = closes[i] if i < len(closes) else None
        # Keep rows with a close only; holidays/partial missing rows are noise.
        if close is None:
            continue
        candles.append(
            Candle(
                ts=int(ts),
                date=epoch_to_date(int(ts)),
                open=opens[i] if i < len(opens) else None,
                high=highs[i] if i < len(highs) else None,
                low=lows[i] if i < len(lows) else None,
                close=close,
                volume=volumes[i] if i < len(volumes) else None,
            )
        )
    if len(candles) < 30:
        raise RuntimeError("Not enough price history to calculate indicators")
    return candles, meta


def ema(values: List[Optional[float]], period: int) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(values)
    valid_indices = [i for i, v in enumerate(values) if v is not None]
    if len(valid_indices) < period:
        return out

    first_window_indices = valid_indices[:period]
    first_ema = sum(float(values[i]) for i in first_window_indices) / period  # type: ignore[arg-type]
    start_idx = first_window_indices[-1]
    out[start_idx] = first_ema
    k = 2 / (period + 1)
    prev = first_ema

    for i in range(start_idx + 1, len(values)):
        v = values[i]
        if v is None:
            out[i] = prev
            continue
        prev = float(v) * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(values: List[Optional[float]], period: int = 14) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(values)
    closes = [float(v) if v is not None else None for v in values]
    valid_positions = [i for i, v in enumerate(closes) if v is not None]
    if len(valid_positions) <= period:
        return out

    # RSI over contiguous close series after removing None values, then map back.
    compact = [(i, float(closes[i])) for i in valid_positions]
    gains: List[float] = []
    losses: List[float] = []
    for j in range(1, period + 1):
        change = compact[j][1] - compact[j - 1][1]
        gains.append(max(change, 0.0))
        losses.append(abs(min(change, 0.0)))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    def calc_rsi(gain: float, loss: float) -> float:
        if loss == 0:
            return 100.0
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    out[compact[period][0]] = calc_rsi(avg_gain, avg_loss)

    for j in range(period + 1, len(compact)):
        change = compact[j][1] - compact[j - 1][1]
        gain = max(change, 0.0)
        loss = abs(min(change, 0.0))
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        out[compact[j][0]] = calc_rsi(avg_gain, avg_loss)
    return out


def sma(values: List[Optional[float]], period: int) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(values)
    window: List[float] = []
    for i, value in enumerate(values):
        if value is not None:
            window.append(float(value))
        if len(window) > period:
            window.pop(0)
        if len(window) == period:
            out[i] = sum(window) / period
    return out


def pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return (a / b - 1) * 100


def last_not_none(values: List[Optional[float]]) -> Optional[float]:
    for v in reversed(values):
        if v is not None:
            return v
    return None


def round_or_none(v: Optional[float], digits: int = 2) -> Optional[float]:
    if v is None or math.isnan(v) or math.isinf(v):
        return None
    return round(float(v), digits)




def _safe_get(obj: Any, path: List[Any], default: Any = None) -> Any:
    cur = obj
    for part in path:
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and isinstance(part, int) and 0 <= part < len(cur):
            cur = cur[part]
        else:
            return default
        if cur is None:
            return default
    return cur


def _raw_value(obj: Any, path: List[Any], default: Any = None) -> Any:
    value = _safe_get(obj, path, default)
    if isinstance(value, dict) and "raw" in value:
        return value.get("raw")
    return value


def _round_fund(value: Any, digits: int = 2) -> Optional[float]:
    try:
        if value is None:
            return None
        return round(float(value), digits)
    except Exception:
        return None


def _fmt_quarter_from_date(timestamp: Any) -> Optional[str]:
    if not timestamp:
        return None
    try:
        d = dt.datetime.utcfromtimestamp(int(timestamp)).date()
        q = (d.month - 1) // 3 + 1
        return f"Q{q} {d.year}"
    except Exception:
        return None


def _date_from_ts(timestamp: Any) -> Optional[str]:
    if not timestamp:
        return None
    try:
        return dt.datetime.utcfromtimestamp(int(timestamp)).strftime("%Y-%m-%d")
    except Exception:
        return None


def _days_to(timestamp: Any) -> Optional[int]:
    if not timestamp:
        return None
    try:
        target = dt.datetime.utcfromtimestamp(int(timestamp)).date()
        return (target - dt.datetime.utcnow().date()).days
    except Exception:
        return None



def fetch_quote_summary(symbol: str) -> Dict[str, Any]:
    """Yahoo quoteSummary sometimes blocks/404s; try query1 and query2."""
    modules = ",".join([
        "price",
        "financialData",
        "calendarEvents",
        "earningsTrend",
        "defaultKeyStatistics",
        "incomeStatementHistoryQuarterly",
        "earningsHistory",
        "recommendationTrend",
    ])
    encoded = urllib.parse.quote(symbol)
    urls = [
        f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{encoded}?modules={modules}",
        f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{encoded}?modules={modules}",
    ]
    last_error = None
    for url in urls:
        try:
            payload = _http_get_json(url, timeout=15)
            return _safe_get(payload, ["quoteSummary", "result", 0], {}) or {}
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(0.15)
    if last_error:
        raise last_error
    return {}


def fetch_quote_v7(symbol: str) -> Dict[str, Any]:
    """Fallback Yahoo quote endpoint. It often works when quoteSummary returns 404/401."""
    symbol = symbol.strip().upper()
    if symbol in QUOTE_V7_CACHE:
        return QUOTE_V7_CACHE[symbol]
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={urllib.parse.quote(symbol)}"
    payload = _http_get_json(url, timeout=15)
    result = _safe_get(payload, ["quoteResponse", "result", 0], {}) or {}
    QUOTE_V7_CACHE[symbol] = result
    return result


def _pct_change(new: Any, old: Any) -> Optional[float]:
    try:
        if new is None or old in (None, 0):
            return None
        return (float(new) / float(old) - 1.0) * 100.0
    except Exception:
        return None


def _plain_us_ticker(symbol: str) -> Optional[str]:
    """SEC company facts only covers US-listed companies; skip ETFs and non-US suffixes."""
    s = symbol.strip().upper()
    if not s or "." in s:
        return None
    # SEC mapping uses BRK-B style tickers as BRK-B. Keep hyphen.
    return s


def fetch_sec_ticker_map() -> Dict[str, Any]:
    global SEC_TICKER_CACHE
    if SEC_TICKER_CACHE is not None:
        return SEC_TICKER_CACHE
    req = urllib.request.Request(
        "https://www.sec.gov/files/company_tickers.json",
        headers={
            "User-Agent": "StockTimingRadar/1.0 contact@example.com",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        SEC_TICKER_CACHE = json.loads(resp.read().decode("utf-8", errors="replace"))
    return SEC_TICKER_CACHE


def sec_cik_for_symbol(symbol: str) -> Optional[str]:
    ticker = _plain_us_ticker(symbol)
    if not ticker:
        return None
    try:
        mapping = fetch_sec_ticker_map()
        for item in mapping.values():
            if str(item.get("ticker", "")).upper() == ticker:
                return str(item.get("cik_str", "")).zfill(10)
    except Exception:
        return None
    return None


def fetch_sec_company_facts(symbol: str) -> Optional[Dict[str, Any]]:
    cik = sec_cik_for_symbol(symbol)
    if not cik:
        return None
    if cik in SEC_FACTS_CACHE:
        return SEC_FACTS_CACHE[cik]
    req = urllib.request.Request(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
        headers={
            "User-Agent": "StockTimingRadar/1.0 contact@example.com",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        facts = json.loads(resp.read().decode("utf-8", errors="replace"))
    SEC_FACTS_CACHE[cik] = facts
    return facts


def _sec_units_for_fact(facts: Dict[str, Any], names: List[str], unit: str) -> List[Dict[str, Any]]:
    gaap = _safe_get(facts, ["facts", "us-gaap"], {}) or {}
    for name in names:
        units = _safe_get(gaap, [name, "units"], {}) or {}
        values = units.get(unit)
        if values:
            return values
    return []


def _sec_quarterly_values(values: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for item in values:
        try:
            val = item.get("val")
            fy = item.get("fy")
            fp = str(item.get("fp") or "")
            form = str(item.get("form") or "")
            start = item.get("start")
            end = item.get("end")
            filed = item.get("filed")
            if val is None or not fy or not end or fp.upper() == "FY":
                continue
            # For quarterly facts, prefer 10-Q/10-K frame data with normal quarter length.
            if start:
                days = (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days
                if days < 55 or days > 125:
                    continue
            key = (fy, fp.upper(), end)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "value": float(val),
                "fy": int(fy),
                "fp": fp.upper(),
                "form": form,
                "start": start,
                "end": end,
                "filed": filed,
            })
        except Exception:
            continue
    out.sort(key=lambda x: (x.get("end") or "", x.get("filed") or ""))
    return out


def _sec_latest_with_changes(values: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not values:
        return {
            "value": None,
            "qoq": None,
            "yoy": None,
            "quarter": None,
            "date": None,
            "prevValue": None,
            "prevQuarter": None,
            "yearAgoValue": None,
            "yearAgoQuarter": None,
        }
    latest = values[-1]
    prev = values[-2] if len(values) >= 2 else None
    yoy = None
    for candidate in reversed(values[:-1]):
        if candidate.get("fp") == latest.get("fp") and int(candidate.get("fy", 0)) == int(latest.get("fy", 0)) - 1:
            yoy = candidate
            break
    return {
        "value": latest.get("value"),
        "qoq": _pct_change(latest.get("value"), prev.get("value") if prev else None),
        "yoy": _pct_change(latest.get("value"), yoy.get("value") if yoy else None),
        "quarter": f"{latest.get('fp')} {latest.get('fy')}",
        "date": latest.get("end"),
        "prevValue": prev.get("value") if prev else None,
        "prevQuarter": f"{prev.get('fp')} {prev.get('fy')}" if prev else None,
        "yearAgoValue": yoy.get("value") if yoy else None,
        "yearAgoQuarter": f"{yoy.get('fp')} {yoy.get('fy')}" if yoy else None,
    }


def build_sec_fundamental(symbol: str) -> Dict[str, Any]:
    """No-key fallback using SEC XBRL company facts for US companies.

    This gives actual latest quarterly revenue/net income/EPS plus QoQ/YoY.
    It does not include analyst estimates or target prices.
    """
    try:
        facts = fetch_sec_company_facts(symbol)
        if not facts:
            return {}
        revenue_values = _sec_quarterly_values(_sec_units_for_fact(facts, [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        ], "USD"))
        profit_values = _sec_quarterly_values(_sec_units_for_fact(facts, ["NetIncomeLoss"], "USD"))
        eps_values = _sec_quarterly_values(_sec_units_for_fact(facts, [
            "EarningsPerShareDiluted",
            "EarningsPerShareBasic",
        ], "USD/shares"))
        rev = _sec_latest_with_changes(revenue_values)
        profit = _sec_latest_with_changes(profit_values)
        eps = _sec_latest_with_changes(eps_values)
        latest_quarter = rev.get("quarter") or profit.get("quarter") or eps.get("quarter")
        report_date = rev.get("date") or profit.get("date") or eps.get("date")
        return {
            "latestQuarter": latest_quarter,
            "earningsDate": report_date,
            "revenue": _round_fund(rev.get("value"), 0),
            "revenuePrevQuarter": _round_fund(rev.get("prevValue"), 0),
            "revenuePrevQuarterLabel": rev.get("prevQuarter"),
            "revenueYearAgo": _round_fund(rev.get("yearAgoValue"), 0),
            "revenueYearAgoLabel": rev.get("yearAgoQuarter"),
            "revenueQoQ": _round_fund(rev.get("qoq"), 2),
            "revenueYoY": _round_fund(rev.get("yoy"), 2),
            "netIncome": _round_fund(profit.get("value"), 0),
            "netIncomePrevQuarter": _round_fund(profit.get("prevValue"), 0),
            "netIncomePrevQuarterLabel": profit.get("prevQuarter"),
            "netIncomeYearAgo": _round_fund(profit.get("yearAgoValue"), 0),
            "netIncomeYearAgoLabel": profit.get("yearAgoQuarter"),
            "profitQoQ": _round_fund(profit.get("qoq"), 2),
            "profitYoY": _round_fund(profit.get("yoy"), 2),
            "eps": _round_fund(eps.get("value"), 3),
            "epsPrevQuarter": _round_fund(eps.get("prevValue"), 3),
            "epsPrevQuarterLabel": eps.get("prevQuarter"),
            "epsYearAgo": _round_fund(eps.get("yearAgoValue"), 3),
            "epsYearAgoLabel": eps.get("yearAgoQuarter"),
            "epsQoQ": _round_fund(eps.get("qoq"), 2),
            "epsYoY": _round_fund(eps.get("yoy"), 2),
            "fundamentalSourceSec": "SEC companyfacts no-key fallback",
        }
    except Exception:
        return {}


def _score_fundamental(f: Dict[str, Any]) -> Tuple[Optional[int], str, List[str]]:
    score = 0.0
    possible = 0
    reasons: List[str] = []

    def add_points(metric: str, value: Any, max_points: int, kind: str = "pct") -> None:
        nonlocal score, possible
        if value is None:
            reasons.append(f"{metric}: N/A")
            return
        possible += max_points
        v = float(value)
        if kind == "surprise":
            pts = max(0.0, min(max_points, (v + 5) / 20 * max_points))
        elif kind == "growth":
            pts = max(0.0, min(max_points, v / 30 * max_points))
        elif kind == "target":
            pts = max(0.0, min(max_points, (v + 5) / 35 * max_points))
        else:
            pts = max(0.0, min(max_points, v / 20 * max_points))
        score += pts
        if v > 10:
            reasons.append(f"{metric} แข็งแรง ({v:.1f}%)")
        elif v > 0:
            reasons.append(f"{metric} เป็นบวก ({v:.1f}%)")
        else:
            reasons.append(f"{metric} อ่อน/ติดลบ ({v:.1f}%)")

    # SEC V2.1 core score: keep analyst consensus/targets out of the table and out of the score.
    add_points("Revenue YoY", f.get("revenueYoY"), 20, "growth")
    add_points("Revenue QoQ", f.get("revenueQoQ"), 15, "growth")
    add_points("EPS YoY", f.get("epsYoY"), 15, "growth")
    add_points("EPS QoQ", f.get("epsQoQ"), 10, "growth")
    add_points("Profit YoY", f.get("profitYoY"), 15, "growth")
    add_points("Profit QoQ", f.get("profitQoQ"), 10, "growth")
    add_points("Actual vs prior company guide", f.get("actualVsPriorGuidanceRevenuePct"), 15, "surprise")

    if possible == 0:
        return None, "Insufficient data", ["ข้อมูลพื้นฐาน/estimate ไม่พอสำหรับให้คะแนน"]

    final = round(score / possible * 100)
    if final >= 85:
        signal = "Fundamental Beat / Strong"
    elif final >= 70:
        signal = "Solid / Watch"
    elif final >= 55:
        signal = "Mixed"
    else:
        signal = "Weak / Avoid"
    return int(final), signal, reasons[:8]


def build_fundamental(symbol: str, latest: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort Level 1 fundamentals.

    v8.1 hotfix:
    - Yahoo quoteSummary often returns 404/401 on some machines.
    - Fallback to Yahoo v7 quote for target/EPS/earnings date.
    - Fallback to SEC companyfacts for US quarterly revenue/net income/EPS + QoQ/YoY.
    Missing values stay None; no fabricated figures.
    """
    if not INCLUDE_FUNDAMENTALS:
        return {
            "fundamentalScore": None,
            "fundamentalSignal": "Fundamentals disabled",
            "fundamentalReasons": ["ตั้ง INCLUDE_FUNDAMENTALS=1 เพื่อเปิดข้อมูลพื้นฐาน"],
        }

    source_notes: List[str] = []
    qs: Dict[str, Any] = {}
    quote: Dict[str, Any] = {}
    yahoo_error: Optional[str] = None

    try:
        qs = fetch_quote_summary(symbol)
        if qs:
            source_notes.append("Yahoo quoteSummary")
    except Exception as exc:  # noqa: BLE001
        yahoo_error = str(exc)[:160]

    try:
        quote = fetch_quote_v7(symbol)
        if quote:
            source_notes.append("Yahoo quote v7")
    except Exception as exc:  # noqa: BLE001
        if not yahoo_error:
            yahoo_error = str(exc)[:160]

    sec_f = build_sec_fundamental(symbol)
    if sec_f:
        source_notes.append("SEC companyfacts")

    trend0 = _safe_get(qs, ["earningsTrend", "trend", 0], {}) or {}
    earnings_date = (
        _raw_value(qs, ["calendarEvents", "earnings", "earningsDate", 0])
        or quote.get("earningsTimestamp")
        or quote.get("earningsTimestampStart")
        or quote.get("earningsTimestampEnd")
    )
    current_price = latest.get("close") or _raw_value(qs, ["price", "regularMarketPrice"]) or quote.get("regularMarketPrice")

    target_mean = _raw_value(qs, ["financialData", "targetMeanPrice"]) or quote.get("targetMeanPrice")
    target_low = _raw_value(qs, ["financialData", "targetLowPrice"]) or quote.get("targetLowPrice")
    target_high = _raw_value(qs, ["financialData", "targetHighPrice"]) or quote.get("targetHighPrice")
    target_median = _raw_value(qs, ["financialData", "targetMedianPrice"]) or quote.get("targetMedianPrice")
    analyst_count = (
        _raw_value(qs, ["financialData", "numberOfAnalystOpinions"])
        or _raw_value(qs, ["defaultKeyStatistics", "numberOfAnalystOpinions"])
        or quote.get("numberOfAnalystOpinions")
    )

    # Actual quarterly values: SEC first; Yahoo financialData totalRevenue is usually TTM, so use it only as fallback.
    revenue = sec_f.get("revenue") if sec_f.get("revenue") is not None else _raw_value(qs, ["financialData", "totalRevenue"]) or quote.get("revenue")
    net_income = sec_f.get("netIncome") if sec_f.get("netIncome") is not None else _raw_value(qs, ["financialData", "netIncomeToCommon"]) or quote.get("netIncomeToCommon")
    eps = sec_f.get("eps") if sec_f.get("eps") is not None else _raw_value(qs, ["defaultKeyStatistics", "trailingEps"]) or quote.get("epsTrailingTwelveMonths")

    est_revenue = _raw_value(trend0, ["revenueEstimate", "avg"])
    est_eps = _raw_value(trend0, ["earningsEstimate", "avg"]) or quote.get("epsForward")

    revenue_surprise = None
    if revenue is not None and est_revenue not in (None, 0):
        revenue_surprise = (float(revenue) / float(est_revenue) - 1) * 100
    eps_surprise = None
    if eps is not None and est_eps not in (None, 0):
        eps_surprise = (float(eps) / float(est_eps) - 1) * 100
    target_upside = None
    if current_price and target_mean:
        target_upside = (float(target_mean) / float(current_price) - 1) * 100

    latest_quarter = sec_f.get("latestQuarter") or _fmt_quarter_from_date(earnings_date)
    earnings_date_text = sec_f.get("earningsDate") or _date_from_ts(earnings_date)

    # If SEC reports period end date, daysToNextQuarter is not meaningful; keep upcoming Yahoo date when available.
    days_to_next = _days_to(earnings_date)

    price_target_connected = any(v is not None for v in [target_low, target_mean, target_median, target_high])
    revenue_estimate_status = "Consensus estimate available" if est_revenue is not None else "N/A = ไม่มี consensus estimate หรือ Yahoo endpoint ไม่ส่งค่า"
    eps_estimate_status = "Consensus estimate available" if est_eps is not None else "N/A = ไม่มี consensus estimate หรือ Yahoo endpoint ไม่ส่งค่า"
    price_target_status = "Connected" if price_target_connected else "Not available / blocked"

    f: Dict[str, Any] = {
        "latestQuarter": latest_quarter,
        "earningsDate": earnings_date_text,
        "daysToNextQuarter": days_to_next,
        "revenue": _round_fund(revenue, 0),
        "revenuePrevQuarter": sec_f.get("revenuePrevQuarter"),
        "revenuePrevQuarterLabel": sec_f.get("revenuePrevQuarterLabel"),
        "revenueYearAgo": sec_f.get("revenueYearAgo"),
        "revenueYearAgoLabel": sec_f.get("revenueYearAgoLabel"),
        "estimatedRevenue": _round_fund(est_revenue, 0),
        "estimatedRevenueStatus": revenue_estimate_status,
        "revenueSurprisePct": _round_fund(revenue_surprise, 2),
        "revenueQoQ": sec_f.get("revenueQoQ"),
        "revenueYoY": sec_f.get("revenueYoY"),
        "netIncome": _round_fund(net_income, 0),
        "netIncomePrevQuarter": sec_f.get("netIncomePrevQuarter"),
        "netIncomePrevQuarterLabel": sec_f.get("netIncomePrevQuarterLabel"),
        "netIncomeYearAgo": sec_f.get("netIncomeYearAgo"),
        "netIncomeYearAgoLabel": sec_f.get("netIncomeYearAgoLabel"),
        "estimatedNetIncome": None,
        "profitSurprisePct": None,
        "profitQoQ": sec_f.get("profitQoQ"),
        "profitYoY": sec_f.get("profitYoY"),
        "eps": _round_fund(eps, 3),
        "epsPrevQuarter": sec_f.get("epsPrevQuarter"),
        "epsPrevQuarterLabel": sec_f.get("epsPrevQuarterLabel"),
        "epsYearAgo": sec_f.get("epsYearAgo"),
        "epsYearAgoLabel": sec_f.get("epsYearAgoLabel"),
        "estimatedEps": _round_fund(est_eps, 3),
        "estimatedEpsStatus": eps_estimate_status,
        "epsSurprisePct": _round_fund(eps_surprise, 2),
        "epsQoQ": sec_f.get("epsQoQ"),
        "epsYoY": sec_f.get("epsYoY"),
        "targetLowPrice": _round_fund(target_low, 2),
        "targetMeanPrice": _round_fund(target_mean, 2),
        "targetMedianPrice": _round_fund(target_median, 2),
        "targetHighPrice": _round_fund(target_high, 2),
        "targetUpsidePct": _round_fund(target_upside, 2),
        "targetAnalystCount": _round_fund(analyst_count, 0),
        "priceTargetConnected": price_target_connected,
        "priceTargetStatus": price_target_status,
        "fundamentalSource": " + ".join(source_notes) if source_notes else f"No source available; last error: {yahoo_error or 'N/A'}",
    }
    score, signal, reasons = _score_fundamental(f)
    f["fundamentalScore"] = score
    f["fundamentalSignal"] = signal
    f["fundamentalReasons"] = reasons

    highlights: List[str] = []
    if f.get("revenueYoY") is not None:
        highlights.append(f"Revenue YoY: {f['revenueYoY']:+.2f}%")
    if f.get("revenueQoQ") is not None:
        highlights.append(f"Revenue QoQ: {f['revenueQoQ']:+.2f}%")
    if f.get("epsYoY") is not None:
        highlights.append(f"EPS YoY: {f['epsYoY']:+.2f}%")
    if f.get("epsQoQ") is not None:
        highlights.append(f"EPS QoQ: {f['epsQoQ']:+.2f}%")
    if f.get("revenueSurprisePct") is not None:
        highlights.append(f"Revenue เทียบ estimate: {f['revenueSurprisePct']:+.2f}%")
    if f.get("epsSurprisePct") is not None:
        highlights.append(f"EPS เทียบ estimate/forward EPS: {f['epsSurprisePct']:+.2f}%")
    # Analyst target is intentionally excluded from SEC core highlights.
    if not highlights:
        highlights.append("ข้อมูลพื้นฐานยังไม่พอ: Yahoo/SEC ไม่มี field ที่ต้องใช้สำหรับ ticker นี้")
    f["fundamentalHighlights"] = highlights
    return f

def score_setup(latest: Dict[str, Optional[float]], previous: Dict[str, Optional[float]]) -> Tuple[int, str, List[str], Dict[str, int]]:
    price = latest.get("close")
    ema5 = latest.get("ema5")
    ema20 = latest.get("ema20")
    ema89 = latest.get("ema89")
    ema200 = latest.get("ema200")
    rsi14 = latest.get("rsi14")
    volume = latest.get("volume")
    vol20 = latest.get("vol20")
    prev_ema5 = previous.get("ema5")

    trend = 0
    momentum = 0
    rsi_score = 0
    volume_score = 0
    reasons: List[str] = []

    # Trend: 40 points
    if price is not None and ema200 is not None and price > ema200:
        trend += 15
        reasons.append("ราคาอยู่เหนือ EMA200 = โครงสร้างใหญ่ยังเป็นขาขึ้น")
    else:
        reasons.append("ราคาอยู่ต่ำกว่า/ยังไม่มี EMA200 = โครงสร้างใหญ่ยังไม่นิ่ง")

    if ema20 is not None and ema89 is not None and ema20 > ema89:
        trend += 10
        reasons.append("EMA20 > EMA89 = medium trend สนับสนุน")

    if ema89 is not None and ema200 is not None and ema89 > ema200:
        trend += 10
        reasons.append("EMA89 > EMA200 = long trend เรียงตัวดี")

    if price is not None and ema89 is not None and price > ema89:
        trend += 5

    # Momentum: 30 points
    if price is not None and ema20 is not None and price > ema20:
        momentum += 10
        reasons.append("ราคาเหนือ EMA20 = momentum รายสัปดาห์/รายวันกลับมาดี")

    if ema5 is not None and ema20 is not None and ema5 > ema20:
        momentum += 10
        reasons.append("EMA5 > EMA20 = แรงระยะสั้นเริ่มนำ")

    if ema5 is not None and prev_ema5 is not None and ema5 > prev_ema5:
        momentum += 5

    if price is not None and ema5 is not None and price > ema5:
        momentum += 5

    # RSI: 20 points
    if rsi14 is None:
        reasons.append("RSI ยังไม่พอข้อมูล")
    elif 45 <= rsi14 <= 65:
        rsi_score = 20
        reasons.append("RSI 45-65 = sweet spot ของ pullback/continuation")
    elif 40 <= rsi14 < 45:
        rsi_score = 14
        reasons.append("RSI 40-45 = เริ่มฟื้น แต่ยังต้องรอยืนยัน")
    elif 65 < rsi14 <= 70:
        rsi_score = 14
        reasons.append("RSI 65-70 = momentum แรง แต่เริ่มร้อน")
    elif 35 <= rsi14 < 40:
        rsi_score = 9
        reasons.append("RSI 35-40 = oversold watchlist มากกว่า buy now")
    elif 70 < rsi14 <= 80:
        rsi_score = 7
        reasons.append("RSI >70 = หุ้นแรง แต่เสี่ยงไล่ราคา")
    elif rsi14 > 80:
        rsi_score = 2
        reasons.append("RSI >80 = ร้อนจัด ระวังโดนสับขาหลอก")
    else:
        rsi_score = 6
        reasons.append("RSI ต่ำมาก = อาจเด้งได้ แต่ trend ยังต้องพิสูจน์")

    # Volume: 10 points
    if volume is not None and vol20 is not None and vol20 > 0:
        vol_ratio = volume / vol20
        if vol_ratio >= 1.25:
            volume_score = 10
            reasons.append("Volume > 1.25x ค่าเฉลี่ย 20 วัน = มีแรงยืนยัน")
        elif vol_ratio >= 1.0:
            volume_score = 7
            reasons.append("Volume ใกล้/เหนือค่าเฉลี่ย = สัญญาณไม่แห้ง")
        else:
            volume_score = 3
            reasons.append("Volume ต่ำกว่าค่าเฉลี่ย = รอดูแรงซื้อ")

    total = trend + momentum + rsi_score + volume_score

    # Label logic. Strong opinions, but rules-based.
    if price is not None and ema200 is not None and price < ema200 and total < 60:
        label = "AVOID / Turnaround only"
    elif rsi14 is not None and rsi14 >= 75 and total >= 70:
        label = "HOT — อย่าไล่ราคา"
    elif total >= 82 and rsi14 is not None and 45 <= rsi14 <= 70:
        label = "BUY ZONE / Trend Confirmed"
    elif total >= 72:
        label = "WATCH FOR ENTRY"
    elif total >= 58:
        label = "NEUTRAL / Wait"
    else:
        label = "WEAK / Avoid"

    parts = {"trend": trend, "momentum": momentum, "rsi": rsi_score, "volume": volume_score}
    return total, label, reasons, parts


def build_analysis(symbol: str, range_: str = "1y", interval: str = "1d", include_fundamentals: Optional[bool] = None) -> Dict[str, Any]:
    include_fundamentals = INCLUDE_FUNDAMENTALS if include_fundamentals is None else bool(include_fundamentals)
    payload = yahoo_chart(symbol, range_=range_, interval=interval)
    candles, meta = parse_candles(payload)

    closes = [c.close for c in candles]
    volumes_float: List[Optional[float]] = [float(c.volume) if c.volume is not None else None for c in candles]
    ema5 = ema(closes, 5)
    ema12 = ema(closes, 12)
    ema20 = ema(closes, 20)
    ema26 = ema(closes, 26)
    ema89 = ema(closes, 89)
    ema200 = ema(closes, 200)
    rsi14 = rsi(closes, 14)
    vol20 = sma(volumes_float, 20)

    macd_line: List[Optional[float]] = []
    for i in range(len(closes)):
        if ema12[i] is None or ema26[i] is None:
            macd_line.append(None)
        else:
            macd_line.append(float(ema12[i]) - float(ema26[i]))
    macd_signal = ema(macd_line, 9)
    macd_hist: List[Optional[float]] = []
    for i in range(len(closes)):
        if macd_line[i] is None or macd_signal[i] is None:
            macd_hist.append(None)
        else:
            macd_hist.append(float(macd_line[i]) - float(macd_signal[i]))

    enriched: List[Dict[str, Any]] = []
    for i, c in enumerate(candles):
        enriched.append(
            {
                "date": c.date,
                "timestamp": c.ts,
                "open": round_or_none(c.open),
                "high": round_or_none(c.high),
                "low": round_or_none(c.low),
                "close": round_or_none(c.close),
                "volume": c.volume,
                "ema5": round_or_none(ema5[i]),
                "ema20": round_or_none(ema20[i]),
                "ema89": round_or_none(ema89[i]),
                "ema200": round_or_none(ema200[i]),
                "rsi14": round_or_none(rsi14[i]),
                "macd1226": round_or_none(macd_line[i]),
                "macdSignal9": round_or_none(macd_signal[i]),
                "macdHist": round_or_none(macd_hist[i]),
                "vol20": round_or_none(vol20[i], 0),
            }
        )

    latest_row = enriched[-1]
    prev_row = enriched[-2] if len(enriched) >= 2 else enriched[-1]
    score, label, reasons, score_parts = score_setup(latest_row, prev_row)

    window_52w = candles[-252:] if len(candles) >= 252 else candles
    high_values_52w = [c.high for c in window_52w if c.high is not None]
    low_values_52w = [c.low for c in window_52w if c.low is not None]
    high_52w = max(high_values_52w) if high_values_52w else None
    low_52w = min(low_values_52w) if low_values_52w else None

    latest = {
        **latest_row,
        "symbol": symbol.upper(),
        "currency": meta.get("currency"),
        "exchange": meta.get("exchangeName") or meta.get("fullExchangeName"),
        "instrumentType": meta.get("instrumentType"),
        "regularMarketPrice": round_or_none(meta.get("regularMarketPrice")),
        "regularMarketTime": epoch_to_date(int(meta.get("regularMarketTime"))) if meta.get("regularMarketTime") else None,
        "score": score,
        "scoreParts": score_parts,
        "signal": label,
        "reasons": reasons,
        "pctVsEma5": round_or_none(pct(latest_row.get("close"), latest_row.get("ema5"))),
        "pctVsEma20": round_or_none(pct(latest_row.get("close"), latest_row.get("ema20"))),
        "pctVsEma89": round_or_none(pct(latest_row.get("close"), latest_row.get("ema89"))),
        "pctVsEma200": round_or_none(pct(latest_row.get("close"), latest_row.get("ema200"))),
        "high52w": round_or_none(high_52w),
        "low52w": round_or_none(low_52w),
        "pctFrom52wHigh": round_or_none(pct(latest_row.get("close"), high_52w)),
        "pctFrom52wLow": round_or_none(pct(latest_row.get("close"), low_52w)),
        "volumeRatio20": round_or_none((latest_row.get("volume") or 0) / latest_row.get("vol20") if latest_row.get("vol20") else None),
    }

    if latest.get("macd1226") is not None and latest.get("macdSignal9") is not None:
        if latest["macd1226"] > latest["macdSignal9"]:
            latest["reasons"].append("MACD 12,26 อยู่เหนือ Signal 9 = momentum สนับสนุน")
        else:
            latest["reasons"].append("MACD 12,26 ยังต่ำกว่า Signal 9 = momentum ยังต้องรอ")

    # V8.9 / SEC V1: use SEC EDGAR for core fundamentals.
    # Yahoo remains the price/technical source only. Analyst target is reserved for V2.
    if build_fundamental_sec_v1 is not None:
        fundamental = build_fundamental_sec_v1(symbol, latest, include=include_fundamentals)
    else:
        fundamental = {
            "fundamentalScore": None,
            "fundamentalSignal": "SEC V1 import error",
            "fundamentalReasons": [SEC_V1_IMPORT_ERROR or "Cannot import sec_v1_fundamentals.py"],
            "fundamentalSource": "SEC V1 module import failed",
        }
    latest.update(fundamental)

    return {
        "symbol": symbol.upper(),
        "latest": latest,
        "fundamental": fundamental,
        "series": enriched,
        "meta": {
            "range": range_,
            "interval": interval,
            "source": "Yahoo Finance chart endpoint",
            "dataDelayNote": "Data may be delayed depending on exchange and source.",
        },
    }


def scan_symbols(symbols: Iterable[str], range_: str = "1y", interval: str = "1d", include_fundamentals: bool = False) -> Dict[str, Any]:
    """Scan a symbol list and return both table rows and full quote payloads.

    The original GitHub Pages UI expects data/scanner.json to contain:
      { rows: [...], quotes: { TICKER: full_detail_payload }, errors: [...] }

    Local Python/IDLE mode now returns the same shape from /api/scan, so the
    browser no longer depends on a pre-generated static scanner.json file.
    """
    rows: List[Dict[str, Any]] = []
    quotes: Dict[str, Dict[str, Any]] = {}
    errors: List[Dict[str, str]] = []
    seen = set()
    clean_symbols: List[str] = []
    for raw in symbols:
        symbol = raw.strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        clean_symbols.append(symbol)

    def one(symbol: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Dict[str, str]]]:
        try:
            data = build_analysis(symbol, range_, interval, include_fundamentals=include_fundamentals)
            return data["latest"], data, None
        except Exception as exc:  # noqa: BLE001
            return None, None, {"symbol": symbol, "error": str(exc) or repr(exc) or type(exc).__name__}

    workers = max(1, min(SCAN_WORKERS, len(clean_symbols) or 1))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(one, symbol): symbol for symbol in clean_symbols}
        for future in as_completed(futures):
            row, detail, err = future.result()
            if row is not None:
                rows.append(row)
                sym = str(row.get("symbol") or futures[future]).upper()
                if detail is not None:
                    quotes[sym] = detail
            if err is not None:
                errors.append(err)

    rows.sort(key=lambda r: (r.get("score") is not None, r.get("score", -1)), reverse=True)
    return {
        "rows": rows,
        "quotes": quotes,
        "errors": sorted(errors, key=lambda e: e.get("symbol", "")),
        "count": len(rows),
        "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "mode": "local-python-api-sec-v1",
    }


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {"none", "null", "nan", "-", "n/a"}:
        return None
    try:
        n = float(text)
        if not math.isfinite(n):
            return None
        return n
    except Exception:
        return None


def _safe_int(value: Any) -> Optional[int]:
    n = _safe_float(value)
    return int(n) if n is not None else None


def _utc_day() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


def _next_utc_midnight_iso() -> str:
    now = dt.datetime.now(dt.timezone.utc)
    nxt = (now + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return nxt.isoformat().replace("+00:00", "Z")


def _next_local_reset_text() -> str:
    now = dt.datetime.now(dt.timezone.utc)
    nxt_utc = (now + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return nxt_utc.astimezone().strftime("%Y-%m-%d %H:%M %Z")


def _read_json_file(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _write_json_file(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)



def _mask_secret(value: str) -> str:
    value = (value or "").strip()
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}…{value[-4:]}"


def alpha_vantage_key_status() -> Dict[str, Any]:
    key = os.environ.get("ALPHA_VANTAGE_API_KEY", "").strip()
    return {
        "ok": True,
        "hasKey": bool(key),
        "maskedKey": _mask_secret(key) if key else None,
        "quota": alpha_vantage_quota_status(),
    }


def save_alpha_vantage_key(api_key: str) -> Dict[str, Any]:
    """Deprecated in V2.7.

    Public-GitHub-safe mode no longer writes API keys to local files. The
    browser stores the key in localStorage and sends it only with the manual
    analyst-consensus request. This endpoint is kept only so older frontends do
    not crash; it intentionally does not persist secrets.
    """
    api_key = (api_key or "").strip().strip('"').strip("'")
    if not api_key or len(api_key) < 8:
        raise ValueError("Invalid Alpha Vantage API key")
    return {
        "ok": True,
        "hasKey": False,
        "maskedKey": _mask_secret(api_key),
        "storage": "browser-localStorage-only",
        "note": "V2.7 does not persist API keys on the server.",
        "quota": alpha_vantage_quota_status(),
    }

def alpha_vantage_key(provided_api_key: Optional[str] = None) -> str:
    key = (provided_api_key or "").strip().strip('"').strip("'")
    if not key:
        # Optional deployment fallback. Safe for private deployments using host
        # environment variables; not required for public BYOK/localStorage mode.
        key = os.environ.get("ALPHA_VANTAGE_API_KEY", "").strip()
    if not key or "PASTE" in key.upper() or len(key) < 8:
        raise RuntimeError(
            "Missing Alpha Vantage API key. Paste your key in the Analyst Consensus tab "
            "or set ALPHA_VANTAGE_API_KEY as a private environment variable."
        )
    return key


def alpha_vantage_quota_status() -> Dict[str, Any]:
    today = _utc_day()
    raw = _read_json_file(ALPHA_VANTAGE_QUOTA_FILE, {})
    if raw.get("date") != today:
        raw = {"date": today, "used": 0, "calls": []}
    used = int(raw.get("used") or 0)
    return {
        "dateUtc": today,
        "used": used,
        "limit": ALPHA_VANTAGE_DAILY_LIMIT,
        "remaining": max(0, ALPHA_VANTAGE_DAILY_LIMIT - used),
        "resetAtUtc": _next_utc_midnight_iso(),
        "resetAtLocal": _next_local_reset_text(),
    }


def _increment_alpha_vantage_quota(ticker: str, endpoint: str) -> Dict[str, Any]:
    today = _utc_day()
    raw = _read_json_file(ALPHA_VANTAGE_QUOTA_FILE, {})
    if raw.get("date") != today:
        raw = {"date": today, "used": 0, "calls": []}
    used = int(raw.get("used") or 0)
    if used >= ALPHA_VANTAGE_DAILY_LIMIT:
        raise RuntimeError("ALPHA_VANTAGE_DAILY_LIMIT_REACHED")
    raw["used"] = used + 1
    raw.setdefault("calls", []).append({
        "ticker": ticker.upper(),
        "endpoint": endpoint,
        "atUtc": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    })
    _write_json_file(ALPHA_VANTAGE_QUOTA_FILE, raw)
    return alpha_vantage_quota_status()


def _av_cache_path(ticker: str, endpoint: str) -> Path:
    safe = "".join(ch for ch in ticker.upper() if ch.isalnum() or ch in {".", "-", "_"})
    return ALPHA_VANTAGE_CACHE_DIR / f"{_utc_day()}_{endpoint}_{safe}.json"


def _fetch_alpha_vantage_overview(ticker: str, api_key: Optional[str] = None) -> Tuple[Dict[str, Any], bool, Dict[str, Any]]:
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("Missing ticker")
    cache_path = _av_cache_path(ticker, "OVERVIEW")
    cached = _read_json_file(cache_path, None)
    if isinstance(cached, dict) and cached.get("raw"):
        return cached["raw"], True, alpha_vantage_quota_status()

    status = alpha_vantage_quota_status()
    if status["remaining"] <= 0:
        raise RuntimeError("ALPHA_VANTAGE_DAILY_LIMIT_REACHED")

    api_key = alpha_vantage_key(api_key)
    _increment_alpha_vantage_quota(ticker, "OVERVIEW")
    params = urllib.parse.urlencode({"function": "OVERVIEW", "symbol": ticker, "apikey": api_key})
    url = f"https://www.alphavantage.co/query?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "StockRadarV2/1.0 local-idle-app",
            "Accept": "application/json,text/plain,*/*",
            "Connection": "close",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw_text = resp.read().decode("utf-8", errors="replace")
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Alpha Vantage returned non-JSON response: {raw_text[:160]}") from exc

    if isinstance(data, dict) and (data.get("Note") or data.get("Information") or data.get("Error Message")):
        return data, False, alpha_vantage_quota_status()

    _write_json_file(cache_path, {
        "ticker": ticker,
        "endpoint": "OVERVIEW",
        "fetchedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "raw": data,
    })
    return data, False, alpha_vantage_quota_status()


def parse_alpha_vantage_overview(ticker: str, raw: Dict[str, Any], current_price: Optional[float] = None) -> Dict[str, Any]:
    ticker = ticker.upper()
    if not raw or not isinstance(raw, dict):
        raise RuntimeError("Alpha Vantage returned empty overview data")
    if raw.get("Note"):
        raise RuntimeError("Alpha Vantage provider limit reached. Try again after the provider resets quota.")
    if raw.get("Information"):
        raise RuntimeError(str(raw.get("Information")))
    if raw.get("Error Message"):
        raise RuntimeError(str(raw.get("Error Message")))
    if not raw.get("Symbol") and len(raw.keys()) <= 2:
        raise RuntimeError("Alpha Vantage returned no overview data for this ticker")

    target = _safe_float(raw.get("AnalystTargetPrice"))
    current = _safe_float(current_price)
    upside = ((target / current) - 1.0) * 100.0 if target is not None and current and current > 0 else None
    rating_keys = [
        "AnalystRatingStrongBuy",
        "AnalystRatingBuy",
        "AnalystRatingHold",
        "AnalystRatingSell",
        "AnalystRatingStrongSell",
    ]
    ratings = {key: _safe_int(raw.get(key)) for key in rating_keys}
    analyst_count = sum(v for v in ratings.values() if v is not None) or None
    rating_score = None
    if analyst_count:
        weights = {
            "AnalystRatingStrongBuy": 2,
            "AnalystRatingBuy": 1,
            "AnalystRatingHold": 0,
            "AnalystRatingSell": -1,
            "AnalystRatingStrongSell": -2,
        }
        rating_score = sum((ratings[k] or 0) * weights[k] for k in rating_keys) / analyst_count

    return {
        "ticker": raw.get("Symbol") or ticker,
        "name": raw.get("Name"),
        "source": "Alpha Vantage OVERVIEW",
        "fetchedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "analyst": {
            "targetMeanPrice": target,
            "targetUpsidePct": upside,
            "targetAnalystCount": analyst_count,
            "ratings": ratings,
            "ratingScore": rating_score,
            "status": "Loaded" if target is not None or analyst_count else "No analyst target fields in OVERVIEW response",
        },
        "overview": {
            "sector": raw.get("Sector"),
            "industry": raw.get("Industry"),
            "latestQuarter": raw.get("LatestQuarter"),
            "marketCapitalization": _safe_float(raw.get("MarketCapitalization")),
            "epsTtm": _safe_float(raw.get("EPS")),
            "revenueTtm": _safe_float(raw.get("RevenueTTM")),
            "profitMargin": _safe_float(raw.get("ProfitMargin")),
            "returnOnEquityTtm": _safe_float(raw.get("ReturnOnEquityTTM")),
            "peRatio": _safe_float(raw.get("PERatio")),
            "pegRatio": _safe_float(raw.get("PEGRatio")),
            "beta": _safe_float(raw.get("Beta")),
            "fiftyTwoWeekHigh": _safe_float(raw.get("52WeekHigh")),
            "fiftyTwoWeekLow": _safe_float(raw.get("52WeekLow")),
        },
    }


def build_alpha_vantage_consensus_payload(ticker: str, current_price: Optional[float] = None, api_key: Optional[str] = None) -> Dict[str, Any]:
    try:
        raw, cached, quota = _fetch_alpha_vantage_overview(ticker, api_key=api_key)
        parsed = parse_alpha_vantage_overview(ticker, raw, current_price=current_price)
        parsed.update({"ok": True, "cached": cached, "quota": quota})
        return parsed
    except RuntimeError as exc:
        msg = str(exc)
        if msg == "ALPHA_VANTAGE_DAILY_LIMIT_REACHED":
            return {
                "ok": False,
                "errorCode": "DAILY_LIMIT_REACHED",
                "error": "Daily Alpha Vantage limit reached.",
                "quota": alpha_vantage_quota_status(),
            }
        if "Missing Alpha Vantage API key" in msg:
            return {
                "ok": False,
                "errorCode": "MISSING_API_KEY",
                "error": "Missing Alpha Vantage API key. Paste and save the key in the Analyst Consensus panel first.",
                "quota": alpha_vantage_quota_status(),
            }
        return {
            "ok": False,
            "errorCode": "ALPHA_VANTAGE_ERROR",
            "error": msg,
            "quota": alpha_vantage_quota_status(),
        }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, fmt: str, *args: Any) -> None:
        message = fmt % args
        if HTTP_VERBOSE_LOG or any(code in message for code in (' 400 ', ' 401 ', ' 403 ', ' 404 ', ' 429 ', ' 500 ', ' 502 ')):
            sys.stdout.write("%s - %s\n" % (self.log_date_time_string(), message))

    def _client_disconnected(self, exc: BaseException) -> None:
        # Browsers often abort an in-flight /api/scan request when the page is
        # refreshed, a tab is closed, or a new scan starts. Python's built-in
        # HTTP server reports that as BrokenPipeError / ConnectionResetError.
        # It is not a data or SEC parsing failure, so keep IDLE clean.
        sys.stdout.write(f"{self.log_date_time_string()} - client disconnected while sending response; ignored.\n")

    def send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as exc:
            self._client_disconnected(exc)

    def end_headers(self) -> None:
        # IDLE/local mode: avoid browser 304 caching while iterating on app.js/styles.css.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def copyfile(self, source: Any, outputfile: Any) -> None:
        # Same protection for static files such as app.js/index.html.
        try:
            shutil.copyfileobj(source, outputfile)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as exc:
            self._client_disconnected(exc)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw_body = self.rfile.read(length).decode("utf-8", errors="replace") if length else "{}"
            try:
                payload_in = json.loads(raw_body or "{}")
            except json.JSONDecodeError:
                payload_in = {}
            if path == "/api/analyst-consensus":
                symbol = str(payload_in.get("symbol") or payload_in.get("ticker") or "").strip().upper()
                current_price = _safe_float(payload_in.get("currentPrice") or payload_in.get("price"))
                api_key = str(payload_in.get("apiKey") or payload_in.get("key") or "").strip()
                payload = build_alpha_vantage_consensus_payload(symbol, current_price=current_price, api_key=api_key)
                status_code = 429 if payload.get("errorCode") == "DAILY_LIMIT_REACHED" else 200
                self.send_json(status_code, payload)
                return
            if path == "/api/alpha-vantage/key":
                api_key = str(payload_in.get("apiKey") or payload_in.get("key") or "").strip()
                self.send_json(200, save_alpha_vantage_key(api_key))
                return
            self.send_json(404, {"ok": False, "error": "Unknown POST route"})
        except Exception as exc:  # noqa: BLE001
            self.send_json(400, {"ok": False, "error": str(exc)})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        try:
            if path == "/api/quote":
                symbol = (params.get("symbol") or params.get("ticker") or [""])[0]
                range_ = (params.get("range") or ["1y"])[0]
                interval = (params.get("interval") or ["1d"])[0]
                include_fundamentals = (params.get("includeFundamentals") or ["1"])[0].lower() not in {"0", "false", "no"}
                payload = build_analysis(symbol, range_, interval, include_fundamentals=include_fundamentals)
                self.send_json(200, payload)
                return

            if path == "/api/scan":
                raw_symbols = (params.get("symbols") or [",".join(read_watchlist_file())])[0]
                symbols = [s.strip() for s in raw_symbols.replace("\n", ",").split(",")]
                range_ = (params.get("range") or ["1y"])[0]
                interval = (params.get("interval") or ["1d"])[0]
                include_fundamentals = (params.get("includeFundamentals") or ["0"])[0].lower() not in {"0", "false", "no"}
                self.send_json(200, scan_symbols(symbols, range_, interval, include_fundamentals=include_fundamentals))
                return

            if path == "/api/analyst-consensus":
                symbol = (params.get("symbol") or params.get("ticker") or [""])[0].strip().upper()
                current_price = _safe_float((params.get("currentPrice") or params.get("price") or [None])[0])
                payload = build_alpha_vantage_consensus_payload(symbol, current_price=current_price)
                status_code = 429 if payload.get("errorCode") == "DAILY_LIMIT_REACHED" else 200
                self.send_json(status_code, payload)
                return

            if path == "/api/alpha-vantage/key-status":
                self.send_json(200, alpha_vantage_key_status())
                return

            if path == "/api/alpha-vantage/quota":
                self.send_json(200, {"ok": True, "quota": alpha_vantage_quota_status()})
                return

            if path == "/api/health":
                self.send_json(200, {"ok": True, "app": "Stock Timing Radar v8.0 Stability", "fundamentalMode": "SEC EDGAR V2.7 first + upgraded guidance engine + public-safe BYOK Alpha Vantage", "priceTargetMode": "V2.7 Alpha Vantage OVERVIEW BYOK manual loader; browser localStorage key; one click = max one API call; same-day cache is free; excluded from SEC table", "priceTargetSources": ["Alpha Vantage OVERVIEW"], "secV1ImportError": SEC_V1_IMPORT_ERROR, "alphaVantageQuota": alpha_vantage_quota_status()})
                return

            # Compatibility fix for the original static GitHub Pages UI.
            # In local Python mode, /data/scanner.json is generated on demand
            # instead of being a pre-built file under static/data/.
            if path == "/data/scanner.json":
                raw_symbols = (params.get("symbols") or [",".join(read_watchlist_file())])[0]
                symbols = [s.strip() for s in raw_symbols.replace("\n", ",").split(",")]
                range_ = (params.get("range") or ["1y"])[0]
                interval = (params.get("interval") or ["1d"])[0]
                self.send_json(200, scan_symbols(symbols, range_, interval, include_fundamentals=False))
                return

            return super().do_GET()
        except urllib.error.HTTPError as exc:
            self.send_json(exc.code, {"error": f"Market data HTTP error: {exc.code} {exc.reason}"})
        except urllib.error.URLError as exc:
            self.send_json(502, {"error": f"Could not reach market data source: {exc.reason}"})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as exc:
            self._client_disconnected(exc)
        except Exception as exc:  # noqa: BLE001
            self.send_json(400, {"error": str(exc)})


def main() -> None:
    os.chdir(STATIC_DIR)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Stock Timing Radar running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
