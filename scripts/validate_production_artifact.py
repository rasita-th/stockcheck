#!/usr/bin/env python3
"""Create and validate immutable production-data artifacts.

This module is intentionally dependency-free so producers and the publisher use
exactly the same metadata, hashing, path and replay rules.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPOSITORY = "rasita-th/stockcheck"
SCHEMA_VERSION = "2.0"

PRODUCERS: dict[str, dict[str, Any]] = {
    "Refresh Finnhub Earnings Events": {
        "events": {"schedule", "workflow_dispatch", "push"},
        "paths": (
            "data/finnhub/**",
            "data/earnings_calendar.json",
            "data/eps_surprises.json",
            "data/finnhub_features.json",
            "data/generated/**",
            "data/source_state/**",
            "site/data/**",
            "static/data/**",
        ),
    },
    "Refresh Finnhub Analyst Features": {
        "events": {"schedule", "workflow_dispatch"},
        "paths": (
            "data/finnhub/**",
            "data/recommendation_trends.json",
            "data/finnhub_features.json",
            "site/data/recommendation_trends.json",
            "site/data/finnhub_features.json",
            "static/data/recommendation_trends.json",
            "static/data/finnhub_features.json",
        ),
    },
    "Refresh Finnhub Full Backfill": {
        "events": {"workflow_dispatch"},
        "paths": (
            "data/finnhub/**",
            "data/earnings_calendar.json",
            "data/eps_surprises.json",
            "data/recommendation_trends.json",
            "data/finnhub_features.json",
            "site/data/earnings_calendar.json",
            "site/data/eps_surprises.json",
            "site/data/recommendation_trends.json",
            "site/data/finnhub_features.json",
            "static/data/earnings_calendar.json",
            "static/data/eps_surprises.json",
            "static/data/recommendation_trends.json",
            "static/data/finnhub_features.json",
        ),
    },
}

BLOCKED_PATTERNS = (
    ".github/**",
    "scripts/**",
    "tests/**",
    "requirements.txt",
    "site/*.js",
    "site/*.css",
    "static/*.js",
    "static/*.css",
)


def fail(message: str, code: str) -> "NoReturn":
    raise SystemExit(f"{code}: {message}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def changed_paths() -> list[str]:
    output = git_output("diff", "--name-only", "HEAD", "--")
    return sorted({line.strip() for line in output.splitlines() if line.strip()})


def matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return path == prefix or path.startswith(prefix + "/")
    return fnmatch.fnmatchcase(path, pattern)


def validate_paths(producer: str, paths: list[str]) -> None:
    config = PRODUCERS.get(producer)
    if not config:
        fail(f"unknown producer {producer!r}", "REJECTED_UNKNOWN_PRODUCER")
    allowed = config["paths"]
    for path in paths:
        if any(matches(path, pattern) for pattern in BLOCKED_PATTERNS):
            fail(f"blocked path {path}", "REJECTED_PATH")
        if not any(matches(path, pattern) for pattern in allowed):
            fail(f"path {path} is outside the allowlist for {producer}", "REJECTED_PATH")


def write_output(values: dict[str, Any]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={str(value).lower() if isinstance(value, bool) else value}\n")


def create_metadata(args: argparse.Namespace) -> None:
    patch = Path(args.patch)
    metadata_path = Path(args.metadata)
    producer = os.environ.get("GITHUB_WORKFLOW", "").strip()
    if producer not in PRODUCERS:
        fail(f"unknown producer {producer!r}", "REJECTED_UNKNOWN_PRODUCER")
    paths = changed_paths()
    validate_paths(producer, paths)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "repository": os.environ.get("GITHUB_REPOSITORY", REPOSITORY),
        "producer": producer,
        "producer_run_id": str(os.environ.get("GITHUB_RUN_ID", "")),
        "producer_run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
        "producer_event": os.environ.get("GITHUB_EVENT_NAME", ""),
        "producer_branch": os.environ.get("GITHUB_REF_NAME", ""),
        "producer_sha": os.environ.get("GITHUB_SHA", ""),
        "base_sha": git_output("rev-parse", "HEAD"),
        "produced_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "patch_sha256": sha256(patch),
        "changed_paths": paths,
    }
    metadata_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": "1.0", "producers": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0" or not isinstance(payload.get("producers"), dict):
        fail("publisher ledger has an unsupported schema", "REJECTED_LEDGER")
    return payload


def parse_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def validate_artifact(args: argparse.Namespace) -> None:
    patch = Path(args.patch)
    metadata = json.loads(Path(args.metadata).read_text(encoding="utf-8"))
    schema = str(metadata.get("schema_version") or "")
    if schema not in {"1.0", SCHEMA_VERSION}:
        fail(f"unsupported artifact schema {schema!r}", "REJECTED_SCHEMA")

    expected = {
        "producer_run_id": str(args.run_id),
        "producer_sha": args.source_sha,
    }
    for key, value in expected.items():
        if str(metadata.get(key) or "") != str(value):
            fail(f"{key} mismatch", "REJECTED_SOURCE")

    producer = str(metadata.get("producer") or args.workflow_name)
    config = PRODUCERS.get(producer)
    if not config or producer != args.workflow_name:
        fail(f"workflow name {args.workflow_name!r} does not match an allowed producer", "REJECTED_UNKNOWN_PRODUCER")
    if args.repository != REPOSITORY:
        fail(f"unexpected repository {args.repository!r}", "REJECTED_SOURCE")
    if args.branch != "main":
        fail(f"producer branch must be main, got {args.branch!r}", "REJECTED_SOURCE")
    if args.event not in config["events"]:
        fail(f"event {args.event!r} is not allowed for {producer}", "REJECTED_SOURCE")

    actual_hash = sha256(patch)
    if schema == SCHEMA_VERSION:
        if metadata.get("repository") != REPOSITORY:
            fail("metadata repository mismatch", "REJECTED_SOURCE")
        if str(metadata.get("producer_branch")) != args.branch:
            fail("metadata branch mismatch", "REJECTED_SOURCE")
        if str(metadata.get("producer_event")) != args.event:
            fail("metadata event mismatch", "REJECTED_SOURCE")
        if int(metadata.get("producer_run_attempt") or 0) != int(args.run_attempt):
            fail("producer run attempt mismatch", "REJECTED_SOURCE")
        if metadata.get("patch_sha256") != actual_hash:
            fail("patch SHA-256 mismatch", "REJECTED_HASH_MISMATCH")
        paths = metadata.get("changed_paths")
        if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
            fail("changed_paths must be a string list", "REJECTED_SCHEMA")
    else:
        # One-release compatibility for artifacts produced before PR-A merged.
        paths = []

    validate_paths(producer, paths)
    ledger = load_ledger(Path(args.ledger))
    previous = ledger["producers"].get(producer, {})
    run_id = int(args.run_id)
    run_attempt = int(args.run_attempt)
    produced_at = parse_time(metadata.get("produced_at"))
    previous_at = parse_time(previous.get("last_produced_at"))

    status = "READY"
    reason = "artifact passed validation"
    if int(previous.get("last_run_id") or 0) == run_id and int(previous.get("last_run_attempt") or 0) >= run_attempt:
        status, reason = "SKIPPED_REPLAY", "producer run and attempt were already published"
    elif previous.get("last_patch_sha256") == actual_hash and actual_hash:
        status, reason = "SKIPPED_DUPLICATE", "patch content was already published"
    elif produced_at and previous_at and produced_at <= previous_at:
        status, reason = "SKIPPED_STALE", "artifact is older than the last published artifact"
    elif not patch.exists() or patch.stat().st_size == 0:
        status, reason = "NO_CHANGES", "producer completed with an empty patch"

    write_output({
        "status": status,
        "reason": reason,
        "producer": producer,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "patch_sha256": actual_hash,
        "changed_count": len(paths),
        "produced_at": metadata.get("produced_at", ""),
        "legacy_schema": schema == "1.0",
    })
    print(json.dumps({"status": status, "reason": reason, "producer": producer, "changed_paths": paths}, indent=2))


def record_ledger(args: argparse.Namespace) -> None:
    path = Path(args.ledger)
    ledger = load_ledger(path)
    ledger["producers"][args.producer] = {
        "last_run_id": int(args.run_id),
        "last_run_attempt": int(args.run_attempt),
        "last_produced_at": args.produced_at,
        "last_patch_sha256": args.patch_sha256,
        "last_published_source_sha": args.source_sha,
        "publisher_run_id": os.environ.get("GITHUB_RUN_ID", ""),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-metadata")
    create.add_argument("--patch", required=True)
    create.add_argument("--metadata", required=True)
    create.set_defaults(func=create_metadata)

    validate = sub.add_parser("validate")
    validate.add_argument("--patch", required=True)
    validate.add_argument("--metadata", required=True)
    validate.add_argument("--ledger", required=True)
    validate.add_argument("--repository", required=True)
    validate.add_argument("--workflow-name", required=True)
    validate.add_argument("--run-id", required=True)
    validate.add_argument("--run-attempt", required=True)
    validate.add_argument("--source-sha", required=True)
    validate.add_argument("--branch", required=True)
    validate.add_argument("--event", required=True)
    validate.set_defaults(func=validate_artifact)

    record = sub.add_parser("record")
    record.add_argument("--ledger", required=True)
    record.add_argument("--producer", required=True)
    record.add_argument("--run-id", required=True)
    record.add_argument("--run-attempt", required=True)
    record.add_argument("--produced-at", required=True)
    record.add_argument("--patch-sha256", required=True)
    record.add_argument("--source-sha", required=True)
    record.set_defaults(func=record_ledger)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
