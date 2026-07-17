#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== Repository =="
git status --short
git branch --show-current
git log -1 --oneline

echo "== Required tools =="
command -v git
command -v python3
command -v node

echo "== Python syntax =="
python3 -m py_compile scripts/preflight_check.py
if [[ -f scripts/prepare_stable_site_v9_4_1.py ]]; then
  python3 -m py_compile scripts/prepare_stable_site_v9_4_1.py
fi

echo "== JavaScript syntax =="
node --check site/app.js
node --check site/market.js

for file in site/app-shell-*.js site/runtime-guard-*.js site/shared-app-shell-*.js; do
  [[ -f "$file" ]] || continue
  node --check "$file"
done

echo "== Static validation =="
python3 scripts/preflight_check.py --site site

echo "Preflight passed."
