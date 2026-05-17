# v8.1.3 — Attention Workflow Commit Fix

This release fixes the GitHub Actions failure in `Generate Attention List`.

## Fixed

- The workflow now stages every generated data file under `data/`, `site/data/`, and `static/data/` before committing.
- This prevents `git pull --rebase` from failing with `cannot rebase: You have unstaged changes`.
- Uses `git pull --rebase --autostash origin main` before pushing back to `main`.

## Why

`generate_attention.py` and `update_technical_data.py` can update multiple JSON files, not only `attention_today.json`. The previous workflow committed only attention files, leaving other generated JSON files unstaged.
