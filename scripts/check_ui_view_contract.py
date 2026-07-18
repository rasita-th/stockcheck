#!/usr/bin/env python3
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PAIRS = [
    ("memo-only-fix.js", "site/memo-only-fix.js", "static/memo-only-fix.js"),
    ("memo-only-fix.css", "site/memo-only-fix.css", "static/memo-only-fix.css"),
    ("final-ui-coordinator.js", "site/final-ui-coordinator.js", "static/final-ui-coordinator.js"),
    ("final-ui-coordinator.css", "site/final-ui-coordinator.css", "static/final-ui-coordinator.css"),
    ("notification-phase2.js", "site/notification-phase2.js", "static/notification-phase2.js"),
    ("notification-phase2.css", "site/notification-phase2.css", "static/notification-phase2.css"),
    ("attention-p0.js", "site/attention-p0.js", "static/attention-p0.js"),
    ("attention-p0.css", "site/attention-p0.css", "static/attention-p0.css"),
    ("attention-pr3.js", "site/attention-pr3.js", "static/attention-pr3.js"),
    ("attention-pr3.css", "site/attention-pr3.css", "static/attention-pr3.css"),
    ("today-view-isolation.css", "site/today-view-isolation.css", "static/today-view-isolation.css"),
]
errors = []


def read(relative_path: str) -> str:
    path = ROOT / relative_path
    if not path.exists():
        errors.append(f"missing: {relative_path}")
        return ""
    return path.read_text(encoding="utf-8")


for label, site_path, static_path in PAIRS:
    site_text = read(site_path)
    static_text = read(static_path)
    if site_text and static_text and site_text != static_text:
        errors.append(f"site/static mismatch: {label}")

memo_js = read("site/memo-only-fix.js")
memo_css = read("site/memo-only-fix.css")
attention_js = read("site/attention-p0.js")
pr3_js = read("site/attention-pr3.js")
pr3_css = read("site/attention-pr3.css")
today_css = read("site/today-view-isolation.css")
coordinator_js = read("site/final-ui-coordinator.js")
coordinator_css = read("site/final-ui-coordinator.css")
legacy_workflow = ROOT / ".github/workflows/fill-alert-center-content.yml"

for forbidden in ('if (document.body.classList.contains("attention-active")) return true;', "data-memo-previous-display", 'style.setProperty("display", "none", "important")'):
    if forbidden in memo_js:
        errors.append(f"Memo guard contains legacy runtime hiding: {forbidden}")
if "attention-p0.js" not in memo_js or "10.2.0" not in memo_js:
    errors.append("Memo stability loader must load attention-p0.js v10.2.0 as fallback")
if "attention-pr3.js?v=10.3.0" not in memo_js or "loadAttentionP3" not in memo_js:
    errors.append("Memo stability loader must load attention-pr3.js v10.3.0 after the fallback")
if "attention-p0.css" not in memo_css or "10.2.0" not in memo_css:
    errors.append("Memo stability stylesheet must import attention-p0.css v10.2.0")
if "today-view-isolation.css" not in memo_css:
    errors.append("Memo stability stylesheet must import today-view-isolation.css")
if "attention-pr3.css?v=10.3.0" not in memo_css:
    errors.append("Memo stability stylesheet must import attention-pr3.css v10.3.0")
if "body.memo-active .attention-page" not in memo_css:
    errors.append("Memo CSS must explicitly hide the Today page")
if "body.memo-active #memoPage.memo-page" not in memo_css:
    errors.append("Memo CSS must explicitly show only #memoPage")
if "body.attention-active .attention-page" in memo_css and "display: block" in memo_css:
    errors.append("Memo CSS must not own Today page visibility")

for token in (
    "body.attention-active .portfolio-tabs",
    "body.attention-active .workspace",
    "body.attention-active .scanner-panel",
    "body.attention-active .decision-screener",
    "body.attention-active .lower-grid",
    "body.attention-active .mobile-scan-btn",
    "body.attention-active .bottom-sheet",
    "body.attention-active .attention-p0-page",
    "display: none !important",
):
    if token not in today_css:
        errors.append(f"Today isolation CSS missing Scanner guard: {token}")

for token in (
    "normalizePayload",
    "technical_watch",
    "source_chain",
    "externalSources",
    "เหตุการณ์สำคัญวันนี้",
    "จับตาทางเทคนิค",
    "ข่าวและเหตุการณ์",
    "ดูข้อมูลต้นฉบับ",
    "lastKnownGood",
    "Today render error",
):
    if token not in attention_js:
        errors.append(f"Today PR2 fallback adapter missing: {token}")
if 'window.StockcheckAttentionP0 = { version: "10.2.0"' not in attention_js:
    errors.append("Today fallback runtime version must be 10.2.0")
if 'definitions = [["primary_source", "Open source"]' in attention_js:
    errors.append("Today must not expose legacy internal source actions")
if "technical_json</" in attention_js:
    errors.append("Today UI must not render technical_json as visible source text")

for token in (
    "PR3 · PERSONAL RISK DESK",
    "attention-p3-ready",
    "เปลี่ยนจากรอบก่อน",
    "ตรวจแล้ว",
    "พัก 1 วัน",
    "ซ่อนวันนี้",
    "data-pr3-action",
    "data-pr3-pref",
    "StockcheckAttentionP3",
):
    if token not in pr3_js:
        errors.append(f"Today PR3 runtime missing: {token}")
for token in (".attention-p3-page", ".pr3-summary-grid", ".pr3-actions", "attention-p3-ready"):
    if token not in pr3_css:
        errors.append(f"Today PR3 CSS missing: {token}")

for forbidden in ("insertBefore(", "appendChild(", "final-memo-primary", "final-scanner-secondary", "memoCandidates", "placeMemoBeforeScanner"):
    if forbidden in coordinator_js:
        errors.append(f"Height coordinator contains DOM relocation logic: {forbidden}")
for token in ("openStockDetail", "closeStockDetail", "ensurePageGuides", "data-page-guide"):
    if token not in coordinator_js:
        errors.append(f"Usability coordinator missing: {token}")
if 'requestAnimationFrame(() => openStockDetail(stock));\n    }, true);' not in coordinator_js:
    errors.append("Desktop stock detail click must be captured before app.js rerenders the selected row")
for token in ('const VERSION = "9.6.2"', "window.StockRadarDetailDialog", "open: openStockDetail"):
    if token not in coordinator_js:
        errors.append(f"Desktop stock detail API missing: {token}")
for token in ("stock-detail-open", ".page-guide", "grid-template-columns: 260px minmax(0, 1fr)"):
    if token not in coordinator_css:
        errors.append(f"Usability stylesheet missing: {token}")
if legacy_workflow.exists():
    errors.append("legacy self-mutating CSS workflow still exists")
for index_path in ("site/index.html", "static/index.html"):
    index = read(index_path)
    for asset in ("notification-phase2.css", "notification-phase2.js", "final-ui-coordinator.css", "final-ui-coordinator.js", "memo-only-fix.css", "memo-only-fix.js"):
        if asset not in index:
            errors.append(f"{index_path} missing asset reference: {asset}")
    for token in ("scannerPageGuide", "desktopDetailBackdrop", "data-close-stock-detail"):
        if token not in index:
            errors.append(f"{index_path} missing usability UI: {token}")
    if 'id="setupSummary"' in index or 'id="fundamentalDashboard"' in index or 'id="playbookCards"' in index:
        errors.append(f"{index_path} still renders duplicated desktop detail cards")
    for asset in ("app.js?v=9.6.2", "final-ui-coordinator.css?v=9.6.2", "final-ui-coordinator.js?v=9.6.2"):
        if asset not in index:
            errors.append(f"{index_path} missing popup cache-bust asset: {asset}")

app_js = read("site/app.js")
if "window.StockRadarDetailDialog?.open(select)" not in app_js:
    errors.append("Stock selection handler must open the desktop dialog directly")
base_watchlist_match = re.search(r"const BASE_WATCHLIST = \[(.*?)\];", app_js)
if not base_watchlist_match or len(re.findall(r'"[A-Z0-9.\\-]+"', base_watchlist_match.group(1))) != 10:
    errors.append("First-run BASE_WATCHLIST must contain exactly 10 examples")
if errors:
    print("UI view contract failed:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    raise SystemExit(1)
print("UI view contract passed")
