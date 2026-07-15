#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path

REQUIRED = {
    "global_markets": 3,
    "us_indices": 3,
    "us_sectors": 8,
    "themes": 5,
}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="data/market_pulse.json")
    ap.add_argument("--min-ok-rate", type=float, default=0.75)
    args = ap.parse_args()
    p = Path(args.path)
    if not p.exists() or p.stat().st_size < 100:
        raise SystemExit(f"invalid or missing JSON: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"cannot parse {p}: {exc}")
    if not isinstance(data, dict):
        raise SystemExit("root must be an object")

    total = ok = 0
    problems: list[str] = []
    for key, minimum in REQUIRED.items():
        rows = data.get(key)
        if not isinstance(rows, list):
            problems.append(f"{key}: missing/not a list")
            continue
        if len(rows) < minimum:
            problems.append(f"{key}: {len(rows)} rows, need >= {minimum}")
        for row in rows:
            total += 1
            if not isinstance(row, dict):
                continue
            status = str(row.get("status", "ok")).lower()
            has_identity = bool(row.get("symbol") or row.get("ticker") or row.get("name"))
            numeric = any(isinstance(row.get(k), (int, float)) and math.isfinite(row[k]) for k in ("price", "close", "change_pct", "return_1d", "value"))
            if status == "ok" and has_identity and numeric:
                ok += 1
    rate = ok / total if total else 0.0
    if rate < args.min_ok_rate:
        problems.append(f"valid row rate {rate:.1%}, need >= {args.min_ok_rate:.0%}")
    if problems:
        raise SystemExit("validation failed: " + "; ".join(problems))
    print(json.dumps({"path": str(p), "rows": total, "ok": ok, "ok_rate": round(rate, 4), "groups": {k: len(data[k]) for k in REQUIRED}}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
