# Changelog

All notable changes to Codex Ads are documented here.

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
