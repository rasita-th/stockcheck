# StockCheck v9.1 Stability Foundation

This patch introduces a canonical generated-data layer at `data/generated/`.

Key changes:
- `quote_latest.json` is refreshed independently from daily technical indicators.
- `health.json` exposes freshness and missing-layer diagnostics.
- generated data is published from one canonical location into `site/data/` and `static/data/`.
- live market refresh remains every 15 minutes during the US market window.
- analyst consensus uses a slower cache-aware queue.
- old workflows are moved to `.github/workflows_disabled/` by the installer to avoid duplicate schedules.

This is a foundation release. It intentionally avoids changing `watchlist.txt`.
