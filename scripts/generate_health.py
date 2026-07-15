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
    "attention": ("attention_today.json", 30),
    "consensus": ("recommendation_trends.json", 1440),
    "fundamental": ("fundamental.json", 24 * 60 * 35),
    "market_pulse": ("market_pulse.json", 30),
}

def parse_dt(v: Any):
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None

def inspect(path: Path, stale_after: int) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {"status": "missing", "age_minutes": None, "stale_after_minutes": stale_after}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "invalid", "error": str(exc), "age_minutes": None, "stale_after_minutes": stale_after}
    stamp = (
        data.get("market_as_of")
        or data.get("generated_at")
        or data.get("generatedAt")
        or data.get("generatedAtTechnical")
        or data.get("updated_at")
    )
    dt = parse_dt(stamp)
    age = None if not dt else round((datetime.now(timezone.utc) - dt).total_seconds() / 60, 1)
    status = "ok"
    if age is None:
        status = "unknown"
    elif age > stale_after:
        status = "stale"
    return {
        "status": status,
        "age_minutes": age,
        "stale_after_minutes": stale_after,
        "timestamp": stamp,
        "row_count": data.get("row_count", len(data.get("rows", [])) if isinstance(data.get("rows"), list) else None),
        "source": data.get("source"),
    }

def main() -> None:
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "layers": {name: inspect(DATA / filename, ttl) for name, (filename, ttl) in FILES.items()},
    }
    statuses = [x["status"] for x in payload["layers"].values()]
    payload["status"] = "error" if any(x in {"missing", "invalid"} for x in statuses) else ("stale" if "stale" in statuses else "ok")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT)

if __name__ == "__main__":
    main()
