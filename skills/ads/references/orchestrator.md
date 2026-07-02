# Ads Orchestrator Reference

Load this file when the main `ads` router needs global protocols, safety gates,
style-learning behavior, or cross-skill orchestration. Do not load every
platform reference up front.

## Live Data Protocol

Default to Computer Use-assisted read-only analysis when the user is logged in
or asks you to inspect an ad dashboard. Before live inspection:

1. Ask the user to open the correct account and date range.
2. State the read-only boundary.
3. Load `references/computer-use-live-audit.md`.
4. Separate `Observed`, `Calculated`, and `Inference` in reports.

Never create, edit, pause, enable, delete, apply recommendations, change
budgets, change bids, submit forms, or save settings unless the user confirms
that exact action.

For logged-in ad platforms, analytics dashboards, MMP dashboards, client report
templates opened in a browser, or any page containing private account data,
MUST use Computer Use for live UI inspection. MUST NOT use Browser Plugin,
in-app browser automation, Playwright, screenshot scripts, page HTML extraction,
or network scraping. If Computer Use is unavailable, ask for exports, pasted
tables, or user-provided screenshots instead of switching to Browser Plugin.
Browser/Playwright tools are allowed only for public landing pages, public
brand sites, or local files that do not contain logged-in account data.

If live UI access is unavailable, use exports, pasted metrics, user-provided
screenshots, local files, or read-only MCP/API data.

## Optimizer Profiles

Before audit, reporting, budget, creative, or client-summary work, look for:

- `CODEX_ADS_OPTIMIZER.md`
- `optimizer-profile.md`
- `.codex-ads-optimizer.md`

Use the profile for KPI priorities, kill/scale rules, account-reading order,
risk tolerance, creative heuristics, and client tone. Profiles guide judgment
but never override safety, privacy, platform policy, or read-only boundaries.

## Experience-Based Style Learning

The profile may contain:

```yaml
style_learning_mode: suggest_only
# off | suggest_only | auto_append_anonymized
```

Modes:

- `off`: Do not propose or write learned style rules.
- `suggest_only`: Default. When the user corrects the analysis or says a
  preference should be remembered, propose a generalized learned rule and ask
  before writing it.
- `auto_append_anonymized`: Only when explicitly configured. Append generalized
  rules to a learned-rules section without another prompt.

Rules:

- Manual rules have higher priority than learned rules.
- Do not overwrite the manual section unless the user asks for that edit.
- Put learned rules under `## Learned Style Rules` or
  `## 从使用经验学习到的偏好`.
- In `suggest_only`, use `### Pending Suggestions`.
- In `auto_append_anonymized`, write only anonymized, generalized rules.
- Never store real client names, account IDs, campaign names, ad names, exact
  spend, exact CPA/ROAS, emails, phone numbers, payment details, screenshots,
  URLs with tokens, or backend cohort values.
- Do not turn one ambiguous case into a permanent rule. Include conditions and
  assumptions.

Suggested profile structure:

```markdown
## Manual Optimizer Rules

## Style Learning Settings

style_learning_mode: suggest_only

## Learned Style Rules

### Pending Suggestions

### Accepted Learned Rules

### Rejected Learned Rules
```

## Agency Constraint Mode

When KPI, product, price, paywall, roadmap, or business direction cannot be
changed, route to `ads-levers`.

Separate:

- Uncontrollable: product positioning, features, pricing, paywall, KPI
  definition, business model, release cadence.
- Partly influenceable: landing/store copy, event setup, offer framing,
  funnel evidence, CRM/backend/MMP data access.
- Controllable by media buying: platform mix, geo, budget, bid strategy,
  optimization event, campaign/ad group/asset group structure, audience,
  placement, creative angle, copy, exclusions, remarketing, test cadence,
  reporting narrative.

Do not celebrate shallow metrics when the KPI is deeper. Low CPI is not good
when payment quality is poor; low CPL is not good when valid-lead quality is
poor.

## Context Intake

For audits and analysis, collect or infer:

1. Industry / business type
2. Monthly ad spend and platform split
3. Primary goal
4. Active platforms

Use this context to choose benchmarks, evaluate budget sufficiency, and
calibrate severity.

## Quality Gates

- Never recommend Google Broad Match without Smart Bidding.
- Google geo recommendations must break country totals back to learning units.
- Flag ad groups/campaigns above 3x target CPA for investigation or pause.
- Respect platform learning phases.
- Always check tracking stack before optimization recommendations.
- Always check compliance for regulated or special-category verticals.
- For TikTok, do not recommend silent video ads as a primary approach.
- For client reports, separate observed facts, calculations, inferences, risks,
  actions, and requests.

## Full Audit Orchestration

For `/ads audit`:

1. Collect context.
2. Collect account data. Prefer read-only live UI if available.
3. Detect business type and active platforms.
4. Use subagents if available: `audit-google`, `audit-meta`, `audit-creative`,
   `audit-tracking`, `audit-budget`, `audit-compliance`.
5. Validate each result before aggregation.
6. Produce platform scores, aggregate health score, critical issues, and quick
   wins.

Wave 2 standalone skills: `ads-amazon`, `ads-attribution`,
`ads-server-side-tracking`.

## Creative Workflow

Sequential pipeline:

1. `ads-dna` -> `brand-profile.json`
2. `ads-create` -> `campaign-brief.md`
3. `ads-generate` -> `ad-assets/`
4. `ads-photoshoot` -> standalone or profile-driven product shots

Use provider setup from `references/image-providers.md`.

## Project Memory Docs

For recurring client operations, use `ads-ops` and create or update:

- `ADS-PROJECT-CONTEXT.md`
- `ADS-OPS-LOG.md`
- `ADS-REPORT-FORMAT.md`

These are project-local working files. Do not put real client details into
reusable skill docs or tests. Ask before writing sensitive identifiers into a
private project file.
