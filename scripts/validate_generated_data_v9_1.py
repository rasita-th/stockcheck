#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "generated"

REQUIRED = ["quote_latest.json", "technical.json", "attention_today.json", "health.json"]

def load(name: str) -> dict[str, Any]:
    path = DATA / name
    if not path.exists() or path.stat().st_size == 0:
        raise SystemExit(f"Missing or empty generated data file: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path} root must be an object")
    return data

def main() -> None:
    docs = {name: load(name) for name in REQUIRED}
    q = docs["quote_latest.json"]
    if not isinstance(q.get("rows"), list) or not q["rows"]:
        raise SystemExit("quote_latest rows must be a non-empty list")
    t = docs["technical.json"]
    if not isinstance(t.get("rows"), list) or not t["rows"]:
        raise SystemExit("technical rows must be a non-empty list")
    a = docs["attention_today.json"]
    if not isinstance(a.get("items"), list):
        raise SystemExit("attention_today items must be a list")
    h = docs["health.json"]
    if h.get("status") == "error":
        raise SystemExit("health status is error")
    print("Generated data validation passed")

if __name__ == "__main__":
    main()
