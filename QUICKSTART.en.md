# Codex Ads Quick Start

Codex Ads is a Codex-first advertising decision workflow. **You do not need slash commands or YAML first.** Give Codex an export, pasted table, screenshot, or read-only dashboard, then use one natural-language prompt below.

## Install the stable channel first

The `v1.9.0` tag must be published before this command becomes available. After publication, pin that version:

```bash
curl -fsSL https://raw.githubusercontent.com/taotao135791-bit/codex-ads/v1.9.0/install.sh | bash -s -- --ref=v1.9.0
```

Windows:

```powershell
irm https://raw.githubusercontent.com/taotao135791-bit/codex-ads/v1.9.0/install.ps1 -OutFile install.ps1
.\install.ps1 -Ref v1.9.0
```

`main` is a rolling development snapshot and may be unstable; it is not the default stable channel. To roll back, reinstall an older tag that actually exists and has been verified. That does not undo ad-account actions or downgrade ledger schema `1.1`, so preserve a `1.0` backup before migration. See the [README](README.en.md#install) for complete install and rollback commands.

## First Use

Start Codex and say:

```text
I want to use Codex Ads for ad optimization. Default to read-only account review. Do not change ad platform settings. If I ask for daily reports, weekly creative reports, or client updates, ask where the client template is first.
```

If the ad dashboard is already open:

```text
I am logged into the ad dashboard. Please review the current account in read-only mode. Tell me which pages you need to inspect first, and do not change any settings.
```

## Keep these boundaries in mind

The natural-language path includes Agent reasoning: Codex understands context, organizes evidence, and asks for missing information. Doctor, normalize, UAC rules, ledger validation, migration, and replay are local deterministic capabilities. They call neither ad nor model APIs and do not change the platform.

- They do not guarantee growth, lower CPA, or higher ROAS.
- They do not replace product, paywall, SDK/tracking, MMP, or backend event work.
- They do not auto-login or change an account; a real write requires confirmation of that exact action.
- Fixtures and public replays are synthetic/anonymized regression samples, not proof of real-world effect.
- Single-account learning is not global by default. When evidence is insufficient, the correct recommendation may be to make no account change.

## Everyday prompts

New operator intake:

```text
I just took over a new agency account and do not know where to start. Ask me five questions first: project type, final client KPI, what cannot be changed, current symptom, and what data I can provide.
```

Account check:

```text
Review this ad account in read-only mode. Check budget pacing, conversion quality, goal setup, and next optimization actions. Do not change any settings.
```

Constrained agency diagnosis:

```text
We are the agency, and the KPI and product direction cannot change. Installs are high but payments are low. Review in read-only mode and tell me which media-buying levers we can still control, what needs client-side validation, and how to explain this to the client.
```

Daily patrol:

```text
Review yesterday's data in read-only mode and tell me the 3 things I must handle today. Check spend, payments/leads, CPA/ROAS, rejected creatives, tracking issues, and geo/device/placement anomalies.
```

Google Ads deep dive:

```text
Review the current Google Ads account in read-only mode. Focus on conversion goals, campaign structure, budget pacing, geo/device/creative performance, then give me an internal action list and a client-facing explanation.
```

Google UAC experiment loop:

```text
This is a Google App campaign. I can change only budget, bid target, and
creative—not product, paywall, SDK, MMP, backend events, or store listing.
Check payment measurement, learning eligibility, and conversion delay before
deciding whether optimization is possible. If evidence is sufficient, propose
one single-variable experiment; otherwise tell me what data to collect, how
long to wait, and what not to touch.
```

You do not need to memorize commands for a UAC project. Say these five things as the work progresses:

```text
1. Initialize a project for this UAC account.
2. Analyze this week's UAC data and tell me whether to make a change. (Attach the data.)
3. Create one experiment draft from this analysis.
4. At <exact time and timezone> today I made <actual change>, with <no/these other changes>. Record it.
5. Review the current experiment. (Attach the latest data at the same grain.)
```

Codex keeps live material in a private, ignored workspace and handles field mapping, Doctor, analysis, and ledger validation internally. Step 3 displays a draft first and does not write the ledger until you confirm that draft. A local ledger write is not permission to edit Google Ads; a live account action requires a second, exact confirmation.

Daily report:

```text
Prepare today's daily report using the client template. I have opened the ad dashboard and the template. Read the template structure and generate the report; do not write back, edit, or send anything.
```

Client template adaptation:

```text
This client's daily report template is different from other clients. Read the template structure in read-only mode, generate a field mapping first, mark which fields come from the ad dashboard and which require backend/MMP/CRM data, then produce a paste-ready draft.
```

Weekly creative report:

```text
Review this week's creative performance using the client creative weekly template. Tell me what to keep, reduce, stop, what is fatigued, and what new creative we should produce next week.
```

Creative request:

```text
Based on this week's creative performance, prepare next week's request brief for design/video production. Include goal, platform, size, angle, visual direction, copy, and acceptance criteria for each asset.
```

Client update:

```text
Turn the optimization findings into a client-facing update. Use less platform jargon and explain the cause, risk, next action, and expected impact.
```

Anomaly triage:

```text
Payments/leads suddenly dropped. Before recommending budget changes, triage data delay, tracking, approvals, delivery, geo/placement/creative mix, and possible client-side issues.
```

## Budget, tCPA, and creative only: the 9-step loop

1. **Import:** Attach an export or paste data with dates, campaign/OS/geo grain, shallow-to-payment metrics, creative performance, recent changes, conversion delay, and reconciliation status.
2. **Declare permissions:** State that only budget, tCPA, and creative are executable. Mark product, paywall, SDK, MMP, backend events, and store listing as protected.
3. **Doctor:** Ask Codex to run the read-only Doctor before a decision so version, dependencies, input, ledger, schema, and unfinished experiments are checked.
4. **Analyze:** Run the UAC analysis and review measurement, learning eligibility, permissions, and optimization feasibility.
5. **Choose the safe action:** Enter an experiment only when evidence and maturity pass admission. Otherwise collect data, request client support, wait, or make no account change.
6. **Create and confirm:** Display one unapproved single-variable draft without writing the ledger. Append a local `proposed` entry only after the user confirms that draft. This never changes Google Ads; a human separately approves and executes the platform edit before the entry becomes `observing`, while a declined proposal becomes `cancelled`.
7. **Wait for maturity:** Wait for minimum observation days, mature conversion volume, and conversion delay. Do not stack a second variable.
8. **Backfill and review:** Enter guardrails, concurrent changes, mature metrics, and rule evaluation; run `validate-ledger` and `review-ledger`, then continue, stop, roll back, or extend observation.
9. **Add historical replay:** Save an anonymized case only after privacy review. Replay evaluates the workflow, not real-world effect; use an experiment ID that has never appeared in the ledger for the next loop.

## Advanced: deterministic checks and schema 1.1

Ordinary users can ask Codex to run these tools. The commands below are for a source checkout; after a one-line install, the helper is under `~/.codex/skills/ads/scripts/`, not the current project.

```bash
# Create an ignored private project; then put the raw summary in its input/
python3 scripts/uac_experiment.py init-workspace my-uac-project
python3 scripts/uac_experiment.py normalize --workspace "workspaces/my-uac-project"

# Read-only project health and analysis; analysis leaves the ledger unchanged
python3 scripts/uac_experiment.py doctor --workspace "workspaces/my-uac-project"
python3 scripts/uac_experiment.py analyze --workspace "workspaces/my-uac-project"

# Legacy explicit paths remain compatible: map object JSON/YAML or one CSV row
python3 scripts/uac_experiment.py normalize UAC-SUMMARY.csv --output UAC-NORMALIZED.yaml

# Replay an anonymized historical case; not causal or real-effect proof
python3 scripts/uac_experiment.py replay examples/replays/example-anonymized --json

# Ledger 1.0 → 1.1: preview first, then write a separate file
python3 scripts/uac_experiment.py migrate-ledger ADS-EXPERIMENTS.yaml
python3 scripts/uac_experiment.py migrate-ledger ADS-EXPERIMENTS.yaml \
  --output ADS-EXPERIMENTS.v1.1.yaml
```

Workspace normalization always writes a draft and `NORMALIZATION.json`; it creates `normalized/UAC-INPUT.yaml` only when the strict contract passes. Otherwise the workflow stops and must not analyze the draft. Ledger `1.0` remains readable, new templates use `1.1`, and analysis output remains `1.0`. Analyze, append, review, and cancel do not migrate implicitly; use `migrate-ledger --write` only after backup and review.

`python3 scripts/sync_skill_layout.py --check` and `python3 scripts/knowledge_doctor.py` are source-maintainer commands. The former checks the canonical router against its legacy mirror; the latter checks knowledge-freshness metadata. Neither proves that a platform rule is correct for a particular account.

## Guided Access

Before live account review:

```text
1. Open the ad dashboard yourself and log in.
2. Switch to the correct account.
3. Set the date range, such as yesterday, last 7 days, last 30 days, this week, or this month.
4. If you need a daily or weekly report, open the client template or provide its path/link/file keyword.
5. Tell Codex: read-only review, do not change settings.
```

Codex Ads may read:

- overview, campaign tables, creative tables, conversion goals, diagnostics, recommendations, geo/device/network/creative breakdowns
- client template structure, fields, date format, and table layout

Codex Ads will not:

- change budgets, bids, goals, campaign status, recommendations, or saved settings
- send reports
- persist real account names, account IDs, campaign names, emails, or billing data into repository files

## Optimizer Customization

Each optimizer can keep their own judgment rules in:

```text
CODEX_ADS_OPTIMIZER.md
```

Ask Codex to create one:

```text
Create a CODEX_ADS_OPTIMIZER.md file for my optimization style. My style is: check conversion goals first, then budget pacing, then geo and creative. Client updates should be direct but not overly aggressive.
```

Or turn your existing experience into a profile:

```text
Turn the following optimization experience into CODEX_ADS_OPTIMIZER.md. In future account reviews, use these rules before making recommendations.
```

Useful sections:

- core KPIs
- when to scale budget
- when to reduce budget or pause
- how to judge geo, device, creative, and conversion goals
- client reporting tone
- recommendations you dislike
- daily/weekly report format

## Optimizer Profile Template

```markdown
# Codex Ads Optimizer Profile

## My Optimization Style
- 

## Priority Order
1. Conversion goals and tracking
2. Budget pacing and CPA/ROAS
3. Geo, device, network, audience
4. Creative and landing page

## Scaling Rules
- 

## Reduction / Pause Rules
- 

## Creative Judgment
- 

## Client Reporting Tone
- 

## Things Codex Should Not Do
- 
```
