# v8.1.2 — Attention Data Integrity + Mobile UI Polish

This release fixes the Today attention list so it no longer ships misleading sample price/change data.

## Fixes

- `scripts/generate_attention.py` now reads `site/data/technical.json` first and uses the same `price` / `dayPct` source as the scanner.
- Yahoo Finance price is now only a fallback when a ticker is missing from the scanner static data.
- Negative daily moves are preserved as negative signals, for example `Price -5.7%`.
- Price-move trigger labels display as `Price Drop` with a down icon when day change is negative.
- `scripts/validate_static_data.py` now fails deploy if `attention_today.json` contradicts `technical.json` by more than tolerance.
- The attention GitHub Action refreshes the technical layer before generating attention data.
- Mobile Memo header spacing is tightened so `Stock Memo` is not clipped/too far left.
- Yahoo Finance Analysis buttons get extra bottom spacing on mobile so they are not hidden behind the sticky `Scan Now` button.

## Principle

If attention data cannot be synced with scanner data, radar should be quiet or warn — not show stale/sample triggers.
