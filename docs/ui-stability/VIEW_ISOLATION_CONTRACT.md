# View Isolation Contract

This document defines the runtime ownership rules for the primary Stock Timing Radar views.

## Canonical views

- **Scanner** shows the watchlist/filter workspace, Alert Center, stock detail rail, Stock Screener, and lower dashboard cards.
- **Today** shows only `#attentionPage` beneath the shared application header and primary navigation.
- **Memo** shows only `#memoPage` beneath the shared application header and primary navigation.
- **Market Pulse** remains its own page and runtime.

## State ownership

- `body.memo-active` is the only body class that activates Memo.
- `body.attention-active` is the only body class that activates Today.
- Memo and Today must never be active simultaneously.
- `app.js` owns page creation and primary view switching.
- `memo-only-fix.js` is a narrow exclusivity guard. It must not hide or move page DOM nodes.
- `final-ui-coordinator.js` owns only the measured desktop Alert Center height. It must not move Memo or Scanner DOM nodes.

## Prohibited patterns

- Treating `attention-active` as Memo state.
- Showing `.attention-page` from Memo-specific CSS.
- Moving Memo or Scanner with `insertBefore`, `appendChild`, or similar runtime DOM relocation.
- Broad subtree MutationObservers for page layout.
- Workflows that rewrite production CSS and push directly to `main`.

## Required validation

`scripts/check_ui_view_contract.py` verifies source/static parity, asset references, view isolation, the absence of DOM relocation, and removal of the legacy self-mutating CSS workflow.
