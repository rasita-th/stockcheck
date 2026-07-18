from __future__ import annotations

from typing import Any

from .common import canonical_url, domain_from_url, headline_similarity, materiality_rank, parse_datetime, stable_hash, subtype_group


def events_related(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if str(left.get("ticker") or "").upper() != str(right.get("ticker") or "").upper():
        return False
    if subtype_group(left.get("event_subtype")) != subtype_group(right.get("event_subtype")):
        return False
    left_time = parse_datetime(left.get("event_time") or left.get("detected_at"))
    right_time = parse_datetime(right.get("event_time") or right.get("detected_at"))
    if left_time and right_time and abs((left_time - right_time).total_seconds()) > 72 * 3600:
        return False
    left_url, right_url = canonical_url((left.get("source") or {}).get("url")), canonical_url((right.get("source") or {}).get("url"))
    return bool(left_url and right_url and left_url == right_url) or headline_similarity(str(left.get("headline") or ""), str(right.get("headline") or "")) >= 0.38


def _source_identity(source: dict[str, Any]) -> tuple[str, str, str]:
    return str(source.get("type") or ""), canonical_url(source.get("url")), str(source.get("published_at") or "")


def merge_event_cluster(cluster: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(cluster, key=lambda event: (-int((event.get("source") or {}).get("quality") == "primary"), -materiality_rank(event.get("materiality")), str(event.get("event_time") or "")))
    merged, sources, identities, related_ids = dict(ordered[0]), [], set(), []
    for event in cluster:
        related_ids.append(str(event.get("event_id") or ""))
        for source in [event.get("source") or {}, *(event.get("source_chain") or [])]:
            if not isinstance(source, dict) or not source.get("type"):
                continue
            identity = _source_identity(source)
            if identity not in identities:
                identities.add(identity)
                sources.append(source)
    primary_sources = [source for source in sources if source.get("quality") == "primary" and source.get("url")]
    secondary_domains = {source.get("domain") or domain_from_url(source.get("url")) for source in sources if source.get("quality") != "primary"} - {""}
    if primary_sources:
        merged.update({"verification_status": "confirmed", "verification_level": "confirmed_primary" if len(sources) == 1 else "corroborated", "verification_reason": "Matched a configured primary source." if len(sources) == 1 else "Matched a configured primary source and additional coverage.", "source": primary_sources[0]})
    else:
        merged.update({"verification_status": "unverified", "verification_level": "corroborated_secondary" if len(secondary_domains) >= 2 else "unverified_report", "verification_reason": "Multiple independent domains reported a similar event, but no primary source was matched." if len(secondary_domains) >= 2 else "Primary source not yet located."})
    merged["source_chain"] = sources
    merged["secondary_source_count"] = sum(1 for source in sources if source.get("quality") != "primary")
    merged["related_event_ids"] = [event_id for event_id in dict.fromkeys(related_ids) if event_id]
    merged["materiality"] = max((str(event.get("materiality") or "low") for event in cluster), key=materiality_rank)
    merged["dedupe_key"] = merged.get("dedupe_key") or f"{merged.get('ticker')}:{subtype_group(merged.get('event_subtype'))}:{stable_hash(*sorted(related_ids))}"
    if len(cluster) > 1:
        merged["event_id"] = f"event:{merged.get('ticker')}:{stable_hash(merged['dedupe_key'])}"
    return merged


def deduplicate_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clusters: list[list[dict[str, Any]]] = []
    for event in events:
        if not isinstance(event, dict) or not event.get("event_id"):
            continue
        for cluster in clusters:
            if events_related(cluster[0], event):
                cluster.append(event)
                break
        else:
            clusters.append([event])
    return sorted((merge_event_cluster(cluster) for cluster in clusters), key=lambda event: str(event.get("event_time") or ""), reverse=True)
