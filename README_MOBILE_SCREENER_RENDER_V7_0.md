# v7.0 Mobile Screener Render Fix

This patch fixes the mobile screener creation flow where a newly-created screener could be saved but not appear in the mobile tab UI.

## What changed
- Adds a hard v7.0 renderer for `.portfolio-tabs` using the single `localStorage` screeners state.
- Uses unique `data-v70-*` attributes so older mobile handlers do not intercept `+ New` / save actions.
- Adds a dedicated v7.0 Save as New Screener bottom sheet.
- Forces `renderPortfolioTabs()` + `renderAll()` + active tab scroll after save.
- Keeps custom screeners visible on mobile by putting the active custom screener first.
- Keeps portfolio tabs horizontally scrollable on mobile.

## Console test
After deploy, open mobile Safari and run if needed from desktop devtools remote inspector:

```js
window.__stockcheckCreateScreenerV70('Test Mobile Screener')
```

The new screener should immediately appear and become active.
