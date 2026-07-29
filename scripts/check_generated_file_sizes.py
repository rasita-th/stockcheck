#!/usr/bin/env python3
"""Reject generated outputs that exceed repository-safe size budgets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
MIB = 1024 * 1024
EXACT_LIMITS = {
    "data/finnhub/state.json": (10 * MIB, 15 * MIB),
    "data/finnhub_features.json": (3 * MIB, 5 * MIB),
    "site/data/finnhub_features.json": (3 * MIB, 5 * MIB),
    "static/data/finnhub_features.json": (3 * MIB, 5 * MIB),
}
DEFAULT_JSON_LIMIT = (10 * MIB, 25 * MIB)
PATCH_LIMIT = (25 * MIB, 40 * MIB)


def budget_for(path: str, patch_hard_limit_mib: int | None = None) -> tuple[int, int] | None:
    if path in EXACT_LIMITS:
        return EXACT_LIMITS[path]
    if path.endswith(".json") and (path.startswith("data/") or path.startswith("site/data/") or path.startswith("static/data/")):
        return DEFAULT_JSON_LIMIT
    if path.endswith("production-data.patch"):
        warning, hard = PATCH_LIMIT
        if patch_hard_limit_mib is not None:
            hard = patch_hard_limit_mib * MIB
        return warning, hard
    return None


def inspect(paths: Iterable[str], patch_hard_limit_mib: int | None = None) -> dict[str, int]:
    sizes: dict[str, int] = {}
    failures: list[str] = []
    for path in sorted(set(paths)):
        budget = budget_for(path, patch_hard_limit_mib=patch_hard_limit_mib)
        target = ROOT / path
        if budget is None or not target.exists() or not target.is_file():
            continue
        size = target.stat().st_size
        warning, hard = budget
        sizes[path] = size
        if size > hard:
            failures.append(f"{path} is {size / MIB:.2f} MiB; hard limit is {hard / MIB:.2f} MiB")
        elif size > warning:
            print(f"::warning::{path} is {size / MIB:.2f} MiB; warning threshold is {warning / MIB:.2f} MiB")
    print(json.dumps({"checked": sizes, "patch_hard_limit_mib": patch_hard_limit_mib}, indent=2))
    if failures:
        raise SystemExit("REJECTED_FILE_TOO_LARGE: " + "; ".join(failures))
    return sizes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch-hard-limit-mib", type=int)
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    if args.patch_hard_limit_mib is not None and not 40 <= args.patch_hard_limit_mib <= 50:
        raise SystemExit("patch hard-limit override must be between 40 and 50 MiB")
    inspect(args.paths, patch_hard_limit_mib=args.patch_hard_limit_mib)


if __name__ == "__main__":
    main()
