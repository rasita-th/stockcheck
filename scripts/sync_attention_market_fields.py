#!/usr/bin/env python3
"""Project fresh canonical market fields into the Today attention mirrors."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
TECHNICAL_PATH = ROOT / "data" / "generated" / "technical.json"
ATTENTION_PATHS = (
    ROOT / "data" / "generated" / "attention_today.json",
    ROOT / "site" / "data" / "attention_today.json",
    ROOT / "static" / "data" / "attention_today.json",
)


def _number(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        try:
            value = float(row.get(key))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            return value
    return None


def _impact_label(change_pct: float | None) -> str:
    if change_pct is None:
        return "ยังไม่มีราคาฐานสำหรับเปรียบเทียบ"
    if abs(change_pct) < 0.5:
        return "ราคายังเปลี่ยนแปลงไม่มาก"
    direction = "ปรับขึ้น" if change_pct > 0 else "ปรับลง"
    return f"ราคาหลังเริ่มติดตาม{direction} {abs(change_pct):.1f}%"


def sync_payload(attention: dict[str, Any], technical: dict[str, Any]) -> int:
    rows = technical.get("rows") if isinstance(technical.get("rows"), list) else []
    by_ticker = {
        str(row.get("ticker") or row.get("symbol") or "").strip().upper(): row
        for row in rows
        if isinstance(row, dict)
    }
    updated = 0
    for section in ("items", "technical_watch"):
        attention_rows = attention.get(section) if isinstance(attention.get(section), list) else []
        for item in attention_rows:
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker") or "").strip().upper()
            source = by_ticker.get(ticker)
            if not isinstance(source, dict):
                continue
            price = _number(source, "price", "close", "regularMarketPrice")
            day_pct = _number(source, "dayPct", "day_change_pct", "changePercent")
            relative_volume = _number(
                source,
                "volumeRatio20",
                "relativeVolume",
                "relVolume",
                "volumeRatio",
            )
            if price is not None:
                item["price"] = price
            if day_pct is not None:
                item["day_change_pct"] = day_pct
            if relative_volume is not None:
                item["relative_volume"] = relative_volume

            impact = item.get("impact")
            if isinstance(impact, dict) and price is not None:
                baseline = _number(impact, "baseline_price")
                change_pct = round((price / baseline - 1) * 100, 2) if baseline else None
                impact["current_price"] = price
                impact["change_pct"] = change_pct
                impact["label_th"] = _impact_label(change_pct)
            updated += 1
    return updated


def sync_paths(technical_path: Path, attention_paths: Iterable[Path]) -> int:
    technical = json.loads(technical_path.read_text(encoding="utf-8"))
    paths = tuple(attention_paths)
    if not paths:
        raise SystemExit("no attention paths configured")
    attention = json.loads(paths[0].read_text(encoding="utf-8"))
    updated = sync_payload(attention, technical)
    rendered = json.dumps(attention, ensure_ascii=False, indent=2) + "\n"
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    return updated


def main() -> None:
    updated = sync_paths(TECHNICAL_PATH, ATTENTION_PATHS)
    print(f"Synchronized canonical market fields for {updated} attention rows.")


if __name__ == "__main__":
    main()
