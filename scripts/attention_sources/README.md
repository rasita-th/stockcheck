# Attention source modules

- `common.py`: canonical URLs, aliases, entity confidence and headline classification.
- `discovery.py`: company IR/RSS and GDELT discovery adapters.
- `dedupe.py`: cross-source event clustering and verification-chain construction.
- `pipeline.py`: feature-flagged round-robin collection and source health.

The modules use Python's standard library and require no paid API key.
