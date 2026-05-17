# Stock Timing Radar v8.1.4 — Attention Logic Quality

This release fixes the Attention List logic so the radar prioritizes company events and avoids stale buy/trim zone alerts.

## What changed

- Earnings/SEC events are now top-tier attention triggers.
- Added `data/earnings_calendar.json` and static copies for manual earnings overrides.
- Earnings calendar priority: manual `earnings_calendar.json` first, Yahoo fallback second.
- Attention price/change uses scanner-synced `technical.json` first.
- Buy/trim zone alerts now trigger only when price is near the zone:
  - Buy zone: -10% to +5% from configured buy zone.
  - Trim zone: -3% to +10% from configured trim zone.
- Stale zones such as current price far above an old trim target are suppressed from Today’s Attention.
- Desktop Attention table now includes `Price / Change` so technical triggers have context.
- Validation fails if technical Attention rows lack price/change or zone distances are outside allowed ranges.

## Manual earnings calendar

Update these files when needed:

- `data/earnings_calendar.json`
- `site/data/earnings_calendar.json`
- `static/data/earnings_calendar.json`

Schema:

```json
[
  {
    "ticker": "NVDA",
    "earnings_date": "2026-05-20",
    "time": "after_close",
    "source": "manual"
  }
]
```

## Test locally

```bash
STOCKCHECK_ATTENTION_OFFLINE=1 python scripts/generate_attention.py
python scripts/validate_static_data.py
```

## Deploy

After merging, run GitHub Actions:

1. Generate Attention List
2. Update technical data and deploy GitHub Pages
