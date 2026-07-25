#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"{path}: expected JSON object")
    return payload


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "stockcheck-production-verifier/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def verify_once(base_url: str, manifest: dict[str, Any], receipt: dict[str, Any], nonce: str) -> None:
    assets = manifest["assets"]
    index = fetch(f"{base_url}/index.html?verify={nonce}").decode("utf-8")
    loader_js = fetch(f"{base_url}/memo-only-fix.js?verify={nonce}").decode("utf-8")
    loader_css = fetch(f"{base_url}/memo-only-fix.css?verify={nonce}").decode("utf-8")
    attention = json.loads(fetch(f"{base_url}/data/attention_today.json?verify={nonce}"))
    earnings = json.loads(fetch(f"{base_url}/data/earnings_radar.json?verify={nonce}"))

    required = {
        f"memo-only-fix.js?v={assets['memo_only_fix_js']}": index,
        f"memo-only-fix.css?v={assets['memo_only_fix_css']}": index,
        f"attention-pr4.js?v={assets['attention_pr4_js']}": loader_js,
        f"earnings-radar-pr4.js?v={assets['earnings_radar_pr4_js']}": loader_js,
        f"attention-pr4.css?v={assets['attention_pr4_css']}": loader_css,
        f"earnings-radar-pr4.css?v={assets['earnings_radar_pr4_css']}": loader_css,
    }
    for token, text in required.items():
        if token not in text:
            raise ValueError(f"missing release token {token}")

    expected_attention = str(manifest["data_contracts"]["attention_today"])
    expected_earnings = str(manifest["data_contracts"]["earnings_radar"])
    if not str(attention.get("contract_version") or "").startswith(expected_attention):
        raise ValueError("attention_today contract mismatch")
    if not str(earnings.get("schema_version") or "").startswith(expected_earnings):
        raise ValueError("earnings_radar contract mismatch")
    if not isinstance(attention.get("items"), list) or not isinstance(attention.get("technical_watch"), list):
        raise ValueError("attention_today required sections missing")
    if not isinstance(earnings.get("items"), list) or not isinstance(earnings.get("daily_summary"), list):
        raise ValueError("earnings_radar required sections missing")

    release = str(manifest["release"])
    if str(receipt.get("asset_version") or "") != release:
        raise ValueError("deployment receipt release mismatch")
    if receipt.get("status") != "verified" or receipt.get("production_smoke_passed") is not True:
        raise ValueError("deployment receipt is not verified")
    if not str(receipt.get("source_commit") or ""):
        raise ValueError("deployment receipt source commit missing")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="config/release-manifest.json")
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--attempts", type=int, default=18)
    parser.add_argument("--sleep-seconds", type=int, default=5)
    args = parser.parse_args()

    manifest = load_json(Path(args.manifest))
    receipt = load_json(Path(args.receipt))
    base_url = str(manifest.get("production_base_url") or "").rstrip("/")
    if not base_url.startswith("https://"):
        raise SystemExit("release manifest production_base_url must be HTTPS")

    last_error: Exception | None = None
    for attempt in range(1, args.attempts + 1):
        try:
            verify_once(base_url, manifest, receipt, f"{int(time.time())}-{attempt}")
            print(json.dumps({"status": "verified", "release": manifest["release"], "source_commit": receipt["source_commit"]}))
            return
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            print(f"attempt {attempt}/{args.attempts} failed: {exc}")
            if attempt < args.attempts:
                time.sleep(args.sleep_seconds)
    raise SystemExit(f"production verification failed: {last_error}")


if __name__ == "__main__":
    main()
