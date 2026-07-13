# Changelog

All notable changes to Codex Ads are documented here.

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
