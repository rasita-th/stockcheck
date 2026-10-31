# Product guide

The `ⓘ วิธีใช้` button opens help for the current Scanner, Today, Memo or Market
Pulse page. First visits show a nonmodal invitation; a tour starts only after the
user chooses it. Inline info buttons explain EMA, Drawdown, alerts and data freshness.
Tours contain 5 / 4 / 4 / 5 steps respectively and labelled, illustrative diagrams.
Examples do not enter the live feed or write portfolios, screener filters or memos.

The guide supports desktop/mobile placement, keyboard focus containment, Escape,
replay, reduced motion and unavailable browser storage. `stockRadar.productGuide.v1`
is its only storage key. Each tour has an independent version and completion status.
Increase only the affected tour's version when a substantial workflow change needs
new instruction. Ordinary wording updates do not require repeating the tutorial.
Add a feature-specific glossary item or short tour rather than extending every
first-use tour. All copy and targets are in `site/product-guide.js`; keep the static
mirror identical. Illustrations are local SVG/CSS and require no external service.

Targets resolve to currently visible elements. Today uses its current P4 anchors,
with fallbacks for earlier renderers. If a target is absent, the step shows an
explicit explanatory fallback instead of highlighting an unrelated control. The
spotlight repositions on viewport resize, scrolling and dynamic content changes.
The guide never clicks app controls, submits forms, switches filters or navigates
between pages on behalf of the user. Page links in the help menu are explicit
navigation choices. Closing restores focus to the launcher or original info control.

The Pages builder includes both assets on index and Market Pulse, uses content
hashes to invalidate their caches and verifies index references during the build.
`Validate Product Guide` runs the actual prepared artifact in Chromium at desktop
and mobile sizes. It checks all steps, visible targets, viewport placement, replay,
completion persistence, keyboard close/focus, reduced motion and application storage
preservation. To run locally after preparing/serving a candidate:

```sh
python tests/product_guide_browser_smoke.py --base-url http://127.0.0.1:8790 --chromium /usr/bin/chromium
```

The optional `--chromium` selects a system browser; omitting it uses Playwright's
installed Chromium. Install Playwright in the development virtual environment.
