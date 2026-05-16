# Stock Timing Radar v6.9

Fixes focused on mobile screener creation and GitHub Pages fundamental-data deployment.

## Mobile screener creation

- `+ New` on mobile opens a dedicated **Save as New Screener** bottom sheet.
- Added mobile controls:
  - `＋ Save Screener`
  - `⚙ Screener`
- Screener settings sheet supports:
  - Save as New
  - Rename
  - Delete
  - Import JSON
  - Export JSON
- Custom screener labels are persisted in localStorage.
- All custom screeners are rendered in the horizontal screener tab bar instead of being sliced to a small subset.
- Mobile long-press delete is disabled to prevent accidental delete prompts.

## Fundamental deploy fix

- `watchlist.txt` now supports v1-style lists separated by spaces, commas, semicolons, tabs, or new lines in both technical and fundamental update scripts.
- The technical deploy workflow now fetches the latest `site/data/fundamental.json` from `origin/main` before uploading the Pages artifact, reducing the chance that a scheduled technical deploy overwrites the live site with an old placeholder fundamental layer.

## Test checklist

- `node --check site/app.js`
- `node --check static/app.js`
- `python -m py_compile app.py scripts/update_fundamental_data.py scripts/update_technical_data.py`
- `python app.py` local health check
