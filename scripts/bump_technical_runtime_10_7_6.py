#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
prepare = ROOT / "scripts" / "prepare_stable_site_v9_4_1.py"
manifest = ROOT / "config" / "release-manifest.json"

prepare_text = prepare.read_text(encoding="utf-8")
old = 'TECHNICAL_RUNTIME_VERSION = "10.7.5"'
new = 'TECHNICAL_RUNTIME_VERSION = "10.7.6"'
if old not in prepare_text and new not in prepare_text:
    raise SystemExit("technical runtime version declaration not found")
prepare.write_text(prepare_text.replace(old, new), encoding="utf-8")

manifest_text = manifest.read_text(encoding="utf-8")
old_manifest = '"technical_shards_js": "10.7.5"'
new_manifest = '"technical_shards_js": "10.7.6"'
if old_manifest not in manifest_text and new_manifest not in manifest_text:
    raise SystemExit("technical_shards_js manifest entry not found")
manifest.write_text(manifest_text.replace(old_manifest, new_manifest), encoding="utf-8")

print("Technical runtime cache version set to 10.7.6")
