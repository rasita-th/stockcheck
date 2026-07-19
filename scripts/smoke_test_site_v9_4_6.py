#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PREPARE_SCRIPT = ROOT / "scripts" / "prepare_stable_site_v9_4_1.py"


def deployment_version() -> str:
    text = PREPARE_SCRIPT.read_text(encoding="utf-8")
    match = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', text, flags=re.MULTILINE)
    if not match:
        raise SystemExit(f"{PREPARE_SCRIPT}: VERSION constant not found")
    return match.group(1)


def require_text(path: Path, tokens: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    for token in tokens:
        if token not in text:
            raise SystemExit(f"{path}: missing required token {token!r}")


def validate_json(name: str, require_rows: bool = True) -> None:
    path = SITE / "data" / name
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("rows")
    if not isinstance(rows, list):
        raise SystemExit(f"{path}: rows must be a list")
    if require_rows and not rows:
        raise SystemExit(f"{path}: rows are empty")
    print(f"{name}: {len(rows)} rows")


def validate_market_pulse() -> None:
    path = SITE / "data" / "market_pulse.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("global_markets", "us_indices", "us_sectors", "themes"):
        if not isinstance(data.get(key), list):
            raise SystemExit(f"{path}: {key} must be a list")
    print(f"market_pulse.json: schema {data.get('schema_version', 'legacy')}")


def validate_attention() -> None:
    path = SITE / "data" / "attention_today.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items")
    technical_watch = data.get("technical_watch", [])
    if not isinstance(items, list) or not isinstance(technical_watch, list):
        raise SystemExit(f"{path}: items and technical_watch must be lists")
    if len(items) > 7 or len(technical_watch) > 7:
        raise SystemExit(f"{path}: each Today section may contain at most 7 items")
    for item in items:
        events = item.get("events") if isinstance(item, dict) and isinstance(item.get("events"), list) else []
        if events and all(event.get("event_type") == "technical" for event in events):
            raise SystemExit(f"{path}: technical-only item leaked into main catalysts")
    for item in technical_watch:
        events = item.get("events") if isinstance(item, dict) and isinstance(item.get("events"), list) else []
        if not events or any(event.get("event_type") != "technical" for event in events):
            raise SystemExit(f"{path}: invalid technical_watch item")
    if str(data.get("contract_version") or "").startswith("3.0"):
        for key in ("changes_summary", "recently_resolved", "preferences_applied"):
            if key not in data:
                raise SystemExit(f"{path}: PR3 field missing: {key}")
        for item in items + technical_watch:
            if not isinstance(item.get("change"), dict) or not isinstance(item.get("impact"), dict):
                raise SystemExit(f"{path}: PR3 history fields missing for {item.get('ticker')}")
    print(f"attention_today.json: {len(items)} catalysts, {len(technical_watch)} technical watch")


def main() -> None:
    version = deployment_version()
    require_text(SITE / "index.html", (
        'id="technicalTableBody"', 'id="technicalMobileCards"', 'id="alertCenter"', 'id="detailPanel"',
        f'app.js?v={version}', f'app-shell-v9-4-6.css?v={version}', f'app-shell-v9-4-6.js?v={version}',
    ))
    require_text(SITE / "app-shell-v9-4-6.js", ("Scanner", "Today", "Memo", "Market Pulse", 'data-app-view'))
    require_text(SITE / "memo-only-fix.js", (
        "attention-p0.js", "attention-pr3.js?v=10.3.0", "attention-pr4.js?v=10.4.1",
        "loadAttentionP3", "loadAttentionP4",
    ))
    require_text(SITE / "memo-only-fix.css", (
        "attention-p0.css?v=10.2.0", "today-view-isolation.css",
        "attention-pr3.css?v=10.3.0", "attention-pr4.css?v=10.4.1",
    ))
    require_text(SITE / "attention-p0.js", (
        "สิ่งที่ต้องจับตาวันนี้", "เหตุการณ์สำคัญวันนี้", "จับตาทางเทคนิค", "technical_watch",
        "normalizePayload", "ข่าวและเหตุการณ์", "externalSources", "source_chain", "lastKnownGood", "Today render error",
    ))
    require_text(SITE / "attention-pr3.js", (
        "PR3 · PERSONAL RISK DESK", "เปลี่ยนจากรอบก่อน", "พัก 1 วัน", "ซ่อนวันนี้",
        "data-pr3-action", "data-pr3-pref", "attention-p3-ready", "StockcheckAttentionP3",
    ))
    require_text(SITE / "attention-pr3.css", (".attention-p3-page", ".pr3-summary-grid", ".pr3-actions", "attention-p3-ready"))
    require_text(SITE / "attention-pr4.js", (
        "PR4 · DECISION-FIRST TODAY", "attention-p4-ready", "p4-catalyst-hero", "p4-technical-grid",
        "validatePayload", "externalSources", "data-p4-action", "data-p4-filter", "StockcheckAttentionP4",
        "StockcheckCompanyLogo", "img.logo.dev/ticker/", "fallback=404",
    ))
    require_text(SITE / "attention-pr4.css", (
        ".attention-p4-page", ".p4-summary-strip", ".p4-catalyst-hero", ".p4-technical-grid",
        "body.attention-p4-ready #attentionPageP3",
    ))
    require_text(SITE / "today-view-isolation.css", (
        "body.attention-active .portfolio-tabs", "body.attention-active .workspace",
        "body.attention-active .decision-screener", "body.attention-active .attention-p0-page",
        "body.attention-active.attention-p4-ready #attentionPageP4", "display: none !important",
    ))
    require_text(SITE / "market.html", ('id="marketBriefing"', 'id="pulseHeadline"', f'market.js?v={version}'))
    validate_json("technical.json", require_rows=True)
    validate_json("fundamental.json", require_rows=False)
    validate_market_pulse()
    validate_attention()
    print(f"v{version} static UI smoke test passed")


if __name__ == "__main__":
    main()
