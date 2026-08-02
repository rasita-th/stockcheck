#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import time
import urllib.request
from typing import Any, Callable


class DrawdownVerificationError(ValueError):
    pass


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "stockcheck-drawdown-verifier/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def validate_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    if snapshot.get("schema_version") != "1.1":
        raise DrawdownVerificationError("production screener snapshot schema is not 1.1")
    if snapshot.get("contract") != "canonical-screener-snapshot":
        raise DrawdownVerificationError("production screener snapshot contract is invalid")
    drawdown = snapshot.get("drawdown")
    rows = snapshot.get("rows")
    if not isinstance(drawdown, dict) or drawdown.get("schema_version") != "1.0":
        raise DrawdownVerificationError("production drawdown metric contract is not 1.0")
    if not isinstance(rows, list) or not rows:
        raise DrawdownVerificationError("production screener snapshot rows are empty")

    available = 0
    invalid: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            invalid.append("non-object")
            continue
        symbol = str(row.get("symbol") or row.get("ticker") or "?").upper()
        metric = row.get("drawdown")
        if not isinstance(metric, dict) or metric.get("status") != "available":
            continue
        current = number(metric.get("currentPct"))
        maximum = number(metric.get("maxPct"))
        days = number(metric.get("daysSincePeak"))
        if current is None or maximum is None or days is None or not (-100 <= maximum <= current <= 0) or days < 0:
            invalid.append(symbol)
            continue
        if number(row.get("drawdownCurrentPct")) != current or number(row.get("drawdownMaxPct")) != maximum:
            invalid.append(f"{symbol}:flattened")
            continue
        available += 1

    if invalid:
        raise DrawdownVerificationError(f"invalid production drawdown rows: {invalid[:12]}")
    declared_available = int(drawdown.get("available_count") or 0)
    if declared_available != available:
        raise DrawdownVerificationError("production drawdown available_count mismatch")
    coverage = available / len(rows)
    declared_coverage = number(drawdown.get("coverage"))
    if declared_coverage is None or abs(declared_coverage - coverage) > 0.000001:
        raise DrawdownVerificationError("production drawdown coverage mismatch")
    if coverage < 0.80:
        raise DrawdownVerificationError(f"production drawdown coverage too low: {coverage:.1%}")
    return {"row_count": len(rows), "available_count": available, "coverage": round(coverage, 6)}


def verify_once(base_url: str, nonce: str, fetcher: Callable[[str], bytes] = fetch) -> dict[str, Any]:
    base = base_url.rstrip("/")
    index = fetcher(f"{base}/index.html?drawdown_verify={nonce}").decode("utf-8")
    runtime = fetcher(f"{base}/drawdown-screener-v10-9.js?drawdown_verify={nonce}").decode("utf-8")
    snapshot = json.loads(fetcher(f"{base}/data/screener_snapshot.json?drawdown_verify={nonce}"))
    if "drawdown-screener-v10-9.js?v=10.9.0" not in index:
        raise DrawdownVerificationError("production HTML is missing Drawdown Scanner runtime 10.9.0")
    for token in ('data-drawdown-screener', 'drawdownCurrentPct', 'drawdownMaxPct', 'unavailable'):
        if token not in runtime:
            raise DrawdownVerificationError(f"production Drawdown Scanner runtime missing: {token}")
    return validate_snapshot(snapshot)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--attempts", type=int, default=18)
    parser.add_argument("--sleep-seconds", type=int, default=5)
    args = parser.parse_args()
    last_error: Exception | None = None
    for attempt in range(1, args.attempts + 1):
        try:
            summary = verify_once(args.base_url, f"{int(time.time())}-{attempt}")
            print(json.dumps({"status": "verified", **summary}, ensure_ascii=False))
            return
        except Exception as exc:
            last_error = exc
            print(f"attempt {attempt}/{args.attempts} failed: {exc}")
            if attempt < args.attempts:
                time.sleep(args.sleep_seconds)
    raise DrawdownVerificationError(f"production Drawdown verification failed: {last_error}")


if __name__ == "__main__":
    main()
