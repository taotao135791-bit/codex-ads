# Changelog

All notable changes to Codex Ads are documented here.

## 1.9.2 — 2026-07-14

### Numeric Safety Guardrails and Release Stabilization

- Added versioned normal-change caps for tCPA, tROAS, and daily budget in both
  directions. The bundled `uac-numeric-policy-v1` uses a 20% heuristic default,
  while the final value must still satisfy account evidence, business bounds,
  permissions, and the read-only confirmation contract.
- Added staged optimization output for candidates beyond the active cap. Only
  stage one is immediately proposed; every later stage requires fresh mature
  evidence and is never executed automatically.
- Added strict default, project, and private Workspace policy loading for
  calibratable numeric and signal heuristics, with version chaining, schema and
  runtime validation, effective-policy provenance, and a zero-change fallback
  when a bundled numeric default is unavailable.
- Separated `NORMAL_OPTIMIZATION`, `STAGED_OPTIMIZATION`, confirmed
  `OPERATIONAL_CORRECTION`, and non-attributable `EMERGENCY_INTERVENTION` so an
  ordinary scale action cannot use an incident-response exception.
- Added the human-reviewed `evaluation.yaml.numeric_evaluation` Replay contract
  and direction, median magnitude error, policy-cap, aggressive/conservative,
  rollback, staged-plan, and correct-no-action aggregates. Replay never changes
  a policy automatically.
- Removed one exact historical synthetic refresh-token fixture false positive
  with a digest-only allowlist, without weakening detection for real tokens.
  The current tree passes its redacted scan, while legacy identity metadata and
  tracked bytecode still block the `v1.9.2` tag and GitHub Release. No history
  rewrite, tag, or Release is claimed by this entry.

### Deterministic Numeric Quick Decisions

- Added deterministic derivation for maturity, multi-day budget delivery,
  event-volume stability, target constraints, value readiness, creative
  quality, candidate events, and campaign-split feasibility.
- Added bounded tCPA, tROAS, and daily-budget candidates based on supplied
  account evidence and explicit business limits, with conservative,
  recommended, and aggressive views where the evidence supports them.
- Added fail-closed numeric safety gates for immature or unreliable data,
  recent changes, one-day volatility, missing business limits, restricted
  permissions, and ordinary multi-variable changes.
- Kept AC2.0/AC2.5/AC3.0 as campaign-level labels rather than bid values, and
  kept every numeric decision read-only with evidence, review, and rollback
  fields visible to the operator.
- Added an anonymous numeric Quick Decision example, extended schema and Doctor
  coverage, and cross-platform installed-package smoke tests for the numeric
  modules and deterministic output.
- Added private numeric Replay calibration for direction, magnitude, unsafe
  recommendations, correct no-action, rollback, acceptance, and confounding;
  excluded unexecuted, immature, or confounded cases from invalid denominators.
- Made compact cards expose per-Campaign split budgets, missing candidate
  targets, hard business-boundary corrections, localized data gaps, and
  Campaign-level rollback without enabling any account or ledger write.

### Compatibility and release status

- Existing `decide`, `analyze`, Workspace, Report, Experiment, Replay, and
  Ledger 1.0/1.1 paths remain compatible; legacy caller-supplied numeric hints
  cannot bypass the new evidence and permission gates.
- This entry prepares `v1.9.2`; it does not claim that a remote tag or GitHub
  Release exists. The known full-history privacy block still prohibits tags and
  releases even when the current tree and ordinary CI pass.

## 1.9.1 — 2026-07-13

### Quick Ops and Campaign Level Decision Mode

- Added a read-only `decide` entry that returns one compact campaign operation
  card instead of a full report or automatic experiment.
- Added configurable AC2.0/AC2.5/AC3.0 terminology resolution with explicit
  protection against treating internal level labels as tCPA/tROAS numbers.
- Added deterministic keep, create, parallel, move, wait, and rollback gates
  for AC2.0 → AC2.5 and AC2.5 → AC3.0 decisions.
- Added strict payment/value, currency, deduplication, refund/subscription,
  amount-reconciliation, delay, volume, stability, and split-capacity checks
  before AC3.0 admission.
- Added same-level campaign, creative maturity/value, bid/budget separation,
  permission transformation, and operational-intervention classification.
- Added a private Workspace output, standalone Quick Decision schema, synthetic
  input example, progressive-disclosure Skill reference, and 42-scenario
  no-model behavior fixture.

### Compatibility and release status

- Existing `analyze`, Doctor, normalization, Report, Experiment, Ledger 1.0/1.1,
  Workspace, and Replay contracts remain compatible; Quick Decision never
  appends an experiment or edits Google Ads.
- This entry prepares `v1.9.1`; it does not claim that a remote tag or GitHub
  Release exists. The known full-history privacy block must be cleared before
  any tag or release is created.

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
