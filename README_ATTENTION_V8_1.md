# Stock Timing Radar v8.1 — Today's Attention List

This release adds a quiet daily attention filter. It is not a news feed and not a recommendation engine. It shows only stocks from `data/portfolio.json` that triggered a concrete reason to look today.

## What changed

- New nav item: `📡 Today`
- New static data files:
  - `data/portfolio.json`
  - `data/attention_today.json`
  - `site/data/portfolio.json`
  - `site/data/attention_today.json`
- New generator:
  - `scripts/generate_attention.py`
- New GitHub Actions workflow:
  - `.github/workflows/attention.yml`

## Trigger types

- Price move: absolute daily move >= 5%
- SEC filing: 8-K, 10-Q, 10-K, S-3, 424B, Form 4, DEF 14A
- Earnings soon: within 7 days, if Yahoo calendar data is available
- Buy zone / trim zone: from `portfolio.json`

## Static site behavior

The app reads `site/data/attention_today.json` in the browser. If the JSON is older than 36 hours, the UI shows a stale-data warning.

Empty state is a success state: radar quiet means no stock triggered attention today.

## Manual run

```bash
python scripts/generate_attention.py
```

Then deploy as usual with GitHub Pages workflow.

## GitHub Actions

Run manually:

```text
Actions → Generate Attention List → Run workflow
```

The workflow commits updated attention JSON back to `main`.
