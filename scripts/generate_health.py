#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "generated"
OUT = DATA / "health.json"
FILES = {
    "quote": ("quote_latest.json", 30),
    "technical": ("technical.json", 1440),
    "source_market": ("source_freshness.json", 30),
    "attention": ("attention_today.json", 90),
    "events": ("events.json", 90),
    "consensus": ("recommendation_trends.json", 1440),
    "fundamental": ("fundamental.json", 24 * 60 * 35),
    "market_pulse": ("market_pulse.json", 30),
}


def parse_dt(value: Any):
    if not value:
        return None
    raw = str(value).strip()
    try:
        if raw.endswith(" UTC"):
            return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def inspect(path: Path, stale_after: int) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        status = "unavailable" if path.name == "source_freshness.json" else "missing"
        return {"status": status, "age_minutes": None, "stale_after_minutes": stale_after}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "invalid", "error": str(exc), "age_minutes": None, "stale_after_minutes": stale_after}
    stamp = (
        data.get("market_as_of")
        or data.get("checked_at")
        or data.get("generated_at")
        or data.get("generatedAtTechnical")
        or data.get("generatedAtFundamental")
        or data.get("generatedAt")
        or data.get("updated_at")
    )
    parsed = parse_dt(stamp)
    age = None if not parsed else round((datetime.now(timezone.utc) - parsed).total_seconds() / 60, 1)
    status = "unknown" if age is None else "stale" if age > stale_after else "ok"
    rows = data.get("rows")
    row_count = data.get("row_count")
    if row_count is None and isinstance(rows, list):
        row_count = len(rows)
    if row_count is None and isinstance(data.get("count"), int):
        row_count = data.get("count")
    result = {
        "status": status,
        "age_minutes": age,
        "stale_after_minutes": stale_after,
        "timestamp": stamp,
        "row_count": row_count,
        "source": data.get("source"),
    }
    if path.name == "source_freshness.json":
        source_status = data.get("status")
        if source_status in {"fresh", "source_partial", "source_stale", "invalid"}:
            result["status"] = source_status
        for key in (
            "expected_market_date", "oldest_market_date", "newest_market_date",
            "timestamp_coverage", "stale_count", "stale_ratio", "missing_timestamp_count",
        ):
            result[key] = data.get(key)
    if path.name == "attention_today.json":
        result["row_count"] = len(data.get("items", [])) if isinstance(data.get("items"), list) else None
        result["coverage_status"] = data.get("coverage_status")
        result["source_health"] = data.get("source_health")
        if data.get("coverage_status") == "partial" and result["status"] == "ok":
            result["status"] = "partial"
    if path.name == "events.json":
        result["row_count"] = len(data.get("events", [])) if isinstance(data.get("events"), list) else None
    return result


def main() -> None:
    payload = {
        "schema_version": "1.2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "layers": {name: inspect(DATA / filename, ttl) for name, (filename, ttl) in FILES.items()},
    }
    statuses = [layer["status"] for layer in payload["layers"].values()]
    error_states = {"missing", "invalid", "source_stale"}
    partial_states = {"partial", "source_partial"}
    payload["status"] = "error" if any(status in error_states for status in statuses) else "stale" if "stale" in statuses else "partial" if any(status in partial_states for status in statuses) else "ok"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
