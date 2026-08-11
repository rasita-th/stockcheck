#!/usr/bin/env python3
"""Project fresh canonical market fields into the Today attention mirrors."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
TECHNICAL_PATH = ROOT / "data" / "generated" / "technical.json"
ATTENTION_PATHS = (
    ROOT / "data" / "generated" / "attention_today.json",
    ROOT / "site" / "data" / "attention_today.json",
    ROOT / "static" / "data" / "attention_today.json",
)


def _number(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        try:
            value = float(row.get(key))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            return value
    return None


def _impact_label(change_pct: float | None) -> str:
    if change_pct is None:
        return "ยังไม่มีราคาฐานสำหรับเปรียบเทียบ"
    if abs(change_pct) < 0.5:
        return "ราคายังเปลี่ยนแปลงไม่มาก"
    direction = "ปรับขึ้น" if change_pct > 0 else "ปรับลง"
    return f"ราคาหลังเริ่มติดตาม{direction} {abs(change_pct):.1f}%"


def _priority(score: int, subtype: str, day_pct: float) -> str:
    if subtype == "price_drop" and abs(day_pct) >= 8:
        return "Risk"
    if score >= 88:
        return "Critical"
    if score >= 72:
        return "Risk"
    if score >= 52:
        return "Action"
    if score >= 32:
        return "Watch"
    return "Developing"


def _price_event_score(event: dict[str, Any], item: dict[str, Any], day_pct: float) -> int:
    materiality_score = {"high": 45, "medium": 28, "low": 12}.get(
        str(event.get("materiality") or ""),
        8,
    )
    urgency_score = {"today": 25, "immediate": 30, "upcoming": 12}.get(
        str(event.get("urgency") or ""),
        5,
    )
    portfolio_score = 15 if item.get("portfolio_status") == "holding" else 5
    source = event.get("source") if isinstance(event.get("source"), dict) else {}
    verification_score = 0
    if event.get("verification_status") == "confirmed" and source.get("quality") == "primary":
        verification_score = 12
    elif event.get("verification_status") == "estimated":
        verification_score = -8
    move_score = 14 if abs(day_pct) >= 8 else 7
    return max(0, min(100, materiality_score + urgency_score + portfolio_score + verification_score + move_score))


def _replace_price_event_identity(event: dict[str, Any], marker: str) -> None:
    old_id = str(event.get("event_id") or "")
    new_id = old_id.replace(":price-drop:", f":{marker}:").replace(":price-move:", f":{marker}:")
    if new_id and new_id != old_id:
        event["event_id"] = new_id
        related = event.get("related_event_ids")
        if isinstance(related, list):
            event["related_event_ids"] = [new_id if str(value) == old_id else value for value in related]
        event.pop("dedupe_key", None)


def _sync_technical_metrics(event: dict[str, Any], source: dict[str, Any]) -> None:
    metrics = {
        "technical_score": _number(source, "score", "technical_score"),
        "rsi14": _number(source, "rsi14", "rsi", "RSI14"),
        "pct_vs_ema20": _number(source, "pctVsEma20", "pct_vs_ema20"),
        "pct_vs_ema200": _number(source, "pctVsEma200", "pct_vs_ema200"),
        "volume_ratio20": _number(
            source,
            "volumeRatio20",
            "relativeVolume",
            "relVolume",
            "volumeRatio",
        ),
    }
    for key, value in metrics.items():
        if value is not None:
            event[key] = value
    signal = str(source.get("signal") or source.get("technical_signal") or "").strip()
    if signal:
        event["technical_signal"] = signal
    if any(value is not None for value in metrics.values()) or signal:
        event["technical_metrics_source"] = "canonical_technical_snapshot"


def _sync_price_event(event: dict[str, Any], item: dict[str, Any], day_pct: float) -> None:
    subtype = "price_drop" if day_pct < 0 else "price_move"
    marker = "price-drop" if day_pct < 0 else "price-move"
    _replace_price_event_identity(event, marker)
    reason = f"The stock moved {day_pct:+.1f}% today."
    event["event_subtype"] = subtype
    event["headline"] = f"Price {day_pct:+.1f}%"
    event["why_today"] = reason
    event["materiality"] = "high" if abs(day_pct) >= 8 else "medium"
    score = _price_event_score(event, item, day_pct)
    event["priority_score"] = score
    event["priority"] = _priority(score, subtype, day_pct)


def _event_rank(event: dict[str, Any]) -> tuple[int, int, str]:
    order = {"Critical": 0, "Risk": 1, "Action": 2, "Watch": 3, "Developing": 4}
    return (
        order.get(str(event.get("priority") or ""), 9),
        -int(event.get("priority_score") or 0),
        str(event.get("event_id") or ""),
    )


def _sync_technical_watch_item(
    item: dict[str, Any],
    source: dict[str, Any],
    day_pct: float | None,
) -> bool:
    events = item.get("events") if isinstance(item.get("events"), list) else []
    if not events:
        return True
    retained: list[dict[str, Any]] = []
    semantic_changed = False
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("event_type") == "technical":
            _sync_technical_metrics(event, source)
        if event.get("event_subtype") in {"price_drop", "price_move"}:
            if day_pct is None:
                retained.append(event)
                continue
            semantic_changed = True
            if abs(day_pct) < 5:
                continue
            _sync_price_event(event, item, day_pct)
        retained.append(event)
    if not retained:
        return False
    if not semantic_changed:
        item["events"] = retained
        return True

    retained.sort(key=_event_rank)
    old_priority_score = int(item.get("priority_score") or 0)
    personal_delta = max(0, int(item.get("personal_priority_score") or 0) - old_priority_score)
    primary = retained[0]
    reasons: list[str] = []
    for event in retained[:3]:
        reason = str(event.get("why_today") or event.get("summary") or event.get("headline") or "").strip()
        if reason and reason not in reasons:
            reasons.append(reason)
    source_info = primary.get("source") if isinstance(primary.get("source"), dict) else {}
    item["events"] = retained
    item["priority"] = primary.get("priority")
    item["priority_score"] = int(primary.get("priority_score") or 0)
    item["personal_priority_score"] = item["priority_score"] + personal_delta
    item["why_today"] = reasons
    item["signals"] = reasons
    item["event_type"] = primary.get("event_type")
    item["event_subtype"] = primary.get("event_subtype")
    item["event_time"] = primary.get("event_time")
    item["verification_status"] = primary.get("verification_status")
    item["source_status"] = source_info.get("quality") or item.get("source_status") or "unknown"
    item["source"] = source_info or item.get("source")
    item["trigger_level"] = primary.get("trigger_level")
    item["primary_trigger"] = primary.get("event_subtype") or primary.get("event_type")
    item["severity"] = (
        "high"
        if item["priority"] in {"Critical", "Risk"}
        else "medium"
        if item["priority"] in {"Action", "Watch"}
        else "low"
    )
    return True


def _refresh_technical_summary(attention: dict[str, Any]) -> None:
    rows = attention.get("technical_watch") if isinstance(attention.get("technical_watch"), list) else []
    attention["technical_summary"] = {
        "risk": sum(1 for item in rows if item.get("event_subtype") == "technical_risk"),
        "setup": sum(1 for item in rows if item.get("event_subtype") == "technical_setup"),
        "total": len(rows),
    }


def sync_payload(attention: dict[str, Any], technical: dict[str, Any]) -> int:
    rows = technical.get("rows") if isinstance(technical.get("rows"), list) else []
    by_ticker = {
        str(row.get("ticker") or row.get("symbol") or "").strip().upper(): row
        for row in rows
        if isinstance(row, dict)
    }
    updated = 0
    for section in ("items", "technical_watch"):
        attention_rows = attention.get(section) if isinstance(attention.get(section), list) else []
        retained_rows: list[dict[str, Any]] = []
        for item in attention_rows:
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker") or "").strip().upper()
            source = by_ticker.get(ticker)
            if not isinstance(source, dict):
                if section == "technical_watch":
                    retained_rows.append(item)
                continue
            price = _number(source, "price", "close", "regularMarketPrice")
            day_pct = _number(source, "dayPct", "day_change_pct", "changePercent")
            relative_volume = _number(
                source,
                "volumeRatio20",
                "relativeVolume",
                "relVolume",
                "volumeRatio",
            )
            if price is not None:
                item["price"] = price
            if day_pct is not None:
                item["day_change_pct"] = day_pct
            if relative_volume is not None:
                item["relative_volume"] = relative_volume

            impact = item.get("impact")
            if isinstance(impact, dict) and price is not None:
                baseline = _number(impact, "baseline_price")
                change_pct = round((price / baseline - 1) * 100, 2) if baseline else None
                impact["current_price"] = price
                impact["change_pct"] = change_pct
                impact["label_th"] = _impact_label(change_pct)
            updated += 1
            if section != "technical_watch" or _sync_technical_watch_item(item, source, day_pct):
                retained_rows.append(item)
        if section == "technical_watch":
            retained_rows.sort(key=lambda item: _event_rank((item.get("events") or [{}])[0]))
            attention[section] = retained_rows
    _refresh_technical_summary(attention)
    return updated


def sync_paths(technical_path: Path, attention_paths: Iterable[Path]) -> int:
    technical = json.loads(technical_path.read_text(encoding="utf-8"))
    paths = tuple(attention_paths)
    if not paths:
        raise SystemExit("no attention paths configured")
    attention = json.loads(paths[0].read_text(encoding="utf-8"))
    updated = sync_payload(attention, technical)
    rendered = json.dumps(attention, ensure_ascii=False, indent=2) + "\n"
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    return updated


def main() -> None:
    updated = sync_paths(TECHNICAL_PATH, ATTENTION_PATHS)
    print(f"Synchronized canonical market fields for {updated} attention rows.")


if __name__ == "__main__":
    main()
