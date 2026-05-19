# Stock Timing Radar v8.2.13 — Safe Refresh Reupload

This patch is meant to cleanly reapply the v8.2 data-refresh architecture from a ZIP on a fresh branch.

## Goals

- Fast price/technical refresh is separated from slow Finnhub data.
- Slow Finnhub endpoints share one budget manager.
- Fundamental data refreshes slowly by default: monthly/manual, not every 10 minutes.
- Analyst consensus/ticker parser uses one runtime loader only.
- Old overlapping runtime loaders are removed from `index.html`.
- The old overlapping `fundamental_resolver.yml` workflow is disabled.
- `watchlist.txt` is not touched.

## Workflows

### Fast data

- `.github/workflows/refresh_technical.yml`
- Runs every 15 minutes during broad US market window.
- Updates only:
  - `technical.json`
  - `scanner.json`
  - `attention_today.json`

### Daily attention

- `.github/workflows/attention.yml`
- Daily after US close.
- Updates only fast/attention data.

### Slow Finnhub data

- `.github/workflows/refresh_finnhub_bundle.yml`
- Manual + monthly schedule.
- Uses `scripts/generate_finnhub_bundle_cached.py` with one shared budget.
- Updates only:
  - `fundamental.json`
  - `fundamental_resolver_report.json`
  - `finnhub_bundle_cache.json`
  - `recommendation_trends.json`
  - `eps_surprises.json`

## Apply

From a fresh cloned repo:

```bash
python3 /path/to/apply_v8_2_13.py .
python3 -m py_compile scripts/generate_finnhub_bundle_cached.py
git status
git add -A
git commit -m "Redeploy safe data refresh architecture v8.2.13"
git push -u origin redeploy-v8-2-13-safe-refresh --force-with-lease
```

Then open a PR into `main`.
