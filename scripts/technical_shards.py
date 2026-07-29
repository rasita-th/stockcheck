#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUTS = (
    ROOT / "data" / "generated" / "technical",
    ROOT / "site" / "data" / "technical",
    ROOT / "static" / "data" / "technical",
)
SAFE_SYMBOL = re.compile(r"^[A-Z0-9._-]{1,32}$")


def safe_symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper()
    if not SAFE_SYMBOL.fullmatch(symbol):
        raise ValueError(f"unsafe technical shard symbol: {value!r}")
    return symbol


def build_index(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    errors = payload.get("errors") if isinstance(payload.get("errors"), list) else []
    return {
        "schema_version": "2.0",
        "generatedAt": payload.get("generatedAt"),
        "generatedAtTechnical": payload.get("generatedAtTechnical") or payload.get("generatedAt"),
        "count": len(rows),
        "rows": rows,
        "errors": errors,
        "range": payload.get("range"),
        "interval": payload.get("interval"),
        "mode": "github-pages-technical-index-v2",
        "shardPattern": "symbols/{symbol}.json",
    }


def build_legacy_summary(payload: dict[str, Any], *, mode: str) -> dict[str, Any]:
    """Keep the old filenames as small summary fallbacks during rollout."""
    index = build_index(payload)
    return {
        "schema_version": "2.0-summary",
        "generatedAt": index["generatedAt"],
        "generatedAtTechnical": index["generatedAtTechnical"],
        "count": index["count"],
        "rows": index["rows"],
        "errors": index["errors"],
        "range": index["range"],
        "interval": index["interval"],
        "mode": mode,
        "dataLayer": "technical",
        "quotes": {},
        "detailContract": "technical/symbols/{symbol}.json",
    }


def build_shards(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    quotes = payload.get("quotes") if isinstance(payload.get("quotes"), dict) else {}
    generated = payload.get("generatedAtTechnical") or payload.get("generatedAt")
    result: dict[str, dict[str, Any]] = {}
    for raw_symbol, detail in quotes.items():
        symbol = safe_symbol(raw_symbol)
        if not isinstance(detail, dict):
            continue
        result[symbol] = {
            "schema_version": "2.0",
            "symbol": symbol,
            "generatedAt": generated,
            "latest": detail.get("latest"),
            "series": detail.get("series") if isinstance(detail.get("series"), list) else [],
            "meta": detail.get("meta") if isinstance(detail.get("meta"), dict) else {},
        }
    return result


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)


def write_outputs(payload: dict[str, Any], output_dirs: Iterable[Path] = DEFAULT_OUTPUTS) -> dict[str, int]:
    index = build_index(payload)
    shards = build_shards(payload)
    written: dict[str, int] = {}
    expected = {f"{symbol}.json" for symbol in shards}
    for output_dir in output_dirs:
        symbols_dir = output_dir / "symbols"
        symbols_dir.mkdir(parents=True, exist_ok=True)
        for stale in symbols_dir.glob("*.json"):
            if stale.name not in expected:
                stale.unlink()
        write_json(output_dir / "index.json", index)
        for symbol, shard in shards.items():
            write_json(symbols_dir / f"{symbol}.json", shard)
        written[str(output_dir)] = len(shards)
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", default="site/data/technical.json")
    args = parser.parse_args()
    payload = json.loads((ROOT / args.source).read_text(encoding="utf-8"))
    result = write_outputs(payload)
    print(json.dumps({"written": result}, indent=2))


if __name__ == "__main__":
    main()
