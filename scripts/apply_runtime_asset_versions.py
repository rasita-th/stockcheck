#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
MANIFEST = ROOT / "config" / "release-manifest.json"


def replace_version(html: str, asset: str, version: str) -> str:
    pattern = rf"({re.escape(asset)})(?:\?[^\"']*)?"
    updated, count = re.subn(pattern, rf"\1?v={version}", html, flags=re.I)
    if count < 1:
        raise SystemExit(f"asset reference missing: {asset}")
    return updated


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assets = manifest.get("assets") if isinstance(manifest.get("assets"), dict) else {}
    shell_js = str(assets.get("app_shell_js") or "").strip()
    shell_css = str(assets.get("app_shell_css") or "").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", shell_js):
        raise SystemExit("manifest assets.app_shell_js must be semantic")
    if not re.fullmatch(r"\d+\.\d+\.\d+", shell_css):
        raise SystemExit("manifest assets.app_shell_css must be semantic")

    index_path = SITE / "index.html"
    index = index_path.read_text(encoding="utf-8")
    index = replace_version(index, "app-shell-v9-4-6.css", shell_css)
    index = replace_version(index, "app-shell-v9-4-6.js", shell_js)
    index_path.write_text(index, encoding="utf-8")

    market_path = SITE / "market.html"
    market = market_path.read_text(encoding="utf-8")
    market = replace_version(market, "app-shell-v9-4-6.css", shell_css)
    market_path.write_text(market, encoding="utf-8")

    index_check = index_path.read_text(encoding="utf-8")
    market_check = market_path.read_text(encoding="utf-8")
    for token in (
        f"app-shell-v9-4-6.js?v={shell_js}",
        f"app-shell-v9-4-6.css?v={shell_css}",
    ):
        if token not in index_check:
            raise SystemExit(f"index cache identity missing: {token}")
    if f"app-shell-v9-4-6.css?v={shell_css}" not in market_check:
        raise SystemExit("market shell CSS cache identity missing")

    print(f"Applied shell runtime identities: js={shell_js} css={shell_css}")


if __name__ == "__main__":
    main()
