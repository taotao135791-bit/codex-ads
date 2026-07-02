---
name: ads
description: >-
  Route paid advertising work: 广告账户审计, 只读看后台, 日报/周报, 甲方模板, 每日巡检, 客户回复, 素材需求,
  Google/Meta/TikTok, KPI受限诊断.
---

# Ads Router

Codex Ads is a router for paid-media work. Keep this file lean: route the task,
load only the needed sub-skill, and use references on demand.

## Always Do First

1. Read optimizer profile files in the current working directory if present:
   `CODEX_ADS_OPTIMIZER.md`, `optimizer-profile.md`, or
   `.codex-ads-optimizer.md`.
2. Stay read-only in ad platforms unless the user confirms an exact edit.
3. Keep real account names, IDs, campaign names, emails, payment details, and
   live metrics out of reusable skill files, examples, tests, and templates.
4. For live dashboard work, load `references/computer-use-live-audit.md`.
5. For global protocols, quality gates, and style learning details, load
   `references/orchestrator.md`.

## Live Dashboard Tool Gate

For logged-in ad platforms, analytics dashboards, MMP dashboards, client report
templates opened in a browser, or any page containing private account data:

- MUST use Computer Use for live UI inspection.
- MUST NOT use Browser Plugin, in-app browser automation, Playwright,
  screenshot scripts, page HTML extraction, or network scraping.
- MUST NOT take screenshots of private dashboards unless the user explicitly
  asks for a current-work deliverable that requires screenshots.
- If Computer Use is unavailable, ask for exports, pasted tables, or
  user-provided screenshots instead of switching to Browser Plugin.
- Browser/Playwright tools are allowed only for public landing pages, public
  brand sites, or local files that do not contain logged-in account data.

## Path Resolution

This router may run from a manual Codex install or from a plugin/source tree.

- Manual install: router at `~/.codex/skills/ads/SKILL.md`, sub-skills at
  `~/.codex/skills/ads-*/SKILL.md`.
- Plugin/source layout: router at `skills/ads/SKILL.md`, sub-skills as sibling
  directories under `skills/`.
- When the route table says load `ads-google`, read that sub-skill's `SKILL.md`
  from the first existing path: `~/.codex/skills/ads-google/SKILL.md`,
  `../ads-google/SKILL.md`, or `../skills/ads-google/SKILL.md`.

## Natural Language Routing

Users do not need slash commands. Treat natural-language requests such as
"只读看一下这个广告账户", "帮我出日报", "按甲方模板做素材周报",
"安装很多支付很少但 KPI 不能改", "帮我做每日巡检", "整理素材需求单",
"适配这个甲方日报模板", "review this Google Ads account", or
"prepare a client update" as valid Ads skill invocations.

## Route Table

| User intent | Load this sub-skill |
| --- | --- |
| full audit, account health, PPC audit | `ads-audit` |
| Google Ads, Search, PMax, AI Max, broad match | `ads-google` |
| Meta, Facebook, Instagram, Threads, Advantage+ | `ads-meta` |
| YouTube, Demand Gen, Shorts, CTV | `ads-youtube` |
| LinkedIn, B2B ads, Lead Gen Forms, ABM | `ads-linkedin` |
| TikTok, Spark Ads, Smart+, TikTok Shop | `ads-tiktok` |
| Microsoft Ads, Bing, Copilot ads | `ads-microsoft` |
| Apple Ads / ASA / iOS app ads | `ads-apple` |
| Amazon Ads, Sponsored Products, ACOS/TACOS | `ads-amazon` |
| attribution, GA4, MMP, AdAttributionKit | `ads-attribution` |
| server-side tracking, sGTM, CAPI, dedup | `ads-server-side-tracking` |
| creative audit, fatigue, copy/design review | `ads-creative` |
| landing page, CRO, post-click experience | `ads-landing` |
| budget allocation, bidding, scale/kill | `ads-budget` |
| KPI/product fixed, install-heavy/pay-light | `ads-levers` |
| patrol, anomaly, client reply, changelog | `ads-ops` |
| daily report, weekly creative report, template | `ads-report` |
| strategic media plan | `ads-plan` |
| competitor ads / ad library research | `ads-competitor` |
| CPA, ROAS, LTV:CAC, forecast math | `ads-math` |
| A/B test design and sample size | `ads-test` |
| brand DNA extraction | `ads-dna` |
| campaign brief / copy concepts | `ads-create` |
| AI image generation | `ads-generate` |
| product photography generation | `ads-photoshoot` |

When a request spans multiple rows, load the narrowest primary sub-skill first,
then load supporting sub-skills only when needed.

## New Operator Intake

For broad first-time requests like "我刚接了一个项目", "帮我看看这个账户",
"不知道从哪里下手", or "first time reviewing this account", ask five things
in one concise message if they are not already provided:

1. Project type
2. Final KPI the client judges
3. What cannot be changed
4. Current symptom
5. Available data

Then route:
- Constraint/KPI/product boundary problems -> `ads-levers`
- Daily operations or client communication -> `ads-ops`
- Platform diagnosis -> the relevant platform sub-skill
- Reporting/template work -> `ads-report`

## Project Memory

For repetitive client work, use `ads-ops` to create or update three local
working documents in the current project directory:

1. `ADS-PROJECT-CONTEXT.md` for long-term background, KPI, client requirements,
   current status, and daily-report expectations.
2. `ADS-OPS-LOG.md` for daily actions, reasons, observed results, and review.
3. `ADS-REPORT-FORMAT.md` for fixed client daily/weekly report formats.

Use the first existing template directory: `~/.codex/skills/ads-ops/assets/`,
`../ads-ops/assets/`, or `../skills/ads-ops/assets/`. Ask before storing real
client identifiers; anonymize by default.

## Style Learning

Optimizer profiles may include:

```yaml
style_learning_mode: suggest_only
# off | suggest_only | auto_append_anonymized
```

Manual rules win over learned rules. In `suggest_only`, propose generalized
learned style rules and ask before writing. In `auto_append_anonymized`, append
only anonymized, generalized behavior rules to a learned-rules section. Never
store real client names, account IDs, campaign names, ad names, exact spend,
exact CPA/ROAS, emails, phone numbers, payment details, screenshots, URLs with
tokens, or backend cohort values.

## Non-Negotiable Gates

- Google: do not make pause/scale/geo recommendations from country totals
  alone; break results back to campaign, bid strategy, ad group / asset group,
  device, conversion action, and geo.
- Learning phase: do not recommend disruptive edits during active learning.
- Tracking: verify conversion tracking and attribution before optimization.
- Compliance: check special categories for housing, employment, credit,
  finance, healthcare, and other regulated verticals.
- Reporting: separate observed facts, calculated metrics, and inferences.
