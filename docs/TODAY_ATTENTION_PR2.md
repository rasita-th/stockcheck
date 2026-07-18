# Today Attention PR2 — Free News Rollout

PR2 is deployed in two backward-compatible stages.

## PR2A: data and source foundation

- Adds free GDELT discovery and configured company IR/RSS monitoring.
- Treats GDELT as discovery only, never as a primary source.
- Resolves company identity through configured names, aliases and domains.
- Deduplicates similar reports into one canonical event.
- Requires a primary-source URL before an event can be confirmed.
- Caps unverified reports at `Watch`.
- Preserves every field from the P0 `2.0-p0` contract and adds optional PR2 metadata.
- Uses `ATTENTION_NEWS_ENABLED=0` for the first production deploy.

## PR2B: UI isolation and release

- Adds a runtime contract adapter for P0 and PR2 additive payloads.
- Removes Scanner/Screener panels from the Today view without moving or cloning DOM nodes.
- Adds News & Events filtering and source-chain details.
- Enables the free-news feature only after PR2A passes production-equivalent validation.

## Source hierarchy

1. SEC EDGAR
2. Company IR / press release / configured RSS
3. Regulator or government source
4. Corroborated public-news reports
5. Single unverified public-news report

## Safety contract

- Schema changes are additive only.
- The P0 generator remains the compatibility owner.
- `generate_attention_pr2.py` is an adapter over P0, not a replacement contract.
- Golden-file tests block removal of legacy UI fields.
- Frontend fields added by PR2 remain optional until the old contract is retired in a later release.
