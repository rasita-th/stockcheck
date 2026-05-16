#!/usr/bin/env python3
"""Validate static data files before GitHub Pages deployment.

This is intentionally lightweight: the goal is to fail loudly when a workflow
would deploy malformed JSON or a missing data layer, instead of leaving the UI
blank and making the problem look like a render bug.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = ROOT / "site" / "data"

REQUIRED_FILES = ["technical.json", "fundamental.json"]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing required static data file: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def validate_layer(name: str, data: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    rows = data.get("rows")
    if not isinstance(rows, list):
        raise SystemExit(f"{name}: rows must be a list")
    errors = data.get("errors", [])
    if errors is not None and not isinstance(errors, list):
        raise SystemExit(f"{name}: errors must be a list if present")
    if name == "technical" and len(rows) == 0:
        raise SystemExit("technical: rows is empty; refusing to deploy a blank scanner")
    if name == "fundamental" and len(rows) == 0:
        warnings.append("fundamental rows is empty; the UI will show a visible warning")
    if not (data.get("generatedAt") or data.get("generatedAtTechnical") or data.get("generatedAtFundamental")):
        warnings.append(f"{name} has no generatedAt timestamp")
    return warnings


def main() -> None:
    all_warnings: list[str] = []
    for file_name in REQUIRED_FILES:
        data = load_json(SITE_DATA / file_name)
        all_warnings.extend(validate_layer(file_name.replace(".json", ""), data))
    scanner_path = SITE_DATA / "scanner.json"
    if scanner_path.exists():
        load_json(scanner_path)
    for warning in all_warnings:
        print(f"::warning::{warning}")
    print("Static data validation passed")


if __name__ == "__main__":
    main()
