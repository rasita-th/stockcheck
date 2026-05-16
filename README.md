# Stock Timing Radar

Dark-mode stock scanner focused on ranking stocks by distance from EMA lines.

This package is deploy-ready for GitHub Pages.

Read: [`README_DEPLOY_GITHUB.md`](README_DEPLOY_GITHUB.md)

## Quick local run

```bash
python app.py
```

Open `http://localhost:8787`.

## GitHub Pages

Use GitHub Actions as Pages source. The app is split into:

- Technical layer: `site/data/technical.json`
- Fundamental layer: `site/data/fundamental.json`

The browser UI merges both layers and keeps `Technical` / `Fundamental` tabs separated.
