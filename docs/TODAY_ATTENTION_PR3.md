# Today Attention PR3 — Personal Risk Desk

PR3 extends the catalyst-first PR2 contract without removing legacy fields.

## Features

- `change`: status versus the previous successful run (`new`, `escalated`, `updated`, `ongoing`, `eased`)
- `impact`: price change from the first observed price while the event remains active
- `personal_priority_score`: configurable ranking boost for holdings and event types
- `recently_resolved`: recently removed attention events
- official regulator discovery from configured FDA, FAA, NRC and DOE public pages
- local browser workflow actions: reviewed, snooze 24 hours and hide today

## Data contract

The deployed payload uses `contract_version: 3.0-attention-workflow`. PR2 fields remain available, including `items`, `technical_watch`, `source_health`, `events`, `priority` and source metadata.

PR3 adds:

```json
{
  "changes_summary": {
    "new": 0,
    "escalated": 0,
    "updated": 0,
    "ongoing": 0,
    "eased": 0,
    "resolved": 0
  },
  "recently_resolved": [],
  "preferences_applied": {},
  "items": [
    {
      "change": {
        "status": "new",
        "label_th": "เพิ่มเข้ามาวันนี้",
        "first_seen_at": "...",
        "active_days": 0
      },
      "impact": {
        "baseline_price": 100,
        "current_price": 103,
        "change_pct": 3,
        "label_th": "ราคาหลังเริ่มติดตามปรับขึ้น 3.0%"
      },
      "personal_priority_score": 80,
      "personalization_reasons": ["หุ้นในพอร์ต +8"]
    }
  ]
}
```

## Source policy

Regulator events are emitted only when:

1. the source is an official configured page,
2. the company identity match is medium or high confidence,
3. the headline maps to a material event category,
4. the link was not present during the initial source bootstrap.

A regulator source failure produces partial coverage and never a false all-clear.

## User workflow state

Reviewed, snoozed and hidden status is stored in browser `localStorage`. It does not modify shared repository data. Clearing browser storage resets those actions.

## Rollback

`attention-p0.js` remains loaded before `attention-pr3.js`. PR3 only hides the PR2 page after PR3 loads data successfully and adds `attention-p3-ready` to the body. If PR3 fails, the PR2 catalyst-first page remains available.

## Validation

- `tests/test_attention_pr3.py`
- `scripts/validate_attention_pr3.py`
- `scripts/smoke_test_site_v9_4_6.py`
- production Pages smoke test in `.github/workflows/deploy-pages.yml`
