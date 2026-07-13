<p align="center">
  <img src="assets/logo.svg" alt="Codex Ads logo" width="100%">
</p>

# Codex Ads

Codex Ads is a local Codex skill bundle for paid advertising audits, optimization plans, creative review, attribution checks, PPC math, and client-ready reports.

It helps marketers and operators inspect Google, Meta, YouTube, LinkedIn, TikTok, Microsoft, Apple, and Amazon Ads using structured checklists, scoring rules, platform benchmarks, and practical next actions.

[中文说明](README.md) · [Quick Start](QUICKSTART.en.md)

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

## UAC Experiment Loop (v1.8)

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

Quick workflow: provide data and permissions; run the UAC audit; review the
feasibility state; generate at most one experiment; approve and execute it
manually; wait for declared maturity; enter the result; then continue, stop,
or roll back.

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

## Install

One-line install for Codex from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/taotao135791-bit/codex-ads/main/install.sh | bash
```

If you already cloned the repository, run this from the repo directory:

```bash
bash install.sh
```

Install to a custom location:

```bash
curl -fsSL https://raw.githubusercontent.com/taotao135791-bit/codex-ads/main/install.sh | bash -s -- --target=codex --skill-dir="$HOME/custom/skills" --agent-dir="$HOME/custom/agents"
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/taotao135791-bit/codex-ads/main/install.ps1 -OutFile install.ps1
.\install.ps1
```

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
