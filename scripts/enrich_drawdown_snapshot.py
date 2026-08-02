#!/usr/bin/env python3
"""Enrich canonical screener mirrors with drawdown summary metrics.

This runs after ``build_screener_snapshot.py``. Historical ticker shards remain
the source for the price series while the canonical row remains the source for
the latest price used by Scanner, filters and alerts.
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARDS_ROOT = ROOT / "site" / "data" / "technical" / "symbols"
SNAPSHOT_PATHS = (
    ROOT / "data" / "screener_snapshot.json",
    ROOT / "data" / "generated" / "screener_snapshot.json",
    ROOT / "site" / "data" / "screener_snapshot.json",
    ROOT / "static" / "data" / "screener_snapshot.json",
    ROOT / "data" / "generated" / "technical.json",
    ROOT / "site" / "data" / "technical.json",
    ROOT / "static" / "data" / "technical.json",
    ROOT / "data" / "generated" / "scanner.json",
    ROOT / "site" / "data" / "scanner.json",
    ROOT / "static" / "data" / "scanner.json",
)


def finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def iso_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def close_value(row: dict[str, Any]) -> float | None:
    for key in ("adjClose", "adjustedClose", "close"):
        value = finite(row.get(key))
        if value is not None and value > 0:
            return value
    return None


def calculate_drawdown(
    series: list[dict[str, Any]],
    *,
    latest_price: float | None = None,
    latest_date: str | None = None,
    max_observations: int = 756,
) -> dict[str, Any]:
    points: list[tuple[str, float]] = []
    for raw in series[-max_observations:]:
        if not isinstance(raw, dict):
            continue
        day = str(raw.get("date") or "")[:10]
        price = close_value(raw)
        if iso_date(day) is not None and price is not None:
            points.append((day, price))

    if latest_price is not None and latest_price > 0 and iso_date(latest_date) is not None:
        if points and points[-1][0] == latest_date:
            points[-1] = (latest_date, latest_price)
        elif not points or points[-1][0] < latest_date:
            points.append((latest_date, latest_price))

    if len(points) < 2:
        return {
            "schemaVersion": "1.0",
            "status": "unavailable",
            "window": "up-to-756-sessions",
            "observations": len(points),
            "source": "adjusted_close_then_close",
        }

    running_peak = points[0][1]
    running_peak_date = points[0][0]
    current_peak_date = points[0][0]
    max_pct = 0.0
    max_peak_date = points[0][0]
    max_trough_date = points[0][0]
    current_pct = 0.0

    for day, price in points:
        if price > running_peak:
            running_peak = price
            running_peak_date = day
        drawdown = (price / running_peak - 1.0) * 100.0
        current_pct = drawdown
        current_peak_date = running_peak_date
        if drawdown < max_pct:
            max_pct = drawdown
            max_peak_date = running_peak_date
            max_trough_date = day

    as_of = points[-1][0]
    peak_day = iso_date(current_peak_date)
    as_of_day = iso_date(as_of)
    days_since_peak = (as_of_day - peak_day).days if as_of_day and peak_day else None
    status = "complete" if len(points) >= 20 else "partial-history"
    result = {
        "schemaVersion": "1.0",
        "status": status,
        "window": "up-to-756-sessions",
        "observations": len(points),
        "currentPct": round(min(0.0, current_pct), 2),
        "maxPct": round(min(0.0, max_pct), 2),
        "currentPeakDate": current_peak_date,
        "maxPeakDate": max_peak_date,
        "maxTroughDate": max_trough_date,
        "daysSincePeak": days_since_peak,
        "asOf": as_of,
        "source": "adjusted_close_then_close",
    }
    validate_metric(result)
    return result


def validate_metric(metric: dict[str, Any]) -> None:
    if metric.get("status") == "unavailable":
        return
    current = finite(metric.get("currentPct"))
    maximum = finite(metric.get("maxPct"))
    if current is None or maximum is None:
        raise ValueError("drawdown percentages must be finite")
    if not (-100.0 <= maximum <= current <= 0.0):
        raise ValueError(f"invalid drawdown domain: max={maximum}, current={current}")
    if iso_date(metric.get("asOf")) is None:
        raise ValueError("drawdown asOf must be an ISO date")


def load_shard(symbol: str) -> dict[str, Any] | None:
    path = SHARDS_ROOT / f"{symbol}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def enrich_payload(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise SystemExit("canonical snapshot rows must be a list")

    available = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or row.get("ticker") or "").strip().upper()
        shard = load_shard(symbol) if symbol else None
        series = (shard or {}).get("series")
        metric = calculate_drawdown(
            series if isinstance(series, list) else [],
            latest_price=finite(row.get("price") or row.get("regularMarketPrice") or row.get("close")),
            latest_date=str(row.get("regularMarketTime") or row.get("date") or "")[:10] or None,
        )
        row["drawdown"] = metric
        row["drawdownCurrentPct"] = metric.get("currentPct")
        row["drawdownMaxPct"] = metric.get("maxPct")
        row["drawdownDaysSincePeak"] = metric.get("daysSincePeak")
        row["drawdownAsOf"] = metric.get("asOf")
        row["drawdownStatus"] = metric.get("status")
        if metric.get("status") in {"complete", "partial-history"}:
            available += 1

    payload["schema_version"] = "1.1"
    payload["drawdown_schema_version"] = "1.0"
    payload["drawdown_available_count"] = available
    payload["drawdown_coverage"] = round(available / len(rows), 6) if rows else 0.0
    return payload


def main() -> None:
    canonical = SNAPSHOT_PATHS[0]
    if not canonical.exists():
        raise SystemExit(f"missing canonical snapshot: {canonical}")
    payload = json.loads(canonical.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("canonical snapshot root must be an object")
    enriched = enrich_payload(payload)
    encoded = json.dumps(enriched, ensure_ascii=False, separators=(",", ":")) + "\n"
    for path in SNAPSHOT_PATHS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded, encoding="utf-8")
        print(f"wrote {path}")
    print(
        "drawdown enrichment: "
        f"{enriched['drawdown_available_count']}/{enriched.get('row_count', len(enriched.get('rows', [])))} rows"
    )


if __name__ == "__main__":
    main()
