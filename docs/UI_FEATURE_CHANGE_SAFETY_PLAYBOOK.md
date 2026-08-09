# Stockcheck UI & Feature Change Safety Playbook

> **Purpose:** This document is the required planning and release playbook for any future UI-only change, local interaction fix, or new feature in Stockcheck. Its goal is to prevent a focused change from breaking unrelated views, navigation, runtime state, data identity, cache behavior, or production deployment.
>
> **Operating principle:** A change is not safe because the diff is small. A change is safe only when its ownership, blast radius, test surface, artifact identity, and production behavior are explicitly proven.

---

## 1. When this playbook is mandatory

Use this playbook before writing code for any of the following:

- changing spacing, typography, color, borders, layout, responsive behavior, z-index, drawer/modal geometry, sticky/fixed elements, or visibility rules;
- changing a click, tap, keyboard, drag, close/open, tab, navigation, or view-switch interaction;
- adding a new panel, drawer, modal, tab, route, page, badge, CTA, card, chart, filter, alert, memo action, or floating control;
- adding a new JavaScript runtime, event listener, observer, persistence key, cache identity, script order dependency, or boot-time recovery path;
- adding a feature that consumes canonical market data, detail shards, localStorage, notifications, Today, Memo, Scanner, Market Pulse, or shared shell state;
- changing an existing feature in a way that could alter DOM ownership, pointer reachability, body classes, scroll locking, focus, or responsive layout.

Pure text/copy edits can use the lightweight path in section 15, but they still require target verification and a visual smoke check when the text can alter layout.

---

## 2. Non-negotiable invariants

Every PR must preserve these invariants unless the PR is explicitly scoped to change one of them and has dedicated migration/acceptance coverage.

### 2.1 Production and data ownership

The production architecture remains:

```text
Data Producer
→ Generate
→ Validate
→ Upload immutable artifact
→ Publish Production Data
→ Validate merged tree
→ Commit/push main
→ Deploy GitHub Pages
→ Verify Production Deployment
```

Rules:

- only **Publish Production Data** may automatically write production data to `main`;
- producers remain read-only;
- a UI/feature PR must not modify producer/publisher ownership unless that is the explicit project being reviewed;
- canonical market state remains the source of truth for Scanner, filters, ranking, alerts, notification counts, detail summary, and other price-sensitive consumers;
- detail/history shards may enrich historical series but must not overwrite the canonical live price;
- no silent fallback from canonical data to legacy data.

### 2.2 Runtime ownership

For every shared state, there must be one clear owner.

Examples:

- primary app view selection: one owner;
- Stock Detail open/close state: one owner;
- shared header geometry: one owner;
- notification collection/count: one owner;
- canonical market snapshot: one owner;
- release/cache identity for each runtime asset: one owner.

Do not solve an interaction bug by adding a second capture-phase event owner, a second view-state coordinator, or another global monkey patch unless the ownership migration itself is the scoped change.

### 2.3 Idempotency

Functions called by observers, lifecycle hooks, pageshow/resize handlers, recovery paths, or repeated bootstrap logic must be idempotent.

Example rule:

```js
if (!isOpen()) return;
close();
```

is safer than:

```js
body.classList.remove("open");
```

on every observer callback.

A function that is asked to close an already-closed surface must not create another relevant mutation just because it was called again.

### 2.4 Exact-artifact equivalence

A passing source-tree test is not sufficient.

The browser candidate test must run against the same prepared Pages artifact shape that the deploy workflow will publish, including:

- injected/removed scripts;
- cache-busted asset references;
- generated runtime mirrors;
- production preparation transforms;
- release identity stamping.

### 2.5 Production outcome

A green CI result and a successful Pages deployment do not finish a UI/feature change.

The change is complete only when the intended user flow passes on the production URL after deploy.

---

## 3. Change classification before coding

Every proposed change must be classified before code is written. Use the highest applicable risk class.

| Class | Typical examples | Minimum process |
|---|---|---|
| **A — Visual-local** | color, border opacity, typography, spacing inside one existing component | visual contract + desktop/mobile exact-artifact smoke |
| **B — Layout/geometry** | drawer size, fixed/sticky positioning, z-index, responsive breakpoint, header/footer clearance | A + geometry/pointer tests + overlapping-surface tests |
| **C — Interaction/runtime** | click handler, tab switch, open/close, body class, observer, keyboard, scroll lock | B + failing interaction regression + lifecycle/idempotency review |
| **D — New UI feature** | new panel/tab/modal/page/filter/action using existing data | C + feature contract + integration path + rollback/disable path |
| **E — Data-affecting feature** | new signal, canonical field, new persisted schema, alert derivation | D + data lineage, schema validation, migration/fallback tests, publisher invariants |
| **F — Pipeline/release architecture** | producer/publisher, deploy, artifact preparation, cache/version ownership | separate architecture PR; never bundle with UI redesign |

If a PR starts as Class A and discovers a Class C or F problem, stop and split the work.

---

## 4. The required planning packet

Before implementation, write a short planning packet in the PR description or an investigation note.

### 4.1 Target identity

Record:

```text
Repository:
Base branch:
Base SHA:
Production URL:
Current deployed SHA:
Current relevant asset versions:
Device/viewports affected:
```

Never infer the target from project name alone.

### 4.2 User outcome

Define one sentence:

> After this change, the user can ______ without changing ______.

Example:

> After this change, the user can read Key Technicals with lower divider contrast on mobile without changing data, navigation, detail open/close behavior, or chart rendering.

This sentence is the scope fence.

### 4.3 Explicit non-goals

List what the PR must not change.

For a local Stock Detail visual change, typical non-goals are:

- canonical data schema;
- signal calculation;
- watchlist storage;
- primary navigation ownership;
- chart renderer;
- notification policy;
- production publisher;
- unrelated responsive surfaces.

### 4.4 Ownership map

For each touched behavior, record:

```text
Concern                     Current owner
-------------------------------------------------
DOM markup                   ...
Component visual CSS         ...
Open/close state             ...
View switching               ...
Shared shell geometry        ...
Canonical data               ...
Persistence                  ...
Asset/cache identity         ...
Pages preparation            ...
Production verifier          ...
```

If the owner is unclear, investigate before coding.

### 4.5 Impact map

List all directly and indirectly affected surfaces.

A change to a Stock Detail drawer can indirectly affect:

- shared header;
- Today/Memo/Scanner navigation;
- backdrop click handling;
- scroll locking;
- mobile full-screen behavior;
- fixed alert/FAB controls;
- pointer interception;
- keyboard focus/Escape;
- body classes;
- screenshot/layout tests;
- asset cache identity.

The impact map must include **what shares geometry, state, event propagation, or runtime asset identity**, not just files imported by the component.

---

## 5. Investigate first when behavior is already broken

If the request is a bug fix rather than a new feature, do not patch the symptom first.

Create a reproduction contract:

```text
Device / viewport:
Browser:
Production URL:
Production SHA:
User action sequence:
Expected result:
Actual result:
DOM state:
Body classes:
Overlay geometry:
Pointer target / interception:
Network requests:
Loaded runtime assets + versions:
Console/page errors:
Relevant localStorage state:
```

When multiple runtimes are plausible causes, use bounded A/B isolation rather than speculative rewrites.

Examples:

- disable one runtime at a time;
- block one script at a time;
- compare cold vs warm profile;
- compare detail closed vs detail open;
- compare localStorage enabled vs blocked;
- compare desktop vs mobile breakpoint.

The investigation should identify a causal layer such as:

- visual CSS;
- geometry/stacking;
- pointer/focus interaction;
- runtime event ownership;
- observer/lifecycle loop;
- persistence/bootstrap;
- cache/asset identity;
- canonical data;
- deploy/artifact preparation.

Do not merge an architecture rewrite merely because it could theoretically solve the symptom.

---

## 6. Test-first contract by change type

### 6.1 Visual-local change

Before changing CSS, capture the current contract and intended delta.

Test at minimum:

- target component is present;
- desktop and mobile target selectors remain present;
- no visibility regression to adjacent sections;
- no unexpected overflow;
- no fixed controls cover decision-relevant content;
- key numbers remain readable and labels remain secondary.

Use screenshot evidence when the change is visual hierarchy rather than behavior.

### 6.2 Layout/geometry change

Add measured browser assertions.

Examples:

```text
header.bottom <= drawer.top
header.bottom <= backdrop.top
navControl bounding box is not covered by any active overlay
modal/drawer stays inside viewport
mobile drawer top == 0 when full-screen is intended
```

Never rely only on z-index string assertions.

Geometry is a browser fact; measure it in the browser.

### 6.3 Interaction change

Use real browser interaction, not only synthetic DOM events.

Preferred acceptance:

```text
open surface
→ click/tap real control
→ expected state changes
→ prior surface closes/retains as designed
→ focus/pointer remains reachable
```

Use Playwright locator clicks or equivalent pointer semantics so overlays that intercept clicks cause a failure.

### 6.4 Observer/lifecycle change

Add explicit idempotency coverage.

Verify:

- calling close twice causes no additional meaningful mutation;
- observer callbacks do not mutate their own watched state indefinitely;
- repeated resize/pageshow/bootstrap is bounded;
- no broad body/subtree observer is introduced when a narrower event or ResizeObserver can solve the problem;
- no duplicate listener ownership is installed after warm reload.

### 6.5 New feature

Test the complete feature path plus neighboring existing paths.

For example, a new Detail action should cover:

```text
Scanner → open Detail → new action → expected result
Scanner → open Detail → existing tabs still work
Scanner → Today/Memo still work while Detail open/closed as designed
mobile Detail → new action
reload/persistence behavior
```

A new feature is not accepted merely because its own component works in isolation.

---

## 7. CSS and geometry safety rules

### 7.1 Prefer local selectors

Default to selectors scoped to the target component.

Avoid changing generic rules such as:

```css
.bottom-sheet {}
.card {}
button {}
body.open {}
```

when the requested change concerns one specific surface.

Prefer:

```css
#detailPanel.detail-panel {}
#bulkAddSheet.bottom-sheet {}
```

or a dedicated feature class.

### 7.2 Shared geometry belongs to the shared owner

If a drawer must avoid a shared header, do not hard-code a guessed pixel height inside the drawer.

The shared shell should expose the measured constraint, for example:

```css
--stock-detail-top-offset
```

and the consuming surface should use it.

### 7.3 z-index is not a substitute for interaction design

Before changing stacking values, answer:

- should this overlay physically cover the shared header?
- should the header remain interactive?
- should the backdrop receive clicks in that region?
- what happens to fixed FABs, alerts, tooltips, and other overlays?

If the answer is that two surfaces should coexist, solve the geometry first.

### 7.4 Mobile and desktop are separate acceptance surfaces

Do not assume a desktop fix should apply to mobile.

Explicitly decide:

```text
Desktop/tablet: edge drawer below shared header?
Mobile: full-screen sheet/drawer?
Breakpoint: where does behavior change?
```

Scope CSS accordingly.

---

## 8. JavaScript runtime safety rules

### 8.1 One event owner per behavior

Before adding a click listener, search for existing listeners on:

- the same selector;
- `document` capture/bubble handlers;
- shared shell navigation handlers;
- delegated event handlers;
- legacy compatibility runtimes.

If an owner already exists, extend or migrate that owner. Do not add a parallel global handler as a quick fix.

### 8.2 Script order must be deterministic

If behavior depends on one runtime existing before another, that order is part of the contract and must be validated in the prepared Pages artifact.

Do not rely on a late monkey patch to repair a core behavior without an explicit lifecycle.

### 8.3 Recovery paths must be narrow

A recovery/compatibility script should:

- validate one known bad state;
- modify only that state;
- expose its runtime version;
- be safe when executed repeatedly;
- not rewrite unrelated persistence.

### 8.4 Body classes are shared state

Treat `document.body.classList` as a shared global API.

Before adding/removing a body class, map every runtime that observes or derives behavior from body classes.

Avoid broad class MutationObservers when explicit events can be used.

---

## 9. Persistence and localStorage safety

Any new persisted value requires a persistence contract.

Record:

```text
Key:
Owner:
Schema:
Default:
Read timing:
Write timing:
Malformed-value behavior:
Blocked-storage behavior:
Migration behavior:
Rollback behavior:
```

Required tests when persistence is touched:

- empty profile;
- valid existing value;
- malformed historical value;
- localStorage blocked/throws;
- warm reload;
- downgrade/rollback does not brick bootstrap.

Never make a top-level unguarded `JSON.parse(localStorage...)` capable of aborting application bootstrap.

---

## 10. Data-consumption safety for new features

Before a new UI feature reads market/technical data, document the lineage.

```text
Source
→ canonical generated state
→ published artifact
→ Pages artifact
→ browser bootstrap
→ canonical application state
→ feature consumer
```

For each field used, identify:

- authoritative source;
- timestamp/freshness;
- null/unavailable behavior;
- whether the value is live/canonical or historical/detail-only;
- whether the feature is allowed to operate when stale.

Do not duplicate price, signal, alert, or ranking calculations in the UI when a canonical owner already exists.

---

## 11. Cache and asset identity

Every JavaScript/CSS behavior change must have a deliberate cache plan.

Required sequence:

1. change content/runtime identity;
2. update the release manifest or subsystem asset identity;
3. verify the source/preparation process does not overwrite it;
4. verify prepared Pages HTML references the new identity;
5. verify the Pages artifact contains the matching asset;
6. after deploy, verify production HTML references the new identity;
7. cold-cache browser smoke;
8. warm-cache/reload smoke.

Prefer content-hashed filenames long term. If semantic query-string versions remain in use, each independently deployable runtime should have an independently owned version rather than forcing unrelated assets to share one global bump.

---

## 12. Exact candidate artifact gate

Before opening the PR as ready to merge, build the exact candidate Pages artifact using the same preparation path as production.

The gate must verify:

- source mirrors are synchronized as required;
- prepared runtime order is correct;
- expected assets exist;
- cache identities match manifest ownership;
- no legacy runtime unexpectedly replaces the intended owner;
- canonical data files are present and valid;
- no preparation step silently undoes the local fix.

Then serve that artifact over HTTP and run browser tests against it.

---

## 13. Required browser matrix

Choose all rows relevant to the change; interaction/runtime changes should normally run the full core matrix.

### Core matrix

- desktop cold profile;
- iPhone/mobile profile;
- desktop with localStorage blocked;
- warm reload when runtime/cache/persistence is touched.

### State matrix

When relevant:

- Stock Detail closed;
- Stock Detail open;
- another drawer/modal closed;
- another drawer/modal open;
- Today active;
- Memo active;
- Scanner active;
- empty/new profile;
- existing persisted profile;
- malformed recoverable persisted state.

### Navigation invariant

At minimum for shared-shell changes:

```text
Scanner → Today → Memo → Scanner → Market Pulse
```

If Stock Detail is involved, also test:

```text
Scanner → open Stock Detail → real pointer click Today
```

and verify the intended Detail close/retain behavior.

### Error invariant

The browser test fails on:

- page errors;
- critical first-party script/stylesheet/document/fetch failures;
- unexpected visible closed sheets;
- failed required interactions;
- wrong runtime/cache identity;
- missing canonical rows when expected.

Console errors should be collected and reviewed even when not all third-party console noise is fatal.

---

## 14. PR structure and change isolation

One PR should answer one engineering question.

Good examples:

- “Reduce Stock Detail secondary divider contrast”
- “Keep Stock Detail below desktop header”
- “Make detail close observer idempotent”
- “Add earnings filter using existing canonical field”

Bad example:

> Redesign Detail + refactor navigation + migrate storage + change data schema + rewrite deploy versions.

If implementation discovers an independent root cause, open a second PR.

### Required PR sections

Every non-trivial UI/feature PR should contain:

```text
Problem / Goal
User outcome
Base production identity
Reproduction or before-state
Root cause / design rationale
Ownership map
Impact map
Test-first evidence
Fix / implementation
Exact-artifact browser acceptance
Explicit non-goals
Data ownership impact
Cache/persistence impact
Production acceptance
Rollback
```

---

## 15. Lightweight path for truly local visual edits

A visual-only edit may use the lightweight path only when all are true:

- no DOM structure change;
- no positioning mode change (`static/relative/absolute/fixed/sticky`);
- no z-index change;
- no pointer-events/visibility/display change;
- no breakpoint behavior change;
- no JavaScript change;
- no shared/global selector change;
- no data/persistence/cache behavior change beyond the CSS asset identity required to deliver it.

Process:

```text
1. Verify target/base SHA.
2. Define intended visual delta and non-goals.
3. Use component-scoped CSS.
4. Update CSS asset identity.
5. Build exact Pages artifact.
6. Screenshot/visual check desktop + mobile.
7. Run core bootstrap/navigation smoke to prove no shared regression.
8. Focused PR.
9. Deploy.
10. Production visual + browser smoke.
```

If any condition above becomes false, upgrade to the normal process.

---

## 16. New feature planning template

Before implementing a new feature, complete this template.

```markdown
## Feature
Name:
User problem:
Decision/use case:

## User flow
Entry point:
Primary action:
Success state:
Empty state:
Error/degraded state:
Mobile behavior:
Desktop behavior:

## Ownership
UI owner:
Interaction owner:
Data owner:
Persistence owner:
Navigation owner:
Cache/runtime owner:

## Data contract
Fields consumed:
Authoritative source:
Freshness policy:
Fallback policy:
No-data behavior:

## Shared surfaces affected
[ ] Header/navigation
[ ] Scanner
[ ] Stock Detail
[ ] Today
[ ] Memo
[ ] Market Pulse
[ ] Alerts/notifications
[ ] Watchlist/portfolio
[ ] Shared drawers/modals
[ ] localStorage
[ ] Pages preparation
[ ] Release manifest

## Risk classification
Class:
Why:

## Test plan
Failing/new contract test:
Integration flow:
Desktop browser flow:
Mobile browser flow:
Persistence/cache cases:
Neighboring regression flows:

## Release
Asset identity change:
Exact artifact preparation:
Production acceptance:
Rollback/disable path:
```

A feature should not enter implementation until every applicable field has an answer.

---

## 17. Stop conditions — do not merge

Stop and do not merge when any of the following is true:

- target repository/base/deployed identity is uncertain;
- a reported bug has not been reproducibly demonstrated;
- root cause remains a hypothesis while the PR rewrites architecture;
- an interaction fix has no failing browser regression before the fix;
- a visual geometry change has no measured geometry/pointer acceptance;
- the PR modifies multiple independent ownership layers;
- a shared/global selector is changed without an impact map;
- a second global event/navigation owner is introduced without an explicit ownership migration;
- an observer mutates the state it observes without a bounded/idempotent contract;
- a runtime behavior changes but cache/content identity does not;
- candidate browser tests use source tree rather than the exact prepared artifact;
- CI validates strings/files but not the user interaction that matters;
- desktop passes but mobile is untested for a shared UI change;
- Pages deploy succeeds but post-deploy production browser flow has not passed;
- an unresolved P1/P0 review thread remains;
- rollback is unclear.

---

## 18. Merge and production release sequence

Use this sequence for Class B–F changes and any bug involving runtime behavior:

```text
1. Verify repo/base/production SHA.
2. Record user outcome and non-goals.
3. Build ownership + impact maps.
4. Reproduce current behavior if fixing a bug.
5. Classify root-cause/risk layer.
6. Write failing regression or new-feature contract.
7. Implement the smallest scoped change.
8. Run unit/contract tests.
9. Synchronize required site/static mirrors.
10. Update cache/runtime identity.
11. Build exact Pages candidate artifact.
12. Run desktop/mobile browser matrix.
13. Run neighboring regression flows.
14. Open/update focused PR with evidence.
15. Resolve CI and review findings; split unrelated findings.
16. Re-run all relevant gates on final head SHA.
17. Merge using expected head SHA.
18. Deploy that exact production commit once.
19. Verify production build/runtime/asset identity.
20. Run post-deploy browser interaction smoke on production URL.
21. Verify canonical/data invariants when feature consumes market data.
22. Close only when the production user outcome is proven.
```

---

## 19. Production acceptance examples

### Example A — local Stock Detail visual refinement

Acceptance:

- new typography/divider hierarchy visible on production mobile and desktop;
- price, score, key technical values remain readable;
- no overflow;
- Detail tabs work;
- Today/Memo/Scanner/Market Pulse still work;
- Detail open/close works;
- no new page/bootstrap errors;
- correct CSS identity is loaded in production.

### Example B — change desktop drawer geometry

Acceptance:

- measure shared header bottom;
- active drawer/backdrop begins at or below required header boundary;
- real pointer click on Today remains reachable while Detail is open if that is the intended product behavior;
- mobile full-screen behavior remains unchanged;
- no other bottom sheet inherits the new geometry unintentionally.

### Example C — add a new Detail feature using market data

Acceptance:

- feature reads canonical market state rather than recalculating live price independently;
- stale/unavailable state is explicit;
- Detail price still equals Scanner price identity;
- new action works desktop/mobile;
- navigation and existing tabs remain usable;
- persistence is safe when blocked/malformed if used;
- exact candidate and production browser flows pass.

---

## 20. Lessons encoded from the navigation incident

The following are now permanent engineering lessons:

1. **A symptom can have multiple independent root causes.** First-click navigation hang and pointer interception looked similar but came from different layers.
2. **Do not redesign ownership before causal isolation.** A/B runtime isolation can disprove plausible architectural theories quickly.
3. **Observers must be idempotent.** A cleanup function can become a main-thread failure when invoked from a self-triggering observer path.
4. **Visible does not mean clickable.** Browser geometry and pointer reachability must be tested for overlays.
5. **z-index alone is not an interaction model.** If the header must remain usable, design the overlay geometry so it does not cover the header.
6. **Test the deploy artifact, not an approximation.** Preparation scripts can remove, inject, reorder, or re-version runtimes.
7. **Cache identity is part of correctness.** Correct source code is irrelevant if production clients can retain the old runtime.
8. **Unrelated CI failures can expose invalid build-stage assumptions.** Distinguish source-tree invariants from prepared-artifact invariants.
9. **Split independent causes into independent PRs.** It improves proof, rollback, review, and future debugging.
10. **The user must not be final QA.** Post-deploy browser verification is required.

---

## 21. Future coding-agent instruction

Use this block as a project instruction for future implementation agents:

```text
Before changing Stockcheck UI or adding a feature, classify the change by risk and write a target/ownership/impact plan. Do not patch symptoms or add parallel global runtime owners. Preserve canonical data ownership and the single-writer production architecture.

For bugs, reproduce the exact user flow and isolate one causal layer before writing the fix. Write a regression that fails first. For overlays and navigation, use real pointer interactions and measured browser geometry. Observer/recovery code must be idempotent and bounded.

Keep each PR focused on one root cause or one atomic feature. Do not combine UI redesign, navigation refactor, storage migration, schema change, release-pipeline change, or unrelated cleanup unless they are inseparable dependencies.

Every JS/CSS behavior change must have an explicit cache/content identity. Build the exact Pages artifact through the production preparation path and browser-test that artifact on desktop and mobile, plus localStorage blocked/warm-cache cases when relevant.

After merge, deploy the exact commit and run production browser acceptance for the user flow and neighboring critical flows. A green CI or successful Pages deploy is not completion. Completion means the intended production user outcome is proven with no regression to shared navigation, canonical data identity, persistence, or runtime bootstrap.
```

---

## 22. Final decision rule

Before merging, ask two questions:

> **What exactly is allowed to change?**

and

> **What evidence proves everything else that shares this component's state, geometry, events, data, or runtime identity did not change?**

If the second question cannot be answered with a test or production-verifiable invariant, the PR is not ready to merge.
