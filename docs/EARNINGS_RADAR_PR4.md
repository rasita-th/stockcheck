# PR4 Earnings Radar rollout

## Goal

Build the Today layout toward the approved visual direction without coupling a
large data-contract migration to the final UI activation.

The existing PR3 renderer and `earnings_calendar.json` remain valid fallbacks.
PR4 is delivered as four independently reviewable pull requests.

## PR sequence

### PR4A — Market-wide earnings data contract

- Read the full Finnhub batch earnings calendar from `data/finnhub/state.json`.
- Keep the legacy coverage-universe `earnings_calendar.json` unchanged.
- Publish `earnings_radar.json` to `data/generated`, `site/data`, and
  `static/data`.
- Overlay Company IR / SEC confirmed rows over Finnhub estimates.
- Mark each event as `portfolio`, `related`, `coverage`, or `market`.
- Keep relevance explicit in `data/earnings_relevance.json`.
- Preserve missing EPS, revenue, event time, name, and source values as null or
  ticker-only; never invent values.

### PR4B — Visual hierarchy foundation

- Add a PR4 renderer and stylesheet while retaining PR3 as runtime fallback.
- Promote the top confirmed portfolio catalyst to a hero treatment.
- Replace repeated badges with functional status text and semantic left rails.
- Render technical watch as compact comparison cards.
- Increase typography contrast for prices and key metrics.
- Use one line-icon vocabulary rather than decorative emoji.

### PR4C — Earnings Radar and calendar interaction

- Add market-wide summary cards from `earnings_radar.json`.
- Add date navigation and filters for time, portfolio, related, and coverage.
- Highlight portfolio rows across the full row rather than with another badge.
- Keep provider confidence and source origin visible in details.
- Add mobile card rows and desktop table rows from the same normalized data.

### PR4D — Activation and production verification

- Activate the PR4 renderer through the existing loader.
- Bump outer and inner asset versions.
- Update UI contract, JavaScript syntax, schema, and Pages smoke tests.
- Refresh earnings data, deploy Pages, and record a production receipt that
  confirms the PR4 asset version and earnings-radar contract.

## Earnings Radar contract

`earnings_radar.json` is additive and uses schema `1.0`.

Key sections:

- `summary`: counts for the selected date.
- `daily_summary`: one summary row per date in the publish window.
- `coverage`: portfolio, coverage-universe, source, estimate, and profile-name
  coverage.
- `items`: normalized market-wide earnings rows.
- `policy`: machine-readable statements about overrides, missing values, and
  relevance.

Each item includes:

- provider and official-source fields;
- EPS and revenue actual/estimate values when present;
- portfolio relationship and explicit related holdings;
- display name and industry only when present in the portfolio or profile cache;
- a deterministic priority score used only for UI ordering.

## Rollback

- PR4A can be reverted without changing Today because no renderer reads the new
  file yet.
- PR4B and PR4C load after PR3; failure leaves PR3 visible.
- PR4D is the only activation PR and can roll back by removing one loader import
  and restoring the prior asset version.
