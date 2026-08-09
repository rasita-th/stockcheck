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
    request = urllib.request.Request(
        url,
        headers={"Cache-Control": "no-cache", "User-Agent": "stockcheck-drawdown-verifier/2.0"},
    )
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
    if snapshot.get("drawdown_schema_version") != "1.0":
        raise DrawdownVerificationError("production drawdown metric contract is not 1.0")

    rows = snapshot.get("rows")
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
        if not isinstance(metric, dict):
            invalid.append(f"{symbol}:missing")
            continue
        status = metric.get("status")
        if status == "unavailable":
            if row.get("drawdownCurrentPct") is not None or row.get("drawdownStatus") != "unavailable":
                invalid.append(f"{symbol}:unavailable")
            continue
        if status not in {"complete", "partial-history"}:
            invalid.append(f"{symbol}:status")
            continue
        current = number(metric.get("currentPct"))
        maximum = number(metric.get("maxPct"))
        days = metric.get("daysSincePeak")
        observations = metric.get("observations")
        if (
            current is None
            or maximum is None
            or not isinstance(days, int)
            or days < 0
            or not isinstance(observations, int)
            or observations < 2
            or not (-100 <= maximum <= current <= 0)
        ):
            invalid.append(symbol)
            continue
        flattened = {
            "drawdownCurrentPct": current,
            "drawdownMaxPct": maximum,
            "drawdownDaysSincePeak": days,
            "drawdownAsOf": metric.get("asOf"),
            "drawdownStatus": status,
        }
        if any(row.get(key) != value for key, value in flattened.items()):
            invalid.append(f"{symbol}:flattened")
            continue
        available += 1

    if invalid:
        raise DrawdownVerificationError(f"invalid production drawdown rows: {invalid[:12]}")

    declared_available = snapshot.get("drawdown_available_count")
    if declared_available != available:
        raise DrawdownVerificationError("production drawdown available_count mismatch")
    coverage = available / len(rows)
    declared_coverage = number(snapshot.get("drawdown_coverage"))
    if declared_coverage is None or abs(declared_coverage - coverage) > 0.000001:
        raise DrawdownVerificationError("production drawdown coverage mismatch")
    if coverage < 0.80:
        raise DrawdownVerificationError(f"production drawdown coverage too low: {coverage:.1%}")
    return {"row_count": len(rows), "available_count": available, "coverage": round(coverage, 6)}


def verify_once(base_url: str, nonce: str, fetcher: Callable[[str], bytes] = fetch) -> dict[str, Any]:
    base = base_url.rstrip("/")
    index = fetcher(f"{base}/index.html?drawdown_verify={nonce}").decode("utf-8")
    loader = fetcher(f"{base}/memo-only-fix.js?drawdown_verify={nonce}").decode("utf-8")
    runtime = fetcher(f"{base}/drawdown-screener-v10-9.js?drawdown_verify={nonce}").decode("utf-8")
    snapshot = json.loads(fetcher(f"{base}/data/screener_snapshot.json?drawdown_verify={nonce}"))

    if "memo-only-fix.js" not in index:
        raise DrawdownVerificationError("production HTML is missing the runtime loader")
    if "drawdown-screener-v10-9.js?v=${DRAWDOWN_VERSION}" not in loader or 'DRAWDOWN_VERSION = "10.9.1"' not in loader:
        raise DrawdownVerificationError("production loader is missing Drawdown Scanner runtime 10.9.1")
    for token in (
        'const VERSION = "10.9.1"',
        "StockcheckTechnicalV2?.drawdownFor",
        "dataset.drawdownScreener",
        "drawdownCurrentPct",
        "currentPct",
        'status === "unavailable"',
    ):
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
