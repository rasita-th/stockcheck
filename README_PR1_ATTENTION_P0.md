# PR1 — Today Attention P0 Foundation

## Scope

- Replace Finnhub-backed Today generation with a free event-first pipeline.
- Use SEC accession cursors so multiple filings on the same day are not skipped.
- Normalize SEC, earnings and technical events before ranking.
- Limit Today Attention to seven decision-relevant items.
- Add source health, verification status and partial-coverage UI states.
- Expand the monitored universe to the current holdings list.
- Add pull-request validation and safer branch-aware workflow commits.

## Deliberately deferred to PR2

- GDELT and public-news discovery
- automated company IR page/feed monitoring
- regulator-specific feeds
- cross-source event verification and news deduplication

These features depend on the normalized event model introduced in this PR.
