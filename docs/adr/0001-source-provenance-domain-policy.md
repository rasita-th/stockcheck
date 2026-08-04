# ADR 0001: Source provenance and domain eligibility

- Status: Accepted for staged adoption
- Date: 2026-08-04
- Owners: Earnings domain and Today Attention domain
- Scope: Data-contract boundary only; no UI or production behavior change in this PR

## Context

A Finnhub earnings estimate entered the Today Attention event stream and was rejected only at final generated-data validation. The immediate containment filtered Finnhub rows in the PR3 generator, but that provider-specific blacklist is not a durable architecture.

The current legacy `source` object mixes several concerns:

- provider identity
- evidence quality
- verification status
- domain eligibility

As a result, consumers must infer whether a row is allowed from fields such as `source.type`, and a shared earnings calendar can be interpreted differently by Earnings Radar and Today Attention.

## Decision

Introduce a versioned source-policy contract with four independent concepts:

1. `provider`: where the record came from
2. `source_class`: `primary`, `secondary`, `discovery`, `internal`, or `unknown`
3. `evidence_kind`: `official_record`, `company_disclosure`, `public_report`, `market_estimate`, `internal_signal`, or `unknown`
4. domain decision: `allow`, `allow_estimated`, `allow_unverified`, `allow_internal_only`, or `reject`

Policy is fail-closed. Unknown providers or invalid canonical fields are rejected until their adapter declares valid provenance.

## Domain matrix

| Evidence | Earnings Radar | Today catalyst | Technical watch |
|---|---|---|---|
| Official record | allow | allow | reject |
| Company disclosure | allow | allow | reject |
| Market estimate | allow as estimated | reject | reject |
| Public report | reject | allow as unverified | reject |
| Internal signal | reject | reject | allow internal only |
| Unknown | reject | reject | reject |

Provider names are used only by the temporary legacy adapter. Canonical consumers decide from `source_class` and `evidence_kind`, not from a provider blacklist.

## Migration

The rollout follows the data-structure safety rules:

1. **P1 — Contract foundation:** add this ADR, policy module and tests without changing production behavior.
2. **P2 — Additive dual-write:** canonical earnings rows gain provenance and domain-policy fields while legacy fields remain.
3. **P3 — Dual-read:** Attention and Earnings Radar read canonical fields first and migrate legacy rows with visible diagnostics.
4. **P4 — Central policy gate:** all P0/PR2/PR3 Attention candidates pass through one shared gate.
5. **P5 — Retirement:** remove provider-specific filters only after legacy-read metrics reach zero across stable production runs.

Each behavior-changing phase must include golden fixtures, contract tests, immutable artifact validation and rollback instructions. UI changes remain in separate PRs.

## Invariants

- Every canonical event has a schema version and provenance descriptor.
- A market estimate may appear in Earnings Radar only with estimated semantics.
- A market estimate cannot become a Today catalyst.
- Public news discovery cannot be presented as confirmed primary evidence.
- Internal technical evidence may appear only in Technical Watch.
- Unknown sources fail before publication.
- Producer workflows remain read-only; only the production publisher writes `main`.

## Consequences

Positive:

- Provider changes are isolated in adapters.
- Domain policy has one owner and one testable matrix.
- New providers fail closed instead of silently entering consumer contracts.
- Dual-write and dual-read support backward-compatible migration.

Costs:

- Legacy mappings remain temporarily necessary.
- Producers and consumers must migrate in multiple small PRs.
- Diagnostics must distinguish rejected, estimated, unverified and internal-only rows.

## Rollback

This PR is contract-only. Reverting it removes the unused module, tests and ADR without changing generated data or runtime behavior.
