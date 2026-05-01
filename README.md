# V2.7 note — Public GitHub safe mode

This package uses BYOK for Alpha Vantage. Do not commit API keys. Paste the key in the Analyst Consensus tab and save it only in browser localStorage. See `README_SEC_V2_7_PUBLIC_BYOK.md`.

# Stock Timing Radar — GitHub Pages Edition

This repo is ready for GitHub Pages + GitHub Actions.

## What this version does

- Runs Python inside GitHub Actions on a schedule.
- Reads tickers from `watchlist.txt`.
- Calculates EMA 5/20/89/200, RSI(14), MACD(12,26,9), volume, 52-week high/low.
- Writes static JSON to `site/data/scanner.json`.
- Deploys `site/` to GitHub Pages.

## Edit your watchlist

Open `watchlist.txt` and put one ticker per line:

```txt
NVDA
PLTR
TSLA
TSM
COST
MSFT
AMZN
ORCL
HOOD
MSTR
```

Use Yahoo-style tickers, for example:

```txt
PTT.BK
AOT.BK
0700.HK
9988.HK
```

## GitHub setup

1. Upload this whole folder to your GitHub repository.
2. Go to **Settings → Pages**.
3. Under **Build and deployment**, set **Source** to **GitHub Actions**.
4. Go to **Actions**.
5. Run **Update stock data and deploy GitHub Pages**.
6. Wait until it finishes, then open the Pages URL.

## Important note

GitHub Pages is static. The webpage can only scan tickers already generated into `site/data/scanner.json` by GitHub Actions. To add a new ticker online, edit `watchlist.txt` and run the workflow again.

## v8: Technical / Fundamental tabs

This version adds a Fundamental tab next to the Technical scanner.

Fundamental data is best-effort and generated during the GitHub Actions workflow. It is not real-time and it does not use an AI API key. If free Yahoo fields are missing, values are shown as `N/A` rather than fabricated.

Fundamental tab includes:
- Fundamental Score / Signal
- Latest Quarter / Earnings Date / Days to Next Quarter
- Revenue / Estimated Revenue / Surprise %
- QoQ and YoY placeholders when unavailable
- EPS / Estimated EPS
- Analyst target mean and upside to target
- Rules-based Fundamental Highlight in the detail section

To refresh after editing `watchlist.txt`:
1. Commit changes
2. Go to Actions
3. Run `Update stock data and deploy GitHub Pages`
4. Wait for a green check

## v8.1 Fundamental hotfix
This build adds a no-key fallback for the Fundamental tab:
- Yahoo quote v7 fallback for target/EPS/earnings date fields
- SEC companyfacts fallback for US quarterly revenue/net income/EPS plus QoQ/YoY
