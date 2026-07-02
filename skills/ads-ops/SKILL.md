---
name: ads-ops
description: "Daily agency advertising operations skill. Use for repetitive media-buying work such as daily account patrols, anomaly triage, client-safe replies, creative request briefs, report cleanup from CSV/XLSX exports, arbitrary client template adaptation, optimization changelogs, weekly/monthly meeting summaries, action tracking, and junior operator checklists. Triggers on patrol, daily check, anomaly, sudden drop, sudden spike, client reply, client explanation, creative request, design brief, material request, clean report, report cleanup, adapt template, template mapping, client-report-map, changelog, change history, weekly meeting, monthly review, and agency operations."
---

# Ads Ops: Daily Agency Operations

Use this sub-skill for repetitive agency work that is too small for a full
audit but too important to improvise: checking accounts, explaining changes,
turning problems into creative requests, cleaning exports, and preparing
meeting notes. Default to read-only account inspection and local file outputs.

## Computer Use First

For daily patrols, anomaly triage, creative performance review, changelog
review, template inspection, and any task that depends on the current ad
dashboard state, default to Computer Use-assisted read-only inspection when the
user is logged in or has opened the relevant page.

Before inspection:
- Ask the user to open the correct account, date range, and relevant table or
  template.
- State the read-only boundary.
- Do not click save, apply, pause, enable, edit, export, send, or write back
  unless the user confirms the exact action.

If Computer Use is unavailable or the user has not opened the dashboard, fall
back to exports, screenshots, pasted tables, local files, or read-only cloud
document inspection.

## Route by Intent

| User intent | Workflow |
| --- | --- |
| "每日巡检", "daily check", "patrol" | Daily Patrol |
| "突然掉量", "支付突然少了", "CPA 飙升", "anomaly" | Anomaly Triage |
| "怎么跟甲方说", "client reply", "客户解释" | Client Reply |
| "给设计提需求", "素材需求单", "creative request" | Creative Request |
| "清洗报表", "合并导出表", "clean CSV/XLSX" | Report Cleanup |
| "适配甲方模板", "template mapping", "adapt template" | Template Adapter |
| "记录今天改了什么", "change log" | Change Log |
| "周会/月会", "meeting summary", "复盘" | Meeting Summary |
| "记录项目背景", "记住甲方要求", "日报格式", "长期 KPI" | Project Memory Docs |

If the request involves install-heavy/pay-light, low-CPI/poor-ROI, or fixed
KPI/product constraints, combine this workflow with `ads-levers` thinking.

## Project Memory Docs

Purpose: preserve recurring client context without bloating the skill itself.
Use these files in the user's current project directory, not inside the skill
repo:

1. `ADS-PROJECT-CONTEXT.md` — long-term project background, business model,
   KPI, client constraints, current status, and daily-report expectations.
2. `ADS-OPS-LOG.md` — daily operations, reason for each action, observed
   results, review notes, and follow-up dates.
3. `ADS-REPORT-FORMAT.md` — fixed client daily/weekly report layout, required
   fields, formulas, data sources, and narrative rules.

Use templates from the `assets/` directory next to this `SKILL.md` when
creating new files. In a manual Codex install this is also
`~/.codex/skills/ads-ops/assets/`:

- `project-context-template.md`
- `ops-log-template.md`
- `report-format-template.md`

Workflow:
1. Before recurring daily/weekly work, check whether the three files exist.
2. If missing and useful, offer to create them from the templates.
3. Read them before patrols, reports, client replies, anomaly triage, and
   meeting summaries.
4. Update them only when the user asks, confirms a suggestion, or has enabled
   safe project-memory updates in their optimizer profile.
5. Keep reusable skill files anonymized. Ask before writing real client names,
   account IDs, campaign names, exact spend, exact CPA/ROAS, emails, phone
   numbers, payment details, backend cohort values, or private links into a
   project-local memory file.

When saving learned project context, separate durable facts from daily notes:

- Durable project facts -> `ADS-PROJECT-CONTEXT.md`
- Actions and review history -> `ADS-OPS-LOG.md`
- Report structure and formulas -> `ADS-REPORT-FORMAT.md`

## Daily Patrol

Purpose: catch the few things the operator must handle today.

Inspect or ask for:
- date range and timezone
- spend vs expected pacing
- conversions / payment / qualified lead vs recent baseline
- CPA, ROAS, CVR, CPI, CPL, or primary KPI
- delivery status, learning status, budget limited status
- disapprovals, rejected creatives, policy warnings
- tracking event status and sudden zeroes
- geo / device / placement / creative spend concentration

Output:
```markdown
# Daily Patrol

## Today Needs Attention
1.
2.
3.

## Normal
-

## Watchlist
-

## Do Not Touch Yet
-

## Suggested Next Checks
-
```

Rule: prioritize "what needs action today" over a full account essay.

## Anomaly Triage

Purpose: avoid panic edits. Diagnose before changing budgets, bids, or targets.

Sequence:
1. Confirm whether the anomaly is real: date range, timezone, data delay,
   attribution lag, backend / MMP / CRM comparison.
2. Check tracking: event firing, event deduplication, value/currency, status
   warnings, platform diagnostics.
3. Check delivery: budget exhausted, bid target too tight, learning reset,
   approval issue, audience size, billing issue.
4. Check mix shift: geo, device, placement, creative, keyword/query, campaign,
   product/ASIN, app version where relevant.
5. Check creative fatigue or rejection.
6. Check product/client-side incidents only after media-side checks are clear.

Output:
```markdown
# Anomaly Triage

## Symptom
-

## Most Likely Cause
-

## Checks Before Any Edit
1.
2.
3.

## Safe Actions
-

## Hold / Do Not Change
-

## Client Note
-
```

## Client Reply

Purpose: turn internal findings into client-safe language.

Generate one or more tones when useful:
- concise update
- direct but calm explanation
- risk escalation
- request for client-side data or approval

Rules:
- Do not blame product, tracking, or client team unless proven.
- Separate observed facts, calculated deltas, and inferred causes.
- State what the agency will do, what the client needs to provide, and what
  result would confirm or disprove the diagnosis.
- Avoid heavy platform jargon unless the client already uses it.

Default structure:
```markdown
## Client Reply

当前观察：

可能原因：

我们会做：

需要贵方配合：

预计验证时间：
```

## Creative Request

Purpose: convert performance gaps into briefs that design, editing, or UGC
production can execute.

Collect:
- platform and placement
- objective and KPI
- audience / geo / funnel stage
- losing angle and winning angle if known
- product or offer constraints
- required formats and safe zones
- proof points, claims, banned words, legal disclaimers

Output:
```markdown
# Creative Request

## Goal
-

## Required Assets
| Priority | Format | Platform | Angle | Hook | Visual Direction | Copy | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |

## Must Include
-

## Avoid
-

## Acceptance Check
-
```

For install-heavy/pay-light accounts, require at least one brief that
pre-filters purchase intent instead of maximizing install curiosity.

## Report Cleanup

Purpose: reduce copy-paste errors when working from exports.

For pasted tables, CSV, XLSX, or screenshots, normalize:
- Spend / Cost
- Impressions
- Clicks
- CTR
- CPC
- Installs / Registrations / Leads
- Payments / Purchases / Qualified Leads
- CVR by step
- CPA / CPI / CPL
- Revenue / Value
- ROAS

Workflow:
1. Identify platform and original column names.
2. Map fields to a normalized schema.
3. Recalculate derived metrics from raw fields when possible.
4. Flag missing columns and suspicious values.
5. Output a clean Markdown table, CSV-ready table, or Google Sheets-ready table.

Flag:
- spend with zero primary conversions
- high installs/leads with weak deep conversion
- impossible rates
- negative spend/revenue
- missing currency or timezone
- duplicate rows after export merging

## Template Adapter

Purpose: handle the reality that every client daily/weekly report template is
different. Do not force one report layout. Instead, map the template to a
standard internal data model, then fill a draft.

Workflow:
1. Inspect the template read-only through Computer Use, local file reading,
   pasted table, or screenshot.
2. Extract only the structure: sheet/tab names, section names, table columns,
   date fields, narrative blocks, formulas, required fields, and formatting
   constraints.
3. Build a field mapping from template labels to internal fields.
4. Identify missing inputs and whether they require platform export, backend,
   MMP, CRM, Shopify/app store, or client confirmation.
5. Fill a local draft by default. Ask before writing into any shared template.
6. Optionally save an anonymized `client-report-map.yaml` for future reuse.

Standard internal fields:
```text
date, platform, account_scope, campaign, ad_group_or_ad_set, creative_or_ad,
geo, device, spend, impressions, clicks, ctr, cpc, installs, registrations,
leads, qualified_leads, payments, purchases, revenue, value, cvr, cpa, cpi,
cpl, roas, budget_pacing, day_over_day_change, week_over_week_change,
risk_note, action, client_request
```

Mapping output:
```markdown
# Client Report Template Mapping

## Template Detected
- Type:
- Format:
- Date field:
- Main table:
- Narrative section:

## Field Mapping
| Template Field | Internal Field | Source | Formula | Required | Status |
| --- | --- | --- | --- | --- | --- |

## Missing Inputs
1.
2.
3.

## Fill Plan
1.
2.
3.
```

Quality checks:
- date range and timezone match the dashboard/export
- currency and units are consistent
- derived metrics use the correct denominator
- required template fields are filled or marked blocked
- backend-only metrics are not invented from platform data
- client-facing narrative does not include internal blame or private notes

## Change Log

Purpose: make optimization history reviewable and protect the operator from
"what changed?" confusion.

If `ADS-OPS-LOG.md` exists, append the change there instead of creating a
separate one-off changelog, unless the user asks for a standalone file.

Record:
- date and timezone
- platform / account / campaign / ad set / ad / keyword
- action
- reason
- expected effect
- risk
- follow-up date
- result after review

Output:
```markdown
# Ads Change Log

| Date | Platform | Object | Action | Reason | Expected Effect | Risk | Follow-up |
| --- | --- | --- | --- | --- | --- | --- | --- |
```

If reading platform change history, stay read-only and do not expose account
IDs or sensitive names in reusable files.

## Meeting Summary

Purpose: turn daily reports, creative reports, patrol notes, and changelogs
into a weekly or monthly update.

Output:
```markdown
# Weekly / Monthly Ads Review

## Executive Summary
-

## What Changed
-

## What Worked
-

## What Did Not Work
-

## Tests Completed
-

## Next Week / Month Plan
-

## Client Decisions Needed
-

## Internal Operator Notes
-
```

For client versions, remove internal blame, raw uncertainty, and private
operator notes. For internal versions, preserve risks and exact next actions.

## Safety

- Stay read-only in ad platforms unless the user explicitly confirms an exact
  edit.
- Ask before writing into cloud docs, shared spreadsheets, or client templates.
- Keep client-specific IDs, names, emails, and exact live metrics out of skill
  files and reusable examples.
- When unsure whether an action is safe, produce a recommendation and wait for
  confirmation instead of clicking.
