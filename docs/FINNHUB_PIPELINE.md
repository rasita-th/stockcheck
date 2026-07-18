# Unified Finnhub pipeline

## Purpose

All Finnhub calls are coordinated by `scripts/finnhub_pipeline.py`. The pipeline keeps a single authoritative state in `data/finnhub/` and dual-writes the existing public contracts so the current UI and downstream scripts continue to work.

## Keys and schedules

| Role | Secret preference | Features | Schedule |
|---|---|---|---|
| Events (Key A) | `FINNHUB_API_KEY_EVENTS`, fallback `FINNHUB_API_KEY` | Market-wide earnings calendar, company earnings, EPS estimates, revenue estimates | Every 3 hours |
| Analyst (Key B) | `FINNHUB_API_KEY_ANALYST`, fallback `FINNHUB_API_KEY_2`, then `FINNHUB_API_KEY` | Recommendation trends, price target, company profile, basic financials | Every 6 hours |
| Full backfill | Both roles | All endpoints | Manual only |

Each key is capped at 48 calls per run, below the 60 calls/minute account limit. The pipeline applies endpoint TTLs and never calls a fresh ticker. Provider errors preserve last-known-good data.

## Contracts

Existing files remain backward-compatible:

- `recommendation_trends.json`
- `eps_surprises.json`
- `earnings_calendar.json`

New optional data is published in `finnhub_features.json`. Official company IR or SEC-confirmed earnings dates always override Finnhub estimates.

## Deployment

Scheduled workflows share the `stockcheck-data-publisher` concurrency group, commit only their owned data files, rebase before push, and let the existing `Deploy GitHub Pages` workflow deploy on the resulting `main` push.

The former 15-minute consensus queue is removed to prevent duplicate calls and competing commits.
