#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "generated"
OUTPUTS = (
    DATA / "health.json",
    ROOT / "site" / "data" / "health.json",
    ROOT / "static" / "data" / "health.json",
)
FILES = {
    "quote": ("quote_latest.json", 30),
    "technical": ("technical.json", 1440),
    "source_market": ("source_freshness.json", 30),
    "attention": ("attention_today.json", 90),
    "events": ("events.json", 90),
    "consensus": ("recommendation_trends.json", 1440),
    "fundamental": ("fundamental.json", 24 * 60 * 35),
    # The producer runs every 12 hours. Keep the TTL slightly wider than the
    # schedule so a healthy artifact is not marked stale between runs.
    "market_pulse": ("market_pulse.json", 13 * 60),
}
MARKET_TZ = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)


def nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + (nth - 1) * 7)


def last_weekday(year: int, month: int, weekday: int) -> date:
    following = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    candidate = following - timedelta(days=1)
    return candidate - timedelta(days=(candidate.weekday() - weekday) % 7)


def observed_fixed_holiday(year: int, month: int, day: int) -> date:
    holiday = date(year, month, day)
    if holiday.weekday() == 5:
        return holiday - timedelta(days=1)
    if holiday.weekday() == 6:
        return holiday + timedelta(days=1)
    return holiday


def easter_sunday(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    leap = (32 + 2 * e + 2 * i - h - k) % 7
    correction = (a + 11 * h + 22 * leap) // 451
    month = (h + leap - 7 * correction + 114) // 31
    day = (h + leap - 7 * correction + 114) % 31 + 1
    return date(year, month, day)


def market_holidays(year: int) -> set[date]:
    return {
        observed_fixed_holiday(year, 1, 1),
        nth_weekday(year, 1, 0, 3),
        nth_weekday(year, 2, 0, 3),
        easter_sunday(year) - timedelta(days=2),
        last_weekday(year, 5, 0),
        observed_fixed_holiday(year, 6, 19),
        observed_fixed_holiday(year, 7, 4),
        nth_weekday(year, 9, 0, 1),
        nth_weekday(year, 11, 3, 4),
        observed_fixed_holiday(year, 12, 25),
    }


def is_trading_day(day: date) -> bool:
    if day.weekday() >= 5:
        return False
    return not any(day in market_holidays(year) for year in (day.year - 1, day.year, day.year + 1))


def previous_trading_day(day: date) -> date:
    candidate = day - timedelta(days=1)
    while not is_trading_day(candidate):
        candidate -= timedelta(days=1)
    return candidate


def market_session(now: datetime) -> dict[str, Any]:
    local = now.astimezone(MARKET_TZ)
    trading_day = is_trading_day(local.date())
    if local.weekday() >= 5:
        phase = "weekend"
    elif not trading_day:
        phase = "market-holiday"
    elif local.time() < MARKET_OPEN:
        phase = "pre-market"
    elif local.time() < MARKET_CLOSE:
        phase = "market-open"
    else:
        phase = "post-market"
    latest = local.date() if trading_day and local.time() >= MARKET_CLOSE else previous_trading_day(local.date())
    return {
        "timezone": str(MARKET_TZ),
        "phase": phase,
        "market_open": phase == "market-open",
        "local_date": local.date().isoformat(),
        "latest_completed_session": latest.isoformat(),
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


def inspect(path: Path, stale_after: int, *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if not path.exists() or path.stat().st_size == 0:
        status = "unavailable" if path.name in {"quote_latest.json", "source_freshness.json"} else "missing"
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
    age = None if not parsed else round((now - parsed).total_seconds() / 60, 1)
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
    if path.name == "quote_latest.json":
        session = market_session(now)
        fallback_count = int(data.get("fallback_count") or 0)
        explicit_fallback = data.get("status") in {"fallback", "degraded-fallback", "degraded_fallback"}
        if fallback_count > 0 or explicit_fallback:
            result["status"] = "degraded-fallback"
        elif parsed is None:
            result["status"] = "unavailable"
        elif session["market_open"]:
            result["status"] = "fresh" if age is not None and age <= stale_after else "stale"
        else:
            local_stamp = parsed.astimezone(MARKET_TZ)
            completed = (
                local_stamp.date().isoformat() == session["latest_completed_session"]
                and local_stamp.time() >= MARKET_CLOSE
            )
            result["status"] = "latest-completed-session" if completed else "stale"
        result["fallback_count"] = fallback_count
        result["session"] = session
    if path.name == "source_freshness.json":
        source_status = data.get("status")
        if source_status in {"fresh", "source_partial", "source_stale", "invalid"}:
            result["status"] = source_status
        for key in (
            "expected_market_date", "oldest_market_date", "newest_market_date",
            "timestamp_coverage", "stale_count", "stale_ratio", "missing_timestamp_count",
        ):
            result[key] = data.get(key)
        result["upstream_status"] = source_status
        if source_status == "fresh":
            session = market_session(now)
            newest = data.get("newest_market_date")
            expected = session["local_date"] if session["market_open"] else session["latest_completed_session"]
            result["status"] = (
                "fresh" if session["market_open"] and newest == expected
                else "latest-completed-session" if not session["market_open"] and newest == expected
                else "stale"
            )
            result["session"] = session
    if path.name == "attention_today.json":
        result["row_count"] = len(data.get("items", [])) if isinstance(data.get("items"), list) else None
        result["coverage_status"] = data.get("coverage_status")
        result["source_health"] = data.get("source_health")
        if data.get("coverage_status") == "partial" and result["status"] == "ok":
            result["status"] = "partial"
    if path.name == "events.json":
        result["row_count"] = len(data.get("events", [])) if isinstance(data.get("events"), list) else None
    return result


def overall_status(layers: dict[str, dict[str, Any]]) -> str:
    statuses = [layer["status"] for layer in layers.values()]
    critical_unavailable = layers.get("quote", {}).get("status") == "unavailable"
    error_states = {"missing", "invalid", "source_stale"}
    partial_states = {"partial", "source_partial", "degraded-fallback", "unavailable"}
    if critical_unavailable or any(status in error_states for status in statuses):
        return "error"
    if "stale" in statuses:
        return "stale"
    if any(status in partial_states for status in statuses):
        return "partial"
    return "ok"


def main() -> None:
    now = datetime.now(timezone.utc)
    payload = {
        "schema_version": "1.3",
        "generated_at": now.isoformat(),
        "market_session": market_session(now),
        "layers": {name: inspect(DATA / filename, ttl, now=now) for name, (filename, ttl) in FILES.items()},
    }
    payload["status"] = overall_status(payload["layers"])
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    for output in OUTPUTS:
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_bytes(encoded)
        os.replace(temporary, output)
        print("wrote", output)


if __name__ == "__main__":
    main()
