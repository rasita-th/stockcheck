# PR2B — Today UI Isolation and Free-News Release

This stacked branch completes PR2 by:

- hiding every Scanner/Screener container whenever Today is active
- keeping Scanner DOM mounted and untouched for safe view switching
- adding a P0/PR2 runtime contract adapter with last-known-good fallback
- adding News & Events filtering and optional source-chain details
- removing the raw Scanner-data action from Today cards
- enabling the free-news collection flag
- extending pre-deploy and post-deploy smoke tests to validate the isolation CSS served by GitHub Pages
