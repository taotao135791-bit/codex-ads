---
name: ads-google-app
description: >-
  Google App campaigns (UAC) analysis and experiment loop for app-install and in-app
  action/value campaigns. Use for UAC, Google UAC, App campaign, Google App campaigns,
  应用安装广告, 应用内行为广告, tCPA App campaign, tROAS App campaign, or Google 应用广告.
---

# Google App Campaigns: UAC Experiment Loop

Use this skill instead of the generic Google audit when the campaign type is
App. The goal is to determine whether optimization is currently possible and
turn at most one supported recommendation into a traceable, reversible
experiment. It does not promise growth or bypass product, measurement, budget,
permission, or platform limits.

## Reference Resolution

Read resources from the first existing location:

- Skill assets: `~/.codex/skills/ads-google-app/assets/`, `assets/`, or
  `../skills/ads-google-app/assets/`
- Deterministic helper: `~/.codex/skills/ads/scripts/uac_experiment.py`,
  `../../scripts/uac_experiment.py`, or `scripts/uac_experiment.py`
- Global safety: `~/.codex/skills/ads/references/orchestrator.md`,
  `../ads/references/orchestrator.md`, or `../skills/ads/references/orchestrator.md`

For any other `ads/references/<file>.md`, use
`~/.codex/skills/ads/references/<file>.md`,
`../ads/references/<file>.md`, `../skills/ads/references/<file>.md`, then
`ads/references/<file>.md` in a source checkout.

Useful assets:

- `UAC-INPUT.example.yaml`
- `ADS-EXPERIMENTS.minimal.yaml`
- `ADS-EXPERIMENTS.full.yaml`
- `ADS-EXPERIMENTS.example.yaml`
- `uac-analysis.schema.json`
- `ads-experiments.schema.json`

## Start Here

1. Read the optimizer profile if one exists.
2. Read `ADS-EXPERIMENTS.yaml` or `ADS-EXPERIMENTS.json` in the current
   project before proposing a change.
3. If an experiment is running, check its single variable, observation days,
   conversion volume, conversion delay, guardrails, and concurrent changes.
4. Do not stack a new variable while a key experiment is waiting for maturity
   or volume without an explicit reason.
5. For private live dashboards, use Computer Use read-only under the main Ads
   safety gate. Never use browser scraping or screenshot scripts.
6. Build the structured analysis first; derive the Markdown report, daily
   summary, creative request, and experiment record from it.

## Minimum Friendly Intake

Accept pasted tables, CSV/XLSX exports, screenshots, or structured YAML/JSON.
Ordinary operators do not need to fill every schema field. Ask only for the
missing fields that block the next decision.

Recommended minimum:

- date range and timezone
- campaign and ad group / asset group when available
- OS, country, device, optimization event, and bid strategy
- spend, installs, registrations, deep events, payments, and value
- current budget and target
- asset or creative-concept performance
- available permissions
- recent changes
- conversion delay
- Google Ads, Firebase, MMP, and backend reconciliation status

If the export cannot preserve campaign, ad group / asset group, OS, event,
asset, cohort, and time-window grain, state exactly:

`无法在当前证据下完成该层级判断。`

## Objective Identification

Identify both business goal and platform optimization event. Supported goals
include Install, Registration, In-app action, Likely to perform an in-app
action, In-app action value, tCPA, tROAS, Maximize conversions, and Maximize
conversion value.

Do not grade an event from its name. Require evidence for:

- event definition and firing behavior
- relationship to payment, retention, or value in a mature cohort
- event volume and delay
- deduplication, currency, and value accuracy
- iOS/Android differences
- whether the business judges the same event

Classify the event as too shallow, too deep, insufficient volume, unreliable,
misaligned, a supported proxy, an unsupported proxy, or insufficient evidence.
Treat any event-volume number as `heuristic`, `platform_guidance`, or
`account_specific_evidence`; never present an experience threshold as a law.

## Measurement Reliability

Check or request:

- Google Ads vs Firebase
- Google Ads vs MMP
- MMP vs backend payment
- duplicate events
- value and currency
- event and attribution delay
- iOS vs Android
- first vs repeat event definitions
- payment vs trial vs subscription vs refund
- attribution-window effects

Return one state:

- `measurement_reliable`
- `measurement_uncertain`
- `measurement_unreliable`
- `insufficient_evidence`

When measurement is unreliable, payment-based optimization is
`TRACKING_BLOCKED`; request reconciliation and do not compensate with budget,
target, or creative changes.

## Learning Eligibility

Return exactly one:

- `LEARNABLE`
- `BORDERLINE`
- `INSUFFICIENT_EVENT_VOLUME`
- `BUDGET_CONSTRAINED`
- `TARGET_TOO_AGGRESSIVE`
- `MEASUREMENT_UNRELIABLE`
- `CONVERSION_DELAY_NOT_MATURE`
- `INSUFFICIENT_EVIDENCE`

For every state, include triggering evidence, missing data, prohibited actions,
and any low-risk experiment. Do not infer eligibility from country totals.

## Required Analysis Grain

Preserve these dimensions when available:

- campaign
- ad group or asset group
- country
- OS and device
- optimization event
- asset and creative concept
- conversion cohort
- time window

A country is a segment, not the learning unit. Never pause, scale, or reallocate
from a country total alone. Separate Observed facts, Calculated metrics, and
Inference. Keep incompatible attribution windows or immature cohorts apart.

## Creative Diagnosis

Do not call the lowest-CPI asset a winner. Classify mature evidence as:

- low CPI
- high registration rate
- high deep-action rate
- high payment rate
- high value
- low-quality-install attraction
- insufficient sample
- new, fatigued, or stable

Consider concept, promise, product depth, CTA, paid-intent prefiltering,
overemphasis on free, expectation mismatch, size/placement coverage,
lifecycle, backend cohort, and evidence volume. An asset label is an
observation, not a causal conclusion.

## Funnel and Constraint Boundary

Use the default funnel when applicable:

`Spend → Install → Registration → Key action → Paywall view → Trial → Payment → Retention / Value`

Find the largest evidenced drop, then separate media-side controllable
variables from product and tracking dependencies. Do not attribute all
post-registration loss to creative, and do not equate install growth with
commercial-value growth.

Every key finding or recommendation gets one permission class:

- `OPTIMIZER_CAN_EXECUTE`
- `CLIENT_APPROVAL_REQUIRED`
- `CLIENT_DATA_REQUIRED`
- `PRODUCT_DEPENDENCY`
- `TRACKING_DEPENDENCY`
- `PLATFORM_LIMITATION`
- `NOT_ACTIONABLE`
- `INSUFFICIENT_EVIDENCE`

For limited agency permissions, order output as directly executable, client
support, unverified hypotheses, and do-not-touch items.

## Optimization Feasibility Gate

Before recommendations, return one state:

- `DIRECTLY_OPTIMIZABLE`
- `LIMITED_INCREMENT_AVAILABLE`
- `EXPERIMENT_AVAILABLE`
- `DATA_BLOCKED`
- `PERMISSION_BLOCKED`
- `TRACKING_BLOCKED`
- `PRODUCT_FUNNEL_BLOCKED`
- `LEARNING_BLOCKED`
- `NO_ACTION_RECOMMENDED`

It is valid and useful to conclude:

`当前最优动作是不修改账户，先补齐数据或等待转化成熟。`

Never create activity merely to appear useful.

## Experiment Admission Contract

A recommendation becomes an experiment only when all are present:

- explicit problem and evidence
- falsifiable hypothesis
- permission classification
- one primary variable
- control or baseline
- primary metric and guardrails
- observation days and minimum mature conversions
- conversion-delay rule
- success rule
- failure or rollback rule
- inconclusive rule

Otherwise classify it as investigation, client request, monitoring item, or
non-actionable finding. Generated experiments are always `proposed` with
`execution.approved: false`. The helper never edits Google Ads.

Use the deterministic helper when structured input is available:

```bash
python scripts/uac_experiment.py analyze UAC-INPUT.yaml \
  --ledger ADS-EXPERIMENTS.yaml \
  --json-output UAC-ANALYSIS.json \
  --markdown-output UAC-REPORT.md
```

To append the single unapproved proposal after reviewing the report:

```bash
python scripts/uac_experiment.py analyze UAC-INPUT.yaml \
  --ledger ADS-EXPERIMENTS.yaml --append-experiment
```

The flag writes only a local proposal. Execution still requires human approval
and an explicit platform edit confirmation.

## Experiment Readback

Before each analysis, review any active ledger entry and return one result:

- `WIN`
- `LOSS`
- `INCONCLUSIVE`
- `INVALIDATED`
- `STOPPED_FOR_GUARDRAIL`
- `WAITING_FOR_MATURITY`
- `INSUFFICIENT_VOLUME`
- `CONFOUNDED`

More than one concurrent variable makes the result `CONFOUNDED`. Reaching the
minimum days without minimum conversions is `INSUFFICIENT_VOLUME`, not a loss.
An immature delay window is `WAITING_FOR_MATURITY`. Store learning as
account-specific, product-specific, creative-specific, or reusable heuristic;
one account result is never a global truth.

## Default Report Order

1. Executive summary
2. 当前优化状态
3. 数据与测量可靠性
4. 学习资格
5. 关键证据
6. 当前主要阻塞
7. 可控变量
8. 不可控变量
9. 当前唯一优先实验
10. 实验观察条件
11. 客户需要配合的事项
12. Do not touch
13. 下一次复盘条件
14. 置信度和数据缺口

Do not output a dozen equal-priority recommendations. If data is missing,
making a data request the single primary action is acceptable.

## Non-Negotiable Safety

- Default read-only; confirm the exact edit before any live change.
- Never auto-login, bypass permissions, scrape a protected dashboard, or
  simulate clicks.
- Never manufacture account data, causality, volume thresholds, or certainty.
- Do not change budget, target, and creative together while calling it a valid
  experiment.
- Do not decide from daily volatility before conversion delay is mature.
- Do not optimize payment when the payment event is unreliable.
- Do not promise that AI can overcome product, tracking, permission, learning,
  or budget constraints.
