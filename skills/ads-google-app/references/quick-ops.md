# UAC Quick Ops

Use this reference for daily Google App campaign questions that need one
immediate operation decision rather than a full diagnosis, experiment, or
report. Keep the live account read-only until the user confirms one exact edit.

## Contents

1. Entry and output contract
2. Terminology mapping
3. Evidence intake
4. Campaign-level decisions
5. Same-level campaign decisions
6. Creative decisions
7. Bid and budget decisions
8. Permission transformation
9. Operations versus experiments
10. Deterministic helper

## 1. Entry and output contract

Route `/ads decide` and questions such as these to Quick Decision:

- 这素材还能跑吗？
- 新素材放现有 campaign 还是新开？
- 现有 AC2.5 要不要再开一个 AC2.5？
- AC2.5 要不要进入或并行 AC3.0？
- 今天预算和目标怎么调？
- 直接给我操作结论。

Route “为什么” questions to Diagnosis, explicit hypothesis validation to
Experiment, and daily/weekly/client reports to Report. Asking “要不要测试
AC3.0” remains a Quick Decision; asking to create or formally validate an
experiment enters Experiment.

Lead with `结论：`. Then state exactly:

1. which campaign to operate;
2. which campaign level to keep or use;
3. whether to create or run in parallel;
4. what to do with creative;
5. what to do with bid target;
6. what to do with budget;
7. what not to do;
8. when to review;
9. when and how to roll back;
10. confidence and missing evidence.

Return one primary action. Use `null` for an unknown number. Never invent a
duration, event count, spend cap, target, or budget to make the card look
complete. Quick Decision creates neither a full report nor a ledger experiment.

## 2. Terminology mapping

Treat AC2.0, AC2.5, AC3.0 and 广告 2.0/2.5/3.0 as internal campaign-level
labels. Never call them official Google product names. Never parse them as bid
values. In particular:

- `AC2.5` can be a campaign-level label;
- `广告 2.5` can be a campaign-level label;
- `tCPA 2.5` is a bid target, not a campaign level;
- bare `2.5` is unresolved, not a campaign level.

Resolve semantics in this order:

1. actual account optimization event, bid strategy, and value setting;
2. the private project's `campaign_level_glossary`;
3. a clearly labeled Agent inference.

When account settings conflict with a glossary, preserve the account settings
as observed fact, report the conflict, lower confidence, and keep the current
level until the team confirms the label. When no glossary exists, continue
read-only analysis from actual settings, label the mapping inferred, and ask
for mapping confirmation before switching levels.

A project glossary may describe, without standardizing globally:

- objective family;
- optimization event;
- conversion-volume or value optimization;
- tCPA, tROAS, or another strategy;
- value and currency requirements;
- mature payment or revenue-event requirements.

## 3. Evidence intake

Reuse the normalized UAC input, Doctor, measurement state, learning state,
feasibility state, permissions, Workspace, ledger, and Replay. Add only the
facts needed for this decision:

- current and candidate campaign settings;
- candidate-event reliability, delay, mature volume, stability, and business-
  KPI relationship;
- value, currency, deduplication, refund/subscription, value reconciliation,
  delay, volume, stability, and budget state;
- budget and event volume after a proposed split;
- independent geo, OS, budget, audience, or user-hypothesis reasons;
- asset-level mature cohort, fatigue, promise, and replacement coverage;
- exact permissions and client-approval requirements;
- recent product, release, crash, onboarding, paywall, pricing, store, market,
  or operational changes;
- declared review and rollback conditions.

Treat `unknown` differently from `false`. A failed hard gate blocks the action;
unknown evidence produces a hold, data request, or wait. Do not reuse the
current campaign's global conversion count as proof that a candidate event or
two post-split campaigns can learn.

## 4. Campaign-level decisions

### AC2.0 to AC2.5

Allow a candidate AC2.5 only when its configured event is reliable, delay-
mature, sufficiently stable and voluminous under an account-declared rule,
and more useful for the final KPI. If the current AC2.0 is healthy, preserve it
while testing only when both campaigns have enough declared budget and event
volume after the split.

Do not enter AC2.5 when the candidate event is unreliable. Wait when volume or
delay is immature. Move directly only when the current level is demonstrably
misaligned, the candidate is ready, one campaign can learn, the platform edit
is supported, a rollback baseline exists, and permissions allow the change.

### AC2.5 to AC3.0

Require all applicable value gates before recommending AC3.0:

- final business KPI is value, revenue, or ROAS;
- the candidate strategy optimizes value rather than only conversion count;
- payment and value events are reliable;
- value and currency are correct;
- duplicates, refunds, subscriptions, and renewals are defined;
- Google, MMP, and backend value amounts reconcile;
- conversion delay is mature;
- value-event volume and value stability satisfy a declared account rule;
- one campaign has sufficient budget, and a parallel test has sufficient
  post-split budget and event volume for both campaigns.

A count reconciliation is not automatically a value-amount reconciliation.
Block AC3.0 for known value/currency/refund/reconciliation defects. Wait for
unknown, immature, or insufficient value signals. Preserve a healthy AC2.5
while testing AC3.0; do not close it merely to restart learning.

Roll back a mature, failed AC3.0 only to a known stable AC2.5 baseline under a
declared condition. Describe the rollback as a current operational decision,
not proof that value optimization can never work.

## 5. Same-level campaign decisions

Default to `ADD_TO_EXISTING` when level, event, geo, OS, bid strategy, business
goal, and budget ownership are the same and the new assets only change the
expression. Reject duplication when the only reason is recent performance,
“restart learning,” or “try again.”

Use `CREATE_NEW_SAME_LEVEL` only when independent geo, OS, budget, audience,
commercial hypothesis, client attribution, or structure is genuinely required
and both post-split campaigns can learn. Use
`DUPLICATE_FOR_CONTROLLED_TEST` only after strict experiment admission and
traffic isolation; otherwise it is not a valid experiment.

## 6. Creative decisions

Judge creative from asset-level mature evidence, not CPI or CTR alone. Include
running time, spend, deep events, payment/value, conversion delay, concept,
promise, paid-intent prefiltering, fatigue, historical concept evidence,
replacement coverage, and fit with the current optimization event.

Return one creative state such as keep, run with a declared limit, wait for
maturity, reduce exposure, pause, replace, or insufficient data. If a tired
asset has no replacement, reduce exposure instead of stopping all coverage.
Place a compatible new asset in the existing campaign unless the independent
campaign-structure gate also passes.

## 7. Bid and budget decisions

Keep campaign level, bid, and budget in separate structured sections. When the
operator supplies mature multi-day facts and explicit business bounds, derive
the signals first and return at most one bounded numeric change. Read
`docs/quick-ops-numeric-decisions.md` in a source checkout for the input fields,
units, evidence types, thresholds, and complete output contract.

Use these sources in order:

1. measurement, maturity, conversion-delay, and recent-change hard gates;
2. actual account settings and normalized multi-day facts;
3. business CPA/ROAS and budget constraints as hard bounds;
4. platform guidance for safety only;
5. explicitly labeled heuristics;
6. legacy supplied recommendation values only as ignored compatibility hints.

For tCPA, require the current target, mature actual CPA, a business CPA ceiling,
multi-day delivery, and mature event evidence. For tROAS, additionally require
reliable value, currency, deduplication, refund handling, and Google/MMP/backend
amount reconciliation. Ratios use `3.0` for 300% ROAS; normalization also accepts
`"300%"`. Never derive a tCPA or tROAS number from an AC label.

Return `null`, `WAIT`, or `NO_CHANGE` when a hard gate fails, a business bound
is missing, or the supplied facts do not evidence a primary constraint. Do not
relax tCPA merely to spend when mature CPA is already outside the business
ceiling, and do not emit tROAS when the value signal is unreliable.

The structured output separates `conservative_value`, the single
`recommended_value`, and `aggressive_value`; the compact card displays only the
recommended value. Apply these single-variable rules:

- target is primary: keep budget unchanged;
- budget is primary and mature efficiency passes the business bound: keep the
  target unchanged;
- campaign level changes: keep target and budget unchanged;
- an urgent confirmed multi-variable intervention is operational, not a valid
  experiment.

Preserve an eligible ideal recommendation in `target_recommendation` or
`budget_recommendation`, then project permissions into its `execution` object
and the compatible `bid_decision` / `budget_decision`. A read-only or approval-
blocked user sees the current executable value plus a client request, never an
impossible change labeled as “execute now.”

## 8. Permission transformation

Calculate factual eligibility first, then transform any unavailable write into
the best action currently executable. Do not show an impossible change as the
primary action.

- Creative-only: keep campaign, level, bid, and budget unchanged; return only
  supported asset work.
- Cannot create campaign: keep the current campaign and prepare an exact client
  approval request.
- Cannot change optimization event: do not recommend an immediate level move.
- Read-only: return hold plus a client request; perform no write.
- MMP without backend: wait for backend value reconciliation before AC3.0.
- Mixed OS permissions: act only on the editable OS when segmented evidence
  exists; otherwise hold.
- Aggregate-only data: request campaign/event/asset grain before acting.

Creative permission does not prove that approved replacement assets exist.
Local ledger approval never implies permission to edit Google Ads.

## 9. Operations versus experiments

Classify an ordinary Quick card as `OPERATIONAL_DECISION`. Do not append it to
the experiment ledger. A valid experiment requires a single variable, baseline,
mature observation rule, success rule, rollback rule, and attributable design.

Allow an explicitly confirmed emergency to change multiple variables when
delivery is broken or configuration is clearly invalid, but label it:

```text
OPERATIONAL_INTERVENTION
NOT_A_VALID_EXPERIMENT
ATTRIBUTION_WILL_BE_CONFOUNDED
```

Do not publish causal learning from that intervention. Do not stack an ordinary
change while an existing experiment is unfinished.

## 10. Deterministic helper

Use the private Workspace whenever available:

```bash
python3 scripts/uac_experiment.py decide \
  --workspace "workspaces/<project>"
```

For an explicit anonymous input:

```bash
python3 scripts/uac_experiment.py decide \
  skills/ads-google-app/assets/UAC-QUICK-OPS.example.yaml
```

For a fully synthetic numeric tCPA example whose only change is `5.0 → 5.5`:

```bash
python3 scripts/uac_experiment.py decide \
  skills/ads-google-app/assets/UAC-QUICK-NUMERIC.example.yaml --json
```

Use `--json` for the structured contract. Workspace mode writes private
`analysis/UAC-QUICK-DECISION.json` and
`reports/UAC-QUICK-DECISION.md`. It keeps the experiment ledger unchanged and
never edits Google Ads. Use `--glossary` only for an explicit local mapping;
inside a Workspace, keep that file inside the same private Workspace.
