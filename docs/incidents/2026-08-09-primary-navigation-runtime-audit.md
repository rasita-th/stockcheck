# Primary navigation runtime investigation — 2026-08-09

## Purpose

This PR is investigation-only. It changes no production JavaScript, CSS, data schema, publisher, or deploy behavior.

The goal is to establish a reproducible failure map and an ordered fix plan before touching the runtime again. This follows the repository engineering rule: reproduce first, identify one root cause at a specific layer, then fix it in a focused PR.

## Verified target

- Repository: `rasita-th/stockcheck`
- Default branch: `main`
- Production URL: `https://rasita-th.github.io/stockcheck/`
- Main at investigation start: `bd191d7b8f8c696365404a21742143eb3a7e65d1`
- Latest main observed during investigation: `8ae48bf2c370a0aef70494304f94a62de4449565`
- Affected user flow: Scanner → Today → Memo → Scanner → Market Pulse
- Confirmed root-cause layer: UI runtime / body-class MutationObserver feedback loop
- Data domains intentionally out of scope: technical, fundamental, canonical screener snapshot, market pulse, publisher artifacts
- Automatic main writer remains: `Publish Production Data`

## Reproduction evidence

### Candidate PR #211

PR #211 attempted to make `app-shell-v9-4-6.js` the synchronous navigation owner and to browser-test the exact prepared Pages artifact.

Candidate artifact preparation succeeded and reported:

- prepared Pages runtime `v10.8.7`
- technical index: 408 rows
- representative NVDA technical shard: 251 series rows
- fundamental: 407 rows
- Today P0/P3/P4 assets synchronized

The original browser smoke reached:

```text
[primary-nav] desktop-nav: start
[primary-nav] desktop-nav: runtime ok
```

and then stalled on the first Today click until the workflow timeout.

### Bounded A/B diagnostic

A follow-up diagnostic served the exact candidate Pages artifact and ran the first Today click with individual runtime assets blocked. Every variant had a bounded action timeout and emitted before/after evidence.

| Variant | Result | Observation |
|---|---|---|
| baseline | FAIL | Today `locator.click()` timed out while performing click |
| drawdown blocked | FAIL | same hang |
| `memo-only-fix.js` blocked | FAIL | same hang |
| Attention P0 blocked | FAIL | same hang |
| Attention PR3 blocked | FAIL | same hang |
| Attention PR4 blocked | FAIL | same hang |
| **`final-ui-coordinator.js` blocked** | **PASS** | click returned; `attention-active=true`; `memo-active=false`; visible renderer=`attentionPageP4` |

This isolates `final-ui-coordinator.js` as the causal runtime for the hard navigation hang. The drawdown observer is a separate hardening concern, but it is not the cause of this incident.

## Confirmed root cause

`final-ui-coordinator.js` owns a body-class observer:

```js
const viewObserver = new MutationObserver(() => {
  syncAlertHeight();
  if (!scannerViewIsActive()) closeStockDetail({ restoreFocus: false });
});
viewObserver.observe(document.body, {
  attributes: true,
  attributeFilter: ["class"]
});
```

When Today or Memo becomes active, changing the body class invokes this observer. `closeStockDetail()` then executes an unconditional body-class mutation even when Stock Detail was not open:

```js
const wasOpen = document.body.classList.contains("stock-detail-open");
document.body.classList.remove("stock-detail-open");
```

That redundant mutation is observed again by the same `MutationObserver`, which calls `closeStockDetail()` again. The result is a self-triggering body-class mutation loop that can starve the browser main thread during the navigation click.

The smallest correct repair is to make both sides idempotent:

1. only remove `stock-detail-open` when it is actually present;
2. only call `closeStockDetail()` from the body-class observer when Stock Detail is actually open.

This is one atomic runtime root cause. It does not require a navigation architecture rewrite, data change, Today renderer change, or drawdown change.

## Runtime ownership findings that are not the current root cause

The application still has historical overlap in primary-view handling:

- `app.js` Memo runtime handles `[data-app-view]`;
- legacy Today code in `app.js` handles the same primary controls;
- `memo-only-fix.js` enforces Memo/Today exclusivity;
- PR #211 attempted to add a fourth capture owner in `app-shell-v9-4-6.js`.

This is undesirable architectural debt, but the A/B result shows it is not necessary to refactor these owners to fix the current hang. A primary-view ownership consolidation should be a separate PR only if regression evidence shows remaining behavioral conflicts after the confirmed observer fix.

## Today renderer map

Today currently has four generations of page DOM:

- legacy `#attentionPage` from `app.js`
- `#attentionPageP0`
- `#attentionPageP3`
- `#attentionPageP4`

`today-view-isolation.css` selects the highest ready renderer. The A/B diagnostic proved that P4 renders correctly after the click when `final-ui-coordinator.js` is removed, so the renderer stack is not the blocking root cause for this incident.

## Other findings

### Release-identity coupling in PR #211

PR #211 also changed `release-manifest.assets.app_js` to `10.8.7` without moving all contracts that currently treat that value as a shared UI identity.

This produced three separate gate failures:

1. **Validate Drawer UI** — drawer tests passed, then failed because `final-ui-coordinator.js` was still `10.8.3` while manifest `app_js` was `10.8.7`.
2. **Validate Today Attention PR4** — data/unit/runtime tests passed, then view contract failed on the same coordinator/manifest mismatch.
3. **Validate Single Production Publisher** — release-control compile passed, then failed because `deploy-pages.yml` still declared `TODAY_DEPLOY_VERSION=10.8.3` while manifest release was `10.8.7`.

For the immediate runtime repair, use the repository's current coupled release contract consistently. Decoupling `app_js`, `app_shell_js`, and `final_ui_coordinator_js` is a separate release-control improvement and should not be mixed into the hang fix.

### Drawdown observer

`drawdown-screener-v10-9.js` observes the full body subtree and writes into descendants. That broad pattern deserves a separate hardening PR, but A/B testing showed that disabling drawdown does not unblock the Today click.

### Browser-test watchdog

The diagnostic proved the test infrastructure should retain bounded action timeouts and incremental evidence so a main-thread hang fails quickly instead of consuming the workflow timeout.

### Pages concurrency

`deploy-pages.yml` currently uses `cancel-in-progress: true`. Because generated-data publisher commits can move `main`, deployment concurrency should be reviewed separately to ensure every production identity that matters receives the required verification. This is not part of the current runtime repair.

## Root-cause classification

| ID | Layer | Finding | Evidence status | Current action |
|---|---|---|---|---|
| R1 | UI runtime | `final-ui-coordinator` body-class observer self-triggers through `closeStockDetail()` | **Confirmed by source + A/B** | **Fix first** |
| R2 | Test infrastructure | browser interaction lacked bounded diagnostic isolation | Confirmed | keep bounded regression evidence |
| R3 | Release control | shared `app_js` identity creates unrelated validator coupling | Confirmed by CI | follow current contract now; decouple later |
| R4 | Runtime architecture | multiple historical view owners remain | Confirmed by source, not causal to current hang | follow-up only if regression remains |
| R5 | Runtime hardening | drawdown uses broad subtree observer | Confirmed by source, **A/B non-causal** | separate follow-up |
| R6 | Deployment governance | Pages uses `cancel-in-progress: true` | Confirmed by workflow source | separate follow-up |

## Ordered repair plan

### Fix PR 1 — Final UI observer loop

Scope only the confirmed root cause:

- make `closeStockDetail()` idempotent with respect to `stock-detail-open`;
- guard the body-class observer so it closes detail only when detail is open;
- mirror `site/` and `static/`;
- update the runtime/cache identity according to the current release contract;
- add desktop + iPhone browser regression for Scanner → Today → Memo → Scanner → Market Pulse;
- browser-test the exact prepared Pages artifact.

Acceptance:

- no Today/Memo click hangs;
- Today and Memo remain mutually exclusive;
- Scanner restores correctly;
- Stock Detail still closes if a view switch occurs while it is genuinely open;
- existing drawer contracts remain green;
- no canonical-data, producer, publisher, chart, or notification behavior changes.

### Fix PR 2 — Only if evidence remains after Fix PR 1

If primary navigation still has a reproducible ownership conflict after the observer fix, then consolidate primary-view ownership in a separate PR. Do not do this speculatively.

### Follow-up PRs

Keep these isolated from the incident repair:

- decouple release asset identities;
- harden drawdown observer scope/idempotency;
- review Pages deployment concurrency.

## Production release path

1. Build the exact Pages artifact from the focused fix PR.
2. Run desktop + iPhone primary-navigation regression on that artifact.
3. Run existing bootstrap, drawer, Today, data, and publisher topology gates.
4. Confirm no unresolved review threads and document rollback parent.
5. Merge the expected head SHA.
6. Verify the Pages deployment contains the fix commit (or a later main commit with the fix as an ancestor).
7. Run production browser smoke against Scanner → Today → Memo → Scanner → Market Pulse.
8. Confirm no bootstrap/page errors and no silent data fallback.
9. Close PR #211 as superseded after production acceptance.

## Explicit non-goals

This investigation does not change:

- canonical screener snapshot schema or precedence
- technical/fundamental producer behavior
- publisher single-writer topology
- notification policy
- chart renderer
- Stock Detail design
- Add Watchlist design
- Today visual design

## Stop conditions

Do not merge the runtime repair while any of these remain true:

- the exact candidate artifact fails the primary navigation regression;
- desktop or iPhone flow hangs;
- runtime behavior changed without cache/release identity update;
- site/static mirrors differ;
- drawer/Today/publisher gates fail;
- the production deploy cannot be tied to a main commit containing the fix;
- production browser smoke has not passed.

## Rollback

The behavior fix must remain independently revertible to its immediate parent production SHA. No data-schema rollback is required because the confirmed issue is in UI runtime lifecycle only.
