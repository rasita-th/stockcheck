# Today Attention P0

This release changes Today Attention from a price-plan trigger list into an event-first morning risk desk.

## P0 sources

- SEC EDGAR submissions and company ticker mapping
- Company-IR or SEC-confirmed earnings entries in `data/earnings_calendar.json`
- The scanner's canonical `technical.json` for price and volume context

No Finnhub data is used by the Today Attention production workflow.

## Event model

Raw events are normalized into `events.json`. Each event includes an event ID, ticker, event type/subtype, source quality, verification status, timestamps, materiality and urgency.

`attention_today.json` groups events by ticker and publishes at most seven items using the following display priority:

1. Critical
2. Risk
3. Action
4. Watch
5. Developing

## Coverage states

The UI must not report an all-clear when a required source is unavailable. `coverage_status=partial` is displayed whenever source health is incomplete.

## Earnings policy

- `confirmed`: company IR or SEC primary source required
- `estimated`: must remain visibly estimated
- stale manual dates are not accepted as confirmed events

## SEC cursor

SEC state is stored in `data/source_state/sec.json` using accession numbers. This prevents multiple filings on the same calendar day from being skipped.

## Validation

Run:

```bash
python -m unittest discover -s tests -p "test_attention_p0.py" -v
STOCKCHECK_ATTENTION_OFFLINE=1 python scripts/generate_attention_p0.py
python scripts/generate_health.py
python scripts/publish_generated_data.py
python scripts/validate_generated_data_v9_1.py
python scripts/check_ui_view_contract.py
```

PR2 will add free news discovery, company IR monitoring and source verification on top of this normalized event foundation.
