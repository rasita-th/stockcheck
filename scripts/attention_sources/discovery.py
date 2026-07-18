from __future__ import annotations

import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from html.parser import HTMLParser
from typing import Any, Callable, Iterable

from .common import UTC, canonical_url, classify_headline, domain_from_url, entity_confidence, http_bytes, http_json, normalize_text, parse_datetime, stable_hash, subtype_group, utc_now


def _child_text(node: ET.Element, names: Iterable[str]) -> str:
    wanted = {name.lower() for name in names}
    for child in list(node):
        if child.tag.split("}")[-1].lower() in wanted:
            return "".join(child.itertext()).strip()
    return ""


def parse_feed(payload: bytes) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(payload)
    except Exception:
        return []
    entries: list[dict[str, Any]] = []
    for node in root.iter():
        if node.tag.split("}")[-1].lower() not in {"item", "entry"}:
            continue
        title, link = _child_text(node, ("title",)), _child_text(node, ("link",))
        if not link:
            for child in list(node):
                if child.tag.split("}")[-1].lower() == "link" and child.attrib.get("href"):
                    link = child.attrib["href"]
                    break
        if title and link:
            entries.append({"title": title, "url": canonical_url(link), "published_at": _child_text(node, ("pubdate", "published", "updated", "date")), "summary": _child_text(node, ("description", "summary", "content"))})
    return entries


class _LinkParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url, self.links, self.href, self.text = base_url, [], "", []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            values = {key.lower(): value or "" for key, value in attrs}
            self.href, self.text = urllib.parse.urljoin(self.base_url, values.get("href", "")), []

    def handle_data(self, data: str) -> None:
        if self.href:
            self.text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self.href:
            title = " ".join("".join(self.text).split())
            if title:
                self.links.append({"title": title, "url": canonical_url(self.href), "published_at": "", "summary": ""})
            self.href, self.text = "", []


def parse_ir_page(payload: bytes, base_url: str) -> list[dict[str, Any]]:
    try:
        parser = _LinkParser(base_url)
        parser.feed(payload.decode("utf-8", errors="replace"))
        return parser.links
    except Exception:
        return []


def build_event(ticker: str, headline: str, url: str, source_type: str, source_quality: str, published_at: Any, detected_at: datetime, confidence: str, confidence_reason: str, summary: str = "") -> dict[str, Any] | None:
    classification = classify_headline(headline)
    if classification["event_subtype"] == "general_news":
        return None
    event_time = (parse_datetime(published_at) or detected_at).astimezone(UTC).replace(microsecond=0).isoformat()
    canonical = canonical_url(url)
    source = {"type": source_type, "quality": source_quality, "url": canonical, "published_at": event_time, "domain": domain_from_url(canonical)}
    primary = source_quality == "primary"
    effective_materiality = classification["materiality"] if primary else "low"
    effective_urgency = "today" if primary else "developing"
    dedupe_key = f"{ticker}:{subtype_group(classification['event_subtype'])}:{event_time[:10]}:{stable_hash(normalize_text(headline), size=12)}"
    return {
        "event_id": f"{source_type}:{ticker}:{stable_hash(canonical or headline)}", "ticker": ticker,
        "event_type": classification["event_type"], "event_subtype": classification["event_subtype"],
        "headline": headline.strip(), "summary": summary.strip() or classification["summary"], "why_today": summary.strip() or classification["summary"],
        "materiality": effective_materiality, "reported_materiality": classification["materiality"], "urgency": effective_urgency,
        "event_time": event_time, "detected_at": detected_at.astimezone(UTC).replace(microsecond=0).isoformat(),
        "verification_status": "confirmed" if primary else "unverified", "verification_level": "confirmed_primary" if primary else "unverified_report",
        "verification_reason": "Published by a configured primary source." if primary else "Discovered in public news; primary source not yet matched.",
        "entity_confidence": confidence, "entity_confidence_reason": confidence_reason, "dedupe_key": dedupe_key,
        "source": source, "source_chain": [source], "secondary_source_count": 0 if primary else 1,
    }


def gdelt_query_url(entry: dict[str, Any], timespan: str = "24h", maxrecords: int = 20) -> str:
    aliases = [alias for alias in entry.get("aliases") or [] if len(alias) >= 4][:3]
    terms = [f'"{alias}"' for alias in aliases]
    params = {"query": f"({' OR '.join(terms)})", "mode": "artlist", "maxrecords": str(max(1, min(maxrecords, 50))), "timespan": timespan, "sort": "datedesc", "format": "json"}
    return "https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode(params)


def collect_gdelt(entry: dict[str, Any], old_state: dict[str, Any], fetch_json: Callable[[str], dict[str, Any] | None] = http_json, now: datetime | None = None, timespan: str = "24h", maxrecords: int = 20, bootstrap_hours: int = 6) -> tuple[list[dict[str, Any]], dict[str, Any], str, str | None]:
    now = now or utc_now()
    data = fetch_json(gdelt_query_url(entry, timespan, maxrecords))
    if not data:
        return [], old_state, "error", "GDELT response unavailable"
    rows = data.get("articles") or data.get("items") or []
    if not isinstance(rows, list):
        return [], old_state, "error", "GDELT article list is invalid"
    seen = {str(value) for value in old_state.get("seen_urls", []) if value}
    bootstrapping, cutoff, all_urls, events = not seen, now - timedelta(hours=max(0, bootstrap_hours)), [], []
    for row in rows[:maxrecords]:
        if not isinstance(row, dict):
            continue
        url, title = canonical_url(row.get("url") or row.get("external_url")), str(row.get("title") or "").strip()
        if not url or not title:
            continue
        all_urls.append(url)
        if url in seen:
            continue
        published = parse_datetime(row.get("seendate") or row.get("date") or row.get("published_at"))
        if bootstrapping and (published is None or published < cutoff):
            continue
        confidence, reason = entity_confidence(title, url, entry)
        if confidence == "rejected":
            continue
        event = build_event(entry["ticker"], title, url, "gdelt", "secondary", published or now, now, confidence, reason, "A potentially material public-news report was detected. Primary-source verification is pending.")
        if event:
            events.append(event)
    state = {"last_successful_check": now.astimezone(UTC).replace(microsecond=0).isoformat(), "seen_urls": list(dict.fromkeys(all_urls + list(seen)))[:250], "last_result_count": len(rows)}
    return events, state, "ok", None


def collect_ir(entry: dict[str, Any], old_state: dict[str, Any], fetch_bytes_fn: Callable[[str], bytes | None] = http_bytes, now: datetime | None = None, bootstrap_hours: int = 6) -> tuple[list[dict[str, Any]], dict[str, Any], str, str | None]:
    now = now or utc_now()
    sources = [(url, "feed") for url in entry.get("ir_feeds") or []] + [(url, "page") for url in entry.get("ir_urls") or []]
    if not sources:
        return [], old_state, "partial", "IR URL unavailable"
    seen = {str(value) for value in old_state.get("seen_urls", []) if value}
    bootstrapping, cutoff, all_urls, events, successes = not seen, now - timedelta(hours=max(0, bootstrap_hours)), [], [], 0
    for url, kind in sources[:3]:
        payload = fetch_bytes_fn(url)
        if not payload:
            continue
        successes += 1
        rows = parse_feed(payload) if kind == "feed" else parse_ir_page(payload, url)
        for row in rows[:120]:
            item_url, title = canonical_url(row.get("url")), str(row.get("title") or "").strip()
            if not item_url or not title:
                continue
            domain = domain_from_url(item_url)
            if entry.get("domains") and not any(domain == allowed or domain.endswith(f".{allowed}") for allowed in entry.get("domains") or []):
                continue
            all_urls.append(item_url)
            if item_url in seen:
                continue
            published = parse_datetime(row.get("published_at"))
            if bootstrapping and (kind == "page" or published is None or published < cutoff):
                continue
            confidence, reason = entity_confidence(title, item_url, entry)
            if confidence == "rejected":
                confidence, reason = "high", "configured company IR domain"
            event = build_event(entry["ticker"], title, item_url, "company_ir", "primary", published or now, now, confidence, reason, str(row.get("summary") or "").strip())
            if event:
                events.append(event)
    state = {"last_successful_check": now.astimezone(UTC).replace(microsecond=0).isoformat() if successes else old_state.get("last_successful_check"), "seen_urls": list(dict.fromkeys(all_urls + list(seen)))[:250], "configured_sources": len(sources), "successful_sources": successes}
    return events, state, "ok" if successes else "error", None if successes else "Configured IR sources were unavailable"
