# Stockcheck Production Pipeline Runbook

## Architecture

`Data producer → immutable schema 2.0 artifact → Publish Production Data → Deploy GitHub Pages → Verify Production Deployment`

Automatic repository writer: `Publish Production Data` only.
Manual writer exception: `Roll back Market Pulse data` only.

## Normal statuses

- `PUBLISHED`: data commit created; its push to `main` triggers the sole Pages workflow.
- `NO_CHANGES`: producer succeeded but generated no patch; no commit or deploy.
- `SKIPPED_REPLAY`: the same producer run/attempt was already published.
- `SKIPPED_DUPLICATE`: identical patch content was already published.
- `SKIPPED_STALE`: artifact was older than the latest published artifact for that producer.

The four no-op statuses above are healthy outcomes and must not be rerun automatically.

## Hard failures

- `REJECTED_HASH_MISMATCH`: artifact bytes differ from metadata.
- `REJECTED_PATH`: artifact attempted to change a path outside its producer allowlist.
- `REJECTED_SOURCE`: workflow, branch, event, SHA, run ID, or attempt did not match.
- `REJECTED_SCHEMA`: unsupported artifact metadata.
- Validation failure after patch apply: merged production data is invalid; publisher must not push.
- Deployment receipt mismatch: verifier is checking a release identity different from the deployment run.

## Rerun policy

Rerun failed jobs only for transient network, DNS, HTTP 429/5xx, runner download, or GitHub Pages propagation failures.

Do not rerun blindly for schema mismatch, rejected paths, hash mismatch, invalid JSON, release mismatch, missing secrets, or source identity mismatch. Fix the producer, manifest, secret, or deployment contract first.

## Producer recovery

1. Open the producer run and identify whether generation or validation failed.
2. Confirm the provider secret exists and the provider response is usable.
3. Rerun the producer only after the cause is transient or corrected.
4. Never manually commit generated data to `main` to bypass the publisher.

## Publisher recovery

1. Read the Production publisher result summary.
2. For `NO_CHANGES`, replay, duplicate, or stale statuses, take no action.
3. For a contract rejection, inspect `metadata.json` and `production-data.patch` from the producer artifact.
4. For merge validation failure, reproduce validators against latest `main` plus the patch.
5. Rerun only after the underlying artifact or transient Git operation is corrected.

## Deployment recovery

1. Confirm the publisher pushed the intended commit.
2. Inspect `Deploy GitHub Pages` build and smoke steps.
3. Rerun the failed deployment job for transient Pages errors.
4. Do not regenerate data merely to retry deployment.
5. The deploy receipt must report `status=verified`, `production_smoke_passed=true`, the expected release, and a source commit.

## Verification recovery

The unified verifier downloads the receipt from the exact triggering deploy run and then checks public assets and data contracts.

- Receipt/release mismatch: deterministic; fix the release manifest or deploy release.
- Missing old asset version: usually propagation; wait for retries, then inspect Pages deployment.
- Invalid production JSON or contract mismatch: deterministic data/deployment failure.
- Network/DNS/timeout: transient; rerun failed verifier job.

## Market Pulse rollback

Use `Roll back Market Pulse data` only when current Market Pulse data is invalid and forward repair is not fast enough.

Required inputs:
- exact `source_ref`
- written reason
- confirmation value `ROLLBACK`

Rollback uses the same `production-publisher` concurrency lock. Never bypass the lock or push rollback files manually.

## Release changes

1. Update `config/release-manifest.json`.
2. Keep `TODAY_DEPLOY_VERSION` in `deploy-pages.yml` equal to the manifest release; CI enforces this.
3. Update asset versions in the manifest to match the loader contract.
4. Run verifier fault tests and topology validation.
5. Deploy once and confirm the unified verifier passes.

## Soak checklist

For at least 24 hours after pipeline architecture changes, record:

- non-fast-forward failures: 0
- dirty-worktree failures: 0
- replay commits: 0
- duplicate deploys: 0
- cancelled production runs: 0
- false verifier failures: 0
- automatic `main` writers: 1

Real integrity, authentication, stale-cache, and deployment failures must remain visible and must not be converted to success.
