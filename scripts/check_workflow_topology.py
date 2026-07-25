#!/usr/bin/env python3
"""Enforce the production workflow topology during the staged migration."""
from __future__ import annotations

from pathlib import Path

WORKFLOW_DIR = Path(".github/workflows")
PUBLISHER = "publish-production-data.yml"
ROLLBACK = "rollback-market-pulse.yml"
PRODUCERS = {
    "refresh_finnhub_events.yml",
    "refresh-consensus-v9-1.yml",
    "refresh_finnhub_bundle.yml",
    "refresh-live-v9-1.yml",
}
# Temporary, explicit migration debt. PR-C and PR-D must remove these names;
# new exceptions are forbidden.
LEGACY_WRITER_EXCEPTIONS = {
    "refresh_market_live.yml",
    "refresh-market-pulse-v9-6.yml",
    "update-fundamental.yml",
}
DISPATCH_ALLOWLIST = {PUBLISHER}
OLD_HOSTNAME = "rasita2644-star.github.io/stockcheck"


def main() -> None:
    failures: list[str] = []
    workflows = sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))
    names = {path.name for path in workflows}
    missing = PRODUCERS - names
    if missing:
        failures.append(f"missing protected producer workflows: {sorted(missing)}")
    if "deploy-pages-after-pr3.yml" in names:
        failures.append("deploy-pages-after-pr3.yml: obsolete PR3 Pages bridge must be removed")

    for path in workflows:
        text = path.read_text(encoding="utf-8")
        name = path.name
        has_write = "contents: write" in text
        has_commit = "git commit" in text
        has_push = "git push" in text
        has_credentials = "persist-credentials: true" in text
        dispatches_pages = "workflow_id: 'deploy-pages.yml'" in text or 'workflow_id: "deploy-pages.yml"' in text

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

        writer_allowed = name in {PUBLISHER, ROLLBACK} | LEGACY_WRITER_EXCEPTIONS
        if (has_write or has_commit or has_push) and not writer_allowed:
            failures.append(f"{name}: unapproved repository writer")
        if dispatches_pages and name not in DISPATCH_ALLOWLIST:
            failures.append(f"{name}: unapproved Pages dispatcher")
        if OLD_HOSTNAME in text:
            failures.append(f"{name}: references obsolete production hostname")

    publisher = (WORKFLOW_DIR / PUBLISHER).read_text(encoding="utf-8")
    required = (
        "group: production-publisher",
        "cancel-in-progress: false",
        '"Refresh Live Data v10 PR3"',
        "validate_production_artifact.py validate",
        "data/publisher-state.json",
        "git push origin HEAD:main",
        "Publish result summary",
    )
    for token in required:
        if token not in publisher:
            failures.append(f"{PUBLISHER}: missing contract token {token!r}")

    if failures:
        raise SystemExit("Workflow topology violations:\n- " + "\n- ".join(failures))
    print(
        "Workflow topology is valid. Temporary legacy writer exceptions: "
        + ", ".join(sorted(LEGACY_WRITER_EXCEPTIONS))
    )


if __name__ == "__main__":
    main()
