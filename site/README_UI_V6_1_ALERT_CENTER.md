# Stock Timing Radar v6.1 — In-app Alert Center

This patch adds an in-app alert center for the Python/local preview before converting the workflow to GitHub Pages static JSON.

## Added

- Alert Center panel above Scanner Results.
- Alert categories:
  - Actionable: high score and near EMA20.
  - Near EMA: near EMA20 / EMA89.
  - HOT: overextended / RSI hot / stretched EMA distance.
  - Risk: below EMA200, weak RSI, MACD weakening.
  - Memo: local memo target/status alerts from `stockTimingRadar.memos.v55`.
- Alert counters and filter chips.
- Toast after scan when actionable/HOT/risk/memo alerts are found.
- Click an alert to select ticker and open detail on mobile.

## Notes

- This is in-app only. It works when the web app is opened.
- It does not require browser Push API or a backend push server.
- For GitHub Pages deployment, this same logic can run against generated `technical-latest.json` and `fundamental-latest.json`.
