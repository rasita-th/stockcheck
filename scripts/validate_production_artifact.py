#!/usr/bin/env python3
"""Create and validate immutable production-data artifacts."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

REPOSITORY = "rasita-th/stockcheck"
SCHEMA_VERSION = "2.0"
PRODUCERS: dict[str, dict[str, Any]] = {
    "Refresh Finnhub Earnings Events": {
        "events": {"schedule", "workflow_dispatch", "push"},
        "paths": ("data/finnhub/**", "data/earnings_calendar.json", "data/eps_surprises.json", "data/finnhub_features.json", "data/generated/**", "data/source_state/**", "site/data/**", "static/data/**"),
    },
    "Refresh Finnhub Analyst Features": {
        "events": {"schedule", "workflow_dispatch"},
        "paths": ("data/finnhub/**", "data/recommendation_trends.json", "data/finnhub_features.json", "site/data/recommendation_trends.json", "site/data/finnhub_features.json", "static/data/recommendation_trends.json", "static/data/finnhub_features.json"),
    },
    "Refresh Finnhub Full Backfill": {
        "events": {"workflow_dispatch"},
        "paths": ("data/finnhub/**", "data/earnings_calendar.json", "data/eps_surprises.json", "data/recommendation_trends.json", "data/finnhub_features.json", "site/data/earnings_calendar.json", "site/data/eps_surprises.json", "site/data/recommendation_trends.json", "site/data/finnhub_features.json", "static/data/earnings_calendar.json", "static/data/eps_surprises.json", "static/data/recommendation_trends.json", "static/data/finnhub_features.json"),
    },
}
BLOCKED_PATTERNS = (".github/**", "scripts/**", "tests/**", "requirements.txt", "site/*.js", "site/*.css", "static/*.js", "static/*.css")


def fail(message: str, code: str) -> NoReturn:
    raise SystemExit(f"{code}: {message}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def patch_paths(path: Path) -> list[str]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    output = subprocess.check_output(["git", "apply", "--numstat", str(path)], text=True)
    result: set[str] = set()
    for line in output.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3 and parts[2].strip():
            result.add(parts[2].strip())
    return sorted(result)


def matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return path == prefix or path.startswith(prefix + "/")
    return fnmatch.fnmatchcase(path, pattern)


def validate_paths(producer: str, paths: list[str]) -> None:
    config = PRODUCERS.get(producer)
    if not config:
        fail(f"unknown producer {producer!r}", "REJECTED_UNKNOWN_PRODUCER")
    for path in paths:
        if any(matches(path, pattern) for pattern in BLOCKED_PATTERNS):
            fail(f"blocked path {path}", "REJECTED_PATH")
        if not any(matches(path, pattern) for pattern in config["paths"]):
            fail(f"path {path} is outside the allowlist for {producer}", "REJECTED_PATH")


def write_output(values: dict[str, Any]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as handle:
            for key, value in values.items():
                handle.write(f"{key}={str(value).lower() if isinstance(value, bool) else value}\n")


def create_metadata(args: argparse.Namespace) -> None:
    patch = Path(args.patch)
    producer = os.environ.get("GITHUB_WORKFLOW", "").strip()
    paths = patch_paths(patch)
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
        "base_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "produced_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "patch_sha256": sha256(patch),
        "changed_paths": paths,
    }
    Path(args.metadata).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
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
    if str(metadata.get("producer_run_id") or "") != str(args.run_id) or str(metadata.get("producer_sha") or "") != args.source_sha:
        fail("producer run ID or SHA mismatch", "REJECTED_SOURCE")
    producer = str(metadata.get("producer") or args.workflow_name)
    config = PRODUCERS.get(producer)
    if not config or producer != args.workflow_name:
        fail(f"workflow {args.workflow_name!r} is not allowed", "REJECTED_UNKNOWN_PRODUCER")
    if args.repository != REPOSITORY or args.branch != "main" or args.event not in config["events"]:
        fail("repository, branch or event is not allowed", "REJECTED_SOURCE")

    actual_hash = sha256(patch)
    paths = patch_paths(patch)
    if schema == SCHEMA_VERSION:
        expected = {"repository": REPOSITORY, "producer_branch": args.branch, "producer_event": args.event}
        for key, value in expected.items():
            if str(metadata.get(key) or "") != str(value):
                fail(f"metadata {key} mismatch", "REJECTED_SOURCE")
        if int(metadata.get("producer_run_attempt") or 0) != int(args.run_attempt):
            fail("producer run attempt mismatch", "REJECTED_SOURCE")
        if metadata.get("patch_sha256") != actual_hash:
            fail("patch SHA-256 mismatch", "REJECTED_HASH_MISMATCH")
        if metadata.get("changed_paths") != paths:
            fail("changed_paths do not match patch content", "REJECTED_PATH")
    validate_paths(producer, paths)

    previous = load_ledger(Path(args.ledger))["producers"].get(producer, {})
    produced_at = parse_time(metadata.get("produced_at"))
    previous_at = parse_time(previous.get("last_produced_at"))
    status, reason = "READY", "artifact passed validation"
    if int(previous.get("last_run_id") or 0) == int(args.run_id) and int(previous.get("last_run_attempt") or 0) >= int(args.run_attempt):
        status, reason = "SKIPPED_REPLAY", "producer run and attempt were already published"
    elif previous.get("last_patch_sha256") == actual_hash and actual_hash:
        status, reason = "SKIPPED_DUPLICATE", "patch content was already published"
    elif produced_at and previous_at and produced_at <= previous_at:
        status, reason = "SKIPPED_STALE", "artifact is older than the last published artifact"
    elif patch.stat().st_size == 0:
        status, reason = "NO_CHANGES", "producer completed with an empty patch"
    write_output({"status": status, "reason": reason, "producer": producer, "run_id": args.run_id, "run_attempt": args.run_attempt, "patch_sha256": actual_hash, "changed_count": len(paths), "produced_at": metadata.get("produced_at", ""), "legacy_schema": schema == "1.0"})
    print(json.dumps({"status": status, "reason": reason, "producer": producer, "changed_paths": paths}, indent=2))


def record_ledger(args: argparse.Namespace) -> None:
    path = Path(args.ledger)
    ledger = load_ledger(path)
    ledger["producers"][args.producer] = {"last_run_id": int(args.run_id), "last_run_attempt": int(args.run_attempt), "last_produced_at": args.produced_at, "last_patch_sha256": args.patch_sha256, "last_published_source_sha": args.source_sha, "publisher_run_id": os.environ.get("GITHUB_RUN_ID", "")}
    path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-metadata")
    create.add_argument("--patch", required=True); create.add_argument("--metadata", required=True); create.set_defaults(func=create_metadata)
    validate = sub.add_parser("validate")
    for name in ("patch", "metadata", "ledger", "repository", "workflow-name", "run-id", "run-attempt", "source-sha", "branch", "event"):
        validate.add_argument(f"--{name}", required=True)
    validate.set_defaults(func=validate_artifact)
    record = sub.add_parser("record")
    for name in ("ledger", "producer", "run-id", "run-attempt", "produced-at", "patch-sha256", "source-sha"):
        record.add_argument(f"--{name}", required=True)
    record.set_defaults(func=record_ledger)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
