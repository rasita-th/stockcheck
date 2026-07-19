#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.exists():
        errors.append(f"missing: {relative}")
        return ""
    return path.read_text(encoding="utf-8")


site = read("site/attention-pr4.js")
static = read("static/attention-pr4.js")
earnings = read("site/earnings-radar-pr4.js")
coordinator = read("site/final-ui-coordinator.js")
loader = read("site/memo-only-fix.js")
deploy = read(".github/workflows/deploy-pages.yml")

if site and static and site != static:
    errors.append("site/static mismatch: attention-pr4.js")

for token in (
    'const VERSION = "10.4.2"',
    "MAX_UNIQUE_LOGOS_PER_PAGE = 6",
    "MAX_NON_DETAIL_LOGOS_PER_PAGE = 5",
    "MAX_LOGO_ATTEMPTS_PER_BROWSER_MONTH = 60",
    "LOGO_FAILURE_TTL_MS = 7 * 24 * 60 * 60 * 1000",
    "stockcheck.logoDev.usage.v2",
    "stockcheck.logoDev.failures.v2",
    "requestedLogoTickers = new Set()",
    "reserveLogoAttempt",
    'format=webp',
    'fallback=404',
    'referrerpolicy="origin"',
    "relevantEarnings",
    "stock-detail-company-logo",
    'version: "2.0.0"',
    "perBrowserMonth: MAX_LOGO_ATTEMPTS_PER_BROWSER_MONTH",
):
    if token not in site:
        errors.append(f"budgeted logo runtime missing: {token}")

for forbidden in (
    'const LOGO_DEV_TOKEN = "pk_',
    "MAX_LOGO_ATTEMPTS_PER_BROWSER_MONTH = 500000",
):
    if forbidden in site:
        errors.append(f"unsafe logo runtime token: {forbidden}")

if '__LOGO_DEV_PUBLISHABLE_KEY__' not in site:
    errors.append("Logo.dev deploy placeholder is missing")
if 'window.StockcheckCompanyLogo?.markup' not in earnings:
    errors.append("Earnings Radar is not using the shared logo adapter")
if 'syncStockDetailLogos' not in coordinator or 'stock-detail-company-logo' not in coordinator:
    errors.append("Stock Detail is not using the shared logo adapter")
if 'attention-pr4.js?v=10.4.2' not in loader:
    errors.append("PR4 loader cache key is not 10.4.2")

for token in (
    'TODAY_DEPLOY_VERSION: "10.6.0"',
    'LOGO_DEV_TOKEN: ${{ secrets.LOGO_DEV }}',
    "python scripts/apply_company_logo_budget.py",
    "python scripts/check_company_logo_budget.py",
):
    if token not in deploy:
        errors.append(f"Pages budget guard missing: {token}")

if not re.search(r'earningsRequest\s*&&\s*!relevantEarnings', site):
    errors.append("market-wide Earnings rows are not excluded from logo requests")

if errors:
    print("Company logo budget contract failed:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    raise SystemExit(1)

print("Company logo budget contract passed: 6/page, 5 non-detail, 60/browser/month")
