# v7.2 Mobile Memo Render + EMA Alert Fix

Fixes:

- New memo save now clears memo filters and forces Memo view render so the newly-created memo appears immediately on mobile.
- Mobile Memo supports Card View / Table View toggle.
- Memo cards now show Price at Note in addition to Current Price and Target.
- Memo creation form adds alert condition options:
  - Price reaches target
  - Price near EMA line
  - EMA5 > EMA89
  - EMA89 > EMA200
  - EMA5 > EMA20 and EMA89 > EMA200
- Memo table includes an EMA alert/condition column.
- Mobile table view has sticky ticker column and horizontal scroll.

Notes:

- EMA alert checks use available screener/static data on GitHub Pages.
- In local Python mode, Refresh Prices can still try backend quote data.
