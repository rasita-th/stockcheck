#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "generated" / "earnings_radar.json"
VALID_RELATIONS = {"portfolio", "related", "coverage", "market"}
VALID_TIMES = {"before_market", "during_market", "after_market", "unknown"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def load() -> dict[str, Any]:
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), "earnings radar root must be an object")
    return payload


def main() -> None:
    payload = load()
    require(str(payload.get("schema_version") or "").startswith("1.0"), "earnings radar schema must be 1.0")
    require(isinstance(payload.get("summary"), dict), "summary must be an object")
    require(isinstance(payload.get("coverage"), dict), "coverage must be an object")
    require(isinstance(payload.get("daily_summary"), list), "daily_summary must be a list")
    require(isinstance(payload.get("items"), list), "items must be a list")
    require(isinstance(payload.get("policy"), dict), "policy must be an object")

    window = payload.get("window") if isinstance(payload.get("window"), dict) else {}
    start = date.fromisoformat(str(window.get("from")))
    end = date.fromisoformat(str(window.get("to")))
    require(start <= end, "earnings radar window is invalid")

    summary = payload["summary"]
    for key in (
        "total",
        "before_market",
        "during_market",
        "after_market",
        "unknown",
        "portfolio",
        "related",
        "coverage",
        "market",
        "confirmed",
        "estimated",
    ):
        require(isinstance(summary.get(key), int) and summary[key] >= 0, f"summary.{key} must be a non-negative integer")
    require(
        summary["total"] == summary["before_market"] + summary["during_market"] + summary["after_market"] + summary["unknown"],
        "summary timing counts do not add up",
    )
    require(
        summary["total"] == summary["portfolio"] + summary["related"] + summary["coverage"] + summary["market"],
        "summary relation counts do not add up",
    )

    coverage = payload["coverage"]
    for key in (
        "portfolio_total",
        "coverage_universe_total",
        "market_source_rows",
        "published_rows",
        "profile_names_known",
        "estimate_rows",
        "official_rows",
    ):
        require(isinstance(coverage.get(key), int) and coverage[key] >= 0, f"coverage.{key} must be a non-negative integer")
    require(coverage["market_source_rows"] >= coverage["published_rows"], "published rows cannot exceed market source rows after official overlays")
    require(coverage["coverage_universe_total"] >= coverage["portfolio_total"], "coverage universe cannot be smaller than portfolio")

    seen: set[tuple[str, str]] = set()
    today_count = 0
    selected_date = str(payload.get("selected_date") or "")
    for item in payload["items"]:
        require(isinstance(item, dict), "each earnings radar item must be an object")
        ticker = str(item.get("ticker") or "")
        event_date = str(item.get("earnings_date") or "")
        require(bool(ticker), "earnings radar item is missing ticker")
        parsed = date.fromisoformat(event_date)
        require(start <= parsed <= end, f"earnings item outside publish window: {ticker} {event_date}")
        key = (ticker, event_date)
        require(key not in seen, f"duplicate earnings item: {ticker} {event_date}")
        seen.add(key)
        require(item.get("relation") in VALID_RELATIONS, f"invalid relation for {ticker}")
        require(item.get("time") in VALID_TIMES, f"invalid event time for {ticker}")
        require(isinstance(item.get("related_to"), list), f"related_to must be a list for {ticker}")
        require(isinstance(item.get("priority_score"), int), f"priority_score must be an integer for {ticker}")
        require(item.get("eps_estimate") is None or isinstance(item.get("eps_estimate"), (int, float)), f"invalid EPS estimate for {ticker}")
        require(item.get("revenue_estimate") is None or isinstance(item.get("revenue_estimate"), (int, float)), f"invalid revenue estimate for {ticker}")
        if item.get("relation") == "portfolio":
            require(item.get("related_to") == [ticker], f"portfolio item relation must point to itself: {ticker}")
        if item.get("relation") == "related":
            require(bool(item.get("related_to")), f"related item is missing related portfolio tickers: {ticker}")
            require(bool(item.get("relation_reason_th")), f"related item is missing Thai rationale: {ticker}")
        if event_date == selected_date:
            today_count += 1

    require(today_count == summary["total"], "selected-date item count does not match summary.total")
    require(len(payload["items"]) == coverage["published_rows"], "coverage.published_rows does not match item count")
    require(len(payload["daily_summary"]) == (end - start).days + 1, "daily_summary does not cover every date in the window")

    mirrors = [ROOT / "site" / "data" / "earnings_radar.json", ROOT / "static" / "data" / "earnings_radar.json"]
    canonical = PATH.read_bytes()
    for mirror in mirrors:
        require(mirror.exists(), f"missing earnings radar mirror: {mirror}")
        require(mirror.read_bytes() == canonical, f"earnings radar mirror differs: {mirror}")

    print(
        "Earnings radar validation passed: "
        f"{summary['total']} selected-date rows / {coverage['published_rows']} window rows / "
        f"{coverage['market_source_rows']} source rows"
    )


if __name__ == "__main__":
    main()
