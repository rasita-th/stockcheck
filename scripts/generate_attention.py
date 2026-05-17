#!/usr/bin/env python3
"""Generate Today's Attention List for Stock Timing Radar.

This script is intentionally quiet and conservative: it outputs only stocks with
concrete triggers from the user's portfolio config. It uses only stdlib urllib so
it can run in GitHub Actions without extra dependencies.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SITE_DATA_DIR = ROOT / "site" / "data"
STATIC_DATA_DIR = ROOT / "static" / "data"
PORTFOLIO_PATHS = [DATA_DIR / "portfolio.json", SITE_DATA_DIR / "portfolio.json"]
EARNINGS_CALENDAR_PATHS = [DATA_DIR / "earnings_calendar.json", SITE_DATA_DIR / "earnings_calendar.json", STATIC_DATA_DIR / "earnings_calendar.json"]
OUT_PATHS = [DATA_DIR / "attention_today.json", SITE_DATA_DIR / "attention_today.json", STATIC_DATA_DIR / "attention_today.json"]
PREVIOUS_PATHS = [SITE_DATA_DIR / "attention_today.json", DATA_DIR / "attention_today.json"]
TECHNICAL_PATHS = [SITE_DATA_DIR / "technical.json", DATA_DIR / "technical.json", STATIC_DATA_DIR / "technical.json", SITE_DATA_DIR / "scanner.json", STATIC_DATA_DIR / "scanner.json"]
IMPORTANT_FORMS = {"8-K", "10-Q", "10-K", "S-3", "424B", "4", "DEF 14A"}
USER_AGENT = os.environ.get("SEC_USER_AGENT") or "Stock Timing Radar attention script contact@example.com"
OFFLINE_MODE = os.environ.get("STOCKCHECK_ATTENTION_OFFLINE", "").lower() in {"1", "true", "yes"}


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


def parse_previous_date() -> date:
    path = first_existing(PREVIOUS_PATHS)
    if not path:
        return (now_ict() - timedelta(days=1)).date()
    prev = load_json(path, {}) or {}
    raw = prev.get("updated_at") or prev.get("generated_at")
    if not raw:
        return (now_ict() - timedelta(days=1)).date()
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
    except Exception:
        return (now_ict() - timedelta(days=1)).date()


def http_json(url: str, timeout: int = 8, headers: dict[str, str] | None = None) -> dict[str, Any] | None:
    if OFFLINE_MODE:
        return None
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"::warning::GET failed {url}: {exc}")
        return None


def to_float(v: Any) -> float | None:
    try:
        n = float(v)
        if math.isfinite(n):
            return n
    except Exception:
        return None
    return None


def load_technical_rows() -> dict[str, dict[str, Any]]:
    """Load scanner/technical JSON and index by ticker.

    Attention List must never drift away from the Scanner.  GitHub Pages is a
    static app, so the safest source for price/change is the exact JSON used by
    the scanner table.  Yahoo is only a fallback when a ticker is absent from
    that static file.
    """
    path = first_existing(TECHNICAL_PATHS)
    if not path:
        return {}
    data = load_json(path, {}) or {}
    rows = data.get("rows") or data.get("items") or data.get("data") or []
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
        if ticker:
            out[ticker] = row
    return out


def price_from_technical(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    price = to_float(row.get("price")) or to_float(row.get("regularMarketPrice")) or to_float(row.get("lastPrice"))
    chg = to_float(row.get("dayPct"))
    if chg is None:
        chg = to_float(row.get("day_change_pct"))
    if chg is None:
        chg = to_float(row.get("changePercent"))
    if price is None and chg is None:
        return None
    return {
        "price": price,
        "day_change_pct": chg,
        "previous_close": None,
        "source": "technical.json",
        "technical_row": row,
    }


def fetch_price(ticker: str, technical_row: dict[str, Any] | None = None) -> dict[str, Any]:
    synced = price_from_technical(technical_row)
    if synced:
        return synced

    safe = urllib.parse.quote(ticker)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{safe}?range=5d&interval=1d"
    data = http_json(url) or {}
    result = (((data.get("chart") or {}).get("result") or []) or [{}])[0]
    meta = result.get("meta") or {}
    quote = (((result.get("indicators") or {}).get("quote") or []) or [{}])[0]
    closes = [to_float(x) for x in (quote.get("close") or [])]
    closes = [x for x in closes if x is not None]
    price = to_float(meta.get("regularMarketPrice")) or (closes[-1] if closes else None)
    prev = to_float(meta.get("chartPreviousClose")) or (closes[-2] if len(closes) >= 2 else None)
    chg = None
    if price is not None and prev not in (None, 0):
        chg = ((price - prev) / prev) * 100
    return {"price": price, "day_change_pct": chg, "previous_close": prev, "source": "yahoo_fallback"}


def sec_filing_url(cik: str, accession: str, primary_document: str = "") -> str:
    cik_int = str(int(str(cik))) if str(cik).strip().isdigit() else str(cik).lstrip("0")
    accession_clean = accession.replace("-", "")
    if primary_document:
        return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_clean}/{primary_document}"
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_clean}/"


def fetch_latest_filing(cik: str | None, last_checked: date) -> dict[str, Any] | None:
    if not cik:
        return None
    cik_padded = str(cik).zfill(10)
    data = http_json(f"https://data.sec.gov/submissions/CIK{cik_padded}.json")
    if not data:
        return None
    recent = (data.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    dates = recent.get("filingDate") or []
    accessions = recent.get("accessionNumber") or []
    docs = recent.get("primaryDocument") or []
    for i, form in enumerate(forms[:40]):
        if form not in IMPORTANT_FORMS:
            continue
        try:
            filing_date = date.fromisoformat(str(dates[i]))
        except Exception:
            continue
        if filing_date <= last_checked:
            continue
        acc = str(accessions[i]) if i < len(accessions) else ""
        doc = str(docs[i]) if i < len(docs) else ""
        return {"form": form, "date": str(filing_date), "url": sec_filing_url(cik_padded, acc, doc)}
    return None


def load_manual_earnings_calendar() -> dict[str, dict[str, Any]]:
    """Load optional earnings overrides.

    Free earnings APIs are spotty.  Today's Attention should not silently miss
    a known portfolio event, so manual overrides are treated as first-class data
    and Yahoo is only a fallback.
    """
    path = first_existing(EARNINGS_CALENDAR_PATHS)
    raw = load_json(path, []) if path else []
    if isinstance(raw, dict):
        raw = raw.get("items") or raw.get("earnings") or []
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or item.get("symbol") or "").strip().upper()
        date_raw = item.get("earnings_date") or item.get("date")
        if not ticker or not date_raw:
            continue
        try:
            d = date.fromisoformat(str(date_raw)[:10])
        except Exception:
            continue
        out[ticker] = {**item, "ticker": ticker, "earnings_date": d, "source": item.get("source") or "manual"}
    return out


def fetch_earnings_date(ticker: str, manual_calendar: dict[str, dict[str, Any]] | None = None) -> tuple[date | None, str | None]:
    manual = (manual_calendar or {}).get(ticker.upper())
    if manual:
        return manual.get("earnings_date"), str(manual.get("source") or "manual")

    # Yahoo quoteSummary sometimes rate-limits this endpoint. Fail silently.
    safe = urllib.parse.quote(ticker)
    url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{safe}?modules=calendarEvents"
    data = http_json(url, timeout=12)
    try:
        result = data["quoteSummary"]["result"][0]
        earnings = result.get("calendarEvents", {}).get("earnings", {})
        raw = earnings.get("earningsDate") or []
        if not raw:
            return None, None
        ts = raw[0].get("raw")
        if ts:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc).date(), "yahoo"
    except Exception:
        return None, None
    return None, None


def add_trigger(triggers: list[dict[str, Any]], typ: str, signal: str, **extra: Any) -> None:
    triggers.append({"type": typ, "signal": signal, **extra})


TRIGGER_SORT_PRIORITY = {
    "sec_filing": 1,
    "earnings_today": 2,
    "earnings_soon": 3,
    "price_move": 4,
    "buy_zone": 5,
    "trim_zone": 5,
}


def best_primary_trigger(triggers: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(triggers, key=lambda t: TRIGGER_SORT_PRIORITY.get(str(t.get("type")), 99))[0]


def calc_severity(triggers: list[dict[str, Any]], day_change_pct: float | None) -> str:
    types = {t.get("type") for t in triggers}
    filing_type = next((t.get("filing_type") for t in triggers if t.get("filing_type")), None)
    days_to_earnings = next((t.get("days_to_earnings") for t in triggers if t.get("days_to_earnings") is not None), None)

    # Event-driven items come first in Today's Attention because they can change
    # the thesis.  Technical/price triggers are important, but mostly context.
    if filing_type in {"8-K", "10-Q", "10-K", "S-3", "424B"}:
        return "high"
    if days_to_earnings is not None and days_to_earnings <= 1:
        return "high"
    if day_change_pct is not None and abs(day_change_pct) > 8:
        return "high"
    if days_to_earnings is not None and days_to_earnings <= 7:
        return "medium"
    if filing_type in {"4", "DEF 14A"}:
        return "medium"
    if day_change_pct is not None and abs(day_change_pct) >= 5:
        return "medium"
    if "buy_zone" in types or "trim_zone" in types:
        return "medium"
    return "low"


def trigger_priority(item: dict[str, Any]) -> tuple[int, int, str]:
    sev = {"high": 0, "medium": 1, "low": 2}.get(item.get("severity"), 3)
    trig = item.get("primary_trigger")
    pr = TRIGGER_SORT_PRIORITY.get(trig, 9)
    return (sev, pr, str(item.get("ticker", "")))


def exchange_for_actions(exchange: str | None, ticker: str) -> str:
    exch = (exchange or "NASDAQ").upper()
    if ticker.endswith(".BK"):
        return "SET"
    if exch in {"NYSE", "NASDAQ", "AMEX", "SET"}:
        return exch
    return "NASDAQ"


def build_actions(stock: dict[str, Any], ticker: str, triggers: list[dict[str, Any]]) -> dict[str, str]:
    exchange = exchange_for_actions(stock.get("exchange"), ticker)
    actions = {
        "tradingview": f"https://www.tradingview.com/symbols/{exchange}-{ticker.replace('.', '')}/",
        "yahoo": f"https://finance.yahoo.com/quote/{ticker}",
        "raw_data": "data/technical.json",
    }
    if stock.get("company_ir_url"):
        actions["company_ir"] = stock["company_ir_url"]
    filing = next((t for t in triggers if t.get("type") == "sec_filing"), None)
    if filing:
        if filing.get("filing_url"):
            actions["sec_filing"] = filing["filing_url"]
        actions["sec_search"] = f"https://www.sec.gov/edgar/search/#/q={urllib.parse.quote(ticker)}"
    return actions


def generate() -> dict[str, Any]:
    portfolio_path = first_existing(PORTFOLIO_PATHS)
    if not portfolio_path:
        raise SystemExit("Missing data/portfolio.json")
    portfolio = load_json(portfolio_path, [])
    if not isinstance(portfolio, list):
        raise SystemExit("portfolio.json must be a list")
    technical_map = load_technical_rows()
    manual_earnings = load_manual_earnings_calendar()
    last_checked = parse_previous_date()
    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for stock in portfolio:
        ticker = str(stock.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        triggers: list[dict[str, Any]] = []
        technical_row = technical_map.get(ticker)
        price_data = fetch_price(ticker, technical_row)
        price = to_float(price_data.get("price"))
        chg = to_float(price_data.get("day_change_pct"))
        if chg is not None and abs(chg) >= 5.0:
            # Keep the sign exactly as the scanner sees it.  A -5% day is a
            # price-drop trigger, not a positive price-move.
            add_trigger(triggers, "price_move", f"Price {chg:+.1f}%")

        filing = fetch_latest_filing(stock.get("sec_cik"), last_checked)
        if filing:
            add_trigger(triggers, "sec_filing", f"New {filing['form']} filing", filing_type=filing["form"], filing_date=filing["date"], filing_url=filing.get("url", ""))

        earnings, earnings_source = fetch_earnings_date(ticker, manual_earnings)
        if earnings:
            days = (earnings - now_ict().date()).days
            if 0 <= days <= 7:
                typ = "earnings_today" if days == 0 else "earnings_soon"
                label = "Earnings today" if days == 0 else f"Earnings in {days} day{'s' if days != 1 else ''}"
                add_trigger(triggers, typ, label, earnings_date=str(earnings), days_to_earnings=days, earnings_source=earnings_source)

        buy_zone = to_float(stock.get("buy_zone"))
        trim_zone = to_float(stock.get("trim_zone"))
        buy_zone_distance_pct = None
        trim_zone_distance_pct = None

        # Zones are valid only when price is near the configured plan.  A stale
        # zone should not shout forever in Today's Attention.
        if price is not None and buy_zone not in (None, 0):
            buy_zone_distance_pct = ((price - buy_zone) / buy_zone) * 100
            if -10 <= buy_zone_distance_pct <= 5:
                if price <= buy_zone:
                    signal = f"Reached buy zone ${buy_zone:g} · {buy_zone_distance_pct:+.1f}% from zone"
                else:
                    signal = f"Near buy zone ${buy_zone:g} · {buy_zone_distance_pct:+.1f}% from zone"
                add_trigger(triggers, "buy_zone", signal, buy_zone_distance_pct=buy_zone_distance_pct)

        if price is not None and trim_zone not in (None, 0):
            trim_zone_distance_pct = ((price - trim_zone) / trim_zone) * 100
            if -3 <= trim_zone_distance_pct <= 10:
                if price >= trim_zone:
                    signal = f"Reached trim zone ${trim_zone:g} · {trim_zone_distance_pct:+.1f}% from zone"
                else:
                    signal = f"Near trim zone ${trim_zone:g} · {trim_zone_distance_pct:+.1f}% from zone"
                add_trigger(triggers, "trim_zone", signal, trim_zone_distance_pct=trim_zone_distance_pct)

        if not triggers:
            continue
        primary = best_primary_trigger(triggers)
        item = {
            "ticker": ticker,
            "name": stock.get("name") or ticker,
            "role": stock.get("role") or "Watchlist",
            "primary_trigger": primary["type"],
            "signals": [t["signal"] for t in triggers],
            "severity": calc_severity(triggers, chg),
            "price": price,
            "day_change_pct": chg,
            "earnings_date": next((t.get("earnings_date") for t in triggers if t.get("earnings_date")), None),
            "filing_type": next((t.get("filing_type") for t in triggers if t.get("filing_type")), None),
            "filing_date": next((t.get("filing_date") for t in triggers if t.get("filing_date")), None),
            "buy_zone": buy_zone,
            "trim_zone": trim_zone,
            "buy_zone_distance_pct": buy_zone_distance_pct,
            "trim_zone_distance_pct": trim_zone_distance_pct,
            "earnings_source": next((t.get("earnings_source") for t in triggers if t.get("earnings_source")), None),
            "actions": build_actions(stock, ticker, triggers),
            "price_source": price_data.get("source") or "unknown",
        }
        # Drop nulls for cleaner JSON.
        items.append({k: v for k, v in item.items() if v is not None})
        time.sleep(0.12)  # gentle SEC/Yahoo pacing

    items.sort(key=trigger_priority)
    output = {
        "updated_at": now_ict().replace(microsecond=0).isoformat(),
        "market": "US",
        "total_monitored": len(portfolio),
        "items": items,
        "errors": errors,
        "data_quality": {
            "price_source": "technical.json first, Yahoo fallback",
            "earnings_source": "manual earnings_calendar.json first, Yahoo fallback",
            "zone_logic": "buy_zone triggers only -10% to +5%; trim_zone triggers only -3% to +10%; stale zones are suppressed",
            "scanner_synced": bool(technical_map),
            "technical_rows": len(technical_map),
            "manual_earnings_rows": len(manual_earnings),
        },
    }
    return output


def main() -> None:
    data = generate()
    for path in OUT_PATHS:
        save_json(path, data)
    print(f"Generated attention list: {len(data['items'])} / {data['total_monitored']} monitored")


if __name__ == "__main__":
    main()
