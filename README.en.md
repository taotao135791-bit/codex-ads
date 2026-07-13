<p align="center">
  <img src="assets/logo.svg" alt="Codex Ads logo" width="100%">
</p>

# Codex Ads — A Codex-first advertising decision workflow

Codex Ads organizes paid-media decisions around Codex. Operators describe goals, permissions, and evidence in natural language; Codex routes the task to focused skills, identifies blockers, and prepares decisions and reports. When a reproducible safety contract matters, local deterministic tools validate the structured facts and experiment ledger.

[中文说明](README.md) · [Quick Start](QUICKSTART.en.md)

## Shortest path for non-programmers

After the `v1.9.1` tag is published, install that fixed version:

```bash
curl -fsSL https://raw.githubusercontent.com/taotao135791-bit/codex-ads/v1.9.1/install.sh | bash -s -- --ref=v1.9.1
```

Then open Codex, attach an export, paste a table, or say that the dashboard is already open, and ask naturally:

```text
This is a Google App campaign with payment as the business KPI. I can change
only budget, tCPA, and creative. Work read-only first: verify measurement and
conversion delay, then tell me whether to run one experiment, wait, or leave
the account unchanged.
```

YAML is not a prerequisite. Codex can first organize facts from user-provided tables, CSV/XLSX files, screenshots, or read-only pages and ask only for gaps that change the next decision. YAML/JSON is the advanced interface for local replay, auditability, and automation.

## Agent reasoning and deterministic behavior

| Layer | What it does | What it does not do |
| --- | --- | --- |
| Codex / Agent reasoning | Understands natural language, reads evidence the user explicitly provides, routes skills, asks for missing context, separates observations/calculations/inferences, and drafts internal or client-facing explanations | It cannot turn incomplete evidence into causality or acquire permissions the user does not have |
| Local deterministic tools | Validate structured contracts, apply UAC state gates, admit at most one single-variable experiment, migrate ledgers, run Doctor, normalize fields, and replay anonymized cases | They do not log in, call ad APIs, infer hidden causes, or replace human approval |

Deterministic means that the same version, structured input, and ledger produce the same rule result. It does not mean free-form Agent explanations are identical or that the result predicts future advertising performance.

### Deterministic capabilities constrained by code and tests

- Schema validation, input normalization, and explicit legacy-ledger migration.
- UAC measurement state, learning state, experiment admission, maturity, and experiment-review state.
- Replay metric calculation, Privacy Doctor, router synchronization, and fixed behavioral regressions.

### Capabilities that still depend on Agent reasoning

- Reading screenshots, XLSX files, multi-row tables, and unstructured text, then mapping observed facts into the internal protocol.
- Understanding creative, product positioning, and business constraints; forming hypotheses; and interpreting anomalous context.
- Writing client communication, creative requests, and business explanations. Free text is not a deterministic rule result.

## Capability maturity

| Module | Maturity | Current boundary |
| --- | --- | --- |
| Google UAC | **Deterministic Workflow** | Schema, normalization, rule states, experiment admission/review, Doctor, Replay, and behavioral tests; natural-language understanding still uses Agent reasoning |
| General Google Ads audit | **Structured Agent Workflow** | Systematic skill and platform guardrails, primarily reasoned from user-provided evidence; no deterministic experiment engine equivalent to UAC |
| Meta / TikTok | **Structured Agent Workflow** | Professional audit and operating workflows without the UAC-equivalent deterministic state and experiment loop |
| Other ad platforms | **Advisory** | Audit, knowledge, and operating guidance whose depth and reproducibility depend on the platform and supplied evidence |
| Reporting and creative tools | **Supporting Tools** | Organize, calculate, and produce deliverables; they do not validate advertising effect |

This table describes reproducibility, not platform quality or performance ranking. Skills outside the structured UAC core should not be presented as equivalent rule engines.

## What Codex Ads cannot guarantee

- Codex Ads does not guarantee growth, lower CPA, or higher ROAS, and one review is not causal proof.
- An admitted experiment is not guaranteed to succeed; admission means only that the evidence and safety conditions are sufficient to test it.
- It does not replace product positioning, in-app funnels, paywalls, SDK/tracking, MMP, backend event delivery, or store-listing work.
- It does not auto-login, bypass permissions, or automatically change an ad account. Every real write requires confirmation of that exact action.
- `tests/fixtures/` and `examples/replays/` are synthetic/anonymized regression samples, not proof of real-world effect or an industry benchmark.
- Replay can inspect workflow behavior against historical evidence; it cannot prove advertising incrementality or causality by itself.
- A result from one account or experiment remains account-, product-, or creative-specific by default; it is not promoted automatically into a global rule.
- When evidence is insufficient, measurement is untrusted, delay is immature, or an experiment is confounded, the correct recommendation may be to collect data, wait, and make no account change.
- Without a reliable deep event, the system cannot optimize payment reliably; advertising-side changes alone cannot repair product or instrumentation failures.

## What It Does

- Runs multi-platform ad account audits with a weighted Ads Health Score.
- Reviews Google, Meta, YouTube, LinkedIn, TikTok, Microsoft, Apple, and Amazon Ads.
- Checks tracking, attribution, conversion setup, budget sufficiency, bidding strategy, creative fatigue, compliance, and landing-page quality.
- Helps agency operators work inside fixed client constraints when KPI, product positioning, pricing, or payment flow cannot be changed, especially install-heavy/pay-light, lead-heavy/low-quality, and low-CPI/poor-ROI accounts.
- Handles repetitive agency operations: daily patrols, anomaly triage, client replies, creative request briefs, report cleanup, changelogs, and weekly/monthly summaries.
- Generates strategic plans by business type, including SaaS, e-commerce, local service, B2B, finance, healthcare, mobile apps, and agencies.
- Produces campaign briefs, copy directions, creative prompts, PPC calculations, A/B test plans, and PDF audit reports.
- Defaults to Computer Use-assisted read-only dashboard inspection when the user is logged into an ad platform; it does not edit budgets, pause campaigns, or apply recommendations unless explicitly confirmed.
- Guides users through safe read-only access before inspecting live dashboards, and keeps reusable docs free of client-specific account details.
- Provides a dedicated Google App campaigns/UAC feasibility and experiment loop that proposes at most one reversible, single-variable test.
- Explicitly recommends waiting, collecting data, or making no change when measurement, maturity, permissions, or evidence block a valid action.

## UAC Campaign Level Quick Ops (v1.9.1)

Operators who do not code can ask naturally or use `/ads decide`. The default is one compact operation card—keep, create, parallel, move, wait, or roll back—not a full report or an automatically recorded experiment.

`AC2.0`, `AC2.5`, `AC3.0`, and their team-local variants are internal labels, not official Google product names and not tCPA values. Actual optimization events, bid strategies, and value settings override a conflicting project glossary. Without a glossary, Codex can continue with a labeled inference, but it must obtain mapping confirmation before a critical level switch.

### Example 1: choose a campaign level

```text
I am running AC2.5. Payment volume is low, but post-registration key actions are healthy. Should I open AC3.0 now?
```

```text
Conclusion: keep the current AC2.5 and do not open AC3.0 yet.

Payment-value volume and stability are not ready. Accumulate mature payment value and reconcile Google, MMP, and backend amounts first.
```

### Example 2: another campaign at the same level

```text
I have new assets while the existing AC2.5 is healthy. Should I open another AC2.5?
```

```text
Conclusion: add the assets to the existing AC2.5; do not open another one.

The event, geo, OS, and objective have not changed. A duplicate would fragment budget and deep-event volume.
```

### Example 3: parallel AC3.0 test

```text
Payment-value reporting is stable and budget is sufficient. Should I keep AC2.5?
```

```text
Conclusion: keep AC2.5 and run a small AC3.0 test in parallel.

Do not close AC2.5 directly. Validate mature ROAS and value volume first.
```

A new campaign is not the default and duplication is never recommended only to “restart learning.” AC3.0 requires payment/value, currency, deduplication, refund/subscription, value reconciliation, delay, volume, stability, and budget gates. Insufficient evidence produces an explicit hold, wait, or client-data request.

Source-checkout users can run:

```bash
python3 scripts/uac_experiment.py decide \
  skills/ads-google-app/assets/UAC-QUICK-OPS.example.yaml
```

See [`skills/ads-google-app/references/quick-ops.md`](skills/ads-google-app/references/quick-ops.md) for the detailed contract. Every live account write still requires exact human confirmation.

## UAC Experiment Loop (v1.9.1)

The `ads-google-app` route checks measurement reliability, learning
eligibility, optimization feasibility, and operator permissions before making
a recommendation. It can persist one human-reviewable experiment proposal with
a baseline, one variable, maturity conditions, guardrails, success, rollback,
and inconclusive rules.

Recommended minimum input: date range, campaign, OS, country, spend, installs,
registrations, deep events, payments/value, budget, bid target, creative
performance, permissions, recent changes, conversion delay, and Google Ads vs
MMP/backend reconciliation. Preserve asset group, device, optimization event,
asset, creative concept, cohort, and time-window grain when available.

Codex Ads cannot guarantee growth without data, replace product/paywall/SDK/MMP
work, optimize reliably toward an untrusted low-volume payment event, bypass
platform learning or permissions, or prove causality from one review.

For an operator who can change only budget, tCPA, and creative, use these nine steps:

1. Import or attach the account export with date range, campaign/OS/geo grain, spend, installs, registrations, payments, creative performance, recent changes, delay, and Google Ads/MMP/backend reconciliation.
2. Declare that budget, tCPA, and creative are executable, while product, paywall, SDK, MMP, backend events, and the store listing are protected.
3. Run the read-only Doctor so version, dependencies, input, ledger, schema, and unfinished experiments are checked before a decision.
4. Run the UAC analysis and review measurement reliability, learning eligibility, permissions, and optimization feasibility.
5. Decide the safe action: collect data, request client support, wait, make no change, or admit one experiment. Insufficient evidence stops the workflow before an account edit.
6. If admitted, display one unapproved single-variable draft without writing the ledger. Append a local `proposed` entry only after the user confirms that draft. Separately confirm and have a human execute the exact Google Ads edit before recording it as `observing`; preserve a declined proposal as `cancelled`.
7. Wait until minimum days, mature conversion volume, and conversion delay are all satisfied; do not stack a second variable.
8. Backfill guardrails, concurrent changes, metrics, and rule evaluation; validate and review the ledger, then choose WIN/LOSS/inconclusive, continue, stop, roll back, or extend observation.
9. Add the anonymized outcome to historical replay only when privacy review permits. Keep the learning account-specific by default and use a new, never-reused experiment ID for the next loop.

### Private workspace (recommended)

Real-account projects belong under the Git-ignored `workspaces/` tree, not as loose customer exports in the repository root. An ordinary operator can simply ask Codex to initialize a UAC project; these are the source-checkout commands Codex composes internally:

```bash
python3 scripts/uac_experiment.py init-workspace my-uac-project
# After putting one raw CSV/JSON/YAML summary in workspaces/my-uac-project/input/:
python3 scripts/uac_experiment.py normalize --workspace "workspaces/my-uac-project"
python3 scripts/uac_experiment.py doctor --workspace "workspaces/my-uac-project" --json
python3 scripts/uac_experiment.py analyze --workspace "workspaces/my-uac-project"
```

`normalize --workspace` always preserves `normalized/UAC-INPUT.draft.yaml` and `normalized/NORMALIZATION.json`. It creates the analyzable `normalized/UAC-INPUT.yaml` only when the strict input contract already passes. Otherwise the workflow stops so Codex can complete the contract from the envelope and user evidence; it must not analyze the draft. `analyze --workspace` writes analysis/report artifacts while explicitly leaving the ledger unchanged by default.

The explicit root paths below remain compatible for legacy projects and advanced automation. Relative paths are for a source checkout; one-line-install users can ask Codex to run the installed helper or use the `~/.codex/skills/` paths documented below.

```bash
cp skills/ads-google-app/assets/UAC-INPUT.example.yaml UAC-INPUT.yaml
cp skills/ads-google-app/assets/ADS-EXPERIMENTS.minimal.yaml ADS-EXPERIMENTS.yaml
python3 scripts/uac_experiment.py analyze UAC-INPUT.yaml \
  --ledger ADS-EXPERIMENTS.yaml \
  --json-output UAC-ANALYSIS.json \
  --markdown-output UAC-REPORT.md
```

The optional `--append-experiment` flag writes only an unapproved local
proposal. It never edits Google Ads. On Windows PowerShell, use `py -3` in
place of `python3`.

The helper auto-discovers one `ADS-EXPERIMENTS.yaml|yml|json` beside the input
or in the current directory; use `--ledger` when more than one exists. After
appending, validate and review the ledger:

```bash
python3 scripts/uac_experiment.py validate-ledger ADS-EXPERIMENTS.yaml
python3 scripts/uac_experiment.py review-ledger ADS-EXPERIMENTS.yaml
```

After a human executes the edit in Google Ads, set the local entry to
`observing`, record approval/execution time and the complete review snapshot,
and keep its result pending. Only after maturity, close it as `completed` or
`stopped` with metrics, evidence quality, one rule evaluation, a matching
decision outcome, and a next action. Cancel an unexecuted proposal without
deleting its audit history:

```bash
python3 scripts/uac_experiment.py cancel-proposal ADS-EXPERIMENTS.yaml UAC-2026-001 \
  --reason "Client declined this experiment." \
  --next-action "Wait for the next approved creative brief."
```

See `ADS-EXPERIMENTS.full.yaml` for the fill-in scaffold and
`ADS-EXPERIMENTS.example.yaml` for an observing example. These commands change
only the local ledger, never the ad account. Before the next loop, assign a new
`experiment_policy.id`; completed and cancelled IDs are never reused.

## v1.9.1 deterministic tools and migration

These are advanced, reproducible interfaces. An ordinary operator can ask Codex to run them and does not need to learn the commands or schema first. The commands below are for a source checkout. After a default one-line Codex install, the helper is at `~/.codex/skills/ads/scripts/uac_experiment.py`, its Python is at `~/.codex/skills/ads/.venv/bin/python`, and the UAC assets are under `~/.codex/skills/ads-google-app/assets/`. Verify the installed version through Doctor:

```bash
"$HOME/.codex/skills/ads/.venv/bin/python" \
  "$HOME/.codex/skills/ads/scripts/uac_experiment.py" doctor . --json
```

| Capability | Source-checkout command | Purpose and boundary |
| --- | --- | --- |
| Workspace | `python3 scripts/uac_experiment.py init-workspace <name>` | Creates an ignored private layout, minimal ledger, and data-gap prompt without writing live data in the repository root |
| Doctor | `python3 scripts/uac_experiment.py doctor --workspace workspaces/<name>` | Read-only version, dependency, input, ledger, schema, and unfinished-experiment checks; it changes no file or ad account |
| normalize | `python3 scripts/uac_experiment.py normalize --workspace workspaces/<name>` | Maps the single raw JSON/YAML or one-row CSV; creates analyze input only when the strict contract passes, otherwise preserves draft/envelope and stops |
| replay | `python3 scripts/uac_experiment.py replay examples/replays/example-anonymized` | Re-runs anonymized historical cases with the current rules and aggregates workflow diagnostics; it is retrospective evidence, not causality, a platform benchmark, or permission to edit an account |
| Router sync check | `python3 scripts/sync_skill_layout.py --check` | Source-maintainer command: checks canonical `skills/ads/` against legacy mirror `ads/`; `--write` synchronizes only from canonical to mirror |
| Knowledge Doctor | `python3 scripts/knowledge_doctor.py` | Source-maintainer command: checks source/freshness metadata; warnings are advisory by default, external links are not checked, and freshness does not prove account-level correctness |

Ledger schema `1.0` remains readable. v1.9.1 templates and newly created ledgers use `1.1`; the analysis-output schema remains `1.0`. Analyze, Quick Decision, append, review, and cancel never migrate a ledger implicitly. Migrate explicitly:

```bash
# 1. Preview JSON without writing
python3 scripts/uac_experiment.py migrate-ledger ADS-EXPERIMENTS.yaml

# 2a. Recommended: write a separate file first
python3 scripts/uac_experiment.py migrate-ledger ADS-EXPERIMENTS.yaml \
  --output ADS-EXPERIMENTS.v1.1.yaml

# 2b. Only after backup and review, replace the source atomically
python3 scripts/uac_experiment.py migrate-ledger ADS-EXPERIMENTS.yaml --write
```

The normalization output is an envelope containing `normalized`, `missing_fields`, `conversion_errors`, and source mapping. It is not automatically an executable experiment or a drop-in `analyze` input; evidence, permissions, maturity, and experiment rules still require review and completion.

## Install

Prefer a fixed version. After the `v1.9.1` tag is published, use this on Unix/macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/taotao135791-bit/codex-ads/v1.9.1/install.sh | bash -s -- --ref=v1.9.1
```

If you already cloned the repository, run this from the repo directory:

```bash
bash install.sh --ref=v1.9.1
```

Install to a custom location:

```bash
curl -fsSL https://raw.githubusercontent.com/taotao135791-bit/codex-ads/v1.9.1/install.sh | bash -s -- \
  --ref=v1.9.1 --target=codex \
  --skill-dir="$HOME/custom/skills" --agent-dir="$HOME/custom/agents"
```

Windows PowerShell, after the tag is published:

```powershell
irm https://raw.githubusercontent.com/taotao135791-bit/codex-ads/v1.9.1/install.ps1 -OutFile install.ps1
.\install.ps1 -Ref v1.9.1
```

`--ref` / `-Ref` accepts only a final `vX.Y.Z` tag, not a branch, commit, `main`, or prerelease. `main` is a rolling development snapshot and may be unstable. Use it only when you intentionally want the latest development state:

```bash
curl -fsSL https://raw.githubusercontent.com/taotao135791-bit/codex-ads/main/install.sh | bash
```

### Roll back to a known-good version

Reinstall a tag that actually exists and that you have already verified. This
repository does not yet have an older known-good release tag, so there is no
copy-paste rollback version today. After at least two versions are published,
replace `vX.Y.Z` below with an older tag that actually exists on the remote
**before** running the template:

```bash
KNOWN_GOOD=vX.Y.Z  # replace first; do not run literally
curl -fsSL "https://raw.githubusercontent.com/taotao135791-bit/codex-ads/${KNOWN_GOOD}/install.sh" | \
  bash -s -- --ref="${KNOWN_GOOD}"
```

Windows:

```powershell
$KnownGood = "vX.Y.Z" # replace first; do not run literally
irm "https://raw.githubusercontent.com/taotao135791-bit/codex-ads/$KnownGood/install.ps1" -OutFile install.ps1
.\install.ps1 -Ref $KnownGood
```

Reinstalling an older tag replaces files managed by the installer, but it does not promise to remove every extra file introduced by a newer version. It does not roll back Google Ads actions or downgrade ledger schema `1.1`. Preserve the original `1.0` ledger before migration and point an older tool at that backup; do not assume it can read `1.1`.

The default install paths are:

| Type | Path |
| --- | --- |
| Skills | `~/.codex/skills` |
| Agents | `~/.codex/agents` |
| Main skill | `~/.codex/skills/ads` |

## Quick Start

You do not need to memorize slash commands. Start Codex and paste a natural-language request:

```text
Review this ad account in read-only mode. Check budget pacing, conversion quality, goal setup, and next optimization actions. Do not change any settings.
```

See [Quick Start](QUICKSTART.en.md) for copy-paste prompts.

Codex Ads asks for business context before deep analysis: industry, monthly spend, primary goal, and active platforms. That context keeps benchmarks and priorities realistic.

For a junior operator taking over a new account, ask Codex Ads to start with
five questions: project type, final client KPI, what cannot be changed, the
current symptom, and what data is available.

## Optimizer Customization

Each optimizer can keep their own rules in `CODEX_ADS_OPTIMIZER.md`. Codex Ads reads it before analysis and uses the optimizer's judgment style, scaling rules, pause rules, creative preferences, and client reporting tone.

Example:

```text
Create a CODEX_ADS_OPTIMIZER.md file for my optimization style. My style is: check conversion goals first, then budget pacing, then geo and creative. Client updates should be direct but not overly aggressive.
```

## Routing Shorthand

Codex Ads is primarily triggered by natural-language requests. The `/ads ...`
items below are routing shorthand for Codex, not shell commands installed on
your machine. You can also say "read-only review this Google Ads account" or
"create today's client report from this template."

| Shorthand | Purpose |
| --- | --- |
| `/ads audit` | Full multi-platform audit |
| `/ads uac` | Google App campaigns/UAC feasibility and experiment loop |
| `/ads google` | Google Ads analysis |
| `/ads meta` | Meta Ads analysis |
| `/ads youtube` | YouTube Ads analysis |
| `/ads linkedin` | LinkedIn Ads analysis |
| `/ads tiktok` | TikTok Ads analysis |
| `/ads microsoft` | Microsoft Ads analysis |
| `/ads apple` | Apple Ads analysis |
| `/ads amazon` | Amazon Ads analysis |
| `/ads attribution` | Cross-platform attribution review |
| `/ads tracking` | Server-side tracking review |
| `/ads creative` | Creative quality and fatigue review |
| `/ads landing` | Landing-page conversion review |
| `/ads budget` | Budget allocation and bidding review |
| `/ads levers` | Agency constrained-scenario diagnosis |
| `/ads patrol` | Daily account patrol |
| `/ads anomaly` | Sudden metric-change triage |
| `/ads client-reply` | Client-safe explanations |
| `/ads creative-request` | Creative/design/video request briefs |
| `/ads clean-report` | Cleanup exported reports and normalize metrics |
| `/ads adapt-template` | Adapt arbitrary client report templates with field mapping |
| `/ads changelog` | Optimization change log |
| `/ads meeting` | Weekly/monthly meeting summary |
| `/ads plan <type>` | Strategic plan by business type |
| `/ads competitor` | Competitor ad research |
| `/ads math` | PPC calculator |
| `/ads test` | A/B test design |
| `/ads report` | PDF report generation |
| `/ads daily` | Guided daily performance report |
| `/ads creative-weekly` | Guided weekly creative performance report |
| `/ads dna <url>` | Brand DNA extraction |
| `/ads create` | Campaign concepts and copy briefs |
| `/ads generate` | AI ad image generation |
| `/ads photoshoot` | Product photography prompts |

## Repository Layout

```text
ads/                 Legacy/raw entry and reference files
skills/ads/          Codex plugin entry, kept in sync with ads/
skills/ads-*/        Platform and workflow sub-skills
agents/              Audit and creative agents
scripts/             Optional local Python utilities
tests/               Pytest coverage
evals/               Creative evaluation fixtures
.github/workflows/   Cross-platform CI
.codex-plugin/       Codex plugin metadata
```

## Local Utilities

Some workflows use Python helpers from `scripts/`. The installer creates a
local Codex skill venv at `~/.codex/skills/ads/.venv` instead of modifying
system Python. To install manually:

```bash
python3 -m venv ~/.codex/skills/ads/.venv
~/.codex/skills/ads/.venv/bin/python -m pip install -r ~/.codex/skills/ads/requirements.txt
```

Image generation is configured with `ADS_IMAGE_PROVIDER` and the matching provider key, such as `GOOGLE_API_KEY` or `OPENAI_API_KEY`.

## Test

```bash
pip3 install -r requirements-dev.txt
pytest -q
ruff check scripts tests
```

## Uninstall

```bash
bash uninstall.sh
```

Windows:

```powershell
.\uninstall.ps1
```

## License

MIT. See [LICENSE](LICENSE).
