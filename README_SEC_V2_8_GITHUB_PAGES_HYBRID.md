# SEC V2.8 — GitHub Pages Hybrid Static Mode

V2.8 converts the app into a GitHub-only deployment model.

## Architecture

```text
GitHub Actions daily/manual
  -> SEC fundamentals + company guidance
  -> site/data/fundamental.json

GitHub Actions every ~15 minutes
  -> Yahoo/Stooq technical data
  -> site/data/technical.json

GitHub Pages frontend
  -> loads both JSON files
  -> merges by ticker
  -> displays Technical and Fundamental tabs

Alpha Vantage
  -> BYOK in browser
  -> on-demand only
```

## Workflows

### 1. Update technical data and deploy GitHub Pages

File:

```text
.github/workflows/deploy-pages.yml
```

Runs:

- on push to `main`
- manually via `workflow_dispatch`
- on schedule every ~15 minutes

It runs:

```bash
python scripts/update_technical_data.py
```

### 2. Update static fundamental data

File:

```text
.github/workflows/update-fundamental.yml
```

Runs:

- manually
- daily by schedule

It runs:

```bash
python scripts/update_fundamental_data.py
```

Then commits `site/data/fundamental.json` back to the repo and deploys the updated site.

## Why split data?

Fundamental/SEC/guidance parsing is much heavier than technical price data. Running it every 15 minutes is wasteful and fragile. Technical can update frequently, while fundamentals can remain static until the next daily/manual refresh.

## Expected behavior

- Technical tab updates whenever `technical.json` is refreshed.
- Fundamental tab uses the latest generated `fundamental.json`.
- Analyst Consensus does not run during scan and does not use GitHub secrets.

