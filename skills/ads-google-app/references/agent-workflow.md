# UAC Natural-Language Agent Workflow

This reference is the orchestration contract between an operator's natural
language request and the deterministic UAC helper. Keep YAML, JSON, schemas,
and CLI syntax behind the Agent unless the user explicitly asks to inspect
them. Do not copy decision rules from `SKILL.md` or the Python package into
this file.

## Contents

1. Invariants and command resolution
2. Intent 0: make a Quick Decision
3. Intent 1: initialize a project
4. Intent 2: diagnose the current period
5. Intent 3: create an experiment draft
6. Intent 4: record actual execution
7. Intent 5: review an experiment
8. Operator-facing response contract

## Invariants

For every task:

1. Resolve one private project workspace and keep raw account data inside it.
2. Identify only user-provided files, pasted facts, permissions, and recent
   changes. Never invent missing metrics.
3. Select Quick Decision, Diagnosis, Experiment, or Report before choosing an
   output. Normalize evidence into the internal UAC contract, then run Doctor.
4. Run deterministic Quick Decision, analysis, or ledger review only after the
   required input is valid.
5. Return one primary decision and the evidence, blockers, do-not-touch list,
   and next required input behind it.
6. Stop before a local ledger write until the user confirms the exact draft.
7. Treat confirmation to write a local proposal and confirmation to edit
   Google Ads as two different gates. The helper never performs the latter.

The normal paths are:

```text
Quick: identify -> normalize -> Doctor -> decide -> one short card -> stop
Diagnosis: identify -> normalize -> Doctor -> analyze -> root cause and next check
Experiment: diagnose -> explicit hypothesis -> draft -> local-ledger confirmation
            -> human platform execution -> record -> review
Report: identify -> analyze -> formal reporting workflow
```

Ask only for facts that can change the next gate. Do not make an operator fill
the complete schema by hand.

## Command and path resolution

Use the first available helper:

1. Installed Codex helper:
   `~/.codex/skills/ads/scripts/uac_experiment.py`, with the installed virtual
   environment Python when present.
2. Source checkout: `python3 scripts/uac_experiment.py`.
3. Windows PowerShell source checkout: `py -3 scripts/uac_experiment.py`.

In the examples below, `UAC` means the resolved Python-plus-helper command and
`WS` means the private workspace. Pass paths as separate arguments; never
construct a shell command by interpolating user-provided names. Paths with
spaces must remain quoted at a shell boundary.

Use the workspace files created by `init-workspace` rather than legacy files
in the repository root. A source or installed helper may still receive
explicit legacy paths for compatibility; recommend migration after the task
instead of moving or deleting them automatically.

## Intent 0: make a Quick Decision

Example user requests:

```text
这条素材还能跑吗？
现有 AC2.5 要不要再开一个 AC2.5？
我现在该继续 AC2.5 还是进入 AC3.0？
```

Read `quick-ops.md`. Identify the current campaign, actual optimization event,
bid strategy, team glossary or inferred mapping, candidate-event/value gates,
split capacity, creative evidence, permissions, and review/rollback rules. Do
not ask the operator to write the contract.

Deterministic path:

```bash
UAC normalize --workspace "WS"
UAC doctor --workspace "WS" --json
UAC decide --workspace "WS"
```

Outputs:

- one card whose first non-empty line starts with `结论：`;
- separate campaign-level, structure, creative, bid, and budget decisions;
- a declared wait/data request when mapping, value, split, maturity, or
  permission evidence is missing;
- private JSON/Markdown outputs, with the experiment ledger unchanged.

Stop when the user request routes to Diagnosis, Experiment, or Report; use that
mode rather than stretching the Quick card. A Quick recommendation is an
operational decision, not an experiment. Do not append it to the ledger or
apply a live edit. If the user later requests a formal test, enter Intent 3 and
rebuild it under experiment admission rules.

## Intent 1: initialize a UAC project

Example user request:

```text
帮我为这个 UAC 账户初始化项目。
```

Inputs:

- a non-sensitive local project name;
- optional business KPI, platform optimization event, timezone, permissions,
  protected variables, and available data;
- no customer ID, account name, or full schema is required in the name.

Deterministic path:

```bash
UAC init-workspace <project-name>
UAC doctor --workspace "workspaces/<project-name>" --json
```

Outputs:

- an ignored private workspace with context, input, normalized, analysis,
  experiments, reports, and replay locations;
- a minimal valid local ledger and an operator-facing list of the smallest
  missing facts needed for analysis;
- no file containing live data in the repository root.

Stop when:

- the requested destination is public, tracked, a symlink escape, or outside
  the allowed workspace root;
- the name is ambiguous, sensitive, invalid, or collides with an existing
  non-empty project;
- initialization or the required Doctor check fails.

Confirmation gate: the initialization request authorizes creation of this
local, reversible directory. It does not authorize a ledger proposal or any
Google Ads edit. Never overwrite an existing workspace without a separate,
exact confirmation.

## Intent 2: analyze the current period (Diagnosis)

Example user request:

```text
分析本周 UAC 数据，告诉我该不该动。
```

Inputs:

- pasted text/table or user-provided CSV, XLSX, Markdown, JSON, YAML, or
  screenshot evidence;
- date range/timezone, KPI and optimization event, permissions, recent
  changes, conversion delay, and reconciliation evidence when available;
- the current experiment ledger.

Deterministic path:

1. Put or copy user-provided files under `WS/input/`; do not move the user's
   original file without permission.
2. For object-shaped JSON/YAML or exactly one CSV summary row, run:

   ```bash
   UAC normalize --workspace "WS" --source-label "operator-provided"
   ```

   This writes `normalized/NORMALIZATION.json` and an
   `UAC-INPUT.draft.yaml`. It creates `normalized/UAC-INPUT.yaml` only when the
   normalized fields already satisfy the full deterministic input contract.
   For XLSX, Markdown, screenshots, multi-row CSV, or pasted prose, the Agent
   extracts only observed facts and constructs the same internal contract.
   Preserve source labels and report ambiguity; do not pretend that
   `normalize` directly supports these formats.
3. If needed, complete `WS/normalized/UAC-INPUT.yaml` from observed facts,
   then run:

   ```bash
   UAC doctor --workspace "WS" --json
   UAC analyze --workspace "WS"
   ```

   Do not add `--append-experiment` during analysis.

Outputs:

- normalized evidence with missing fields and conversion conflicts visible;
- Doctor status and safest next step;
- structured analysis and readable report;
- exactly one primary decision: act through one eligible experiment, wait,
  collect data/request support, or make no account change.

Stop and recommend no action when:

- a critical value is missing, conflicting, non-finite, or cannot be tied to
  the required campaign/cohort/time grain;
- Doctor fails, measurement is unreliable, conversion delay is immature,
  volume is insufficient, permission blocks the variable, or evidence does
  not admit an experiment;
- more than one ledger is discoverable and the user has not identified the
  intended project;
- an unfinished experiment makes another variable unsafe.

Confirmation gate: read-only analysis and the requested local report need no
additional confirmation. Analysis never writes a proposal to the ledger and
never authorizes a platform edit.

## Intent 3: create an experiment draft

Example user request:

```text
根据这次分析创建一个实验。
```

Inputs:

- the current structured analysis and readable report;
- the current ledger and explicit permissions;
- one eligible experiment from `analysis.experiments`.

Deterministic path:

```bash
UAC validate-ledger --workspace "WS"
UAC review-ledger --workspace "WS"
UAC analyze --workspace "WS"
```

Present the single proposal from the analysis in ordinary language: evidence,
hypothesis, one variable, baseline/control, treatment, primary metric,
guardrails, minimum days/conversions, delay, success, rollback, and
inconclusive rules. Do not write it to the ledger yet.

Stop without creating a draft when:

- analysis contains no admitted experiment;
- the variable is outside the user's permission;
- the proposal changes budget, target, and/or creative together;
- a proposed, approved, running, or observing experiment is unfinished;
- measurement, volume, maturity, baseline, guardrails, or rollback criteria
  are insufficient;
- the proposed experiment ID has appeared anywhere in the ledger.

Confirmation gate A — local record: ask the user to confirm the exact draft
and that it may be appended to the private local ledger. Only after an
unambiguous confirmation, run:

```bash
UAC analyze --workspace "WS" --append-experiment
UAC validate-ledger --workspace "WS"
UAC review-ledger --workspace "WS"
```

The appended entry must remain `proposed`, unexecuted, and
`execution.approved: false`. Confirmation gate B — live edit — is separate:
state the exact campaign, one variable, old value/state, new value/state, and
rollback condition. The user or authorized operator performs that edit; the
helper does not.

Outputs:

- before gate A: a human-readable draft only;
- after gate A: one validated, unapproved local proposal;
- never an automatic Google Ads change.

## Intent 4: record actual execution

Example user request:

```text
我已经在今天把两个旧素材替换成新的付费价值素材。
```

Inputs:

- one existing experiment ID;
- exact execution time and timezone, actual changed items, executor/approval,
  and whether budget, target, campaign structure, tracking, product, or any
  other variable changed concurrently;
- the difference, if any, between planned and actual treatment.

The statement "today" alone is not an exact timestamp. Resolve it from the
project timezone and ask for the missing time before writing. If multiple
active entries exist, ask which ID; never guess.

Deterministic path:

1. Validate and review the ledger before editing it.
2. Compare the reported action with the proposal's declared variable,
   treatment, approval, and guardrails.
3. After the user confirms the execution facts to record, update only that
   private ledger entry: record the actual timestamp and notes, set the
   appropriate execution/observing state, preserve a pending result, and fill
   the review snapshot from facts rather than defaults.
4. Run:

   ```bash
   UAC validate-ledger --workspace "WS"
   UAC review-ledger --workspace "WS"
   ```

Stop when:

- no matching approved/proposed experiment exists;
- exact time, actual change, approval, or concurrent changes are unknown;
- the action is only planned, not actually executed;
- the ledger would be made invalid.

If actual execution differs from the proposal, preserve both planned and
actual facts and report the deviation. Multiple changed variables or another
material concurrent change must be recorded as a confounder; do not silently
repair the history or call the experiment clean.

Confirmation gate: the user must confirm the facts written to the local
ledger. A report that a human already acted is evidence to record, not
permission for the Agent to perform another live edit.

Output: an observing record with a pending result, plus any deviation or
confounding warning. Never declare success from execution alone.

## Intent 5: review the current experiment

Example user request:

```text
复盘当前实验。
```

Inputs:

- the active ledger entry and its before snapshot;
- a comparable after snapshot at the same campaign/cohort/time grain;
- elapsed days, mature conversion count, conversion-delay status, guardrails,
  actual action, and all concurrent changes.

Deterministic path:

1. Normalize/map the after evidence using the same rules as Intent 2.
2. Update the private ledger's review snapshot and result evidence only from
   confirmed facts; preserve raw evidence under the workspace.
3. Run:

   ```bash
   UAC validate-ledger --workspace "WS"
   UAC review-ledger --workspace "WS"
   ```

4. Translate the deterministic state into exactly one operator action:

   | Review result | Operator action |
   | --- | --- |
   | `WAITING_FOR_MATURITY` | wait until the declared date/delay |
   | `INSUFFICIENT_VOLUME` | continue observing or stop as inconclusive; do not call it a loss |
   | `CONFOUNDED` / `INVALIDATED` | stop causal attribution and decide whether to redesign later |
   | `STOPPED_FOR_GUARDRAIL` | recommend the predeclared rollback |
   | `WIN` / `LOSS` / `INCONCLUSIVE` | close according to the predeclared rule and state the next action |

Stop before a terminal result when:

- minimum days, mature conversions, or conversion delay is not satisfied;
- before/after metrics are incompatible, non-finite, or lack matching grain;
- actual action or concurrent changes are unknown;
- a guardrail breach requires immediate human attention.

Confirmation gate: local evidence recording requires confirmation of the
facts. Any stop, rollback, budget/target/creative change, or other live account
action requires a second confirmation of the exact platform edit.

Outputs:

- one of continue, wait, stop, rollback, or unable-to-attribute;
- the deterministic review state, evidence/maturity gaps, guardrail status,
  and next review condition;
- no causal or platform-wide claim from one account.

## Operator-facing response contract

Do not lead with filenames or enums. Return, in this order:

1. **现在该不该动** — one sentence.
2. **为什么** — the two or three facts that control the gate.
3. **当前唯一动作** — one reversible action, wait condition, or data request.
4. **我没有做什么** — ledger write and account-edit status.
5. **需要你确认/补充什么** — only the next blocking fact or exact gate.

Keep technical artifacts available for audit, but an operator should be able
to complete the workflow without learning YAML, schemas, or CLI syntax.
