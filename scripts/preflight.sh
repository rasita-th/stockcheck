#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "== Repository =="
git status --short
git branch --show-current
git log -1 --oneline

echo "== Required tools =="
command -v git
command -v python3
command -v node

echo "== Source syntax =="
python3 -m py_compile scripts/prepare_stable_site_v9_4_1.py scripts/preflight_check.py scripts/validate_static_data.py
node --check site/app.js
node --check site/market.js
node --check site/app-shell-v9-4-6.js

echo "== Build clean artifact in temporary directory =="
mkdir -p "$TMP/repo"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --exclude .git --exclude stockcheck_terminal_deploy_kit "$ROOT/" "$TMP/repo/"
else
  cp -R "$ROOT/." "$TMP/repo/"
  rm -rf "$TMP/repo/.git" "$TMP/repo/stockcheck_terminal_deploy_kit"
fi

(
  cd "$TMP/repo"
  python3 scripts/prepare_stable_site_v9_4_1.py
  python3 scripts/validate_static_data.py
  python3 scripts/preflight_check.py --site site
)

echo "Preflight passed. Source was not modified; validation ran against a temporary prepared artifact."
