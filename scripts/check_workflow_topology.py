#!/usr/bin/env python3
"""Enforce the production workflow topology."""
from __future__ import annotations

from pathlib import Path

WORKFLOW_DIR = Path(".github/workflows")
PUBLISHER = "publish-production-data.yml"
ROLLBACK = "rollback-market-pulse.yml"
VERIFIER = "verify-production-deployment.yml"
PRODUCERS = {
    "refresh_finnhub_events.yml",
    "refresh-consensus-v9-1.yml",
    "refresh_finnhub_bundle.yml",
    "refresh-live-v9-1.yml",
    "refresh-market-pulse-v9-6.yml",
    "update-fundamental.yml",
}
PAGES_DEPLOYER = "deploy-pages.yml"
LIVE_WATCHDOG = "live-refresh-watchdog.yml"
OLD_HOSTNAME = "rasita2644-star.github.io/stockcheck"
LEGACY_VERIFIERS = {"verify-pr3-pages.yml", "verify-finnhub-today.yml"}


def main() -> None:
    failures: list[str] = []
    workflows = sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))
    names = {path.name for path in workflows}
    missing = PRODUCERS - names
    if missing:
        failures.append(f"missing protected producer workflows: {sorted(missing)}")
    if VERIFIER not in names:
        failures.append(f"missing unified production verifier: {VERIFIER}")
    active_legacy = LEGACY_VERIFIERS & names
    if active_legacy:
        failures.append(f"legacy production verifiers must be removed: {sorted(active_legacy)}")
    if "deploy-pages-after-pr3.yml" in names:
        failures.append("deploy-pages-after-pr3.yml: obsolete PR3 Pages bridge must be removed")
    if "refresh_market_live.yml" in names:
        failures.append("refresh_market_live.yml: legacy live writer must remain disabled")

    automatic_writers: list[str] = []
    pages_deployers: list[str] = []
    pages_dispatchers: list[str] = []
    live_refresh_dispatchers: list[str] = []
    for path in workflows:
        text = path.read_text(encoding="utf-8")
        name = path.name
        has_write = "contents: write" in text
        has_commit = "git commit" in text
        has_push = "git push" in text
        has_credentials = "persist-credentials: true" in text
        dispatches_pages = (
            "workflow_id: 'deploy-pages.yml'" in text
            or 'workflow_id: "deploy-pages.yml"' in text
            or "gh workflow run deploy-pages.yml" in text
        )
        dispatches_live_refresh = (
            "refresh-live-v9-1.yml" in text
            and "createWorkflowDispatch" in text
        )
        deploys_pages = "actions/deploy-pages@" in text

        if name in PRODUCERS:
            for token, present in {
                "contents: write": has_write,
                "git commit": has_commit,
                "git push": has_push,
                "persist-credentials: true": has_credentials,
            }.items():
                if present:
                    failures.append(f"{name}: producer contains forbidden token {token!r}")
            if "actions/upload-artifact@v4" not in text:
                failures.append(f"{name}: producer does not upload an immutable artifact")
            if "validate_production_artifact.py create-metadata" not in text:
                failures.append(f"{name}: producer does not emit schema 2 metadata")

        if has_write or has_commit or has_push:
            if name not in {PUBLISHER, ROLLBACK}:
                failures.append(f"{name}: unapproved repository writer")
            elif name == PUBLISHER:
                automatic_writers.append(name)
        if deploys_pages:
            pages_deployers.append(name)
        if dispatches_pages:
            pages_dispatchers.append(name)
        if dispatches_live_refresh:
            live_refresh_dispatchers.append(name)
        if OLD_HOSTNAME in text:
            failures.append(f"{name}: references obsolete production hostname")

    if automatic_writers != [PUBLISHER]:
        failures.append(f"automatic production writers must be exactly [{PUBLISHER!r}], got {automatic_writers}")
    if pages_deployers != [PAGES_DEPLOYER]:
        failures.append(f"Pages deploy owner must be exactly [{PAGES_DEPLOYER!r}], got {pages_deployers}")
    if pages_dispatchers != [PUBLISHER]:
        failures.append(
            f"Pages dispatcher must be exactly [{PUBLISHER!r}], got {pages_dispatchers}"
        )
    expected_live_dispatchers = [LIVE_WATCHDOG, "refresh-live-v9-1.yml"]
    if live_refresh_dispatchers != expected_live_dispatchers:
        failures.append(
            f"Live refresh dispatcher must be exactly {expected_live_dispatchers!r}, "
            f"got {live_refresh_dispatchers}"
        )

    pages = (WORKFLOW_DIR / PAGES_DEPLOYER).read_text(encoding="utf-8")
    for token in (
        'push:',
        'branches: ["main"]',
        'workflow_dispatch:',
        'expected_commit:',
        'actions: write',
        'DEPLOY_SOURCE_COMMIT:',
        'ref: ${{ env.DEPLOY_SOURCE_COMMIT }}',
        'group: pages-production',
        'cancel-in-progress: true',
        'context="production/stockcheck-pages-v10-8"',
        'gh workflow run verify-production-deployment.yml',
        '--repo "$GITHUB_REPOSITORY"',
        'if: github.event_name == \'workflow_dispatch\'',
    ):
        if token not in pages:
            failures.append(f"{PAGES_DEPLOYER}: missing single-trigger contract token {token!r}")

    publisher = (WORKFLOW_DIR / PUBLISHER).read_text(encoding="utf-8")
    for token in (
        "group: production-publisher",
        "cancel-in-progress: false",
        "actions: write",
        "producer_run_id:",
        "getWorkflowRun",
        "steps.source.outputs.run_id",
        '"Refresh Live Data v10 PR3"',
        '"Refresh Market Pulse v9.6"',
        '"Update static fundamental data"',
        "validate_production_artifact.py validate",
        "scripts/sync_attention_market_fields.py",
        "data/publisher-state.json",
        "git push origin HEAD:main",
        "gh workflow run deploy-pages.yml",
        '-f expected_commit="$PUBLISHED_SHA"',
        "Publish result summary",
    ):
        if token not in publisher:
            failures.append(f"{PUBLISHER}: missing contract token {token!r}")

    watchdog = (WORKFLOW_DIR / LIVE_WATCHDOG).read_text(encoding="utf-8")
    for token in (
        "producer_run_id:",
        "actions: write",
        "contents: read",
        "group: live-refresh-watchdog-main",
        "cancel-in-progress: true",
        "listWorkflowRuns",
        "getWorkflowRun",
        "createWorkflowDispatch",
        "scripts/live-refresh-watchdog.js",
    ):
        if token not in watchdog:
            failures.append(f"{LIVE_WATCHDOG}: missing watchdog contract token {token!r}")
    for forbidden in ("contents: write", "git commit", "git push"):
        if forbidden in watchdog:
            failures.append(f"{LIVE_WATCHDOG}: watchdog contains forbidden token {forbidden!r}")

    live_producer = (WORKFLOW_DIR / "refresh-live-v9-1.yml").read_text(encoding="utf-8")
    for token in (
        "actions: write",
        "jobs:\n  admission:",
        "scripts/live-refresh-dedupe.js",
        "listWorkflowRuns",
        "cancelWorkflowRun",
        'workflow_id: "publish-production-data.yml"',
        'workflow_id: "live-refresh-watchdog.yml"',
        "needs: admission",
        "if: needs.admission.outputs.run_refresh == 'true'",
        "group: live-data-producer-main",
        "cancel-in-progress: false",
    ):
        if token not in live_producer:
            failures.append(f"refresh-live-v9-1.yml: missing delayed-schedule admission token {token!r}")

    verifier = (WORKFLOW_DIR / VERIFIER).read_text(encoding="utf-8")
    for token in (
        'workflows: ["Deploy GitHub Pages"]',
        "actions: read",
        "cancel-in-progress: false",
        "production-deploy-receipt-",
        "config/release-manifest.json",
        "verify_production_deployment.py",
        "if: always() && needs.identity.result == 'success'",
    ):
        if token not in verifier:
            failures.append(f"{VERIFIER}: missing verifier contract token {token!r}")

    receipt_consumers = {
        VERIFIER,
        "report-pages-10-8.yml",
        "verify-production-screener.yml",
    }
    for name in sorted(receipt_consumers):
        consumer = (WORKFLOW_DIR / name).read_text(encoding="utf-8")
        if "production-deploy-receipt-" not in consumer:
            failures.append(f"{name}: completion consumer must download the deployment receipt")
        if "github.event.workflow_run.head_sha" in consumer:
            failures.append(f"{name}: completion consumer must not trust workflow_run.head_sha")

    if "production-deploy-receipt-${{ github.run_id }}" not in pages:
        failures.append(f"{PAGES_DEPLOYER}: deploy owner must upload the immutable deployment receipt")

    for required_path in (Path("config/release-manifest.json"), Path("scripts/verify_production_deployment.py")):
        if not required_path.exists():
            failures.append(f"missing release contract file: {required_path}")

    rollback = (WORKFLOW_DIR / ROLLBACK).read_text(encoding="utf-8")
    for token in ("workflow_dispatch:", "confirm:", "inputs.confirm == 'ROLLBACK'", "group: production-publisher", "cancel-in-progress: false"):
        if token not in rollback:
            failures.append(f"{ROLLBACK}: missing rollback safety token {token!r}")
    for forbidden in ("schedule:", "workflow_run:"):
        if forbidden in rollback:
            failures.append(f"{ROLLBACK}: rollback must be manual only; found {forbidden!r}")

    if failures:
        raise SystemExit("Workflow topology violations:\n- " + "\n- ".join(failures))
    print("Workflow topology is valid. One automatic writer, one exact-commit Pages dispatcher/deployer, one manual rollback, and one receipt-backed production verifier are active.")


if __name__ == "__main__":
    main()
