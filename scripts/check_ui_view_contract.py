#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

PAIRS = [
    ("memo-only-fix.js", "site/memo-only-fix.js", "static/memo-only-fix.js"),
    ("memo-only-fix.css", "site/memo-only-fix.css", "static/memo-only-fix.css"),
    ("final-ui-coordinator.js", "site/final-ui-coordinator.js", "static/final-ui-coordinator.js"),
    ("final-ui-coordinator.css", "site/final-ui-coordinator.css", "static/final-ui-coordinator.css"),
    ("notification-phase2.js", "site/notification-phase2.js", "static/notification-phase2.js"),
    ("notification-phase2.css", "site/notification-phase2.css", "static/notification-phase2.css"),
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
coordinator_js = read("site/final-ui-coordinator.js")
legacy_workflow = ROOT / ".github/workflows/fill-alert-center-content.yml"

for forbidden in (
    'if (document.body.classList.contains("attention-active")) return true;',
    "data-memo-previous-display",
    'style.setProperty("display", "none", "important")',
):
    if forbidden in memo_js:
        errors.append(f"Memo guard contains legacy runtime hiding: {forbidden}")

if "body.memo-active .attention-page" not in memo_css:
    errors.append("Memo CSS must explicitly hide the Today page")
if "body.memo-active #memoPage.memo-page" not in memo_css:
    errors.append("Memo CSS must explicitly show only #memoPage")
if "body.attention-active .attention-page" in memo_css and "display: block" in memo_css:
    errors.append("Memo CSS must not own Today page visibility")

for forbidden in (
    "insertBefore(",
    "appendChild(",
    "final-memo-primary",
    "final-scanner-secondary",
    "memoCandidates",
    "placeMemoBeforeScanner",
):
    if forbidden in coordinator_js:
        errors.append(f"Height coordinator contains DOM relocation logic: {forbidden}")

if legacy_workflow.exists():
    errors.append("legacy self-mutating CSS workflow still exists")

for index_path in ("site/index.html", "static/index.html"):
    index = read(index_path)
    for asset in (
        "notification-phase2.css",
        "notification-phase2.js",
        "final-ui-coordinator.css",
        "final-ui-coordinator.js",
        "memo-only-fix.css",
        "memo-only-fix.js",
    ):
        if asset not in index:
            errors.append(f"{index_path} missing asset reference: {asset}")

if errors:
    print("UI view contract failed:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    raise SystemExit(1)

print("UI view contract passed")
