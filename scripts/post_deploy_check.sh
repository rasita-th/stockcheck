#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-}"
if [[ -z "$BASE_URL" ]]; then
  echo "Usage: $0 https://owner.github.io/repo/"
  exit 2
fi

BASE_URL="${BASE_URL%/}/"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Checking production: $BASE_URL"

curl -fsSL --retry 3 --retry-delay 2 "${BASE_URL}" -o "$TMP/index.html"
for token in Scanner Today Memo "Market Pulse"; do
  grep -q "$token" "$TMP/index.html" || {
    echo "FAIL: live HTML is missing navigation token: $token"
    exit 1
  }
done

curl -fsSL --retry 3 --retry-delay 2 "${BASE_URL}data/technical.json" -o "$TMP/technical.json"
ROWS="$(python3 - "$TMP/technical.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
rows = payload.get("rows")
if not isinstance(rows, list):
    raise SystemExit("technical rows is not a list")
print(len(rows))
PY
)"

if [[ "$ROWS" -le 0 ]]; then
  echo "FAIL: live technical rows = $ROWS"
  exit 1
fi

for asset in app.js market.html market.js; do
  curl -fsSI --retry 3 --retry-delay 2 "${BASE_URL}${asset}" >/dev/null || {
    echo "FAIL: live asset unavailable: $asset"
    exit 1
  }
done

echo "PASS: production page reachable"
echo "PASS: navigation labels found"
echo "PASS: required assets reachable"
echo "PASS: technical rows = $ROWS"
