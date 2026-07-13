# Changelog

All notable changes to Codex Ads are documented here.

## 1.9.0 — 2026-07-13

### Productization, Release and Real-World Validation

- Added a private, cross-platform UAC workspace with natural-language Agent
  workflow guidance while preserving every legacy path and CLI command.
- Made normalization, Doctor, analysis, reports, experiment drafts, and replays
  work together without requiring operators to author schemas by hand.
- Upgraded historical replay to a preferred six-stage evidence trail while
  retaining the legacy five-file contract and separating confounded outcomes.
- Expanded redacted privacy checks for advertising identifiers, API/OAuth/MMP
  credentials, local workspaces, environment files, and unsafe public replays.
- Defined the real UAC package coverage, typing, schema, compatibility,
  workspace, installer, reporting, and release-history gates in CI.
- Documented platform maturity honestly: UAC is deterministic; other platform
  skills remain structured Agent workflows or advisory support.

### Compatibility and release status

- Ledger schemas `1.0` and `1.1`, the historical UAC entry point, legacy replay
  cases, and direct file-based commands remain supported.
- This entry prepares `v1.9.0`; it does not claim that a remote tag or GitHub
  Release already exists. Publishing still requires the release checklist and
  a clean full-history privacy gate.

## 1.8.3 — 2026-07-13

### Stabilization and Real-World Validation Foundation

- Split the deterministic UAC engine into testable internal modules while
  preserving the existing entry point, CLI commands, output fields, and report.
- Added a read-only project Doctor, explicit ledger schema migration,
  lightweight input normalization, and anonymized historical replay metrics.
- Established a canonical Ads router with a deterministic mirror sync check and
  introduced lightweight knowledge-freshness metadata and diagnostics.
- Extended CI with typing, schema migration, Doctor, normalization, replay,
  router-sync, installed-package, and cross-platform compatibility checks.
- Added fixed-version release preparation, rollback guidance, and clearer
  documentation of deterministic guarantees, Agent inference, and limitations.

### Privacy

- Added repository safeguards for private replay data and future generated
  caches. Public examples remain anonymous and contain no live account data.

## 1.8.2 — 2026-07-13

### CI Reliability

- Added the `requests` runtime package to the development test environment so
  redirect and SSRF regression tests run in clean GitHub Actions workers.

## 1.8.1 — 2026-07-13

### UAC Safety Hardening

- Enforced ledger status, approval, execution, review-snapshot, maturity,
  guardrail, confounder, result, and learning consistency.
- Added deep-goal measurement completeness checks for event definitions,
  payment/trial/refund distinctions, attribution windows, and OS differences.
- Normalized operator-friendly goal names while preserving their raw values.
- Prevented unexecuted proposals from publishing learnings and blocked CLI
  outputs from overwriting source inputs or experiment ledgers.
- Added automatic single-ledger discovery, duplicate-ID prevention, and an
  auditable `cancel-proposal` transition for declined unexecuted proposals.
- Added fail-closed UAC scope, date-window, segmentation, signal, and evidence
  validation plus safe investigation-only degradation for incomplete policies.
- Required terminal metrics, evidence quality, mutually consistent result and
  decision outcomes, and an explicit next action before publishing learnings.
- Made the full ledger scaffold safely valid outside the active experiment
  array and aligned the offline JSON Schema with runtime validation.

## 1.8.0 — 2026-07-13

### UAC Experiment Loop

- Added the dedicated `ads-google-app` route for Google App campaigns/UAC.
- Added deterministic measurement, learning-eligibility, optimization-
  feasibility, permission, and single-variable experiment decisions.
- Added a local `ADS-EXPERIMENTS` ledger contract with minimal, full, and
  worked examples plus JSON Schema validation.
- Added structured UAC analysis and Markdown report generation from one source
  of truth.
- Added experiment readback for maturity, low volume, guardrails, concurrent
  changes, and win/loss/inconclusive outcomes.
- Hardened permission blocking, conversion-volume maturity, offline schema
  validation, atomic ledger writes, malformed-input handling, and completed
  experiment learning readback.
- Added behavior fixtures for common limited-permission UAC scenarios.
- Added cross-platform CI, lint, schema, installer, fixture-replay, and report
  smoke checks.

### Compatibility

- Existing routes, report tools, read-only defaults, and other ad-platform
  skills remain available.
- The new Python helper is optional. YAML input uses the lightweight PyYAML
  dependency already used by the development harness.
- Generated experiments remain unapproved proposals until a human confirms an
  exact platform edit.
