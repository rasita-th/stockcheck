# SEC V2.8.1 — GitHub Actions push conflict fix

This keeps the V2.8 GitHub Pages hybrid-static architecture and fixes the fundamental workflow failure where the generated `site/data/fundamental.json` commit is rejected with `fetch first` / non-fast-forward.

## Changes

- `update-fundamental.yml` now checks out full git history with `fetch-depth: 0`.
- After committing generated fundamental data, the workflow runs `git fetch origin main` and `git rebase origin/main` before pushing.
- It pushes with `git push origin HEAD:main`.
- Technical and fundamental workflows share one concurrency group so Pages/data jobs do not overlap and fight each other.

No Alpha Vantage API key is included. Analyst consensus remains BYOK/manual in the browser.
