from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from .common import UTC, build_registry_entry, entity_confidence, http_bytes, utc_now
from .discovery import build_event, parse_feed, parse_ir_page


@dataclass
class RegulatorCollectionResult:
    events: list[dict[str, Any]]
    state: dict[str, Any]
    health: dict[str, Any]
    errors: list[dict[str, str]]


def _rows(payload: bytes, source: dict[str, Any]) -> list[dict[str, Any]]:
    mode = str(source.get("mode") or "page").lower()
    return parse_feed(payload) if mode == "feed" else parse_ir_page(payload, str(source.get("url") or ""))


def collect_regulator_events(
    portfolio: list[dict[str, Any]],
    registry: dict[str, Any] | None,
    config: dict[str, Any] | None,
    old_state: dict[str, Any] | None,
    enabled: bool,
    fetch_bytes_fn: Callable[[str], bytes | None] = http_bytes,
    now: datetime | None = None,
) -> RegulatorCollectionResult:
    now = now or utc_now()
    registry = registry if isinstance(registry, dict) else {}
    config = config if isinstance(config, dict) else {}
    old_state = old_state if isinstance(old_state, dict) else {}

    if not enabled:
        return RegulatorCollectionResult(
            [],
            old_state,
            {"regulators": {"status": "disabled", "source": "Official regulator pages", "checked": 0}},
            [],
        )

    sources = config.get("sources") if isinstance(config.get("sources"), dict) else {}
    assignments = config.get("assignments") if isinstance(config.get("assignments"), dict) else {}
    overrides = registry.get("items") if isinstance(registry.get("items"), dict) else {}
    entries = {
        str(stock.get("ticker") or "").upper(): build_registry_entry(
            stock,
            overrides.get(str(stock.get("ticker") or "").upper(), {}),
        )
        for stock in portfolio
        if str(stock.get("ticker") or "").strip()
    }

    wanted: dict[str, list[str]] = {}
    for ticker, agency_keys in assignments.items():
        ticker = str(ticker or "").upper()
        if ticker not in entries or not isinstance(agency_keys, list):
            continue
        for agency_key in agency_keys:
            key = str(agency_key or "").upper()
            if key in sources:
                wanted.setdefault(key, []).append(ticker)

    prior_sources = old_state.get("sources") if isinstance(old_state.get("sources"), dict) else {}
    next_sources = dict(prior_sources)
    events: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    checked = ok = partial = failed = 0

    for agency_key, tickers in sorted(wanted.items()):
        checked += 1
        source = sources.get(agency_key) if isinstance(sources.get(agency_key), dict) else {}
        url = str(source.get("url") or "").strip()
        name = str(source.get("name") or agency_key)
        if not url:
            partial += 1
            errors.append({"source": "regulator", "ticker": ",".join(tickers), "message": f"{name} URL unavailable"})
            continue

        payload = fetch_bytes_fn(url)
        if not payload:
            failed += 1
            errors.append({"source": "regulator", "ticker": ",".join(tickers), "message": f"{name} source unavailable"})
            continue

        rows = _rows(payload, source)
        if not rows:
            partial += 1
            errors.append({"source": "regulator", "ticker": ",".join(tickers), "message": f"{name} returned no parseable links"})
            next_sources[agency_key] = {
                **(prior_sources.get(agency_key) if isinstance(prior_sources.get(agency_key), dict) else {}),
                "last_successful_check": now.astimezone(UTC).replace(microsecond=0).isoformat(),
                "last_result_count": 0,
            }
            continue

        ok += 1
        previous = prior_sources.get(agency_key) if isinstance(prior_sources.get(agency_key), dict) else {}
        seen = {str(value) for value in previous.get("seen_urls", []) if value}
        current_urls = [str(row.get("url") or "") for row in rows if row.get("url")]
        bootstrapping = not seen

        if not bootstrapping:
            for row in rows[:200]:
                item_url = str(row.get("url") or "").strip()
                headline = str(row.get("title") or "").strip()
                if not item_url or not headline or item_url in seen:
                    continue
                for ticker in tickers:
                    entry = entries[ticker]
                    confidence, reason = entity_confidence(headline, item_url, entry)
                    if confidence == "rejected":
                        continue
                    event = build_event(
                        ticker=ticker,
                        headline=headline,
                        url=item_url,
                        source_type="regulator",
                        source_quality="primary",
                        published_at=row.get("published_at") or now,
                        detected_at=now,
                        confidence=confidence,
                        confidence_reason=reason,
                        summary=str(row.get("summary") or "").strip(),
                    )
                    if not event:
                        continue
                    event["regulator"] = agency_key
                    event["regulator_name"] = name
                    event["verification_reason"] = f"Published on the official {name} website."
                    event["source"]["agency"] = agency_key
                    event["source"]["name"] = name
                    event["source_chain"][0]["agency"] = agency_key
                    event["source_chain"][0]["name"] = name
                    events.append(event)

        next_sources[agency_key] = {
            "last_successful_check": now.astimezone(UTC).replace(microsecond=0).isoformat(),
            "seen_urls": list(dict.fromkeys(current_urls + list(seen)))[:500],
            "last_result_count": len(rows),
            "bootstrapped": bootstrapping,
        }

    if checked == 0:
        status = "partial"
    elif failed == checked:
        status = "error"
    elif failed or partial:
        status = "partial"
    else:
        status = "ok"

    next_state = {
        "schema_version": "1.0",
        "updated_at": now.astimezone(UTC).replace(microsecond=0).isoformat(),
        "sources": next_sources,
    }
    health = {
        "regulators": {
            "status": status,
            "source": "Official regulator pages",
            "checked": checked,
            "ok": ok,
            "partial": partial,
            "errors": failed,
            "accepted_events": len(events),
        }
    }
    return RegulatorCollectionResult(events, next_state, health, errors)
