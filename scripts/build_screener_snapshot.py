#!/usr/bin/env python3
"""Build the canonical screener snapshot consumed by overview, filters and alerts.

The technical producer owns indicators and history. The quote producer owns the
latest market price. This module joins both layers once, recomputes every
price-sensitive field, and publishes one snapshot for all summary consumers.
Ticker history remains in the lazy technical shards.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import score_setup

GENERATED = ROOT / "data" / "generated"
QUOTE_PATH = GENERATED / "quote_latest.json"
TECHNICAL_PATH = ROOT / "site" / "data" / "technical.json"
SHARDS_ROOT = ROOT / "site" / "data" / "technical" / "symbols"

SNAPSHOT_PATHS = (
    ROOT / "data" / "screener_snapshot.json",
    GENERATED / "screener_snapshot.json",
    ROOT / "site" / "data" / "screener_snapshot.json",
    ROOT / "static" / "data" / "screener_snapshot.json",
)
LEGACY_SUMMARY_PATHS = (
    GENERATED / "technical.json",
    ROOT / "site" / "data" / "technical.json",
    ROOT / "static" / "data" / "technical.json",
    GENERATED / "scanner.json",
    ROOT / "site" / "data" / "scanner.json",
    ROOT / "static" / "data" / "scanner.json",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        raise SystemExit(f"missing or empty input: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"{path} root must be an object")
    return payload


def parse_timestamp(value: Any) -> datetime | None:
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


def finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def rounded(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


def pct(price: float | None, baseline: Any) -> float | None:
    base = finite_number(baseline)
    if price is None or base in (None, 0):
        return None
    return rounded(((price / base) - 1.0) * 100.0)


def ticker_of(row: dict[str, Any]) -> str:
    return str(row.get("ticker") or row.get("symbol") or "").strip().upper()


def load_shard(symbol: str, root: Path) -> dict[str, Any] | None:
    path = root / f"{symbol}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict) or payload.get("schema_version") != "2.0":
        return None
    if str(payload.get("symbol") or "").upper() != symbol:
        return None
    return payload


def project_row(
    technical_row: dict[str, Any],
    quote_row: dict[str, Any] | None,
    shard: dict[str, Any] | None,
    quote_generated_at: str,
    technical_generated_at: str,
) -> dict[str, Any]:
    row = dict(technical_row)
    symbol = ticker_of(row)
    price = finite_number((quote_row or {}).get("price"))
    previous_close = finite_number((quote_row or {}).get("previous_close"))
    live_quote = price is not None and price > 0

    if live_quote:
        row["close"] = rounded(price, 4)
        row["price"] = rounded(price, 4)
        row["regularMarketPrice"] = rounded(price, 4)
        row["previousClose"] = rounded(previous_close, 4)
        row["previous_close"] = rounded(previous_close, 4)
        row["day_change"] = rounded(finite_number((quote_row or {}).get("day_change")), 4)
        row["dayPct"] = rounded(finite_number((quote_row or {}).get("day_change_pct")), 4)
        row["day_change_pct"] = row["dayPct"]
        row["pctVsEma5"] = pct(price, row.get("ema5"))
        row["pctVsEma20"] = pct(price, row.get("ema20"))
        row["pctVsEma89"] = pct(price, row.get("ema89"))
        row["pctVsEma200"] = pct(price, row.get("ema200"))
        row["pctFrom52wHigh"] = pct(price, row.get("high52w"))
        row["pctFrom52wLow"] = pct(price, row.get("low52w"))

        series = (shard or {}).get("series")
        if isinstance(series, list) and series:
            latest = dict(series[-1]) if isinstance(series[-1], dict) else {}
            previous = dict(series[-2]) if len(series) > 1 and isinstance(series[-2], dict) else dict(latest)
            latest["close"] = price
            high = finite_number(latest.get("high"))
            low = finite_number(latest.get("low"))
            latest["high"] = max(high, price) if high is not None else price
            latest["low"] = min(low, price) if low is not None else price
            score, signal, reasons, score_parts = score_setup(latest, previous)
            row["score"] = score
            row["signal"] = signal
            row["reasons"] = reasons
            row["scoreParts"] = score_parts

        row["snapshotStatus"] = "live_quote"
        row["snapshotPriceSource"] = "quote_latest.json"
    else:
        row["snapshotStatus"] = "technical_fallback"
        row["snapshotPriceSource"] = "technical.json"

    row["symbol"] = symbol
    row["quoteGeneratedAt"] = quote_generated_at
    row["technicalGeneratedAt"] = technical_generated_at
    return row


def build_snapshot(
    quote_payload: dict[str, Any],
    technical_payload: dict[str, Any],
    shards_root: Path = SHARDS_ROOT,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)

    quote_rows = quote_payload.get("rows")
    technical_rows = technical_payload.get("rows")
    if not isinstance(quote_rows, list) or not quote_rows:
        raise SystemExit("quote_latest rows must be a non-empty list")
    if not isinstance(technical_rows, list) or not technical_rows:
        raise SystemExit("technical rows must be a non-empty list")

    quote_stamp_raw = str(quote_payload.get("market_as_of") or quote_payload.get("generated_at") or "")
    technical_stamp_raw = str(
        technical_payload.get("generatedAtTechnical")
        or technical_payload.get("generatedAt")
        or ""
    )
    quote_stamp = parse_timestamp(quote_stamp_raw)
    technical_stamp = parse_timestamp(technical_stamp_raw)
    stale_after = int(quote_payload.get("stale_after_minutes") or 30)
    if quote_stamp is None:
        raise SystemExit("quote_latest timestamp is missing or invalid")
    quote_age = (current - quote_stamp.astimezone(timezone.utc)).total_seconds() / 60.0
    if quote_age > stale_after:
        raise SystemExit(
            f"quote_latest is stale at snapshot build: {quote_age:.1f}m > {stale_after}m"
        )
    if technical_stamp is None:
        raise SystemExit("technical timestamp is missing or invalid")

    quote_map = {
        ticker_of(row): row
        for row in quote_rows
        if isinstance(row, dict) and ticker_of(row)
    }
    projected: list[dict[str, Any]] = []
    live_count = 0
    missing_symbols: list[str] = []
    seen: set[str] = set()

    for source_row in technical_rows:
        if not isinstance(source_row, dict):
            continue
        symbol = ticker_of(source_row)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        quote_row = quote_map.get(symbol)
        if finite_number((quote_row or {}).get("price")) not in (None, 0):
            live_count += 1
        else:
            missing_symbols.append(symbol)
        projected.append(
            project_row(
                source_row,
                quote_row,
                load_shard(symbol, shards_root),
                quote_stamp_raw,
                technical_stamp_raw,
            )
        )

    coverage = live_count / len(projected) if projected else 0.0
    if coverage < 0.80:
        raise SystemExit(f"live quote coverage too low: {coverage:.1%}")

    source_skew = abs((technical_stamp - quote_stamp).total_seconds())
    status = "ok" if coverage >= 0.95 else "partial"
    return {
        "schema_version": "1.0",
        "contract": "canonical-screener-snapshot",
        "generatedAt": current.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "generatedAtTechnical": technical_stamp_raw,
        "generated_at": current.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
        "quote_generated_at": quote_stamp_raw,
        "technical_generated_at": technical_stamp_raw,
        "stale_after_minutes": stale_after,
        "source_skew_seconds": round(source_skew, 1),
        "status": status,
        "row_count": len(projected),
        "quote_row_count": len(quote_rows),
        "live_quote_count": live_count,
        "live_quote_coverage": round(coverage, 6),
        "watchlist": [ticker_of(row) for row in projected],
        "rows": projected,
        "errors": [
            {"symbol": symbol, "error": "live quote unavailable; technical fallback used"}
            for symbol in missing_symbols
        ],
        "source": "technical indicators + quote_latest live-price projection",
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {path}")


def main() -> None:
    snapshot = build_snapshot(load_json(QUOTE_PATH), load_json(TECHNICAL_PATH))
    for path in SNAPSHOT_PATHS:
        write_json(path, snapshot)
    # Keep legacy consumers, including Today/notification generation, on the
    # same canonical rows instead of an independent technical-only summary.
    for path in LEGACY_SUMMARY_PATHS:
        write_json(path, snapshot)
    print(
        f"canonical screener snapshot: {snapshot['row_count']} rows, "
        f"{snapshot['live_quote_coverage']:.1%} live quote coverage"
    )


if __name__ == "__main__":
    main()
