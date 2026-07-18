from __future__ import annotations

import hashlib
import html
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

UTC = timezone.utc
DEFAULT_USER_AGENT = os.environ.get(
    "ATTENTION_NEWS_USER_AGENT",
    "Stock Timing Radar news monitor contact@users.noreply.github.com",
).strip()
OFFLINE = os.environ.get("STOCKCHECK_ATTENTION_OFFLINE", "").lower() in {"1", "true", "yes"}
AMBIGUOUS_TICKERS = {"BEAM", "COST", "MP", "NASA", "NOW", "OPEN", "RR", "SYM", "TE", "TEM", "TMC"}
TRACKING_QUERY_KEYS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid", "ref", "source"}
LEGAL_SUFFIXES = re.compile(r"\b(incorporated|inc\.?|corporation|corp\.?|limited|ltd\.?|plc|n\.v\.?|group|holdings?|company|co\.?)\b", re.I)

CLASSIFICATION_RULES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("capital_raise", "corporate_event", "high", ("public offering", "registered direct", "private placement", "at-the-market", "atm offering", "shelf registration", "prospectus", "convertible note", "warrant offering")),
    ("guidance", "earnings", "high", ("guidance", "outlook", "forecast", "raises full-year", "cuts full-year")),
    ("earnings_reported", "earnings", "high", ("quarterly results", "financial results", "reports results", "earnings release", "revenue for the quarter")),
    ("transaction", "corporate_event", "high", ("acquire", "acquisition", "merger", "strategic alternatives", "takeover", "sale of the company")),
    ("material_agreement", "corporate_event", "medium", ("contract award", "awarded a contract", "new contract", "purchase order", "defense contract", "strategic partnership", "definitive agreement")),
    ("management_change", "corporate_event", "medium", ("appoints chief", "names chief", "chief executive officer", "chief financial officer", "resigns", "steps down", "board appointment")),
    ("regulatory", "regulatory", "high", ("fda approval", "fda clearance", "faa approval", "nrc approval", "regulatory approval", "antitrust", "department of justice", "federal trade commission", "investigation")),
    ("litigation", "litigation", "medium", ("lawsuit", "class action", "subpoena", "settlement", "legal action")),
    ("product", "corporate_event", "low", ("product launch", "launches", "clinical trial", "phase 1", "phase 2", "phase 3", "commercial launch")),
)
SUBTYPE_GROUPS = {"contract": "material_agreement", "partnership": "material_agreement", "material_agreement": "material_agreement", "m_and_a": "transaction", "transaction": "transaction", "earnings": "earnings_reported", "earnings_reported": "earnings_reported", "guidance": "guidance"}


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_text(value: Any) -> str:
    text = html.unescape(str(value or "")).lower()
    text = re.sub(r"https?://\S+", " ", text)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def compact_company_name(value: str) -> str:
    return " ".join(re.sub(r"[^A-Za-z0-9]+", " ", LEGAL_SUFFIXES.sub(" ", value)).split())


def canonical_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urllib.parse.urlsplit(raw)
        query = [(k, v) for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in TRACKING_QUERY_KEYS]
        path = re.sub(r"/{2,}", "/", parsed.path or "/")
        return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path.rstrip("/") or "/", urllib.parse.urlencode(query), ""))
    except Exception:
        return raw


def domain_from_url(value: Any) -> str:
    try:
        return urllib.parse.urlsplit(str(value or "")).netloc.lower().split(":", 1)[0]
    except Exception:
        return ""


def significant_tokens(value: str) -> set[str]:
    stop = {"the", "and", "for", "with", "from", "into", "after", "new", "announces", "reports", "company"}
    return {token for token in normalize_text(value).split() if len(token) >= 3 and token not in stop}


def headline_similarity(left: str, right: str) -> float:
    a, b = significant_tokens(left), significant_tokens(right)
    return len(a & b) / len(a | b) if a and b else 0.0


def stable_hash(*values: Any, size: int = 16) -> str:
    return hashlib.sha256("|".join(str(v or "") for v in values).encode("utf-8")).hexdigest()[:size]


def parse_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    candidates = [raw, raw.replace("Z", "+00:00")]
    if re.fullmatch(r"\d{14}", raw):
        candidates.insert(0, f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}T{raw[8:10]}:{raw[10:12]}:{raw[12:14]}+00:00")
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except Exception:
            pass
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except Exception:
            pass
    return None


def classify_headline(headline: str) -> dict[str, str]:
    normalized = normalize_text(headline)
    for subtype, event_type, materiality, phrases in CLASSIFICATION_RULES:
        if any(normalize_text(phrase) in normalized for phrase in phrases):
            return {"event_type": event_type, "event_subtype": subtype, "materiality": materiality, "summary": f"A {subtype.replace('_', ' ')} event was detected and requires source review."}
    return {"event_type": "news", "event_subtype": "general_news", "materiality": "low", "summary": "A company-related report was detected, but it did not match a material event category."}


def subtype_group(value: Any) -> str:
    subtype = str(value or "general_news")
    return SUBTYPE_GROUPS.get(subtype, subtype)


def materiality_rank(value: Any) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(str(value or "").lower(), 0)


def build_registry_entry(stock: dict[str, Any], overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    overrides = overrides or {}
    ticker = str(stock.get("ticker") or stock.get("symbol") or "").upper()
    name = str(stock.get("name") or ticker).strip()
    aliases: list[str] = []
    for candidate in [name, compact_company_name(name), *(overrides.get("aliases") or [])]:
        candidate = str(candidate or "").strip()
        if candidate and candidate.lower() not in {alias.lower() for alias in aliases}:
            aliases.append(candidate)
    if ticker and ticker not in AMBIGUOUS_TICKERS and len(ticker) >= 4:
        aliases.append(ticker)
    ir_urls = []
    for candidate in [stock.get("company_ir_url"), *(overrides.get("ir_urls") or [])]:
        candidate = canonical_url(candidate)
        if candidate and candidate not in ir_urls:
            ir_urls.append(candidate)
    domains = []
    for candidate in [*(overrides.get("domains") or []), *(domain_from_url(url) for url in ir_urls)]:
        candidate = str(candidate or "").lower().strip()
        if candidate and candidate not in domains:
            domains.append(candidate)
    return {"ticker": ticker, "name": name, "aliases": aliases, "domains": domains, "ir_urls": ir_urls, "ir_feeds": [canonical_url(url) for url in overrides.get("ir_feeds") or [] if canonical_url(url)], "disabled": bool(overrides.get("disabled")) or " etf" in f" {name.lower()}"}


def entity_confidence(headline: str, url: str, entry: dict[str, Any]) -> tuple[str, str]:
    normalized = normalize_text(headline)
    if not normalized:
        return "rejected", "empty headline"
    for alias in entry.get("aliases") or []:
        alias_norm = normalize_text(alias)
        if alias_norm and alias_norm in normalized:
            return "high", f"headline contains alias: {alias}"
    company_tokens = significant_tokens(compact_company_name(entry.get("name") or ""))
    overlap = company_tokens & significant_tokens(headline)
    if overlap and len(overlap) >= min(2, len(company_tokens)):
        return "medium", f"headline matched company tokens: {', '.join(sorted(overlap))}"
    domain = domain_from_url(url)
    if domain and any(domain == allowed or domain.endswith(f".{allowed}") for allowed in entry.get("domains") or []):
        return "medium", "article domain matches configured company domain"
    return "rejected", "company identity could not be resolved confidently"


def http_bytes(url: str, timeout: int = 18) -> bytes | None:
    if OFFLINE:
        return None
    request = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, text/html, application/json, */*"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except Exception as exc:
        print(f"::warning::news fetch failed {url}: {exc}")
        return None


def http_json(url: str, timeout: int = 18) -> dict[str, Any] | None:
    payload = http_bytes(url, timeout=timeout)
    if not payload:
        return None
    try:
        data = json.loads(payload.decode("utf-8"))
        return data if isinstance(data, dict) else None
    except Exception as exc:
        print(f"::warning::news JSON parse failed {url}: {exc}")
        return None
