#!/usr/bin/env python3
"""Harden and validate the generated Earnings Radar contract.

This post-processing layer intentionally stays separate from the additive PR4A
normalizer. It guarantees that every published contract:

- is backed by cached market rows that actually overlap the published window;
- reports the real cached source date range and in-window row count;
- preserves optional estimate/actual keys as explicit ``null`` values;
- keeps canonical, site, and static mirrors byte-identical.

The script makes no network calls. A stale or non-overlapping provider cache is
an error, not a valid-looking empty market calendar.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "finnhub" / "state.json"
RADAR_PATHS = (
    ROOT / "data" / "generated" / "earnings_radar.json",
    ROOT / "site" / "data" / "earnings_radar.json",
    ROOT / "static" / "data" / "earnings_radar.json",
)
OPTIONAL_ITEM_FIELDS = (
    "fiscal_quarter",
    "event_time",
    "source_url",
    "eps_actual",
    "eps_estimate",
    "revenue_actual",
    "revenue_estimate",
    "note",
    "exchange",
    "industry",
    "logo_url",
    "market_cap_millions",
    "portfolio_role",
    "relation_reason_th",
)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"{path}: root must be an object")
    return payload


def parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except (TypeError, ValueError):
        return None


def raw_market_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    batch = state.get("batch") if isinstance(state.get("batch"), dict) else {}
    calendar = batch.get("earnings_calendar") if isinstance(batch.get("earnings_calendar"), dict) else {}
    rows = calendar.get("data") if isinstance(calendar.get("data"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def harden_payload(payload: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    window = payload.get("window") if isinstance(payload.get("window"), dict) else {}
    start = parse_date(window.get("from"))
    end = parse_date(window.get("to"))
    if start is None or end is None or start > end:
        raise SystemExit("earnings radar publish window is invalid")

    market_rows = raw_market_rows(state)
    market_dates = sorted(
        parsed
        for row in market_rows
        if (parsed := parse_date(row.get("date") or row.get("earnings_date"))) is not None
    )
    if not market_dates:
        raise SystemExit("Finnhub earnings cache contains no dated market rows")

    source_start = market_dates[0]
    source_end = market_dates[-1]
    overlapping_dates = [value for value in market_dates if start <= value <= end]
    if not overlapping_dates:
        raise SystemExit(
            "Finnhub earnings cache does not overlap the publish window: "
            f"source={source_start.isoformat()}..{source_end.isoformat()} "
            f"publish={start.isoformat()}..{end.isoformat()}"
        )

    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    for item in items:
        if not isinstance(item, dict):
            raise SystemExit("earnings radar item must be an object")
        for field in OPTIONAL_ITEM_FIELDS:
            item.setdefault(field, None)

    market_items_in_window = sum(
        1
        for item in items
        if isinstance(item, dict)
        and item.get("source_type") == "finnhub"
        and start <= (parse_date(item.get("earnings_date")) or date.min) <= end
    )
    if market_items_in_window <= 0:
        raise SystemExit(
            "earnings radar publish window has no normalized Finnhub market rows; "
            "refusing to publish an official-only calendar as market-wide"
        )

    coverage = payload.setdefault("coverage", {})
    if not isinstance(coverage, dict):
        raise SystemExit("earnings radar coverage must be an object")
    coverage["market_rows_in_window"] = market_items_in_window
    coverage["market_source_date_range"] = {
        "from": source_start.isoformat(),
        "to": source_end.isoformat(),
    }
    coverage["provider_window_overlap"] = {
        "from": max(start, source_start).isoformat(),
        "to": min(end, source_end).isoformat(),
    }
    coverage["provider_window_overlaps_publish_window"] = True

    policy = payload.setdefault("policy", {})
    if not isinstance(policy, dict):
        raise SystemExit("earnings radar policy must be an object")
    policy["stale_cache"] = (
        "Publication fails when cached market rows do not overlap the requested "
        "window or when no normalized Finnhub rows remain in-window."
    )
    policy["optional_fields"] = (
        "Optional estimate, actual, profile, source, and relation fields are always "
        "present and use null when unavailable."
    )
    return payload


def save_all(payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    for path in RADAR_PATHS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write the hardened payload to all mirrors")
    args = parser.parse_args()

    payload = harden_payload(load_json(RADAR_PATHS[0]), load_json(STATE_PATH))
    if args.write:
        save_all(payload)
    coverage = payload["coverage"]
    print(
        "Earnings Radar hardening passed: "
        f"{coverage['market_rows_in_window']} in-window market rows / "
        f"source {coverage['market_source_date_range']['from']}.."
        f"{coverage['market_source_date_range']['to']}"
    )


if __name__ == "__main__":
    main()
