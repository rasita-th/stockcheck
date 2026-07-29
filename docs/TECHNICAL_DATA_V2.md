# Technical data v2

The Scanner loads `site/data/technical/index.json` first. The index contains summary rows only and excludes full ticker histories.

When a ticker detail view requests quote history, `technical-shards-v2.js` loads `site/data/technical/symbols/<ticker>.json` on demand and caches the result for the current page session.

During the migration window, a missing or invalid v2 index falls back to `site/data/technical.json`. A missing ticker shard leaves that ticker in summary-only mode without failing the entire Scanner.

The producer remains read-only. Generated data is transported through the immutable production artifact and published by the central publisher.
