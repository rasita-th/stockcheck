#!/usr/bin/env python3
"""SEC EDGAR fundamental V1 for Stock Timing Radar.

Python-only module designed to be run/imported in IDLE first.
No API key. No Alpha Vantage. No analyst target in V1.

Used by app.py through build_fundamental_sec_v1(symbol, latest).
"""
from __future__ import annotations

import datetime as dt
import html
import json
import math
import os
import re
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", "StockTimingRadar-SEC-V1 contact@example.com")
SEC_REQUEST_DELAY_SECONDS = float(os.environ.get("SEC_REQUEST_DELAY_SECONDS", "0.12"))
SEC_ACCEPTED_FORMS = {"10-Q", "10-K", "20-F", "40-F"}
GUIDANCE_LOOKBACK_DAYS = int(os.environ.get("SEC_GUIDANCE_LOOKBACK_DAYS", "1460"))  # V2.5: guidance history needs multi-year lookback
GUIDANCE_MAX_FILINGS = int(os.environ.get("SEC_GUIDANCE_MAX_FILINGS", "40"))
GUIDANCE_MAX_DOCUMENTS_PER_FILING = int(os.environ.get("SEC_GUIDANCE_MAX_DOCUMENTS_PER_FILING", "8"))
GUIDANCE_MIN_CONFIDENCE_TO_USE = os.environ.get("SEC_GUIDANCE_MIN_CONFIDENCE", "medium").lower()

_TICKER_INDEX_CACHE: Optional[Dict[str, Dict[str, Any]]] = None
_FACTS_CACHE: Dict[str, Dict[str, Any]] = {}
_SUBMISSIONS_CACHE: Dict[str, Dict[str, Any]] = {}
_ARCHIVE_INDEX_CACHE: Dict[str, Dict[str, Any]] = {}
_ARCHIVE_TEXT_CACHE: Dict[str, str] = {}
_GUIDANCE_RESULT_CACHE: Dict[str, Dict[str, Any]] = {}
_LAST_REQUEST_TS = 0.0

KNOWN_ETF_TICKERS = {
    "SPY", "QQQ", "DIA", "IWM", "VTI", "VOO", "IVV", "SCHD", "JEPI", "JEPQ",
    "ARKK", "ARKQ", "ARKF", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI",
    "XLU", "XLB", "XLRE", "SMH", "SOXX", "COPX", "TQQQ", "SQQQ", "SOXL", "SOXS",
    "TLT", "HYG", "LQD", "GLD", "SLV", "IBIT", "FBTC", "BITO",
}

TAGS: Dict[str, List[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "eps_diluted": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
    "operating_cf": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "PartnersCapital",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "CashAndDueFromBanks",
    ],
    "debt_current": [
        "LongTermDebtAndFinanceLeaseObligationsCurrent",
        "LongTermDebtCurrent",
        "ShortTermBorrowings",
        "DebtCurrent",
        "ShortTermDebtCurrent",
    ],
    "debt_noncurrent": [
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
        "LongTermDebtNoncurrent",
        "LongTermDebt",
    ],
    "debt_total": [
        "LongTermDebtAndFinanceLeaseObligations",
        "DebtAndFinanceLeaseObligations",
        "LongTermDebtAndFinanceLeaseObligationsIncludingCurrentMaturities",
    ],
    "shares_outstanding": ["EntityCommonStockSharesOutstanding"],
    "weighted_avg_diluted_shares": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
}


def _round(value: Any, digits: int = 2) -> Optional[float]:
    try:
        if value is None:
            return None
        return round(float(value), digits)
    except Exception:
        return None


def _pct_change(new: Any, old: Any) -> Optional[float]:
    try:
        if new is None or old in (None, 0):
            return None
        return (float(new) / float(old) - 1.0) * 100.0
    except Exception:
        return None


def _earnings_change_pct(new: Any, old: Any) -> Optional[float]:
    """Directional change for profit/EPS where negative values need special handling.

    Standard percentage change makes -641 vs -223 look like +188%, even though
    the loss widened. For earnings metrics, positive means better and negative
    means worse:
    - loss narrowed => positive
    - loss widened => negative
    - loss to profit => +100 sentinel
    - profit to loss => -100 sentinel
    """
    try:
        if new is None or old in (None, 0):
            return None
        n = float(new)
        o = float(old)
        if o == 0:
            return None
        if o < 0 and n < 0:
            return (abs(o) - abs(n)) / abs(o) * 100.0
        if o < 0 <= n:
            return 100.0
        if o > 0 > n:
            return -100.0
        return (n / o - 1.0) * 100.0
    except Exception:
        return None


def _earnings_change_status(new: Any, old: Any) -> Optional[str]:
    try:
        if new is None or old is None:
            return None
        n = float(new)
        o = float(old)
        if o < 0 and n < 0:
            return "Loss narrowed" if abs(n) < abs(o) else "Loss widened" if abs(n) > abs(o) else "Loss flat"
        if o < 0 <= n:
            return "Turned profitable"
        if o > 0 > n:
            return "Turned to loss"
        if o >= 0 and n >= 0:
            return "Profit increased" if n > o else "Profit decreased" if n < o else "Profit flat"
        return None
    except Exception:
        return None


def _div_pct(numerator: Any, denominator: Any) -> Optional[float]:
    try:
        if numerator is None or denominator in (None, 0):
            return None
        return float(numerator) / float(denominator) * 100.0
    except Exception:
        return None


def _div_ratio(numerator: Any, denominator: Any) -> Optional[float]:
    try:
        if numerator is None or denominator in (None, 0):
            return None
        return float(numerator) / float(denominator)
    except Exception:
        return None


def _days_ago(date_text: Optional[str]) -> Optional[int]:
    if not date_text:
        return None
    try:
        return (dt.datetime.utcnow().date() - dt.date.fromisoformat(str(date_text)[:10])).days
    except Exception:
        return None


def _plain_us_ticker(symbol: str) -> Optional[str]:
    symbol = symbol.strip().upper()
    if not symbol or "." in symbol:
        return None
    return symbol


def _is_probably_etf(symbol: str, latest: Optional[Dict[str, Any]] = None) -> bool:
    symbol = symbol.strip().upper()
    if symbol in KNOWN_ETF_TICKERS:
        return True
    instrument = str((latest or {}).get("instrumentType") or "").upper()
    return instrument in {"ETF", "MUTUALFUND", "FUND", "INDEX"}


def _sec_get_json(url: str, timeout: int = 30) -> Dict[str, Any]:
    global _LAST_REQUEST_TS
    now = time.time()
    wait = SEC_REQUEST_DELAY_SECONDS - (now - _LAST_REQUEST_TS)
    if wait > 0:
        time.sleep(wait)
    _LAST_REQUEST_TS = time.time()

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": SEC_USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9,th;q=0.8",
            "Connection": "close",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def fetch_ticker_index() -> Dict[str, Dict[str, Any]]:
    """Map ticker -> CIK/company name using SEC free files."""
    global _TICKER_INDEX_CACHE
    if _TICKER_INDEX_CACHE is not None:
        return _TICKER_INDEX_CACHE

    index: Dict[str, Dict[str, Any]] = {}
    try:
        payload = _sec_get_json("https://www.sec.gov/files/company_tickers_exchange.json")
        fields = payload.get("fields") or []
        for row in payload.get("data") or []:
            item = dict(zip(fields, row))
            ticker = str(item.get("ticker") or "").upper().strip()
            cik = item.get("cik") or item.get("cik_str")
            if ticker and cik:
                index[ticker] = {
                    "ticker": ticker,
                    "cik": str(cik).zfill(10),
                    "companyName": item.get("name") or item.get("title"),
                    "exchange": item.get("exchange"),
                }
    except Exception:
        payload = _sec_get_json("https://www.sec.gov/files/company_tickers.json")
        for item in payload.values():
            ticker = str(item.get("ticker") or "").upper().strip()
            cik = item.get("cik_str")
            if ticker and cik:
                index[ticker] = {
                    "ticker": ticker,
                    "cik": str(cik).zfill(10),
                    "companyName": item.get("title"),
                    "exchange": None,
                }

    _TICKER_INDEX_CACHE = index
    return index


def company_for_symbol(symbol: str) -> Optional[Dict[str, Any]]:
    ticker = _plain_us_ticker(symbol)
    if not ticker:
        return None
    return fetch_ticker_index().get(ticker)


def fetch_companyfacts(cik: str) -> Dict[str, Any]:
    cik = str(cik).zfill(10)
    if cik not in _FACTS_CACHE:
        _FACTS_CACHE[cik] = _sec_get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
    return _FACTS_CACHE[cik]


def fetch_submissions(cik: str) -> Dict[str, Any]:
    cik = str(cik).zfill(10)
    if cik not in _SUBMISSIONS_CACHE:
        _SUBMISSIONS_CACHE[cik] = _sec_get_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
    return _SUBMISSIONS_CACHE[cik]


def latest_filing_meta(submissions: Dict[str, Any]) -> Dict[str, Any]:
    recent = ((submissions.get("filings") or {}).get("recent") or {})
    forms = recent.get("form") or []
    filing_dates = recent.get("filingDate") or []
    report_dates = recent.get("reportDate") or []
    accession_numbers = recent.get("accessionNumber") or []
    for i, form in enumerate(forms):
        form_text = str(form or "").upper()
        if form_text in SEC_ACCEPTED_FORMS:
            return {
                "formType": form_text,
                "filingDate": filing_dates[i] if i < len(filing_dates) else None,
                "periodEnd": report_dates[i] if i < len(report_dates) else None,
                "accessionNumber": accession_numbers[i] if i < len(accession_numbers) else None,
            }
    return {"formType": None, "filingDate": None, "periodEnd": None, "accessionNumber": None}


def fact_values(
    facts: Dict[str, Any],
    tag_names: List[str],
    units: List[str],
    taxonomies: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    taxonomies = taxonomies or ["us-gaap", "ifrs-full", "dei"]
    all_facts = facts.get("facts") or {}
    for taxonomy in taxonomies:
        bucket = all_facts.get(taxonomy) or {}
        for tag in tag_names:
            node = bucket.get(tag) or {}
            unit_map = node.get("units") or {}
            for unit in units:
                values = unit_map.get(unit)
                if values:
                    return values, {"tag": tag, "unit": unit, "taxonomy": taxonomy, "rawPoints": len(values)}
    return [], {"tag": None, "unit": None, "taxonomy": None, "rawPoints": 0}


def freshest_flow_fact_values(
    facts: Dict[str, Any],
    tag_names: List[str],
    units: List[str],
    taxonomies: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """Select the tag whose usable quarterly series ends most recently.

    Issuers can migrate between equivalent US-GAAP tags. Picking the first tag
    that merely has any history can therefore surface a years-old value while a
    fallback tag contains the current quarter.
    """
    taxonomies = taxonomies or ["us-gaap", "ifrs-full", "dei"]
    all_facts = facts.get("facts") or {}
    best_values: List[Dict[str, Any]] = []
    best_quarters: List[Dict[str, Any]] = []
    best_audit = {"tag": None, "unit": None, "taxonomy": None, "rawPoints": 0, "quarterPoints": 0}
    best_key: Optional[Tuple[str, str, int]] = None

    for taxonomy in taxonomies:
        bucket = all_facts.get(taxonomy) or {}
        for tag in tag_names:
            node = bucket.get(tag) or {}
            unit_map = node.get("units") or {}
            for unit in units:
                values = unit_map.get(unit) or []
                if not values:
                    continue
                quarters, _annuals = duration_points(values)
                if not quarters:
                    continue
                latest = quarters[-1]
                candidate_key = (
                    str(latest.get("end") or ""),
                    str(latest.get("filed") or ""),
                    len(quarters),
                )
                if best_key is None or candidate_key > best_key:
                    best_key = candidate_key
                    best_values = values
                    best_quarters = quarters
                    best_audit = {
                        "tag": tag,
                        "unit": unit,
                        "taxonomy": taxonomy,
                        "rawPoints": len(values),
                        "quarterPoints": len(quarters),
                    }

    return best_values, best_quarters, best_audit


def duration_points(values: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return clean quarterly points and annual points for one duration fact."""
    quarters: List[Dict[str, Any]] = []
    annuals: List[Dict[str, Any]] = []
    seen = set()
    for item in values:
        try:
            val = item.get("val")
            fy = item.get("fy")
            fp = str(item.get("fp") or "").upper()
            form = str(item.get("form") or "").upper()
            start = item.get("start")
            end = item.get("end")
            filed = item.get("filed")
            if val is None or not fy or not end or form not in SEC_ACCEPTED_FORMS:
                continue
            days = None
            if start:
                days = (dt.date.fromisoformat(str(end)[:10]) - dt.date.fromisoformat(str(start)[:10])).days
            point = {
                "value": float(val),
                "fy": int(fy),
                "fp": fp,
                "form": form,
                "start": str(start)[:10] if start else None,
                "end": str(end)[:10],
                "filed": str(filed)[:10] if filed else None,
                "frame": item.get("frame"),
                "days": days,
            }
            key = (point["fy"], point["fp"], point["end"], point["filed"], point["value"])
            if key in seen:
                continue
            seen.add(key)
            if fp in {"Q1", "Q2", "Q3", "Q4"} and days is not None and 55 <= days <= 125:
                quarters.append(point)
            elif fp == "FY" and days is not None and 300 <= days <= 400:
                annuals.append(point)
        except Exception:
            continue

    # Derive Q4 when companyfacts has annual + Q1/Q2/Q3 but no standalone Q4 point.
    by_fy: Dict[int, Dict[str, Dict[str, Any]]] = {}
    for q in quarters:
        by_fy.setdefault(int(q["fy"]), {})[str(q["fp"])] = q
    for annual in annuals:
        fy = int(annual["fy"])
        qs = by_fy.get(fy) or {}
        if all(k in qs for k in ["Q1", "Q2", "Q3"]):
            has_q4 = any(int(q.get("fy", 0)) == fy and q.get("fp") == "Q4" for q in quarters)
            if not has_q4:
                q4_value = float(annual["value"]) - float(qs["Q1"]["value"]) - float(qs["Q2"]["value"]) - float(qs["Q3"]["value"])
                quarters.append({
                    "value": q4_value,
                    "fy": fy,
                    "fp": "Q4",
                    "form": annual.get("form"),
                    "start": None,
                    "end": annual.get("end"),
                    "filed": annual.get("filed"),
                    "frame": None,
                    "days": None,
                    "derived": "FY minus Q1-Q3",
                })

    quarters.sort(key=lambda x: (x.get("end") or "", x.get("filed") or ""))
    annuals.sort(key=lambda x: (x.get("end") or "", x.get("filed") or ""))
    return quarters, annuals


def latest_instant(values: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    seen = set()
    for item in values:
        try:
            val = item.get("val")
            end = item.get("end")
            form = str(item.get("form") or "").upper()
            if val is None or not end or form not in SEC_ACCEPTED_FORMS:
                continue
            point = {
                "value": float(val),
                "fy": int(item.get("fy")) if item.get("fy") else None,
                "fp": str(item.get("fp") or "").upper() or None,
                "form": form,
                "end": str(end)[:10],
                "filed": str(item.get("filed"))[:10] if item.get("filed") else None,
                "frame": item.get("frame"),
            }
            key = (point["end"], point["filed"], point["form"], point["value"])
            if key in seen:
                continue
            seen.add(key)
            points.append(point)
        except Exception:
            continue
    if not points:
        return None
    points.sort(key=lambda x: (x.get("end") or "", x.get("filed") or ""))
    return points[-1]


def latest_with_changes(values: List[Dict[str, Any]], earnings_mode: bool = False) -> Dict[str, Any]:
    if not values:
        return {
            "value": None, "qoq": None, "yoy": None, "quarter": None, "date": None,
            "filed": None, "form": None, "prevValue": None, "prevQuarter": None,
            "yearAgoValue": None, "yearAgoQuarter": None, "qoqStatus": None, "yoyStatus": None,
        }
    latest = values[-1]
    prev = values[-2] if len(values) >= 2 else None
    yoy = None
    for candidate in reversed(values[:-1]):
        if candidate.get("fp") == latest.get("fp") and int(candidate.get("fy", 0)) == int(latest.get("fy", 0)) - 1:
            yoy = candidate
            break

    latest_value = latest.get("value")
    prev_value = prev.get("value") if prev else None
    yoy_value = yoy.get("value") if yoy else None
    change_func = _earnings_change_pct if earnings_mode else _pct_change

    return {
        "value": latest_value,
        "qoq": change_func(latest_value, prev_value),
        "yoy": change_func(latest_value, yoy_value),
        "quarter": f"{latest.get('fp')} {latest.get('fy')}",
        "date": latest.get("end"),
        "filed": latest.get("filed"),
        "form": latest.get("form"),
        "derived": latest.get("derived"),
        "prevValue": prev_value,
        "prevQuarter": f"{prev.get('fp')} {prev.get('fy')}" if prev else None,
        "yearAgoValue": yoy_value,
        "yearAgoQuarter": f"{yoy.get('fp')} {yoy.get('fy')}" if yoy else None,
        "qoqStatus": _earnings_change_status(latest_value, prev_value) if earnings_mode else None,
        "yoyStatus": _earnings_change_status(latest_value, yoy_value) if earnings_mode else None,
    }


def flow_metric(facts: Dict[str, Any], name: str, units: List[str], earnings_mode: bool = False) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    _values, quarters, audit = freshest_flow_fact_values(facts, TAGS[name], units)
    return latest_with_changes(quarters, earnings_mode=earnings_mode), audit


def instant_metric(facts: Dict[str, Any], name: str, units: List[str]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    values, audit = fact_values(facts, TAGS[name], units)
    point = latest_instant(values)
    return point, audit


def _sec_get_text(url: str, timeout: int = 30) -> str:
    """Fetch SEC archive text with the same fair-access throttling as JSON calls."""
    global _LAST_REQUEST_TS
    now = time.time()
    wait = SEC_REQUEST_DELAY_SECONDS - (now - _LAST_REQUEST_TS)
    if wait > 0:
        time.sleep(wait)
    _LAST_REQUEST_TS = time.time()

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": SEC_USER_AGENT,
            "Accept": "text/html,text/plain,application/json,*/*",
            "Accept-Language": "en-US,en;q=0.9,th;q=0.8",
            "Connection": "close",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _strip_html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", raw)
    raw = re.sub(r"(?is)<br\s*/?>", "\n", raw)
    # Keep rough table structure. Many earnings releases put guidance in tables;
    # pipe separators make regex windows easier to parse and debug.
    raw = re.sub(r"(?is)</t[dh]>", " | ", raw)
    raw = re.sub(r"(?is)</tr>|</p>|</div>|</li>|</table>", "\n", raw)
    text = re.sub(r"(?is)<[^>]+>", " ", raw)
    text = html.unescape(text)
    text = (text.replace("\u00a0", " ").replace("\u2013", "-").replace("\u2014", "-")
                .replace("–", "-").replace("—", "-"))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _archive_base_url(cik: str, accession_number: str) -> str:
    cik_no_zeros = str(int(str(cik).lstrip("0") or "0"))
    accession_no_dash = str(accession_number).replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_no_zeros}/{accession_no_dash}"


def fetch_archive_index(cik: str, accession_number: str) -> Dict[str, Any]:
    key = f"{str(cik).zfill(10)}:{accession_number}"
    if key not in _ARCHIVE_INDEX_CACHE:
        _ARCHIVE_INDEX_CACHE[key] = _sec_get_json(f"{_archive_base_url(cik, accession_number)}/index.json")
    return _ARCHIVE_INDEX_CACHE[key]


def fetch_archive_document_text(cik: str, accession_number: str, document_name: str) -> str:
    key = f"{str(cik).zfill(10)}:{accession_number}:{document_name}"
    if key in _ARCHIVE_TEXT_CACHE:
        return _ARCHIVE_TEXT_CACHE[key]
    url = f"{_archive_base_url(cik, accession_number)}/{urllib.parse.quote(document_name)}"
    raw = _sec_get_text(url)
    text = _strip_html_to_text(raw)
    _ARCHIVE_TEXT_CACHE[key] = text
    return text


def _recent_8k_candidates(submissions: Dict[str, Any]) -> List[Dict[str, Any]]:
    recent = ((submissions.get("filings") or {}).get("recent") or {})
    forms = recent.get("form") or []
    filing_dates = recent.get("filingDate") or []
    report_dates = recent.get("reportDate") or []
    accession_numbers = recent.get("accessionNumber") or []
    primary_documents = recent.get("primaryDocument") or []
    primary_descriptions = recent.get("primaryDocDescription") or []
    today = dt.datetime.utcnow().date()
    out: List[Dict[str, Any]] = []
    for i, form in enumerate(forms):
        form_text = str(form or "").upper()
        if form_text not in {"8-K", "6-K"}:
            continue
        filing_date = filing_dates[i] if i < len(filing_dates) else None
        try:
            age = (today - dt.date.fromisoformat(str(filing_date)[:10])).days if filing_date else 10_000
        except Exception:
            age = 10_000
        if age > GUIDANCE_LOOKBACK_DAYS:
            continue
        accession = accession_numbers[i] if i < len(accession_numbers) else None
        if not accession:
            continue
        out.append({
            "formType": form_text,
            "filingDate": filing_date,
            "reportDate": report_dates[i] if i < len(report_dates) else None,
            "accessionNumber": accession,
            "primaryDocument": primary_documents[i] if i < len(primary_documents) else None,
            "primaryDocDescription": primary_descriptions[i] if i < len(primary_descriptions) else None,
            "ageDays": age,
        })
        if len(out) >= GUIDANCE_MAX_FILINGS:
            break
    return out


def _candidate_guidance_documents(index_json: Dict[str, Any], primary_document: Optional[str]) -> List[str]:
    files = ((index_json.get("directory") or {}).get("item") or [])
    scored: List[Tuple[int, str]] = []
    for item in files:
        name = str(item.get("name") or "")
        if not name or not re.search(r"\.(htm|html|txt)$", name, flags=re.I):
            continue
        lname = name.lower()
        score = 0
        # Most earnings releases / outlooks are EX-99.1, but naming varies a lot.
        if re.search(r"(?:^|[\-_])(?:ex|dex)[\-_]?99[\-_\. ]?1", lname) or "ex99" in lname or "ex-99" in lname:
            score += 120
        if re.search(r"(?:^|[\-_])(?:ex|dex)[\-_]?99", lname) or "99" in lname:
            score += 55
        if any(tok in lname for tok in ["earn", "release", "results", "outlook", "guidance", "letter", "shareholder", "press", "presentation"]):
            score += 35
        if primary_document and name == primary_document:
            score += 15
        # Keep a small chance for HTML documents with opaque names because SEC exhibit names are not standardized.
        if score == 0 and re.search(r"\.(htm|html)$", lname):
            score = 1
        if score > 0:
            scored.append((score, name))
    if primary_document and not any(name == primary_document for _, name in scored):
        scored.append((10, primary_document))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [name for _, name in scored[:GUIDANCE_MAX_DOCUMENTS_PER_FILING]]


def _money_to_number(value: str, scale: Optional[str]) -> Optional[float]:
    try:
        num = float(str(value).replace(",", ""))
    except Exception:
        return None
    scale_l = str(scale or "").lower().strip()
    if scale_l in {"b", "bn", "billion", "billions"}:
        num *= 1_000_000_000
    elif scale_l in {"m", "mm", "million", "millions"}:
        num *= 1_000_000
    elif scale_l in {"k", "thousand", "thousands"}:
        num *= 1_000
    return num


def _parse_guidance_year(raw_year: str, filing_date: Optional[str]) -> Optional[int]:
    try:
        year = int(str(raw_year).strip())
        if year < 100:
            # Most current EDGAR filings are 20xx; infer the century from filing year.
            base_year = None
            try:
                base_year = dt.date.fromisoformat(str(filing_date or "")[:10]).year
            except Exception:
                base_year = dt.datetime.utcnow().year
            century = (base_year // 100) * 100
            year = century + year
            if year < base_year - 8:
                year += 100
        return year
    except Exception:
        return None


def _month_name_to_number(name: str) -> Optional[int]:
    months = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
    }
    return months.get(str(name or "").lower().strip("."))


def _calendar_quarter_from_month(month: int) -> int:
    return (int(month) - 1) // 3 + 1


def _period_from_date_text(context: str, filing_date: Optional[str]) -> Optional[str]:
    text = re.sub(r"\s+", " ", context)
    # quarter ending December 31, 2025 / period ending Sep. 30 2025
    m = re.search(r"\b(?:quarter|period|three months|fiscal quarter)\s+(?:ending|ended|end(?:s)?)\s+([A-Za-z]{3,9})\.?\s+([0-9]{1,2}),?\s+(20[0-9]{2})\b", text, flags=re.I)
    if m:
        month = _month_name_to_number(m.group(1))
        year = _parse_guidance_year(m.group(3), filing_date)
        if month and year:
            return f"Q{_calendar_quarter_from_month(month)} {year}"
    # for the quarter ended/ending 12/31/2025
    m = re.search(r"\b(?:quarter|period|three months|fiscal quarter)\s+(?:ending|ended|end(?:s)?)\s+([0-9]{1,2})/([0-9]{1,2})/(20[0-9]{2})\b", text, flags=re.I)
    if m:
        month = int(m.group(1))
        year = _parse_guidance_year(m.group(3), filing_date)
        if 1 <= month <= 12 and year:
            return f"Q{_calendar_quarter_from_month(month)} {year}"
    return None


def _infer_guidance_period(context: str, filing_date: Optional[str]) -> Optional[str]:
    text = re.sub(r"\s+", " ", context).lower()
    q_word = {"first": "Q1", "1st": "Q1", "second": "Q2", "2nd": "Q2", "third": "Q3", "3rd": "Q3", "fourth": "Q4", "4th": "Q4"}
    m = re.search(r"\b(first|1st|second|2nd|third|3rd|fourth|4th)\s+(?:fiscal\s+)?quarter\s+(?:of\s+)?(?:fiscal\s+)?(?:year\s+)?'?([0-9]{2}|20[0-9]{2})\b", text, flags=re.I)
    if m:
        year = _parse_guidance_year(m.group(2), filing_date)
        if year:
            return f"{q_word[m.group(1)]} {year}"
    m = re.search(r"\b(?:fiscal\s+)?(?:year\s+)?'?([0-9]{2}|20[0-9]{2})\s+(first|1st|second|2nd|third|3rd|fourth|4th)\s+(?:fiscal\s+)?quarter\b", text, flags=re.I)
    if m:
        year = _parse_guidance_year(m.group(1), filing_date)
        if year:
            return f"{q_word[m.group(2)]} {year}"
    m = re.search(r"\bq\s*([1-4])\s*(?:fy|fiscal\s+year\s*)?'?([0-9]{2}|20[0-9]{2})\b", text, flags=re.I)
    if m:
        year = _parse_guidance_year(m.group(2), filing_date)
        if year:
            return f"Q{m.group(1)} {year}"
    m = re.search(r"\b(?:fy|fiscal\s+year\s*)'?([0-9]{2}|20[0-9]{2})\s*q\s*([1-4])\b", text, flags=re.I)
    if m:
        year = _parse_guidance_year(m.group(1), filing_date)
        if year:
            return f"Q{m.group(2)} {year}"
    by_date = _period_from_date_text(context, filing_date)
    if by_date:
        return by_date
    m = re.search(r"\b(?:full\s+year|full-year|fiscal\s+year|fy)\s*(?:ending\s+)?(?:fiscal\s+)?'?([0-9]{2}|20[0-9]{2})\b", text)
    if m:
        year = _parse_guidance_year(m.group(1), filing_date)
        if year:
            return f"FY {year}"
    if any(term in text for term in ["next quarter", "upcoming quarter", "following quarter"]) and filing_date:
        try:
            d = dt.date.fromisoformat(str(filing_date)[:10])
            q = (d.month - 1) // 3 + 1
            next_q = q + 1
            year = d.year
            if next_q > 4:
                next_q = 1
                year += 1
            return f"Q{next_q} {year}"
        except Exception:
            return None
    return None


def _guidance_window_ranges(clean: str) -> List[Tuple[int, int]]:
    """Return likely guidance/outlook windows.

    V2.5 scans more than the exact word "guidance"; companies often write
    "business outlook", "financial outlook", "expects", or put numbers in a table.
    """
    triggers = [
        r"financial outlook", r"business outlook", r"outlook", r"guidance",
        r"expect(?:s|ed|ing)?", r"forecast", r"project(?:s|ed|ing)?",
        r"anticipate(?:s|d|ing)?", r"estimate(?:s|d)?", r"range",
        r"for the (?:first|second|third|fourth|1st|2nd|3rd|4th) quarter",
        r"for q[1-4]",
    ]
    ranges: List[Tuple[int, int]] = []
    for pat in triggers:
        for m in re.finditer(pat, clean, flags=re.I):
            start = max(0, m.start() - 900)
            end = min(len(clean), m.end() + 1800)
            window = clean[start:end]
            if re.search(r"\brevenue|\bsales|\bnet sales|\btotal revenues", window, flags=re.I):
                ranges.append((start, end))
    if not ranges:
        return []
    ranges.sort()
    merged: List[Tuple[int, int]] = []
    for start, end in ranges:
        if not merged or start > merged[-1][1] + 120:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged[:20]


def _guidance_context_quality(context: str, period: Optional[str], match_type: str) -> Tuple[str, str]:
    text = re.sub(r"\s+", " ", context).lower()
    flags: List[str] = []
    score = 0
    if period:
        score += 2
    else:
        flags.append("period not explicit")
    if re.search(r"\b(total\s+)?revenues?\b|\bnet sales\b|\bsales\b", text):
        score += 2
    if "total revenue" in text or "total revenues" in text or "net sales" in text:
        score += 1
    if any(term in text for term in ["outlook", "guidance", "expect", "forecast", "project", "anticipate"]):
        score += 2
    if match_type == "range":
        score += 1
    # Do not trust obvious segment / operating metric matches unless total revenue is explicit nearby.
    bad_terms = [
        "arr", "annual recurring revenue", "bookings", "backlog", "rpo", "remaining performance obligations",
        "segment revenue", "cloud revenue", "subscription revenue", "product revenue", "service revenue",
        "advertising revenue", "marketplace revenue", "gmv", "gross merchandise", "ebitda",
    ]
    if any(term in text for term in bad_terms) and not ("total revenue" in text or "total revenues" in text or "net sales" in text):
        score -= 3
        flags.append("may be segment/non-total revenue")
    if re.search(r"\bactual\b|\breported\b|\bwas\b|\bwere\b|\bgrew\b|\bincreased\b|\bdecreased\b", text) and not any(term in text for term in ["expect", "guidance", "outlook", "forecast", "anticipate", "project"]):
        score -= 2
        flags.append("looks like historical result, not forward guidance")
    if score >= 6:
        return "high", "; ".join(flags) or "explicit period/revenue/guidance context"
    if score >= 4:
        return "medium", "; ".join(flags) or "plausible guidance context"
    return "low", "; ".join(flags) or "weak guidance context"


def _normalize_guidance_match(low: Optional[float], high: Optional[float], context: str, filing_date: Optional[str], match_type: str) -> Optional[Dict[str, Any]]:
    if low is None and high is None:
        return None
    if low is None:
        low = high
    if high is None:
        high = low
    if low is None or high is None:
        return None
    if low > high:
        low, high = high, low
    # Avoid accidental per-share or percentage matches.
    if high < 100_000:
        return None
    period = _infer_guidance_period(context, filing_date)
    confidence, reason = _guidance_context_quality(context, period, match_type)
    return {
        "low": low,
        "high": high,
        "midpoint": (float(low) + float(high)) / 2.0,
        "period": period,
        "textSnippet": context[:900],
        "matchType": match_type,
        "confidence": confidence,
        "confidenceReason": reason,
    }


def _extract_revenue_guidance_matches(text: str, filing_date: Optional[str]) -> List[Dict[str, Any]]:
    clean = re.sub(r"\s+", " ", text)
    windows = _guidance_window_ranges(clean)
    if not windows:
        return []
    money = r"\$?\s*([0-9][0-9,]*(?:\.\d+)?)\s*(billion|billions|million|millions|thousand|thousands|bn|mm|b|m|k)?"
    scale_words = r"(billion|billions|million|millions|thousand|thousands|bn|mm|b|m|k)"
    matches: List[Dict[str, Any]] = []

    patterns = [
        # revenue ... $10 million to $12 million
        ("range", re.compile(r"(?:total\s+)?(?:net\s+)?(?:revenue|revenues|sales)[^\.|\n]{0,320}?" + money + r"\s*(?:to|and|-|through)\s*" + money, flags=re.I), (1,2,3,4)),
        # $10 million to $12 million ... revenue
        ("range_rev_after", re.compile(money + r"\s*(?:to|and|-|through)\s*" + money + r"[^\.|\n]{0,180}?(?:total\s+)?(?:net\s+)?(?:revenue|revenues|sales)", flags=re.I), (1,2,3,4)),
        # revenue ... approximately $10 million
        ("single", re.compile(r"(?:total\s+)?(?:net\s+)?(?:revenue|revenues|sales)[^\.|\n]{0,260}?(?:approximately|about|around|of|to be|is expected to be|are expected to be)?\s*" + money, flags=re.I), (1,2,None,None)),
        # table-like: Revenue | $10 | $12 | million
        ("table_range", re.compile(r"(?:total\s+)?(?:net\s+)?(?:revenue|revenues|sales)\s*(?:\||:)?\s*" + money + r"\s*(?:\||to|-|and)\s*" + money + r"(?:\s*" + scale_words + r")?", flags=re.I), (1,2,3,4)),
    ]

    seen = set()
    for start, end in windows:
        window = clean[start:end]
        for match_type, regex, groups in patterns:
            for m in regex.finditer(window):
                context_start = max(0, start + m.start() - 900)
                context_end = min(len(clean), start + m.end() + 900)
                context = clean[context_start:context_end]
                try:
                    g1, s1, g2, s2 = groups
                    if g2 is not None:
                        lo_scale = m.group(s1) or m.group(s2)
                        hi_scale = m.group(s2) or m.group(s1)
                        low = _money_to_number(m.group(g1), lo_scale)
                        high = _money_to_number(m.group(g2), hi_scale)
                    else:
                        low = high = _money_to_number(m.group(g1), m.group(s1))
                except Exception:
                    continue
                item = _normalize_guidance_match(low, high, context, filing_date, "range" if "range" in match_type else "single")
                if not item:
                    continue
                key = (item.get("period"), round(float(item.get("midpoint") or 0), 0), item.get("confidence"), item.get("matchType"))
                if key in seen:
                    continue
                seen.add(key)
                matches.append(item)

    rank = {"high": 3, "medium": 2, "low": 1}
    matches.sort(key=lambda x: (rank.get(str(x.get("confidence")), 0), 1 if x.get("period") else 0, str(x.get("matchType")) == "range"), reverse=True)
    return matches[:8]


def _extract_revenue_guidance(text: str, filing_date: Optional[str]) -> Optional[Dict[str, Any]]:
    matches = _extract_revenue_guidance_matches(text, filing_date)
    return matches[0] if matches else None


def _extract_eps_guidance(text: str, filing_date: Optional[str]) -> Optional[Dict[str, Any]]:
    clean = re.sub(r"\s+", " ", text)
    guidance_words = r"(?:guidance|outlook|expect(?:s|ed|ing)?|forecast|project(?:s|ed|ing)?|anticipate(?:s|d)?|estimate(?:s|d)?)"
    windows: List[Tuple[int, int]] = []
    for m in re.finditer(guidance_words, clean, flags=re.I):
        start = max(0, m.start() - 700)
        end = min(len(clean), m.end() + 1200)
        window = clean[start:end]
        if re.search(r"\beps\b|earnings per share", window, flags=re.I):
            windows.append((start, end))
    eps_re = re.compile(r"(?:eps|earnings per share)[^\.]{0,260}?\$?\s*(-?[0-9]+(?:\.\d+)?)\s*(?:to|and|-)\s*\$?\s*(-?[0-9]+(?:\.\d+)?)", flags=re.I)
    for start, end in windows:
        window = clean[start:end]
        m = eps_re.search(window)
        if not m:
            continue
        low = float(m.group(1)); high = float(m.group(2))
        if low > high:
            low, high = high, low
        context_start = max(0, start + m.start() - 600)
        context_end = min(len(clean), start + m.end() + 600)
        context = clean[context_start:context_end]
        return {"low": low, "high": high, "midpoint": (low + high) / 2.0, "period": _infer_guidance_period(context, filing_date), "textSnippet": context[:700], "matchType": "range"}
    return None



def _quarter_key(value: Any) -> Optional[Tuple[int, int]]:
    """Normalize strings like 'Q3 2026', 'Q3 FY2026', 'Fiscal Q3 2026' to (year, quarter)."""
    text = str(value or '').upper().replace('FISCAL', '').replace('FY', '').strip()
    m = re.search(r"Q\s*([1-4])\D*(20\d{2})", text)
    if m:
        return (int(m.group(2)), int(m.group(1)))
    m = re.search(r"(20\d{2})\D*Q\s*([1-4])", text)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return None


def _quarter_label_from_key(key: Optional[Tuple[int, int]]) -> Optional[str]:
    if not key:
        return None
    year, quarter = key
    return f"Q{quarter} {year}"


def _quarter_ordinal(key: Optional[Tuple[int, int]]) -> Optional[int]:
    if not key:
        return None
    year, quarter = key
    return int(year) * 4 + int(quarter)


def quarter_value_map(facts: Dict[str, Any], name: str, units: List[str]) -> Dict[str, Dict[str, Any]]:
    """Return quarterly points keyed by normalized 'Qn YYYY' labels.

    We keep metadata because actual-vs-guidance comparisons must not use
    low-confidence derived Q4 values blindly. Several companies report annual
    revenue plus Q1-Q3, and deriving Q4 can produce nonsense when fiscal year
    metadata/tags do not line up perfectly.
    """
    try:
        _values, quarters, _audit = freshest_flow_fact_values(facts, TAGS[name], units)
    except Exception:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for q in quarters:
        try:
            fp = str(q.get('fp') or '').upper()
            fy = int(q.get('fy'))
            value = q.get('value')
            if fp in {'Q1', 'Q2', 'Q3', 'Q4'} and value is not None:
                out[f"{fp} {fy}"] = {
                    "value": float(value),
                    "derived": q.get("derived"),
                    "end": q.get("end"),
                    "filed": q.get("filed"),
                    "form": q.get("form"),
                }
        except Exception:
            continue
    return out


def _revenue_guidance_comparable(actual_value: Any, midpoint: Any) -> Tuple[bool, str]:
    """Guardrail for actual-vs-company-guidance comparisons.

    Company guidance is parsed from unstructured 8-K/6-K text, so it can
    accidentally pick up segment revenue, ARR, bookings, or other non-total
    revenue figures. We only show a comparison when the magnitude is plausible.
    """
    try:
        actual = float(actual_value)
        guide = float(midpoint)
    except Exception:
        return False, "N/A: actual or guidance value is not numeric"
    if actual <= 0 or guide <= 0:
        return False, "N/A: actual or guidance revenue is non-positive"
    ratio = actual / guide
    if ratio < 0.30 or ratio > 3.00:
        return False, "N/A: parsed guidance is likely not comparable to total revenue"
    return True, ""

def _add_months(date_obj: dt.date, months: int) -> dt.date:
    month = date_obj.month - 1 + months
    year = date_obj.year + month // 12
    month = month % 12 + 1
    days_in_month = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    day = min(date_obj.day, days_in_month)
    return dt.date(year, month, day)


def next_quarter_end_from_period_end(period_end: Optional[str]) -> Tuple[Optional[str], Optional[int]]:
    """Estimate next fiscal quarter-end from the latest SEC period end.

    This is not an earnings announcement date. SEC gives period ends reliably;
    actual earnings announcement calendars require a separate consensus/calendar source.
    Negative days means the expected next quarter-end has already passed and the
    next SEC companyfacts update is not reflected yet.
    """
    if not period_end:
        return None, None
    try:
        d = dt.date.fromisoformat(str(period_end)[:10])
        next_end = _add_months(d, 3)
        today = dt.datetime.utcnow().date()
        return next_end.isoformat(), (next_end - today).days
    except Exception:
        return None, None

def _guidance_blank_result() -> Dict[str, Any]:
    """Default guidance payload for V1.7.

    V1.7 separates two ideas that were mixed together before:
    - prior guidance: the company's old guide for the latest actual quarter
    - next guidance: the newest forward guide for a future quarter
    """
    return {
        "companyGuidanceConnected": False,
        "companyGuidanceSource": "SEC 8-K/6-K exhibit parser",
        "companyGuidanceStatus": "No recent company guidance found in SEC 8-K/6-K exhibits",
        "guidanceHistory": [],
        "guidanceDebug": [],
        "guidanceParseStats": {"filingsScanned": 0, "documentsScanned": 0, "revenueMatches": 0, "highConfidence": 0, "mediumConfidence": 0, "lowConfidence": 0},

        "priorCompanyGuidanceRevenue": None,
        "priorCompanyGuidanceRevenueLow": None,
        "priorCompanyGuidanceRevenueHigh": None,
        "priorCompanyGuidanceRevenuePeriod": None,
        "priorCompanyGuidanceRevenueFiledDate": None,
        "priorCompanyGuidanceRevenueSourceDocument": None,
        "priorCompanyGuidanceRevenueSnippet": None,
        "priorCompanyGuidanceRevenueConfidence": None,
        "priorCompanyGuidanceRevenueConfidenceReason": None,
        "priorGuidanceRevenueActual": None,
        "priorGuidanceRevenueActualPeriod": None,
        "actualVsPriorGuidanceRevenuePct": None,
        "actualVsPriorGuidanceRevenueStatus": "N/A: no prior guidance matched to latest actual quarter",

        "nextCompanyGuidanceRevenue": None,
        "nextCompanyGuidanceRevenueLow": None,
        "nextCompanyGuidanceRevenueHigh": None,
        "nextCompanyGuidanceRevenuePeriod": None,
        "nextCompanyGuidanceRevenueFiledDate": None,
        "nextCompanyGuidanceRevenueSourceDocument": None,
        "nextCompanyGuidanceRevenueSnippet": None,
        "nextCompanyGuidanceRevenueConfidence": None,
        "nextCompanyGuidanceRevenueConfidenceReason": None,

        "nextCompanyGuidanceEps": None,
        "nextCompanyGuidanceEpsLow": None,
        "nextCompanyGuidanceEpsHigh": None,
        "nextCompanyGuidanceEpsPeriod": None,

        # Backward-compatible aliases used by older JS builds.
        "companyGuidanceRevenue": None,
        "companyGuidanceRevenueLow": None,
        "companyGuidanceRevenueHigh": None,
        "companyGuidanceRevenuePeriod": None,
        "companyGuidanceRevenueFiledDate": None,
        "companyGuidanceRevenueSourceDocument": None,
        "companyGuidanceRevenueSnippet": None,
        "companyGuidanceRevenueConfidence": None,
        "companyGuidanceRevenueConfidenceReason": None,
        "guidanceRevenueDeltaPct": None,
        "guidanceRevenueDeltaStatus": "N/A: use actualVsPriorGuidanceRevenuePct in V1.7",
        "guidanceRevenueActual": None,
        "guidanceRevenueActualPeriod": None,
        "companyGuidanceEps": None,
        "companyGuidanceEpsLow": None,
        "companyGuidanceEpsHigh": None,
        "companyGuidanceEpsPeriod": None,
    }


def _parse_date_safe(value: Any) -> Optional[dt.date]:
    try:
        if not value:
            return None
        return dt.date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def _guidance_entry_from_match(filing: Dict[str, Any], doc_name: str, revenue_g: Dict[str, Any]) -> Dict[str, Any]:
    period = revenue_g.get("period")
    pkey = _quarter_key(period)
    return {
        "type": "revenue",
        "period": period,
        "periodKey": pkey,
        "periodOrdinal": _quarter_ordinal(pkey),
        "filedDate": filing.get("filingDate"),
        "reportDate": filing.get("reportDate"),
        "accessionNumber": filing.get("accessionNumber"),
        "sourceDocument": str(doc_name),
        "low": _round(revenue_g.get("low"), 0),
        "high": _round(revenue_g.get("high"), 0),
        "midpoint": _round(revenue_g.get("midpoint"), 0),
        "textSnippet": revenue_g.get("textSnippet"),
        "matchType": revenue_g.get("matchType"),
        "confidence": revenue_g.get("confidence"),
        "confidenceReason": revenue_g.get("confidenceReason"),
    }


def _entry_midpoint(entry: Optional[Dict[str, Any]]) -> Optional[float]:
    if not entry:
        return None
    try:
        value = entry.get("midpoint")
        return float(value) if value is not None else None
    except Exception:
        return None


def _apply_forward_guidance_aliases(result: Dict[str, Any], entry: Optional[Dict[str, Any]]) -> None:
    """Populate next-guidance fields and old companyGuidance* aliases."""
    if not entry:
        return
    result["nextCompanyGuidanceRevenue"] = entry.get("midpoint")
    result["nextCompanyGuidanceRevenueLow"] = entry.get("low")
    result["nextCompanyGuidanceRevenueHigh"] = entry.get("high")
    result["nextCompanyGuidanceRevenuePeriod"] = entry.get("period")
    result["nextCompanyGuidanceRevenueFiledDate"] = entry.get("filedDate")
    result["nextCompanyGuidanceRevenueSourceDocument"] = entry.get("sourceDocument")
    result["nextCompanyGuidanceRevenueSnippet"] = entry.get("textSnippet")
    result["nextCompanyGuidanceRevenueConfidence"] = entry.get("confidence")
    result["nextCompanyGuidanceRevenueConfidenceReason"] = entry.get("confidenceReason")

    # Backward-compatible aliases. In V1.7 these aliases mean forward guidance,
    # while actual-vs-guide uses actualVsPriorGuidanceRevenuePct.
    result["companyGuidanceRevenue"] = entry.get("midpoint")
    result["companyGuidanceRevenueLow"] = entry.get("low")
    result["companyGuidanceRevenueHigh"] = entry.get("high")
    result["companyGuidanceRevenuePeriod"] = entry.get("period")
    result["companyGuidanceRevenueFiledDate"] = entry.get("filedDate")
    result["companyGuidanceRevenueSourceDocument"] = entry.get("sourceDocument")
    result["companyGuidanceRevenueSnippet"] = entry.get("textSnippet")
    result["companyGuidanceRevenueConfidence"] = entry.get("confidence")
    result["companyGuidanceRevenueConfidenceReason"] = entry.get("confidenceReason")


def _apply_prior_guidance_match(
    result: Dict[str, Any],
    entry: Optional[Dict[str, Any]],
    latest_quarter: Optional[str],
    latest_revenue: Any,
    revenue_by_quarter: Optional[Dict[str, Any]],
) -> None:
    if not entry:
        return
    result["priorCompanyGuidanceRevenue"] = entry.get("midpoint")
    result["priorCompanyGuidanceRevenueLow"] = entry.get("low")
    result["priorCompanyGuidanceRevenueHigh"] = entry.get("high")
    result["priorCompanyGuidanceRevenuePeriod"] = entry.get("period")
    result["priorCompanyGuidanceRevenueFiledDate"] = entry.get("filedDate")
    result["priorCompanyGuidanceRevenueSourceDocument"] = entry.get("sourceDocument")
    result["priorCompanyGuidanceRevenueSnippet"] = entry.get("textSnippet")
    result["priorCompanyGuidanceRevenueConfidence"] = entry.get("confidence")
    result["priorCompanyGuidanceRevenueConfidenceReason"] = entry.get("confidenceReason")

    midpoint = _entry_midpoint(entry)
    actual_value = None
    actual_period = None
    actual_meta: Dict[str, Any] = {}

    period_label = _quarter_label_from_key(entry.get("periodKey")) or entry.get("period")
    lookup = revenue_by_quarter or {}
    raw_actual = lookup.get(period_label or "")
    if isinstance(raw_actual, dict):
        actual_meta = raw_actual
        actual_value = raw_actual.get("value")
    elif raw_actual is not None:
        actual_value = raw_actual

    # If the matched guidance is for the latest quarter, prefer the freshly
    # normalized latest revenue field. This avoids lookup misses from tag quirks.
    if actual_value is None and _quarter_key(latest_quarter) == entry.get("periodKey"):
        actual_value = latest_revenue
    actual_period = period_label

    if actual_meta.get("derived"):
        result["actualVsPriorGuidanceRevenueStatus"] = "N/A: matched actual revenue is SEC-derived Q4; comparison disabled"
        return
    if midpoint in (None, 0):
        result["actualVsPriorGuidanceRevenueStatus"] = "N/A: prior company guidance midpoint missing"
        return
    if actual_value is None:
        result["actualVsPriorGuidanceRevenueStatus"] = f"N/A: no actual revenue found for {period_label or 'matched guide period'}"
        return

    comparable, reason = _revenue_guidance_comparable(actual_value, midpoint)
    if not comparable:
        result["actualVsPriorGuidanceRevenueStatus"] = reason
        return

    result["priorGuidanceRevenueActual"] = _round(actual_value, 0)
    result["priorGuidanceRevenueActualPeriod"] = actual_period
    result["actualVsPriorGuidanceRevenuePct"] = _round((float(actual_value) / float(midpoint) - 1.0) * 100.0, 2)
    result["actualVsPriorGuidanceRevenueStatus"] = f"Actual {actual_period or entry.get('period')} revenue vs prior company guidance midpoint"

    # Backward-compatible aliases for older JS.
    result["guidanceRevenueDeltaPct"] = result["actualVsPriorGuidanceRevenuePct"]
    result["guidanceRevenueDeltaStatus"] = result["actualVsPriorGuidanceRevenueStatus"]
    result["guidanceRevenueActual"] = result["priorGuidanceRevenueActual"]
    result["guidanceRevenueActualPeriod"] = result["priorGuidanceRevenueActualPeriod"]



def _confidence_rank(value: Any) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(str(value or "").lower(), 0)


def _guidance_is_usable(entry: Dict[str, Any]) -> bool:
    min_rank = _confidence_rank(GUIDANCE_MIN_CONFIDENCE_TO_USE)
    if min_rank <= 0:
        min_rank = 2
    return _confidence_rank(entry.get("confidence")) >= min_rank

def build_company_guidance(
    cik: str,
    submissions: Dict[str, Any],
    latest_quarter: Optional[str],
    latest_revenue: Any,
    revenue_by_quarter: Optional[Dict[str, Any]] = None,
    latest_period_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Best-effort company guidance parser from recent 8-K/6-K exhibits.

    V2.5 upgrades V1.7 with a deeper guidance engine:
    - 8-K / 6-K exhibit crawler over several years
    - multiple revenue guidance matches per document, including table-style outlooks
    - high/medium/low confidence scoring
    - debug snippets and parse stats for transparency

    Still conservative: actual-vs-prior-guide only uses medium/high confidence entries
    that match the latest actual quarter.
    """
    cache_key = f"{str(cik).zfill(10)}:{latest_quarter}:{latest_period_end}:{GUIDANCE_LOOKBACK_DAYS}:{GUIDANCE_MAX_FILINGS}:{GUIDANCE_MAX_DOCUMENTS_PER_FILING}"
    if cache_key in _GUIDANCE_RESULT_CACHE:
        return dict(_GUIDANCE_RESULT_CACHE[cache_key])

    result = _guidance_blank_result()
    candidates = _recent_8k_candidates(submissions)
    stats = {
        "filingsScanned": len(candidates),
        "documentsScanned": 0,
        "revenueMatches": 0,
        "highConfidence": 0,
        "mediumConfidence": 0,
        "lowConfidence": 0,
    }
    result["guidanceParseStats"] = stats
    if not candidates:
        _GUIDANCE_RESULT_CACHE[cache_key] = dict(result)
        return result

    revenue_entries: List[Dict[str, Any]] = []
    eps_entries: List[Dict[str, Any]] = []
    debug_rows: List[Dict[str, Any]] = []
    seen_revenue = set()
    seen_eps = set()

    for filing in candidates:
        accession = filing.get("accessionNumber")
        try:
            index_json = fetch_archive_index(cik, str(accession))
            docs = _candidate_guidance_documents(index_json, filing.get("primaryDocument"))
        except Exception:
            docs = [filing.get("primaryDocument")] if filing.get("primaryDocument") else []
        for doc_name in docs:
            if not doc_name:
                continue
            stats["documentsScanned"] += 1
            try:
                text = fetch_archive_document_text(cik, str(accession), str(doc_name))
            except Exception:
                continue

            revenue_matches = _extract_revenue_guidance_matches(text, filing.get("filingDate"))
            for revenue_g in revenue_matches:
                entry = _guidance_entry_from_match(filing, str(doc_name), revenue_g)
                key = (
                    entry.get("period"),
                    entry.get("filedDate"),
                    entry.get("sourceDocument"),
                    entry.get("midpoint"),
                    entry.get("confidence"),
                )
                if key in seen_revenue:
                    continue
                seen_revenue.add(key)
                revenue_entries.append(entry)
                stats["revenueMatches"] += 1
                conf = str(entry.get("confidence") or "low").lower()
                if conf == "high":
                    stats["highConfidence"] += 1
                elif conf == "medium":
                    stats["mediumConfidence"] += 1
                else:
                    stats["lowConfidence"] += 1
                debug_rows.append({
                    "period": entry.get("period"),
                    "filedDate": entry.get("filedDate"),
                    "sourceDocument": entry.get("sourceDocument"),
                    "midpoint": entry.get("midpoint"),
                    "low": entry.get("low"),
                    "high": entry.get("high"),
                    "confidence": entry.get("confidence"),
                    "confidenceReason": entry.get("confidenceReason"),
                    "textSnippet": entry.get("textSnippet"),
                })

            eps_g = _extract_eps_guidance(text, filing.get("filingDate"))
            if eps_g:
                eps_entry = {
                    "period": eps_g.get("period"),
                    "filedDate": filing.get("filingDate"),
                    "sourceDocument": str(doc_name),
                    "low": _round(eps_g.get("low"), 3),
                    "high": _round(eps_g.get("high"), 3),
                    "midpoint": _round(eps_g.get("midpoint"), 3),
                    "textSnippet": eps_g.get("textSnippet"),
                }
                key = (eps_entry.get("period"), eps_entry.get("filedDate"), eps_entry.get("sourceDocument"), eps_entry.get("midpoint"))
                if key not in seen_eps:
                    seen_eps.add(key)
                    eps_entries.append(eps_entry)

    if not revenue_entries and not eps_entries:
        result["guidanceParseStats"] = stats
        _GUIDANCE_RESULT_CACHE[cache_key] = dict(result)
        return result

    # Highest confidence first, then newest filing. This helps avoid grabbing a
    # random segment/ARR number ahead of a clear total revenue outlook.
    revenue_entries.sort(
        key=lambda e: (
            _confidence_rank(e.get("confidence")),
            1 if e.get("periodKey") else 0,
            str(e.get("filedDate") or ""),
            str(e.get("sourceDocument") or ""),
        ),
        reverse=True,
    )
    eps_entries.sort(key=lambda e: (str(e.get("filedDate") or ""), str(e.get("sourceDocument") or "")), reverse=True)

    usable_revenue_entries = [e for e in revenue_entries if _guidance_is_usable(e)]

    result["companyGuidanceConnected"] = bool(usable_revenue_entries or eps_entries)
    result["companyGuidanceStatus"] = (
        "V2.5 guidance engine parsed SEC 8-K/6-K exhibits with confidence scoring; "
        "only medium/high confidence revenue guidance is used for comparison"
    )
    # Keep full-ish history for debug but avoid bloating the response too much.
    result["guidanceHistory"] = usable_revenue_entries[:16]
    result["guidanceDebug"] = debug_rows[:24]
    result["guidanceParseStats"] = stats

    latest_key = _quarter_key(latest_quarter)
    latest_ord = _quarter_ordinal(latest_key)
    period_end_date = _parse_date_safe(latest_period_end)

    # Prior guidance: guidance issued before the latest actual period ended,
    # and specifically guiding the latest actual quarter.
    prior_match: Optional[Dict[str, Any]] = None
    if latest_key:
        matching = []
        for entry in usable_revenue_entries:
            if entry.get("periodKey") != latest_key:
                continue
            filed_date = _parse_date_safe(entry.get("filedDate"))
            # A guide filed after the actual quarter's period-end is usually
            # current-quarter commentary or a parser false positive.
            if period_end_date and filed_date and filed_date > period_end_date:
                continue
            matching.append(entry)
        if matching:
            # Prefer most recent pre-period-end guide among comparable confidence.
            matching.sort(key=lambda e: (_confidence_rank(e.get("confidence")), str(e.get("filedDate") or "")), reverse=True)
            prior_match = matching[0]

    _apply_prior_guidance_match(result, prior_match, latest_quarter, latest_revenue, revenue_by_quarter)

    # Forward guidance: most recent usable entry for a future period.
    next_match: Optional[Dict[str, Any]] = None
    if latest_ord is not None:
        future = []
        for entry in usable_revenue_entries:
            entry_ord = entry.get("periodOrdinal")
            if entry_ord is not None and entry_ord > latest_ord:
                future.append(entry)
        if future:
            future.sort(key=lambda e: (_confidence_rank(e.get("confidence")), str(e.get("filedDate") or "")), reverse=True)
            next_match = future[0]
    if next_match is None and usable_revenue_entries:
        # Display context only; this could be an annual guide or unclear period.
        for entry in usable_revenue_entries:
            if entry is not prior_match:
                next_match = entry
                break
        if next_match is None:
            next_match = usable_revenue_entries[0]
    _apply_forward_guidance_aliases(result, next_match)

    if prior_match is None and latest_quarter:
        if revenue_entries and not usable_revenue_entries:
            result["actualVsPriorGuidanceRevenueStatus"] = f"N/A: only low-confidence guidance candidates found for {latest_quarter}"
        else:
            result["actualVsPriorGuidanceRevenueStatus"] = f"N/A: no medium/high confidence prior guidance found for {latest_quarter}"

    if eps_entries:
        eps = eps_entries[0]
        result["nextCompanyGuidanceEps"] = eps.get("midpoint")
        result["nextCompanyGuidanceEpsLow"] = eps.get("low")
        result["nextCompanyGuidanceEpsHigh"] = eps.get("high")
        result["nextCompanyGuidanceEpsPeriod"] = eps.get("period")
        # Backward-compatible aliases.
        result["companyGuidanceEps"] = eps.get("midpoint")
        result["companyGuidanceEpsLow"] = eps.get("low")
        result["companyGuidanceEpsHigh"] = eps.get("high")
        result["companyGuidanceEpsPeriod"] = eps.get("period")

    _GUIDANCE_RESULT_CACHE[cache_key] = dict(result)
    return result

def data_quality(freshness_days: Optional[int], has_core_data: bool) -> Tuple[str, List[str]]:
    if not has_core_data:
        return "insufficient", ["SEC companyfacts ไม่มี revenue/net income/EPS ที่ใช้ให้คะแนน"]
    if freshness_days is None:
        return "unknown", ["ไม่พบ filing date ล่าสุดจาก SEC submissions"]
    if freshness_days <= 180:
        return "high", []
    if freshness_days <= 365:
        return "aging", [f"SEC filing ล่าสุดอายุ {freshness_days} วัน: ใช้ได้แต่ลดความมั่นใจ"]
    return "stale", [f"SEC filing ล่าสุดอายุ {freshness_days} วัน: ห้ามให้ Strong/Weak จาก fundamental"]


def build_sec_fundamental(symbol: str, latest: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    symbol = symbol.strip().upper()
    if _is_probably_etf(symbol, latest):
        return {
            "assetType": "ETF_OR_FUND",
            "fundamentalSource": "SEC EDGAR skipped: ETF/fund needs separate ETF module",
            "fundamentalDataQuality": "not_applicable",
            "warnings": ["ETF/fund ไม่ควรใช้ stock fundamental score แบบบริษัททั่วไป"],
        }

    company = company_for_symbol(symbol)
    if not company:
        return {
            "assetType": "NON_US_OR_NOT_IN_SEC_MAP",
            "fundamentalSource": "SEC EDGAR: ticker not found in SEC ticker map",
            "fundamentalDataQuality": "not_available",
            "warnings": ["ไม่พบ ticker ใน SEC map: อาจเป็น non-US, ETF, หรือ ticker mapping ยังไม่ตรง"],
        }

    cik = str(company.get("cik")).zfill(10)
    facts = fetch_companyfacts(cik)
    submissions = fetch_submissions(cik)
    filing = latest_filing_meta(submissions)

    audit: Dict[str, Any] = {}
    revenue, audit["revenue"] = flow_metric(facts, "revenue", ["USD"])
    revenue_by_quarter = quarter_value_map(facts, "revenue", ["USD"])
    gross_profit, audit["grossProfit"] = flow_metric(facts, "gross_profit", ["USD"])
    operating_income, audit["operatingIncome"] = flow_metric(facts, "operating_income", ["USD"])
    net_income, audit["netIncome"] = flow_metric(facts, "net_income", ["USD"], earnings_mode=True)
    eps, audit["epsDiluted"] = flow_metric(facts, "eps_diluted", ["USD/shares"], earnings_mode=True)
    operating_cf, audit["operatingCashFlow"] = flow_metric(facts, "operating_cf", ["USD"])
    capex, audit["capex"] = flow_metric(facts, "capex", ["USD"])
    weighted_shares, audit["weightedAvgDilutedShares"] = flow_metric(facts, "weighted_avg_diluted_shares", ["shares"])

    assets, audit["assets"] = instant_metric(facts, "assets", ["USD"])
    liabilities, audit["liabilities"] = instant_metric(facts, "liabilities", ["USD"])
    equity, audit["equity"] = instant_metric(facts, "equity", ["USD"])
    cash, audit["cash"] = instant_metric(facts, "cash", ["USD"])
    shares_out, audit["sharesOutstanding"] = instant_metric(facts, "shares_outstanding", ["shares"])
    debt_total, audit["debtTotal"] = instant_metric(facts, "debt_total", ["USD"])
    debt_current, audit["debtCurrent"] = instant_metric(facts, "debt_current", ["USD"])
    debt_noncurrent, audit["debtNoncurrent"] = instant_metric(facts, "debt_noncurrent", ["USD"])

    if debt_total and debt_total.get("value") is not None:
        total_debt = float(debt_total["value"])
    else:
        has_debt_parts = bool(debt_current or debt_noncurrent)
        total_debt = (
            (float(debt_current["value"]) if debt_current and debt_current.get("value") is not None else 0.0)
            + (float(debt_noncurrent["value"]) if debt_noncurrent and debt_noncurrent.get("value") is not None else 0.0)
        ) if has_debt_parts else None

    revenue_value = revenue.get("value")
    gross_profit_value = gross_profit.get("value")
    operating_income_value = operating_income.get("value")
    net_income_value = net_income.get("value")
    operating_cf_value = operating_cf.get("value")
    capex_value = capex.get("value")

    free_cash_flow = None
    if operating_cf_value is not None and capex_value is not None:
        free_cash_flow = float(operating_cf_value) - abs(float(capex_value))

    latest_quarter = revenue.get("quarter") or net_income.get("quarter") or eps.get("quarter")
    period_end = filing.get("periodEnd") or revenue.get("date") or net_income.get("date") or eps.get("date")
    next_quarter_end, days_to_next_quarter = next_quarter_end_from_period_end(period_end)
    filing_date = filing.get("filingDate") or revenue.get("filed") or net_income.get("filed") or eps.get("filed")
    form_type = filing.get("formType") or revenue.get("form") or net_income.get("form") or eps.get("form")
    freshness_days = _days_ago(filing_date)
    has_core_data = any(v is not None for v in [revenue_value, net_income_value, eps.get("value")])
    quality, warnings = data_quality(freshness_days, has_core_data)

    if revenue.get("derived"):
        warnings.append(f"Revenue {latest_quarter} derived by {revenue.get('derived')}")
    if net_income.get("derived"):
        warnings.append(f"Net income {latest_quarter} derived by {net_income.get('derived')}")
    if form_type in {"20-F", "40-F"}:
        warnings.append("Foreign issuer form: SEC data may be annual/less comparable than US 10-Q/10-K")

    guidance: Dict[str, Any]
    try:
        guidance = build_company_guidance(cik, submissions, latest_quarter, revenue_value, revenue_by_quarter, period_end)
    except Exception as exc:
        guidance = {
            "companyGuidanceConnected": False,
            "companyGuidanceSource": "SEC 8-K/6-K exhibit parser",
            "companyGuidanceStatus": f"Guidance parser error: {str(exc)[:140]}",
            "companyGuidanceRevenue": None,
            "companyGuidanceRevenueLow": None,
            "companyGuidanceRevenueHigh": None,
            "companyGuidanceRevenuePeriod": None,
            "companyGuidanceRevenueFiledDate": None,
            "companyGuidanceRevenueSourceDocument": None,
            "companyGuidanceRevenueSnippet": None,
            "guidanceRevenueDeltaPct": None,
            "guidanceRevenueDeltaStatus": "N/A: parser error",
            "guidanceRevenueActual": None,
            "guidanceRevenueActualPeriod": None,
            "companyGuidanceEps": None,
            "companyGuidanceEpsLow": None,
            "companyGuidanceEpsHigh": None,
            "companyGuidanceEpsPeriod": None,
            "guidanceHistory": [],
            "guidanceDebug": [],
            "guidanceParseStats": {"filingsScanned": 0, "documentsScanned": 0, "revenueMatches": 0, "highConfidence": 0, "mediumConfidence": 0, "lowConfidence": 0},
            "priorCompanyGuidanceRevenue": None,
            "priorCompanyGuidanceRevenueLow": None,
            "priorCompanyGuidanceRevenueHigh": None,
            "priorCompanyGuidanceRevenuePeriod": None,
            "priorCompanyGuidanceRevenueFiledDate": None,
            "priorCompanyGuidanceRevenueSourceDocument": None,
            "priorCompanyGuidanceRevenueSnippet": None,
            "priorCompanyGuidanceRevenueConfidence": None,
            "priorCompanyGuidanceRevenueConfidenceReason": None,
            "priorGuidanceRevenueActual": None,
            "priorGuidanceRevenueActualPeriod": None,
            "actualVsPriorGuidanceRevenuePct": None,
            "actualVsPriorGuidanceRevenueStatus": "N/A: parser error",
            "nextCompanyGuidanceRevenue": None,
            "nextCompanyGuidanceRevenueLow": None,
            "nextCompanyGuidanceRevenueHigh": None,
            "nextCompanyGuidanceRevenuePeriod": None,
            "nextCompanyGuidanceRevenueFiledDate": None,
            "nextCompanyGuidanceRevenueSourceDocument": None,
            "nextCompanyGuidanceRevenueSnippet": None,
            "nextCompanyGuidanceRevenueConfidence": None,
            "nextCompanyGuidanceRevenueConfidenceReason": None,
            "nextCompanyGuidanceEps": None,
            "nextCompanyGuidanceEpsLow": None,
            "nextCompanyGuidanceEpsHigh": None,
            "nextCompanyGuidanceEpsPeriod": None,
        }

    equity_value = equity.get("value") if equity else None
    cash_value = cash.get("value") if cash else None

    out = {
        "assetType": "STOCK",
        "ticker": symbol,
        "cik": cik,
        "companyName": company.get("companyName"),
        "secExchange": company.get("exchange"),
        "latestQuarter": latest_quarter,
        "earningsDate": period_end,  # UI label changed to Period End in V1.4.
        "periodEnd": period_end,
        "nextQuarterEndDate": next_quarter_end,
        "daysToNextQuarter": days_to_next_quarter,
        "latestFilingDate": filing_date,
        "formType": form_type,
        "dataFreshnessDays": freshness_days,
        "fundamentalDataQuality": quality,
        "warnings": warnings,
        "revenue": _round(revenue_value, 0),
        "revenuePrevQuarter": _round(revenue.get("prevValue"), 0),
        "revenuePrevQuarterLabel": revenue.get("prevQuarter"),
        "revenueYearAgo": _round(revenue.get("yearAgoValue"), 0),
        "revenueYearAgoLabel": revenue.get("yearAgoQuarter"),
        "revenueQoQ": _round(revenue.get("qoq"), 2),
        "revenueYoY": _round(revenue.get("yoy"), 2),
        "grossProfit": _round(gross_profit_value, 0),
        "grossMargin": _round(_div_pct(gross_profit_value, revenue_value), 2),
        "operatingIncome": _round(operating_income_value, 0),
        "operatingMargin": _round(_div_pct(operating_income_value, revenue_value), 2),
        "netIncome": _round(net_income_value, 0),
        "netIncomePrevQuarter": _round(net_income.get("prevValue"), 0),
        "netIncomePrevQuarterLabel": net_income.get("prevQuarter"),
        "netIncomeYearAgo": _round(net_income.get("yearAgoValue"), 0),
        "netIncomeYearAgoLabel": net_income.get("yearAgoQuarter"),
        "profitQoQ": _round(net_income.get("qoq"), 2),
        "profitQoQStatus": net_income.get("qoqStatus"),
        "profitYoY": _round(net_income.get("yoy"), 2),
        "profitYoYStatus": net_income.get("yoyStatus"),
        "netMargin": _round(_div_pct(net_income_value, revenue_value), 2),
        "eps": _round(eps.get("value"), 3),
        "epsPrevQuarter": _round(eps.get("prevValue"), 3),
        "epsPrevQuarterLabel": eps.get("prevQuarter"),
        "epsYearAgo": _round(eps.get("yearAgoValue"), 3),
        "epsYearAgoLabel": eps.get("yearAgoQuarter"),
        "epsQoQ": _round(eps.get("qoq"), 2),
        "epsQoQStatus": eps.get("qoqStatus"),
        "epsYoY": _round(eps.get("yoy"), 2),
        "epsYoYStatus": eps.get("yoyStatus"),
        "cash": _round(cash_value, 0),
        "assets": _round(assets.get("value") if assets else None, 0),
        "liabilities": _round(liabilities.get("value") if liabilities else None, 0),
        "stockholdersEquity": _round(equity_value, 0),
        "totalDebt": _round(total_debt, 0),
        "debtToEquity": _round(_div_ratio(total_debt, equity_value), 2),
        "cashToDebt": _round(_div_ratio(cash_value, total_debt), 2),
        "operatingCashFlow": _round(operating_cf_value, 0),
        "capex": _round(capex_value, 0),
        "freeCashFlow": _round(free_cash_flow, 0),
        "fcfMargin": _round(_div_pct(free_cash_flow, revenue_value), 2),
        "sharesOutstanding": _round(shares_out.get("value") if shares_out else None, 0),
        "weightedAvgDilutedShares": _round(weighted_shares.get("value"), 0),
        "tagAudit": audit,
        "fundamentalSource": "SEC EDGAR companyfacts + submissions",
    }
    out.update(guidance)
    if guidance.get("companyGuidanceConnected"):
        warnings.append(str(guidance.get("companyGuidanceStatus") or "Company guidance found"))
    return out


def score_sec_fundamental(f: Dict[str, Any]) -> Tuple[Optional[int], str, List[str]]:
    quality = f.get("fundamentalDataQuality")
    if f.get("assetType") == "ETF_OR_FUND":
        return None, "ETF module required", ["ETF/fund แยก scoring ต่างหาก ไม่ใช้ fundamental score ของหุ้น"]
    if quality in {"not_available", "not_applicable", "insufficient", "error"}:
        return None, "Insufficient SEC data", (f.get("warnings") or ["SEC data ไม่พอสำหรับให้คะแนน"])
    if quality == "stale":
        return None, "Fundamental data stale", (f.get("warnings") or ["ข้อมูล SEC เก่าเกิน 365 วัน"])

    score = 0.0
    possible = 0.0
    reasons: List[str] = []

    latest_q = f.get("latestQuarter") or "latest quarter"
    filing_bits = ["ที่มา: SEC EDGAR companyfacts"]
    if f.get("formType"):
        filing_bits.append(str(f.get("formType")))
    if f.get("latestFilingDate"):
        filing_bits.append(f"filed {f.get('latestFilingDate')}")
    if f.get("periodEnd"):
        filing_bits.append(f"period end {f.get('periodEnd')}")
    source_note = ", ".join(filing_bits)

    def is_num(value: Any) -> bool:
        try:
            return value is not None and math.isfinite(float(value))
        except Exception:
            return False

    def fmt_money(value: Any) -> str:
        if not is_num(value):
            return "N/A"
        v = float(value)
        sign = "-" if v < 0 else ""
        av = abs(v)
        if av >= 1_000_000_000_000:
            return f"{sign}{av / 1_000_000_000_000:.2f}T"
        if av >= 1_000_000_000:
            return f"{sign}{av / 1_000_000_000:.2f}B"
        if av >= 1_000_000:
            return f"{sign}{av / 1_000_000:.2f}M"
        if av >= 1_000:
            return f"{sign}{av / 1_000:.2f}K"
        return f"{sign}{av:.2f}"

    def fmt_eps(value: Any) -> str:
        if not is_num(value):
            return "N/A"
        return f"{float(value):+.3f}"

    def fmt_pct(value: Any) -> str:
        if not is_num(value):
            return "N/A"
        return f"{float(value):+.1f}%"

    def growth_word(v: float, strong: float = 20.0) -> str:
        if v >= strong:
            return "โตแรง"
        if v > 0:
            return "เป็นบวก"
        if v == 0:
            return "ทรงตัว"
        return "หดตัว"

    def earnings_status_th(status: Any, pct_value: float) -> str:
        mapping = {
            "Loss narrowed": "ขาดทุนลดลง",
            "Loss widened": "ขาดทุนเพิ่มขึ้น",
            "Loss flat": "ขาดทุนทรงตัว",
            "Turned profitable": "พลิกเป็นกำไร",
            "Turned to loss": "พลิกเป็นขาดทุน",
            "Profit increased": "กำไรเพิ่มขึ้น",
            "Profit decreased": "กำไรลดลง",
            "Profit flat": "กำไรทรงตัว",
        }
        if status in mapping:
            return mapping[status]
        return growth_word(pct_value)

    def add_growth(metric: str, value: Any, max_points: int, current_field: str, compare_field: str,
                   compare_label_field: str, value_kind: str = "money", status_field: Optional[str] = None) -> None:
        nonlocal score, possible
        if value is None:
            reasons.append(f"{metric}: N/A — SEC companyfacts ยังไม่มีค่าปัจจุบันหรือค่าเทียบช่วงก่อนหน้าที่ match ได้")
            return
        possible += max_points
        v = float(value)
        pts = max(0.0, min(float(max_points), (v + 10.0) / 40.0 * max_points))
        score += pts
        current_value = f.get(current_field)
        compare_value = f.get(compare_field)
        compare_label = f.get(compare_label_field) or "ช่วงเปรียบเทียบ"
        formatter = fmt_eps if value_kind == "eps" else fmt_money
        status_text = earnings_status_th(f.get(status_field), v) if status_field else growth_word(v)
        reasons.append(
            f"{metric} {status_text} จาก {formatter(compare_value)} ใน {compare_label} "
            f"เป็น {formatter(current_value)} ใน {latest_q} ({fmt_pct(v)}) — {source_note}"
        )

    def add_margin(metric: str, value: Any, max_points: int, strong_level: float, numerator_field: str) -> None:
        nonlocal score, possible
        if value is None:
            reasons.append(f"{metric}: N/A — SEC companyfacts ไม่มี numerator หรือ revenue ที่ใช้คำนวณ margin")
            return
        possible += max_points
        v = float(value)
        pts = max(0.0, min(float(max_points), (v + 5.0) / (strong_level + 5.0) * max_points))
        score += pts
        if v >= strong_level:
            label = "แข็งแรง"
        elif v > 0:
            label = "เป็นบวก"
        elif v == 0:
            label = "ทรงตัว"
        else:
            label = "ติดลบ"
        reasons.append(
            f"{metric} {label}ที่ {v:.1f}% โดยคำนวณจาก {fmt_money(f.get(numerator_field))} "
            f"หารด้วย revenue {fmt_money(f.get('revenue'))} ใน {latest_q} — {source_note}"
        )

    def add_positive(metric: str, value: Any, max_points: int) -> None:
        nonlocal score, possible
        if value is None:
            reasons.append(f"{metric}: N/A — SEC companyfacts ไม่มี operating cash flow หรือ capex ที่ใช้คำนวณ FCF")
            return
        possible += max_points
        v = float(value)
        if v > 0:
            score += max_points
            label = "เป็นบวก"
        elif v == 0:
            label = "ทรงตัว"
        else:
            label = "ติดลบ"
        reasons.append(
            f"{metric} {label}ที่ {fmt_money(v)} จาก operating cash flow {fmt_money(f.get('operatingCashFlow'))} "
            f"และ capex {fmt_money(f.get('capex'))} ใน {latest_q} — {source_note}"
        )

    def add_leverage(metric: str, value: Any, max_points: int) -> None:
        nonlocal score, possible
        if value is None:
            reasons.append(f"{metric}: N/A — SEC companyfacts ไม่มี total debt หรือ stockholders' equity ที่ใช้คำนวณ")
            return
        possible += max_points
        v = float(value)
        if v < 0:
            pts = 0
            label = "ผิดปกติ/ตรวจสอบเพิ่ม"
        elif v <= 0.5:
            pts = max_points
            label = "ต่ำและแข็งแรง"
        elif v <= 1.0:
            pts = max_points * 0.8
            label = "ยังคุมได้"
        elif v <= 2.0:
            pts = max_points * 0.45
            label = "เริ่มสูง"
        else:
            pts = max_points * 0.15
            label = "สูง"
        score += pts
        reasons.append(
            f"{metric} {label}ที่ {v:.2f}x จาก total debt {fmt_money(f.get('totalDebt'))} "
            f"เทียบกับ equity {fmt_money(f.get('stockholdersEquity'))} ณ {f.get('periodEnd') or latest_q} — {source_note}"
        )

    add_growth("Revenue YoY", f.get("revenueYoY"), 22, "revenue", "revenueYearAgo", "revenueYearAgoLabel", "money")
    add_growth("Revenue QoQ", f.get("revenueQoQ"), 8, "revenue", "revenuePrevQuarter", "revenuePrevQuarterLabel", "money")
    add_growth("EPS YoY", f.get("epsYoY"), 15, "eps", "epsYearAgo", "epsYearAgoLabel", "eps", "epsYoYStatus")
    add_growth("Net income YoY", f.get("profitYoY"), 10, "netIncome", "netIncomeYearAgo", "netIncomeYearAgoLabel", "money", "profitYoYStatus")
    add_margin("Gross margin", f.get("grossMargin"), 15, 50.0, "grossProfit")
    add_margin("Operating margin", f.get("operatingMargin"), 10, 25.0, "operatingIncome")
    add_margin("Net margin", f.get("netMargin"), 10, 20.0, "netIncome")
    add_positive("Free cash flow", f.get("freeCashFlow"), 10)
    add_leverage("Debt/Equity", f.get("debtToEquity"), 10)

    if possible == 0:
        return None, "Insufficient SEC data", ["SEC companyfacts ไม่มี metric ที่ใช้ให้คะแนน"]

    final = int(round(score / possible * 100))
    if final >= 80:
        signal = "Fundamental Strong"
    elif final >= 65:
        signal = "Solid / Watch"
    elif final >= 50:
        signal = "Mixed"
    else:
        signal = "Weak / Avoid"

    if quality == "aging":
        signal = f"{signal} / Data aging"
        reasons = (f.get("warnings") or []) + reasons

    return final, signal, reasons[:10]

def build_fundamental_sec_v1(symbol: str, latest: Optional[Dict[str, Any]] = None, include: bool = True) -> Dict[str, Any]:
    if not include:
        return {
            "fundamentalScore": None,
            "fundamentalSignal": "Fundamentals disabled",
            "fundamentalReasons": ["ตั้ง INCLUDE_FUNDAMENTALS=1 เพื่อเปิดข้อมูลพื้นฐาน"],
            "fundamentalSource": "Disabled",
        }

    try:
        f = build_sec_fundamental(symbol, latest)
    except Exception as exc:
        f = {
            "assetType": "ERROR",
            "fundamentalSource": "SEC EDGAR error",
            "fundamentalDataQuality": "error",
            "warnings": [f"SEC fetch/normalize error: {str(exc)[:180]}"],
        }

    # Frontend-compatible fields. V1 deliberately leaves estimates/targets null.
    f.setdefault("estimatedRevenue", None)
    f.setdefault("estimatedRevenueStatus", "V2: analyst consensus จะดึงแบบ on-demand ผ่าน Alpha Vantage")
    f.setdefault("estimatedNetIncome", None)
    f.setdefault("profitSurprisePct", None)
    f.setdefault("estimatedEps", None)
    f.setdefault("estimatedEpsStatus", "V2: analyst consensus จะดึงแบบ on-demand ผ่าน Alpha Vantage")
    f.setdefault("epsSurprisePct", None)
    f.setdefault("targetLowPrice", None)
    f.setdefault("targetMeanPrice", None)
    f.setdefault("targetMedianPrice", None)
    f.setdefault("targetHighPrice", None)
    f.setdefault("targetUpsidePct", None)
    f.setdefault("targetAnalystCount", None)
    f.setdefault("priceTargetConnected", False)
    f.setdefault("priceTargetStatus", "V2 only: Alpha Vantage on-demand, not fetched in SEC V1")
    f.setdefault("daysToNextQuarter", None)
    f.setdefault("nextQuarterEndDate", None)
    f.setdefault("companyGuidanceConnected", False)
    f.setdefault("companyGuidanceRevenue", None)
    f.setdefault("companyGuidanceRevenueLow", None)
    f.setdefault("companyGuidanceRevenueHigh", None)
    f.setdefault("companyGuidanceRevenuePeriod", None)
    f.setdefault("companyGuidanceRevenueFiledDate", None)
    f.setdefault("companyGuidanceRevenueSourceDocument", None)
    f.setdefault("companyGuidanceStatus", "No company guidance parsed from SEC 8-K/6-K exhibits")
    f.setdefault("guidanceRevenueDeltaPct", None)
    f.setdefault("guidanceRevenueDeltaStatus", "N/A: no comparable company guidance")
    f.setdefault("guidanceRevenueActual", None)
    f.setdefault("guidanceRevenueActualPeriod", None)
    f.setdefault("companyGuidanceEps", None)
    f.setdefault("companyGuidanceEpsLow", None)
    f.setdefault("companyGuidanceEpsHigh", None)
    f.setdefault("companyGuidanceEpsPeriod", None)
    f.setdefault("guidanceHistory", [])
    f.setdefault("guidanceDebug", [])
    f.setdefault("guidanceParseStats", {"filingsScanned": 0, "documentsScanned": 0, "revenueMatches": 0, "highConfidence": 0, "mediumConfidence": 0, "lowConfidence": 0})
    f.setdefault("priorCompanyGuidanceRevenue", None)
    f.setdefault("priorCompanyGuidanceRevenueLow", None)
    f.setdefault("priorCompanyGuidanceRevenueHigh", None)
    f.setdefault("priorCompanyGuidanceRevenuePeriod", None)
    f.setdefault("priorCompanyGuidanceRevenueFiledDate", None)
    f.setdefault("priorCompanyGuidanceRevenueSourceDocument", None)
    f.setdefault("priorCompanyGuidanceRevenueSnippet", None)
    f.setdefault("priorCompanyGuidanceRevenueConfidence", None)
    f.setdefault("priorCompanyGuidanceRevenueConfidenceReason", None)
    f.setdefault("priorGuidanceRevenueActual", None)
    f.setdefault("priorGuidanceRevenueActualPeriod", None)
    f.setdefault("actualVsPriorGuidanceRevenuePct", None)
    f.setdefault("actualVsPriorGuidanceRevenueStatus", "N/A: no prior guidance matched to latest actual quarter")
    f.setdefault("nextCompanyGuidanceRevenue", None)
    f.setdefault("nextCompanyGuidanceRevenueLow", None)
    f.setdefault("nextCompanyGuidanceRevenueHigh", None)
    f.setdefault("nextCompanyGuidanceRevenuePeriod", None)
    f.setdefault("nextCompanyGuidanceRevenueFiledDate", None)
    f.setdefault("nextCompanyGuidanceRevenueSourceDocument", None)
    f.setdefault("nextCompanyGuidanceRevenueSnippet", None)
    f.setdefault("nextCompanyGuidanceRevenueConfidence", None)
    f.setdefault("nextCompanyGuidanceRevenueConfidenceReason", None)
    f.setdefault("nextCompanyGuidanceEps", None)
    f.setdefault("nextCompanyGuidanceEpsLow", None)
    f.setdefault("nextCompanyGuidanceEpsHigh", None)
    f.setdefault("nextCompanyGuidanceEpsPeriod", None)

    score, signal, reasons = score_sec_fundamental(f)
    f["fundamentalScore"] = score
    f["fundamentalSignal"] = signal
    f["fundamentalReasons"] = reasons

    highlights: List[str] = []
    if f.get("latestFilingDate"):
        highlights.append(f"SEC filing: {f.get('formType') or 'N/A'} filed {f.get('latestFilingDate')}")
    if f.get("dataFreshnessDays") is not None:
        highlights.append(f"Data freshness: {f.get('dataFreshnessDays')} days")
    if f.get("revenueYoY") is not None:
        highlights.append(f"Revenue YoY: {f['revenueYoY']:+.2f}%")
    if f.get("revenueQoQ") is not None:
        highlights.append(f"Revenue QoQ: {f['revenueQoQ']:+.2f}%")
    if f.get("priorCompanyGuidanceRevenue") is not None:
        gp = f.get("priorCompanyGuidanceRevenuePeriod") or "period N/A"
        highlights.append(f"Prior company revenue guidance for {gp}: {f['priorCompanyGuidanceRevenue']:,.0f} midpoint")
    if f.get("actualVsPriorGuidanceRevenuePct") is not None:
        highlights.append(f"Actual vs prior company guidance: {f['actualVsPriorGuidanceRevenuePct']:+.2f}%")
    if f.get("nextCompanyGuidanceRevenue") is not None:
        gp = f.get("nextCompanyGuidanceRevenuePeriod") or "period N/A"
        highlights.append(f"Next company revenue guidance: {f['nextCompanyGuidanceRevenue']:,.0f} midpoint for {gp}")
    if f.get("profitQoQ") is not None:
        status = f.get("profitQoQStatus")
        suffix = f" ({status})" if status else ""
        highlights.append(f"Net income QoQ: {f['profitQoQ']:+.2f}%{suffix}")
    if f.get("profitYoY") is not None:
        status = f.get("profitYoYStatus")
        suffix = f" ({status})" if status else ""
        highlights.append(f"Net income YoY: {f['profitYoY']:+.2f}%{suffix}")
    if f.get("grossMargin") is not None:
        highlights.append(f"Gross margin: {f['grossMargin']:.2f}%")
    if f.get("freeCashFlow") is not None:
        highlights.append(f"Free cash flow: {f['freeCashFlow']:,.0f}")
    for warning in f.get("warnings") or []:
        highlights.append(str(warning))
    if not highlights:
        highlights.append("SEC V1 ยังไม่มีข้อมูลพอสำหรับ ticker นี้")
    f["fundamentalHighlights"] = highlights[:10]
    return f


if __name__ == "__main__":
    # Simple manual test for IDLE: Run Module (F5).
    symbols = ["NVDA", "HOOD", "TMDX", "ASTS", "JEPQ", "TSM"]
    for s in symbols:
        print("=" * 80)
        print(s)
        result = build_fundamental_sec_v1(s, latest={}, include=True)
        keep = {
            k: result.get(k)
            for k in [
                "fundamentalSignal", "fundamentalScore", "fundamentalSource", "fundamentalDataQuality",
                "latestQuarter", "periodEnd", "latestFilingDate", "formType",
                "revenue", "revenueYoY", "revenueQoQ", "grossMargin", "netIncome", "eps",
                "freeCashFlow", "totalDebt", "debtToEquity", "priorCompanyGuidanceRevenue",
                "priorCompanyGuidanceRevenuePeriod", "actualVsPriorGuidanceRevenuePct",
                "nextCompanyGuidanceRevenue", "nextCompanyGuidanceRevenuePeriod", "priceTargetStatus",
            ]
        }
        print(json.dumps(keep, ensure_ascii=False, indent=2))
        if result.get("fundamentalReasons"):
            print("Reasons:", " | ".join(map(str, result["fundamentalReasons"])))
