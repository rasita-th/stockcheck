# Primary navigation runtime investigation — 2026-08-09

## Purpose

This PR is investigation-only. It changes no production JavaScript, CSS, data schema, publisher, or deploy behavior.

The goal is to establish a reproducible failure map and an ordered fix plan before touching the runtime again. This follows the repository engineering rule: reproduce first, identify one root cause at a specific layer, then fix it in a focused PR.

## Verified target

- Repository: `rasita-th/stockcheck`
- Default branch: `main`
- Production URL: `https://rasita-th.github.io/stockcheck/`
- Main at investigation start: `bd191d7b8f8c696365404a21742143eb3a7e65d1`
- Main commit source: `Publish production data from Update static fundamental data`
- Affected user flow: Scanner → Today → Memo → Scanner → Market Pulse
- Affected layer: browser bootstrap / runtime view ownership / release identity gates
- Data domains intentionally out of scope: technical, fundamental, canonical screener snapshot, market pulse, publisher artifacts
- Automatic main writer remains: `Publish Production Data`

## Reproduction evidence

### Candidate PR #211

PR #211 attempted to make `app-shell-v9-4-6.js` the synchronous navigation owner and to browser-test the exact prepared Pages artifact.

Candidate head: `ba8ea81ff17c4dac2062cb93d976b58fb6896d85`.

The candidate artifact preparation succeeded and reported:

- prepared Pages runtime `v10.8.7`
- technical index: 408 rows
- representative NVDA technical shard: 251 series rows
- fundamental: 407 rows
- Today P0/P3/P4 assets synchronized

The browser smoke then reached:

```text
[primary-nav] desktop-nav: start
[primary-nav] desktop-nav: runtime ok
```

and made no further progress until the workflow-level timeout cancelled the job about 14 minutes later. The first action after `runtime ok` is the Today navigation click. Therefore the failure is not merely a slow data assertion: the candidate can enter a browser-main-thread/action hang at the first primary navigation interaction.

### PR #211 CI failures unrelated to the browser hang

Three additional gates failed:

1. **Validate Drawer UI**
   - stock detail drawer contract: passed
   - watchlist add drawer contract: passed
   - failure: `final-ui-coordinator.js` remained `10.8.3` while `release-manifest.assets.app_js` was changed to `10.8.7`

2. **Validate Today Attention PR4**
   - Today/data/unit/runtime tests passed up to view contract validation
   - failure: `Desktop stock detail VERSION 10.8.3 must match release-manifest app_js 10.8.7`

3. **Validate Single Production Publisher**
   - publisher/release-control compile passed
   - failure: `deploy-pages.yml` `TODAY_DEPLOY_VERSION` remained `10.8.3` while the release manifest was changed to `10.8.7`

These are release-identity consistency failures. They do not explain the browser hang, but they prove PR #211 bundled a navigation fix with a global release identity change that touched unrelated UI contracts.

## Runtime ownership map

### Owner 1 — `app.js` Memo runtime

`app.js` creates the Memo page and owns a `setAppView(view)` path. Its capture-phase click handler consumes `[data-app-view]` and calls that function.

### Owner 2 — `app.js` legacy Today runtime

The same `app.js` also creates the legacy Today page and owns `setAttentionActive(active)`. A second capture-phase click handler responds to the same `[data-app-view]` controls.

### Owner 3 — `memo-only-fix.js`

Despite its narrow name, `memo-only-fix.js` currently:

- enforces Memo/Today exclusivity with another capture click handler
- observes `document.body` class changes
- installs an Attention data store
- loads scanner-loading guard
- loads drawdown screener JS/CSS
- dynamically chains Attention P0 → P3 → P4 → Earnings Radar

This is broader than the documented view-isolation ownership model.

### Owner 4 — `app-shell-v9-4-6.js`

PR #211 adds a fourth capture-phase navigation owner and calls `stopImmediatePropagation()` so it can pre-empt the three older owners.

This is symptom containment rather than ownership consolidation. It leaves the old owners alive and makes correct behavior depend on script registration order.

## Today renderer map

Today currently has four generations of page DOM:

- legacy `#attentionPage` from `app.js`
- `#attentionPageP0`
- `#attentionPageP3`
- `#attentionPageP4`

`today-view-isolation.css` hides all `.attention-page` nodes and selects the highest renderer whose readiness class is present.

This fallback design can work, but it means page creation, data loading, readiness, and visible-renderer ownership are distributed across multiple scripts. The navigation owner should not also attempt to infer or own those renderer generations.

## Observer / feedback-loop risk

### Confirmed unsafe pattern in `drawdown-screener-v10-9.js`

The drawdown runtime installs:

```js
new MutationObserver(scheduleRender)
  .observe(document.body, { childList: true, subtree: true });
```

Its scheduled render then writes back into descendants of `document.body`, including repeated `textContent`, `innerHTML`, appended table cells, and card decorations.

That is an observer feedback-loop pattern: mutations can schedule another render which creates more mutations. This violates the repository preference against broad subtree observers and is a credible source of browser-main-thread starvation. It must be isolated with a diagnostic browser test before claiming it is the exact cause of the Today-click hang.

### Other observers

- `scanner-loading-guard.js`: scoped to scanner buttons; low risk for this incident.
- `notification-phase2.js`: scoped to Alert list child changes; low risk for this incident.
- `final-ui-coordinator.js`: body-class observer plus broad page-guide subtree observer. It should be measured during the diagnostic, but its writes are guarded more carefully than the drawdown renderer.

## Root-cause classification

| ID | Layer | Finding | Evidence status | Merge blocker |
|---|---|---|---|---|
| R1 | Browser bootstrap / runtime state | Multiple primary-view owners compete for the same nav controls | Confirmed by source | Yes |
| R2 | Runtime lifecycle | PR #211 adds a fourth capture owner rather than removing duplicate ownership | Confirmed by diff/source | Yes |
| R3 | Runtime performance | Drawdown broad MutationObserver writes into its own observed subtree | Confirmed by source; causal link to nav hang still needs A/B proof | Yes until diagnostic |
| R4 | UI runtime architecture | Four Today renderer generations coexist and readiness CSS chooses one | Confirmed by source | No by itself; must remain deterministic |
| R5 | Release identity | `assets.app_js` is treated as a global UI version by drawer and Today validators | Confirmed by CI failures | Yes for #211 |
| R6 | Release identity | Deploy workflow version must match release manifest, but #211 did not update it | Confirmed by CI failure | Yes for #211 |
| R7 | Test infrastructure | Browser test can hang until workflow timeout; no per-action watchdog/evidence flush | Confirmed by run behavior | Yes for reliable diagnosis |
| R8 | Deployment governance | Pages workflow uses `cancel-in-progress: true`, which can cancel a deploy when a newer production commit arrives | Confirmed by workflow source; separate from nav failure | Follow-up hardening |

## What should be fixed first

### PR 1 — Diagnostic watchdog and A/B isolation

Goal: prove which runtime causes the hard hang without changing production behavior.

Add a diagnostic browser test with a Node-side watchdog and explicit before/after action logging. Run the exact prepared Pages artifact in isolated contexts with request/runtime variants:

1. baseline
2. drawdown runtime disabled
3. `memo-only-fix.js` disabled
4. final coordinator disabled only if needed

Acceptance: every variant terminates within a bounded time and the first failing/hanging component is identified reproducibly.

### PR 2 — Remove the proven observer feedback loop if R3 is causal

If A/B shows drawdown is causal, replace the body-wide self-observing render with narrowly scoped observation or explicit application render hooks. The render must be idempotent and must not mutate when the rendered value is already correct.

Scope: drawdown runtime only; no navigation redesign, no data changes.

### PR 3 — Consolidate primary-view ownership

After the browser is stable, make exactly one runtime own Scanner/Today/Memo switching.

Preferred direction:

- one `setPrimaryView(view)` contract
- Memo/Today modules expose render/refresh hooks only
- remove their independent `[data-app-view]` capture handlers
- `memo-only-fix.js` returns to a narrow compatibility/exclusivity role or loses nav ownership entirely
- `app-shell` may normalize nav markup but should not depend on registration-order pre-emption

Acceptance:

- Scanner → Today → Memo → Scanner passes desktop and iPhone
- body classes are mutually exclusive
- persisted view reload works
- cold/warm cache pass
- localStorage enabled/blocked pass
- visible Today renderer is the highest ready renderer without changing primary-view ownership

### PR 4 — Decouple release identities

Do not bump unrelated drawer/coordinator assets for a navigation-only change merely to satisfy a shared `app_js` number.

Introduce explicit asset identities (for example `app_js`, `app_shell_js`, `final_ui_coordinator_js`) and make validators compare the asset they actually validate. Deployment release/build identity remains a separate release-level field.

This is a validator/manifest PR and must not be mixed with the runtime behavior fix.

### PR 5 — Production release

Once the focused runtime PR(s) and identity contract are green:

1. build the exact Pages artifact
2. run desktop + iPhone candidate browser flow
3. merge with expected head SHA
4. allow one Pages deploy for the production commit
5. verify build identity and asset identities
6. run production browser smoke against Scanner → Today → Memo → Scanner → Market Pulse
7. confirm no console/bootstrap errors and no silent fallback

### Follow-up — deployment concurrency hardening

Evaluate changing Pages deployment concurrency so a production commit cannot lose its required deployment verification merely because a newer data commit arrives. This is a deployment-governance PR, not part of the primary-navigation runtime repair.

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

Do not merge a navigation runtime fix while any of these remain true:

- the hard hang has no isolated A/B reproduction
- the browser test can itself wait until workflow timeout
- multiple primary-view owners remain active
- runtime behavior changes without a distinct cache/asset identity
- the exact deploy artifact has not passed desktop and mobile browser flow
- unrelated validator failures are hidden by bumping every UI asset to the same version
- production browser smoke has not passed on the merged production identity

## Rollback

Each behavior PR must document its immediate parent production SHA and remain independently revertible. No data-schema rollback should be required for this incident because the planned fixes are browser runtime / release-control only.
