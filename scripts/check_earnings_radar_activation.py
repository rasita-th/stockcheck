#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []


def read(path: str) -> str:
    target = ROOT / path
    if not target.exists():
        errors.append(f"missing: {path}")
        return ""
    return target.read_text(encoding="utf-8")


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        errors.append(message)


def require_regex(text: str, pattern: str, message: str) -> None:
    if re.search(pattern, text) is None:
        errors.append(message)


loader = read("site/memo-only-fix.js")
styles = read("site/memo-only-fix.css")
radar_runtime = read("site/earnings-radar-pr4.js")
deploy = read(".github/workflows/deploy-pages.yml")

# Runtime activation: accept any semantic asset version instead of pinning the
# validator to one historical release string.
require_regex(
    loader,
    r"earnings-radar-pr4\.js\?v=\d+\.\d+\.\d+",
    "production loader does not reference a versioned Earnings Radar runtime",
)
require(loader, "loadEarningsRadar", "production loader missing loadEarningsRadar")
require(loader, "loadScript(", "production loader missing dynamic script activation")
require_regex(
    styles,
    r"earnings-radar-pr4\.css\?v=\d+\.\d+\.\d+",
    "production stylesheet does not import a versioned Earnings Radar stylesheet",
)
require(radar_runtime, "StockcheckEarningsRadarP4", "Earnings Radar runtime export is missing")
require(radar_runtime, 'data/earnings_radar.json', "Earnings Radar production data URL is missing")
require(radar_runtime, "data-er-date-input", "Earnings Radar date input contract is missing")
require(radar_runtime, "data-er-export", "Earnings Radar export contract is missing")

# Deployment topology and immutable production verification. These checks are
# intentionally semantic: wording and individual smoke-test implementation may
# evolve without breaking deployment activation.
require_regex(
    deploy,
    r'TODAY_DEPLOY_VERSION:\s*["\']\d+\.\d+\.\d+["\']',
    "Pages workflow does not declare a semantic deploy version",
)
for token, message in (
    ("statuses: write", "Pages workflow cannot publish verified commit status"),
    ("group: pages-production", "Pages workflow is not isolated from publisher concurrency"),
    ("cancel-in-progress: true", "Pages workflow does not supersede stale deployments"),
    ("node --check site/earnings-radar-pr4.js", "Pages workflow does not syntax-check Earnings Radar"),
    ("python scripts/validate_earnings_radar.py", "Pages workflow does not validate Earnings Radar data"),
    ('Path("site/build.json")', "Pages workflow does not stamp immutable build identity"),
    ("actions/upload-pages-artifact@v3", "Pages workflow does not upload a Pages artifact"),
    ("actions/deploy-pages@v4", "Pages workflow does not deploy through GitHub Pages"),
    ("Verify deployed commit and data identity", "Pages workflow lacks production identity verification"),
    ("build.get('source_commit')", "Pages workflow does not compare the deployed commit"),
    ("attention identity mismatch", "Pages workflow does not compare deployed attention data"),
    ("market identity mismatch", "Pages workflow does not compare deployed market data"),
    ("production/stockcheck-pages", "Pages workflow does not expose verified production status"),
):
    require(deploy, token, message)

for relative in (
    "data/generated/earnings_radar.json",
    "site/data/earnings_radar.json",
    "static/data/earnings_radar.json",
):
    path = ROOT / relative
    if not path.exists():
        errors.append(f"missing activation data: {relative}")
        continue
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"invalid activation data {relative}: {exc}")
        continue
    window = payload.get("window") if isinstance(payload.get("window"), dict) else {}
    coverage = payload.get("coverage") if isinstance(payload.get("coverage"), dict) else {}
    if int(window.get("days_forward") or 0) < 45:
        errors.append(f"activation data is not a 45-day contract: {relative}")
    if int(coverage.get("market_source_rows") or 0) <= int(coverage.get("portfolio_total") or 0):
        errors.append(f"activation data is not market-wide: {relative}")

if errors:
    print("Earnings Radar activation contract failed:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    raise SystemExit(1)
print("Earnings Radar activation contract passed")
