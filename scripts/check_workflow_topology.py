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

    pages = (WORKFLOW_DIR / PAGES_DEPLOYER).read_text(encoding="utf-8")
    for token in (
        'push:',
        'branches: ["main"]',
        'workflow_dispatch:',
        'expected_commit:',
        'DEPLOY_SOURCE_COMMIT:',
        'ref: ${{ env.DEPLOY_SOURCE_COMMIT }}',
        'group: pages-production',
        'cancel-in-progress: true',
    ):
        if token not in pages:
            failures.append(f"{PAGES_DEPLOYER}: missing single-trigger contract token {token!r}")

    publisher = (WORKFLOW_DIR / PUBLISHER).read_text(encoding="utf-8")
    for token in (
        "group: production-publisher",
        "cancel-in-progress: false",
        "actions: write",
        '"Refresh Live Data v10 PR3"',
        '"Refresh Market Pulse v9.6"',
        '"Update static fundamental data"',
        "validate_production_artifact.py validate",
        "data/publisher-state.json",
        "git push origin HEAD:main",
        "gh workflow run deploy-pages.yml",
        '-f expected_commit="$PUBLISHED_SHA"',
        "Publish result summary",
    ):
        if token not in publisher:
            failures.append(f"{PUBLISHER}: missing contract token {token!r}")

    verifier = (WORKFLOW_DIR / VERIFIER).read_text(encoding="utf-8")
    for token in (
        'workflows: ["Deploy GitHub Pages"]',
        "actions: read",
        "cancel-in-progress: false",
        "production-deploy-receipt-",
        "config/release-manifest.json",
        "verify_production_deployment.py",
    ):
        if token not in verifier:
            failures.append(f"{VERIFIER}: missing verifier contract token {token!r}")

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
