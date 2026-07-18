# PR2A — Free News Foundation

This branch adds a backward-compatible free-news ingestion layer for Today Attention.

- GDELT is discovery-only.
- Company IR/RSS is the primary-source verification layer.
- Similar reports are deduplicated into one event.
- Unverified reports cannot rank above Watch.
- The legacy P0 contract remains intact through an additive adapter.
- The feature flag remains off for the first deploy.

PR2B will isolate the Today UI from the Stock Screener, add optional source-chain rendering, and enable the news flag after this foundation is validated.
