# Refresh-to-production reliability investigation

Date: 2026-10-31 (Asia/Bangkok). Checkout: `2aa666d4dfffed7d9dfa3eb946fa60eb50143adf`.

## Confirmed findings and changes

- **Finnhub contract failure reproduced:** the fallback fixture is dated August 12,
  but `fetch_sec_events` filters bootstrap events relative to today's date. Freeze
  the test clock and separately assert old events are filtered. Verified empty
  fallback is successful; invalid discovery links still fail. Production retention
  and transport policy remain unchanged.
- **Market-date validation:** normalize timezone-aware timestamps and epoch seconds
  or milliseconds to America/New_York. Reuse the existing health market calendar
  for holidays and trading-day lag. Date-only inputs retain their calendar date.
  Coverage, stale-ratio thresholds and maximum lag remain unchanged. These are
  independently reproduced validator defects; historical run causality still needs
  its source freshness report and authenticated logs.
- **Drawdown verifier:** compare preset membership using the runtime's unrounded
  canonical depth while requiring displayed depth to match within display rounding.
  A depth of 14.99 displays as 15.0 but still belongs to 5–15. Missing, nonfinite or
  stale rendered metrics fail. Failure evidence includes settings, row metrics,
  browser console and screenshots; evidence collection cannot mask the error.
- **Publisher preflight:** a real Git fixture demonstrated that `git apply --check
  --3way` can succeed before the actual merge conflicts. Merge into a disposable
  index first. Conflicts produce `REJECTED_PATCH_BASE` and a receipt containing
  producer/base/current SHA and changed paths without modifying the production
  worktree or index. Clean patches still apply and stage. The existing hash, path,
  source, replay and stale-artifact checks remain enabled. Job outcome and artifact
  validation outcome are reported separately.
- Retain technical source-freshness reports and publisher conflict evidence for
  30 days. The new real-Git publisher regression tests run in the existing single
  publisher validation workflow.

## Validation evidence

- 114 selected Python tests passed across attention reliability, freshness, health,
  browser verifier, artifact/patch/receipt contracts, workflow topology, refresh
  mode, screener/drawdown snapshots and Market Pulse diagnostics.
- Technical-shard, Drawdown runtime, delayed-schedule admission and watchdog
  JavaScript checks passed.
- The local technical snapshot has 406 rows, full timestamp coverage and no stale
  rows under the workflow's unchanged freshness thresholds.
- Desktop and mobile verifier flows each passed three consecutive runs against
  system Chromium and local static data: baseline 10 rows; preset 5–15 returned 3,
  preset 30+ returned 4. The verifier functions ran through a temporary Playwright
  driver adapter because a Selenium ChromeDriver is not installed. This does not
  establish Selenium driver setup or production behavior.
- All four changed workflow files parsed as YAML and their shell blocks passed
  `bash -n`. Clean and conflicting patch integration tests execute the actual
  publisher shell block with real temporary Git repositories.
- Development app HTML and canonical snapshot HTTP responses passed (406 rows).
- Broad Python discovery executed 248 tests before adding the two publisher tests:
  246 passed and two legacy P3 expectations errored. Both expect retired legacy
  earnings fallback, whereas the current P5 reader requires canonical provenance:
  `test_legacy_row_falls_back_visibly` and
  `test_metrics_separate_canonical_and_legacy_reads` in
  `tests/test_earnings_dual_read_p3.py`. These are unresolved baseline test-contract
  mismatches; canonical-only production policy was not weakened.

## External access and outstanding work

Git HTTPS reads through the existing proxy work. GitHub API and production Pages
requests return CONNECT 403 under the current policy. The environment draft saves
`api.github.com` and `rasita-th.github.io` as additive custom network destinations,
plus tested dependency-install and service-start instructions. Saving a draft does
not apply network access or publish an environment snapshot. Review/save environment
settings and publish the environment, then retest the actual operations.

Public run summary pages are readable but require sign-in for logs. The supplied
live run URL `38491140824` identifies run **#1699** on the public page, rather than
#1718 in the supplied summary; correlate by immutable run ID. Neither historical
counts nor the claimed 11-error/BITF root cause have been independently confirmed.

After access is applied:

1. Read exact run logs/artifacts for the reported Finnhub, Live Data, Market Pulse,
   publisher and deploy failures. Preserve run/attempt boundaries. Classify expected
   admission cancellation separately from failure; existing dedupe/watchdog checks
   pass locally, so cancellation counts alone do not justify changing concurrency.
2. Verify repository API authentication and write permissions with existing bindings.
   Do not infer API permission from Git reads or request duplicate GitHub tokens.
3. Publish the reviewed code changes through the repository's normal process, run
   the producers using existing Actions secrets, and correlate each immutable
   artifact with its producer run ID, attempt, SHA and patch hash.
4. Follow the receipt-bound publisher and exact-commit Pages deployment. Rejected
   receipts must remain rejected. A patch conflict needs reconciliation or a new
   producer artifact; do not force-apply stale files.
5. Verify deployed `build.json` source identity, canonical screener/health/shards,
   Drawdown data and desktop/mobile browser flow. Local browser passes do not
   substitute for this step.
6. Observe at least three scheduled producer-to-verifier cycles and distinguish
   failed, cancelled, superseded and successful outcomes before closing the incident.

No commit was pushed, workflow dispatched, or production deployment performed in
this environment. Historical Market Pulse, receipt rejection and core screener
failures remain uncorrelated pending authenticated evidence.
