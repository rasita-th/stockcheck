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


def forbid_text(path: Path, tokens: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    for token in tokens:
        if token in text:
            raise SystemExit(f"{path}: forbidden legacy token {token!r}")


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
    narrative = data.get("narrative")
    if narrative is not None:
        modes = narrative.get("modes") if isinstance(narrative, dict) else None
        if not isinstance(modes, dict):
            raise SystemExit(f"{path}: narrative.modes must be an object when narrative exists")
        for key in ("balanced", "portfolio", "action", "news", "risk"):
            if key not in modes:
                raise SystemExit(f"{path}: narrative mode missing: {key}")
    print(f"market_pulse.json: schema {data.get('schema_version', 'legacy')} (legacy-compatible)")


def main() -> None:
    version = deployment_version()
    require_text(SITE / "index.html", (
        'id="technicalTableBody"',
        'id="technicalMobileCards"',
        'id="alertCenter"',
        'id="detailPanel"',
        f'app.js?v={version}',
        f'app-shell-v9-4-6.css?v={version}',
        f'app-shell-v9-4-6.js?v={version}',
    ))
    require_text(SITE / "app-shell-v9-4-6.js", (
        "Scanner", "Today", "Memo", "Market Pulse",
        'data-app-view', "verifyDataAndRecover",
    ))
    require_text(SITE / "market.html", (
        'index.html#scanner', 'index.html#today', 'index.html#memo', 'Market Pulse',
        'id="marketBriefing"', 'id="pulseHeadline"', 'id="pulseSummaryList"',
        'id="pulseSignalGrid"', 'data-pulse-mode="balanced"', 'data-pulse-mode="portfolio"',
        'data-pulse-mode="action"', 'data-pulse-mode="news"', 'data-pulse-mode="risk"',
        f'market.css?v={version}', f'market.js?v={version}',
    ))
    require_text(SITE / "market.js", (
        'stockTimingRadar.watchlist.v54', 'technical.json', 'normaliseNarrative',
        'applyPortfolioNarrative', 'pulseStaleBadge',
    ))
    forbid_text(SITE / "index.html", (
        "scanner-dashboard", "scanner-layout-v9-3", "shared-app-shell-v9-3",
        "nav-fix-v9-2", "runtime-guard-v9-4-1", "mobile-nav-v9-4-2",
    ))
    validate_json("technical.json", require_rows=True)
    validate_json("fundamental.json", require_rows=False)
    validate_market_pulse()
    print(f"v{version} static UI smoke test passed")


if __name__ == "__main__":
    main()
