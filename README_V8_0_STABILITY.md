# Stock Timing Radar v8.0 — Stability & Data Integrity

This release intentionally stops adding new product surface area and focuses on making the existing app reliable enough to use until the next development cycle.

## What changed

- Mobile screeners are fixed and stable: `Default`, `Momentum`, `Thai`, `Port 1`, `Port 2`, `Port 3`, `Settings`.
- Mobile no longer depends on dynamic `+ New` screener rendering, which was unreliable on Safari/mobile browsers.
- Memo status cockpit remains in place: bilingual Thai + English status, tags, note/current/target price, action plan.
- Memo alerts stay persistent until the user acts on them.
- Static data integrity banner shows technical/fundamental freshness, row counts, and warnings.
- Added `scripts/validate_static_data.py` so GitHub Actions fails loudly if static JSON is malformed or technical data is blank.
- Bundled sample `site/data/*.json` so the static UI has a visible preview before workflows regenerate live data.
- Added debug helper in browser console:

```js
window.__stockcheckDiagnosticsV80()
```

## Release freeze

Recommended: after deploying v8.0, stop feature changes until the next review window. Only patch critical data or rendering bugs.

## Deploy

```bash
cd ~/Downloads
unzip stockcheck_github_pages_deploy_v8_0_stability.zip

cd ~/Desktop/stockcheck
git checkout -b deploy-v8-0-stability

rsync -av --delete \
  --exclude=".git" \
  ~/Downloads/stockcheck_github_deploy_v8_0_stability/ \
  ./

git add .
git commit -m "Release Stock Timing Radar v8.0 stability"
git push -u origin deploy-v8-0-stability
```

Then merge the PR and run GitHub Actions:

1. `Update static fundamental data`
2. `Update technical data and deploy GitHub Pages`

Open with cache busting after deploy:

```text
https://rasita2644-star.github.io/stockcheck/?v=8-stability
```
