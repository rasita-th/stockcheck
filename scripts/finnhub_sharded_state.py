#!/usr/bin/env python3
"""Hydrate and shard Finnhub state without changing producer write ownership.

The pipeline may use data/finnhub/state.json as an ephemeral working file, while
published state is stored as small endpoint/ticker shards under data/finnhub/state/.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FINNHUB_DIR = ROOT / "data" / "finnhub"
LEGACY_PATH = FINNHUB_DIR / "state.json"
SHARD_ROOT = FINNHUB_DIR / "state"
INDEX_PATH = SHARD_ROOT / "index.json"
SCHEMA_VERSION = "2.0.0"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def atomic_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def safe_name(value: Any) -> str:
    name = str(value or "").strip()
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")
    if not name or len(name) > 80 or set(name) - allowed or name in {".", ".."}:
        raise ValueError(f"unsafe shard name: {value!r}")
    return name


def relative_path(path: Path) -> str:
    return path.relative_to(SHARD_ROOT).as_posix()


def resolve_shard(relative: Any) -> Path:
    candidate = SHARD_ROOT / str(relative or "")
    resolved_root = SHARD_ROOT.resolve()
    resolved = candidate.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError(f"shard path escapes state root: {relative!r}")
    return resolved


def hydrate_state() -> dict[str, Any]:
    index = load_json(INDEX_PATH, {})
    if not isinstance(index, dict) or index.get("schema_version") != SCHEMA_VERSION:
        legacy = load_json(LEGACY_PATH, {})
        if isinstance(legacy, dict) and legacy:
            return {"status": "legacy", "endpoint_count": len(legacy.get("endpoints", {}))}
        raise SystemExit("SHARDED_STATE_MISSING: no valid index or legacy state")

    endpoints: dict[str, dict[str, Any]] = {}
    manifest = index.get("endpoints") if isinstance(index.get("endpoints"), dict) else {}
    for endpoint, tickers in manifest.items():
        endpoint_name = safe_name(endpoint)
        if not isinstance(tickers, dict):
            raise SystemExit(f"SHARDED_STATE_INVALID: endpoint manifest {endpoint_name} is not an object")
        bucket: dict[str, Any] = {}
        for ticker, relative in tickers.items():
            ticker_name = safe_name(ticker)
            payload = load_json(resolve_shard(relative), None)
            if not isinstance(payload, dict):
                raise SystemExit(f"SHARDED_STATE_INVALID: missing or invalid shard {relative}")
            bucket[ticker_name] = payload
        endpoints[endpoint_name] = bucket

    batch: dict[str, Any] = {}
    batch_manifest = index.get("batch") if isinstance(index.get("batch"), dict) else {}
    for name, relative in batch_manifest.items():
        payload = load_json(resolve_shard(relative), None)
        if not isinstance(payload, dict):
            raise SystemExit(f"SHARDED_STATE_INVALID: missing or invalid batch shard {relative}")
        batch[safe_name(name)] = payload

    state = {
        "schema_version": str(index.get("state_schema_version") or "1.0.0"),
        "updated_at": index.get("updated_at"),
        "endpoints": endpoints,
        "batch": batch,
        "runs": index.get("runs") if isinstance(index.get("runs"), list) else [],
    }
    atomic_write(LEGACY_PATH, state)
    return {
        "status": "hydrated",
        "endpoint_count": len(endpoints),
        "ticker_shards": sum(len(bucket) for bucket in endpoints.values()),
        "batch_shards": len(batch),
    }


def shard_state(delete_legacy: bool) -> dict[str, Any]:
    state = load_json(LEGACY_PATH, {})
    if not isinstance(state, dict) or not isinstance(state.get("endpoints"), dict):
        raise SystemExit("SHARDED_STATE_INVALID: legacy working state is missing or invalid")

    expected: set[Path] = set()
    endpoint_manifest: dict[str, dict[str, str]] = {}
    for endpoint, entries in sorted(state["endpoints"].items()):
        endpoint_name = safe_name(endpoint)
        if not isinstance(entries, dict):
            continue
        ticker_manifest: dict[str, str] = {}
        for ticker, payload in sorted(entries.items()):
            ticker_name = safe_name(ticker)
            if not isinstance(payload, dict):
                continue
            path = SHARD_ROOT / "endpoints" / endpoint_name / f"{ticker_name}.json"
            atomic_write(path, payload)
            expected.add(path.resolve())
            ticker_manifest[ticker_name] = relative_path(path)
        endpoint_manifest[endpoint_name] = ticker_manifest

    batch_manifest: dict[str, str] = {}
    batch = state.get("batch") if isinstance(state.get("batch"), dict) else {}
    for name, payload in sorted(batch.items()):
        name_safe = safe_name(name)
        if not isinstance(payload, dict):
            continue
        path = SHARD_ROOT / "batch" / f"{name_safe}.json"
        atomic_write(path, payload)
        expected.add(path.resolve())
        batch_manifest[name_safe] = relative_path(path)

    index = {
        "schema_version": SCHEMA_VERSION,
        "state_schema_version": str(state.get("schema_version") or "1.0.0"),
        "updated_at": state.get("updated_at"),
        "endpoints": endpoint_manifest,
        "batch": batch_manifest,
        "runs": (state.get("runs") if isinstance(state.get("runs"), list) else [])[-20:],
        "contract": {
            "legacy_working_file": "ephemeral",
            "published_layout": "endpoint-ticker-shards",
        },
    }
    atomic_write(INDEX_PATH, index)
    expected.add(INDEX_PATH.resolve())

    removed = 0
    if SHARD_ROOT.exists():
        for path in sorted(SHARD_ROOT.rglob("*.json"), reverse=True):
            if path.resolve() not in expected:
                path.unlink()
                removed += 1
        for directory in sorted((p for p in SHARD_ROOT.rglob("*") if p.is_dir()), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass

    if delete_legacy and LEGACY_PATH.exists():
        LEGACY_PATH.unlink()

    return {
        "status": "sharded",
        "endpoint_count": len(endpoint_manifest),
        "ticker_shards": sum(len(bucket) for bucket in endpoint_manifest.values()),
        "batch_shards": len(batch_manifest),
        "removed_stale_shards": removed,
        "legacy_deleted": delete_legacy,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("hydrate")
    shard = subparsers.add_parser("shard")
    shard.add_argument("--delete-legacy", action="store_true")
    args = parser.parse_args()
    result = hydrate_state() if args.command == "hydrate" else shard_state(args.delete_legacy)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
