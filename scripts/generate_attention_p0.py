#!/usr/bin/env python3
"""Build the free, event-first Today Attention List.

P0 design goals:
- use SEC EDGAR, curated primary-source earnings entries and the scanner's own data
- never depend on Finnhub or another paid/licensed data feed
- preserve every unseen SEC accession, including multiple filings on the same day
- normalize events before ranking and grouping them into a short attention list
- report partial source coverage instead of claiming a false all-clear
"""
from __future__ import annotations

import json
import math
import os
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
GENERATED_DIR = DATA_DIR / "generated"
SITE_DATA_DIR = ROOT / "site" / "data"
STATIC_DATA_DIR = ROOT / "static" / "data"
STATE_DIR = DATA_DIR / "source_state"

PORTFOLIO_PATHS = [DATA_DIR / "portfolio.json", SITE_DATA_DIR / "portfolio.json", STATIC_DATA_DIR / "portfolio.json"]
EARNINGS_PATHS = [DATA_DIR / "earnings_calendar.json", SITE_DATA_DIR / "earnings_calendar.json", STATIC_DATA_DIR / "earnings_calendar.json"]
TECHNICAL_PATHS = [SITE_DATA_DIR / "technical.json", GENERATED_DIR / "technical.json", STATIC_DATA_DIR / "technical.json"]
ATTENTION_OUT_PATHS = [DATA_DIR / "attention_today.json", GENERATED_DIR / "attention_today.json", SITE_DATA_DIR / "attention_today.json", STATIC_DATA_DIR / "attention_today.json"]
EVENT_OUT_PATHS = [DATA_DIR / "events.json", GENERATED_DIR / "events.json", SITE_DATA_DIR / "events.json", STATIC_DATA_DIR / "events.json"]
SEC_STATE_PATH = STATE_DIR / "sec.json"

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
USER_AGENT = os.environ.get("SEC_USER_AGENT", "Stock Timing Radar contact@users.noreply.github.com").strip()
OFFLINE_MODE = os.environ.get("STOCKCHECK_ATTENTION_OFFLINE", "").lower() in {"1", "true", "yes"}
MAX_ITEMS = max(1, int(os.environ.get("ATTENTION_MAX_ITEMS", "7")))
SEC_BOOTSTRAP_DAYS = max(0, int(os.environ.get("SEC_BOOTSTRAP_DAYS", "1")))

IMPORTANT_FORMS = {
    "8-K", "8-K/A", "10-Q", "10-Q/A", "10-K", "10-K/A", "20-F", "20-F/A", "6-K", "6-K/A",
    "S-1", "S-1/A", "S-3", "S-3/A", "424B1", "424B2", "424B3", "424B4", "424B5", "424B7",
    "4", "4/A", "SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A", "13D", "13D/A", "13G", "13G/A",
    "DEF 14A", "PRE 14A", "NT 10-Q", "NT 10-K", "SC TO-I", "SC TO-T", "SC TO-C",
}
RISK_SUBTYPES = {"capital_raise", "late_filing", "auditor_change", "delisting_risk", "debt_obligation"}


def now_utc() -> datetime:
    return datetime.now(UTC)


def now_et() -> datetime:
    return datetime.now(ET)


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def first_existing(paths: Iterable[Path]) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def to_float(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except Exception:
        return None


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def parse_datetime(value: Any, fallback_date: date | None = None) -> datetime | None:
    if value:
        raw = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=ET)
        except Exception:
            pass
    if fallback_date:
        return datetime.combine(fallback_date, datetime.min.time(), tzinfo=ET)
    return None


def http_json(url: str, timeout: int = 18) -> dict[str, Any] | None:
    if OFFLINE_MODE:
        return None
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"::warning::GET failed {url}: {exc}")
        return None


def load_portfolio() -> list[dict[str, Any]]:
    path = first_existing(PORTFOLIO_PATHS)
    raw = load_json(path, []) if path else []
    if not isinstance(raw, list):
        raise SystemExit("portfolio.json must contain a list")
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in raw:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        output.append({**row, "ticker": ticker, "name": row.get("name") or ticker, "portfolio_status": str(row.get("portfolio_status") or "holding").lower()})
    return output


def load_technical_rows() -> dict[str, dict[str, Any]]:
    path = first_existing(TECHNICAL_PATHS)
    raw = load_json(path, {}) if path else {}
    rows = raw.get("rows") if isinstance(raw, dict) else []
    output: dict[str, dict[str, Any]] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
        if ticker:
            output[ticker] = row
    return output


def price_context(row: dict[str, Any] | None) -> dict[str, Any]:
    row = row or {}
    price = next((to_float(row.get(key)) for key in ("price", "close", "regularMarketPrice", "lastPrice") if to_float(row.get(key)) is not None), None)
    day_pct = next((to_float(row.get(key)) for key in ("dayPct", "day_change_pct", "changePercent") if to_float(row.get(key)) is not None), None)
    previous_close = next((to_float(row.get(key)) for key in ("previousClose", "previous_close", "chartPreviousClose") if to_float(row.get(key)) is not None), None)
    if previous_close is None and price is not None and day_pct is not None and day_pct > -100:
        previous_close = price / (1 + day_pct / 100)
    relative_volume = next((to_float(row.get(key)) for key in ("relativeVolume", "relVolume", "volumeRatio", "vol20") if to_float(row.get(key)) is not None), None)
    return {"price": price, "day_change_pct": day_pct, "previous_close": previous_close, "relative_volume": relative_volume, "source": "technical.json" if row else "unavailable"}


def load_earnings_calendar() -> list[dict[str, Any]]:
    path = first_existing(EARNINGS_PATHS)
    raw = load_json(path, []) if path else []
    if isinstance(raw, dict):
        raw = raw.get("items") or raw.get("earnings") or []
    output: list[dict[str, Any]] = []
    for row in raw if isinstance(raw, list) else []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
        earnings_date = parse_date(row.get("earnings_date") or row.get("date"))
        if not ticker or not earnings_date:
            continue
        status = str(row.get("status") or "estimated").lower()
        if status not in {"confirmed", "estimated", "reported", "call_pending"}:
            status = "estimated"
        source_type = str(row.get("source_type") or row.get("source") or "curated").lower()
        output.append({**row, "ticker": ticker, "earnings_date": earnings_date, "status": status, "source_type": source_type})
    return output


def fetch_sec_ticker_map() -> tuple[dict[str, dict[str, Any]], str]:
    data = http_json("https://www.sec.gov/files/company_tickers.json")
    if not data:
        return {}, "error"
    output: dict[str, dict[str, Any]] = {}
    for row in data.values():
        if isinstance(row, dict) and row.get("ticker"):
            output[str(row["ticker"]).upper()] = row
    return output, "ok"


def sec_url(cik: str, accession: str, primary_document: str = "") -> str:
    cik_int = str(int(str(cik)))
    base = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession.replace('-', '')}/"
    return base + primary_document if primary_document else base


def classify_sec_filing(form: str, items: str = "") -> dict[str, str]:
    form = str(form or "").strip().upper()
    item_set = {part.strip() for part in str(items or "").replace(";", ",").split(",") if part.strip()}
    if form.startswith(("S-1", "S-3", "424B")):
        return {"event_type": "sec_filing", "subtype": "capital_raise", "headline": f"{form} capital-markets filing", "summary": "A securities registration or prospectus filing may create capital-raise or dilution risk."}
    if form.startswith("NT 10-"):
        return {"event_type": "sec_filing", "subtype": "late_filing", "headline": f"{form} late-filing notice", "summary": "The company notified the SEC that its periodic report will be filed late."}
    if form in {"10-Q", "10-Q/A", "10-K", "10-K/A", "20-F", "20-F/A"}:
        return {"event_type": "sec_filing", "subtype": "periodic_report", "headline": f"New {form} filed", "summary": "A new periodic financial report is available for review."}
    if form.startswith("4"):
        return {"event_type": "sec_filing", "subtype": "insider_activity", "headline": "New Form 4 insider filing", "summary": "An insider transaction was reported; transaction context still requires document review."}
    if "13D" in form:
        return {"event_type": "sec_filing", "subtype": "ownership_change", "headline": f"New {form} ownership filing", "summary": "A beneficial owner disclosed or amended a potentially influential ownership position."}
    if "13G" in form:
        return {"event_type": "sec_filing", "subtype": "ownership_change", "headline": f"New {form} ownership filing", "summary": "A beneficial ownership position was disclosed or amended."}
    if form in {"DEF 14A", "PRE 14A"}:
        return {"event_type": "sec_filing", "subtype": "proxy", "headline": f"New {form} proxy filing", "summary": "Proxy materials may contain governance, compensation or shareholder-vote items."}
    if form.startswith("SC TO"):
        return {"event_type": "sec_filing", "subtype": "tender_offer", "headline": f"New {form} tender-offer filing", "summary": "A tender-offer related filing requires review for transaction terms and timing."}
    if form.startswith("8-K"):
        if any(item.startswith("2.02") for item in item_set):
            return {"event_type": "earnings", "subtype": "earnings_reported", "headline": "Financial results reported in an 8-K", "summary": "The company furnished or filed current financial results."}
        if any(item.startswith("4.01") for item in item_set):
            return {"event_type": "sec_filing", "subtype": "auditor_change", "headline": "Auditor change disclosed in an 8-K", "summary": "A change or disagreement involving the independent accountant was disclosed."}
        if any(item.startswith("3.01") for item in item_set):
            return {"event_type": "sec_filing", "subtype": "delisting_risk", "headline": "Listing-compliance event disclosed", "summary": "The company disclosed a notice or event related to exchange listing compliance."}
        if any(item.startswith("2.03") for item in item_set):
            return {"event_type": "sec_filing", "subtype": "debt_obligation", "headline": "New material debt obligation disclosed", "summary": "The company disclosed a material financing or debt obligation."}
        if any(item.startswith("5.02") for item in item_set):
            return {"event_type": "corporate_event", "subtype": "management_change", "headline": "Management or board change disclosed", "summary": "A director or executive appointment, departure or compensation event was disclosed."}
        if any(item.startswith("2.01") for item in item_set):
            return {"event_type": "corporate_event", "subtype": "transaction", "headline": "Acquisition or disposition disclosed", "summary": "The company disclosed completion of an acquisition or disposition of assets."}
        if any(item.startswith("1.01") for item in item_set):
            return {"event_type": "corporate_event", "subtype": "material_agreement", "headline": "Material agreement disclosed", "summary": "The company entered into a material definitive agreement."}
        return {"event_type": "sec_filing", "subtype": "current_report", "headline": "New 8-K current report", "summary": "A current report was filed and requires item-level review."}
    if form.startswith("6-K"):
        return {"event_type": "sec_filing", "subtype": "foreign_issuer_report", "headline": "New 6-K foreign-issuer report", "summary": "A foreign private issuer furnished a new current report."}
    return {"event_type": "sec_filing", "subtype": "filing", "headline": f"New {form} filing", "summary": "A new SEC filing is available for review."}


def sec_event_materiality(subtype: str) -> str:
    if subtype in {"late_filing", "auditor_change", "delisting_risk"}:
        return "critical"
    if subtype in {"capital_raise", "earnings_reported", "debt_obligation", "transaction", "material_agreement", "periodic_report"}:
        return "high"
    if subtype in {"management_change", "ownership_change", "tender_offer"}:
        return "medium"
    return "low"


def fetch_sec_events(stock: dict[str, Any], ticker_map: dict[str, dict[str, Any]], old_state: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], str, str | None]:
    ticker = stock["ticker"]
    mapping = ticker_map.get(ticker, {})
    cik = str(stock.get("sec_cik") or mapping.get("cik_str") or "").strip()
    if not cik.isdigit():
        return [], old_state, "partial", "CIK unavailable"
    data = http_json(f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json")
    if not data:
        return [], old_state, "error", "SEC submissions unavailable"
    recent = (data.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    accessions = recent.get("accessionNumber") or []
    filing_dates = recent.get("filingDate") or []
    accepted_values = recent.get("acceptanceDateTime") or []
    docs = recent.get("primaryDocument") or []
    items_values = recent.get("items") or []
    report_dates = recent.get("reportDate") or []
    seen = set(str(value) for value in old_state.get("seen_accessions", []) if value)
    bootstrapping = not seen
    cutoff = now_et().date() - timedelta(days=SEC_BOOTSTRAP_DAYS)
    events: list[dict[str, Any]] = []
    all_important: list[str] = []
    for index, raw_form in enumerate(forms[:120]):
        form = str(raw_form or "").strip().upper()
        if form not in IMPORTANT_FORMS:
            continue
        accession = str(accessions[index]) if index < len(accessions) else ""
        if not accession:
            continue
        all_important.append(accession)
        filing_date = parse_date(filing_dates[index] if index < len(filing_dates) else None)
        unseen = accession not in seen
        if bootstrapping and filing_date and filing_date < cutoff:
            unseen = False
        if not unseen:
            continue
        accepted_at = parse_datetime(accepted_values[index] if index < len(accepted_values) else None, filing_date)
        items = str(items_values[index] if index < len(items_values) else "")
        primary_document = str(docs[index] if index < len(docs) else "")
        classification = classify_sec_filing(form, items)
        subtype = classification["subtype"]
        source_url = sec_url(cik, accession, primary_document)
        events.append({
            "event_id": f"sec:{ticker}:{accession}", "ticker": ticker, "event_type": classification["event_type"], "event_subtype": subtype,
            "headline": classification["headline"], "summary": classification["summary"], "why_today": classification["summary"],
            "materiality": sec_event_materiality(subtype), "urgency": "today",
            "event_time": accepted_at.isoformat() if accepted_at else (str(filing_date) if filing_date else None),
            "detected_at": now_utc().isoformat(), "verification_status": "confirmed",
            "source": {"type": "sec", "quality": "primary", "url": source_url, "published_at": accepted_at.isoformat() if accepted_at else (str(filing_date) if filing_date else None), "form": form, "items": items, "accession_number": accession, "report_date": str(report_dates[index]) if index < len(report_dates) else ""},
        })
    return events, {"cik": cik.zfill(10), "last_successful_check": now_utc().isoformat(), "seen_accessions": all_important[:100]}, "ok", None


def earnings_events(calendar: list[dict[str, Any]], portfolio_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    today = now_et().date()
    output: list[dict[str, Any]] = []
    for row in calendar:
        ticker = row["ticker"]
        if ticker not in portfolio_map:
            continue
        event_date: date = row["earnings_date"]
        days = (event_date - today).days
        status = row["status"]
        if status not in {"reported", "call_pending"} and not (0 <= days <= 7):
            continue
        if status in {"reported", "call_pending"} and not (-1 <= days <= 1):
            continue
        timing = str(row.get("time") or "time_unknown")
        source_type = str(row.get("source_type") or "curated")
        primary = source_type in {"company_ir", "company_press_release", "sec"}
        verification = "confirmed" if status in {"confirmed", "reported", "call_pending"} else "estimated"
        if status == "reported":
            headline, why, subtype, urgency = "Earnings reported", "The company has reported results; review the release, guidance and market reaction.", "earnings_reported", "today"
        elif status == "call_pending":
            headline, why, subtype, urgency = "Earnings call pending", "Results are available but the earnings call or guidance discussion is still pending.", "earnings_call_pending", "today"
        elif days == 0:
            headline, why, subtype, urgency = "Earnings today", f"Earnings are scheduled today ({timing.replace('_', ' ')}).", "earnings_today", "today"
        elif days == 1:
            headline, why, subtype, urgency = "Earnings tomorrow", f"Earnings are scheduled tomorrow ({timing.replace('_', ' ')}).", "earnings_upcoming", "upcoming"
        else:
            headline, why, subtype, urgency = f"Earnings in {days} days", f"Earnings are scheduled within {days} days ({timing.replace('_', ' ')}).", "earnings_upcoming", "upcoming"
        output.append({
            "event_id": f"earnings:{ticker}:{event_date}:{status}", "ticker": ticker, "event_type": "earnings", "event_subtype": subtype,
            "headline": headline, "summary": str(row.get("note") or why), "why_today": why,
            "materiality": "high" if days <= 1 or status in {"reported", "call_pending"} else "medium", "urgency": urgency,
            "event_time": str(event_date), "detected_at": now_utc().isoformat(), "verification_status": verification,
            "source": {"type": source_type, "quality": "primary" if primary else ("estimated" if verification == "estimated" else "curated"), "url": row.get("source_url") or "", "published_at": row.get("confirmed_at") or row.get("updated_at") or ""},
            "earnings_status": status, "earnings_timing": timing, "days_to_event": days,
        })
    return output


def technical_events(stock: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    ticker = stock["ticker"]
    today = now_et().date().isoformat()
    price, previous, day_pct = context.get("price"), context.get("previous_close"), context.get("day_change_pct")
    events: list[dict[str, Any]] = []
    if day_pct is not None and abs(day_pct) >= 5:
        direction = "drop" if day_pct < 0 else "move"
        events.append({"event_id": f"technical:{ticker}:price-{direction}:{today}", "ticker": ticker, "event_type": "technical", "event_subtype": "price_drop" if day_pct < 0 else "price_move", "headline": f"Price {day_pct:+.1f}%", "summary": "A large daily price move requires context from filings, earnings or other company events.", "why_today": f"The stock moved {day_pct:+.1f}% today.", "materiality": "high" if abs(day_pct) >= 8 else "medium", "urgency": "today", "event_time": now_utc().isoformat(), "detected_at": now_utc().isoformat(), "verification_status": "confirmed", "source": {"type": "technical_json", "quality": "internal", "url": "data/technical.json", "published_at": ""}})
    if price is None or previous is None:
        return events
    buy_zone, trim_zone = to_float(stock.get("buy_zone")), to_float(stock.get("trim_zone"))
    if buy_zone not in (None, 0) and previous > buy_zone >= price:
        events.append({"event_id": f"technical:{ticker}:buy-zone-cross:{today}", "ticker": ticker, "event_type": "technical", "event_subtype": "buy_zone_cross", "headline": f"Crossed buy-zone level ${buy_zone:g}", "summary": "Price crossed the configured buy-zone level today; this is context, not a recommendation.", "why_today": f"Price crossed below the configured buy-zone level at ${buy_zone:g}.", "materiality": "low", "urgency": "today", "event_time": now_utc().isoformat(), "detected_at": now_utc().isoformat(), "verification_status": "confirmed", "source": {"type": "technical_json", "quality": "internal", "url": "data/technical.json", "published_at": ""}, "trigger_level": buy_zone})
    if trim_zone not in (None, 0) and previous < trim_zone <= price:
        events.append({"event_id": f"technical:{ticker}:trim-zone-cross:{today}", "ticker": ticker, "event_type": "technical", "event_subtype": "trim_zone_cross", "headline": f"Crossed trim-zone level ${trim_zone:g}", "summary": "Price crossed the configured trim-zone level today; this is context, not a recommendation.", "why_today": f"Price crossed above the configured trim-zone level at ${trim_zone:g}.", "materiality": "low", "urgency": "today", "event_time": now_utc().isoformat(), "detected_at": now_utc().isoformat(), "verification_status": "confirmed", "source": {"type": "technical_json", "quality": "internal", "url": "data/technical.json", "published_at": ""}, "trigger_level": trim_zone})
    return events


def event_score(event: dict[str, Any], stock: dict[str, Any], context: dict[str, Any]) -> int:
    score = {"critical": 65, "high": 45, "medium": 28, "low": 12}.get(str(event.get("materiality")), 8)
    score += {"today": 25, "immediate": 30, "upcoming": 12}.get(str(event.get("urgency")), 5)
    score += 15 if stock.get("portfolio_status") == "holding" else 5
    if event.get("verification_status") == "confirmed" and (event.get("source") or {}).get("quality") == "primary":
        score += 12
    elif event.get("verification_status") == "estimated":
        score -= 8
    subtype = str(event.get("event_subtype"))
    if subtype in RISK_SUBTYPES:
        score += 18
    if subtype == "earnings_today":
        score += 12
    day_pct = to_float(context.get("day_change_pct"))
    if day_pct is not None:
        score += 14 if abs(day_pct) >= 8 else 7 if abs(day_pct) >= 5 else 0
    if subtype in {"buy_zone_cross", "trim_zone_cross"}:
        score -= 12
    return max(0, min(100, score))


def priority_label(event: dict[str, Any], score: int, stock: dict[str, Any], context: dict[str, Any]) -> str:
    subtype = str(event.get("event_subtype"))
    holding = stock.get("portfolio_status") == "holding"
    if subtype in {"late_filing", "auditor_change", "delisting_risk"}:
        return "Critical" if holding else "Risk"
    if subtype == "capital_raise":
        return "Critical" if holding and score >= 85 else "Risk"
    if subtype == "earnings_today":
        return "Critical" if holding else "Action"
    if subtype == "price_drop" and abs(to_float(context.get("day_change_pct")) or 0) >= 8:
        return "Risk"
    if subtype in {"buy_zone_cross", "trim_zone_cross"}:
        return "Watch"
    if score >= 88:
        return "Critical"
    if score >= 72:
        return "Risk"
    if score >= 52:
        return "Action"
    if score >= 32:
        return "Watch"
    return "Developing"


def event_rank(event: dict[str, Any]) -> tuple[int, int, str]:
    order = {"Critical": 0, "Risk": 1, "Action": 2, "Watch": 3, "Developing": 4}
    return order.get(str(event.get("priority")), 9), -int(event.get("priority_score") or 0), str(event.get("event_id"))


def aggregate_items(events: list[dict[str, Any]], portfolio_map: dict[str, dict[str, Any]], contexts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        ticker = str(event.get("ticker") or "").upper()
        stock = portfolio_map.get(ticker, {"ticker": ticker, "portfolio_status": "watchlist"})
        context = contexts.get(ticker, {})
        score = event_score(event, stock, context)
        event["priority_score"] = score
        event["priority"] = priority_label(event, score, stock, context)
        grouped[ticker].append(event)
    items: list[dict[str, Any]] = []
    for ticker, ticker_events in grouped.items():
        ticker_events.sort(key=event_rank)
        primary = ticker_events[0]
        stock, context = portfolio_map[ticker], contexts.get(ticker, {})
        reasons: list[str] = []
        for event in ticker_events[:3]:
            reason = str(event.get("why_today") or event.get("summary") or event.get("headline") or "").strip()
            if reason and reason not in reasons:
                reasons.append(reason)
        source = primary.get("source") or {}
        actions = {"primary_source": source.get("url") or "", "company_ir": stock.get("company_ir_url") or "", "tradingview": f"https://www.tradingview.com/symbols/{str(stock.get('exchange') or 'NASDAQ').upper()}-{ticker.replace('.', '')}/", "raw_data": "data/technical.json"}
        items.append({"ticker": ticker, "name": stock.get("name") or ticker, "portfolio_status": stock.get("portfolio_status") or "watchlist", "role": stock.get("role") or "", "priority": primary["priority"], "priority_score": primary["priority_score"], "why_today": reasons, "event_type": primary.get("event_type"), "event_subtype": primary.get("event_subtype"), "event_time": primary.get("event_time"), "verification_status": primary.get("verification_status"), "source_status": source.get("quality") or "unknown", "source": source, "price": context.get("price"), "day_change_pct": context.get("day_change_pct"), "relative_volume": context.get("relative_volume"), "trigger_level": primary.get("trigger_level"), "events": ticker_events, "actions": {key: value for key, value in actions.items() if value}, "severity": "high" if primary["priority"] in {"Critical", "Risk"} else "medium" if primary["priority"] in {"Action", "Watch"} else "low", "primary_trigger": primary.get("event_subtype") or primary.get("event_type"), "signals": reasons})
    items.sort(key=lambda item: event_rank(item["events"][0]))
    return items[:MAX_ITEMS]


def generate() -> dict[str, Any]:
    portfolio = load_portfolio()
    portfolio_map = {stock["ticker"]: stock for stock in portfolio}
    technical_map = load_technical_rows()
    contexts = {ticker: price_context(technical_map.get(ticker)) for ticker in portfolio_map}
    earnings_calendar = load_earnings_calendar()
    old_sec_state = load_json(SEC_STATE_PATH, {}) or {}
    ticker_map, ticker_map_status = fetch_sec_ticker_map()
    events: list[dict[str, Any]] = []
    next_sec_state: dict[str, Any] = {"schema_version": "1.0", "updated_at": now_utc().isoformat(), "tickers": {}}
    sec_ok = sec_partial = sec_error = 0
    errors: list[dict[str, str]] = []
    for stock in portfolio:
        ticker = stock["ticker"]
        old = (old_sec_state.get("tickers") or {}).get(ticker, {}) if isinstance(old_sec_state, dict) else {}
        sec_events, state, status, error = fetch_sec_events(stock, ticker_map, old)
        events.extend(sec_events)
        next_sec_state["tickers"][ticker] = state
        sec_ok += status == "ok"
        sec_partial += status == "partial"
        sec_error += status == "error"
        if error:
            errors.append({"source": "sec", "ticker": ticker, "message": error})
        events.extend(technical_events(stock, contexts[ticker]))
    events.extend(earnings_events(earnings_calendar, portfolio_map))
    unique = {str(event.get("event_id")): event for event in events if event.get("event_id")}
    normalized_events = sorted(unique.values(), key=lambda event: str(event.get("event_time") or ""), reverse=True)
    items = aggregate_items(normalized_events, portfolio_map, contexts)
    sec_status = "ok" if sec_ok and not sec_error and not sec_partial else "partial" if sec_ok or sec_partial else "error"
    source_health = {
        "sec": {"status": sec_status, "checked": len(portfolio), "ok": sec_ok, "partial": sec_partial, "errors": sec_error, "source": "SEC EDGAR"},
        "earnings": {"status": "partial", "rows": len(earnings_calendar), "source": "Company/SEC-confirmed curated calendar", "note": "IR auto-discovery is scheduled for PR2; unconfirmed dates remain estimated."},
        "market_data": {"status": "ok" if technical_map else "error", "rows": len(technical_map), "source": "technical.json"},
        "news": {"status": "unavailable", "source": "Not enabled in PR1", "note": "Free news discovery and IR monitoring are planned for PR2."},
        "sec_ticker_map": {"status": ticker_map_status, "rows": len(ticker_map), "source": "SEC company_tickers.json"},
    }
    coverage_status = "partial" if any(value.get("status") in {"partial", "unavailable", "error"} for value in source_health.values()) else "complete"
    summary = {label: sum(1 for item in items if item.get("priority") == label) for label in ("Critical", "Risk", "Action", "Watch", "Developing")}
    generated_at = now_utc().replace(microsecond=0).isoformat()
    output = {"schema_version": "2.0-p0", "updated_at": generated_at, "market_timezone": "America/New_York", "display_timezone": "Asia/Bangkok", "stale_after_minutes": 90, "total_monitored": len(portfolio), "total_events": len(normalized_events), "coverage_status": coverage_status, "summary": summary, "source_health": source_health, "items": items, "errors": errors, "data_quality": {"free_sources_only": True, "sec_cursor": "accession-number based; multiple same-day filings are preserved", "earnings_source": "confirmed/estimated curated primary-source calendar; no Finnhub dependency", "technical_policy": "large daily moves and same-day zone crossings only; stale near-zone alerts are suppressed", "max_attention_items": MAX_ITEMS}}
    event_output = {"schema_version": "1.0", "generated_at": generated_at, "row_count": len(normalized_events), "events": normalized_events}
    for path in ATTENTION_OUT_PATHS:
        save_json(path, output)
    for path in EVENT_OUT_PATHS:
        save_json(path, event_output)
    save_json(SEC_STATE_PATH, next_sec_state)
    return output


def main() -> None:
    output = generate()
    print(f"Generated P0 attention list: {len(output['items'])} items / {output['total_monitored']} monitored / {output['total_events']} events")
    print(f"Coverage: {output['coverage_status']} | free sources only: {output['data_quality']['free_sources_only']}")


if __name__ == "__main__":
    main()
