# Stock Timing Radar v8.3.0 — Price + Analyst Consensus Pipeline

## Price refresh
- Workflow: `Refresh Prices 20:30 Thailand`
- Daily at 20:30 Thailand / 13:30 UTC
- Refreshes technical/scanner JSON and Today Attention JSON.

## Analyst consensus
- Workflow: `Refresh Analyst Consensus Queue`
- Runs every 15 minutes but is cache-aware and capped.
- Default max calls: 3 tickers per run.
- TTL: 168 hours.
- Non-US tickers such as `.BK` are skipped.

## UI
- Mobile Card View shows day % beside current price.
- EMA bars scale within each stock card:
  `maxAbs = max(5, abs(EMA5), abs(EMA20), abs(EMA89), abs(EMA200))`
- Analyst Consensus table reads `site/data/recommendation_trends.json`.

## Deploy
- GitHub Pages deploys on push to main or manual dispatch.
- Data generation is no longer duplicated inside the deploy job.

After merge:
1. Run `Refresh Prices 20:30 Thailand`
2. Run `Refresh Analyst Consensus Queue`
3. Run `Deploy GitHub Pages`
4. Open `https://rasita2644-star.github.io/stockcheck/?v=8-3-0`
