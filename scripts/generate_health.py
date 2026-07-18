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
    "attention": ("attention_today.json", 90),
    "events": ("events.json", 90),
    "consensus": ("recommendation_trends.json", 1440),
    "fundamental": ("fundamental.json", 24 * 60 * 35),
    "market_pulse": ("market_pulse.json", 30),
}


def parse_dt(value: Any):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def inspect(path: Path, stale_after: int) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {"status": "missing", "age_minutes": None, "stale_after_minutes": stale_after}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "invalid", "error": str(exc), "age_minutes": None, "stale_after_minutes": stale_after}
    stamp = data.get("market_as_of") or data.get("generated_at") or data.get("generatedAt") or data.get("generatedAtTechnical") or data.get("updated_at")
    parsed = parse_dt(stamp)
    age = None if not parsed else round((datetime.now(timezone.utc) - parsed).total_seconds() / 60, 1)
    status = "unknown" if age is None else "stale" if age > stale_after else "ok"
    result = {"status": status, "age_minutes": age, "stale_after_minutes": stale_after, "timestamp": stamp, "row_count": data.get("row_count", len(data.get("rows", [])) if isinstance(data.get("rows"), list) else None), "source": data.get("source")}
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
    payload = {"schema_version": "1.1", "generated_at": datetime.now(timezone.utc).isoformat(), "layers": {name: inspect(DATA / filename, ttl) for name, (filename, ttl) in FILES.items()}}
    statuses = [layer["status"] for layer in payload["layers"].values()]
    payload["status"] = "error" if any(status in {"missing", "invalid"} for status in statuses) else "stale" if "stale" in statuses else "partial" if "partial" in statuses else "ok"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
