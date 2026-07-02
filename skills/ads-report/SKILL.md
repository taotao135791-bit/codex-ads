---
name: ads-report
description: >-
  Guided reporting workflow for paid advertising. Exports daily performance reports,
  weekly creative reports, client-ready summaries, and adapts arbitrary client report
  templates using Computer Use read-only dashboard/template inspection plus user-provided
  files. Use when user says daily report, export daily report, 日报, weekly creative report,
  素材周报, client template, report template, 甲方模板, adapt template, template mapping,
  client-report-map, or reporting.
---

# Ads Report: Guided Daily and Creative Weekly Reporting

## Reference Resolution

For any `ads/references/<file>.md` path below, read the first existing path:
`~/.codex/skills/ads/references/<file>.md`, `../ads/references/<file>.md`,
`../skills/ads/references/<file>.md`, then `ads/references/<file>.md`.

Creates repeatable client-facing reports from live ad platform data, exports,
screenshots, pasted metrics, or templates. Default mode is Computer Use-assisted
read-only inspection when the user is logged in.

## Routing Shorthand

These `/ads ...` entries are Codex routing shorthand, not shell commands.

| Shorthand | What it does |
| --- | --- |
| `/ads report` | General report or PDF audit report |
| `/ads daily` | Daily performance report/export |
| `/ads creative-weekly` | Weekly creative performance report |
| `/ads adapt-template` | Read a client template and generate a field mapping before filling |

## Guided Access First

Before live collection, read `ads/references/computer-use-live-audit.md` and
use this short guided access prompt:

```text
请你自己打开广告后台并登录，切到要导出日报/素材周报的账号。
请设置好日期范围，并打开甲方模板或告诉我模板位置。
我只做只读检查：读取数据、识别模板结构、整理报告。
我不会修改广告账户、不会保存后台设置、不会私自发送报告给甲方。
```

If the user has already opened the dashboard and explicitly authorized read-only
inspection, proceed without repeating the full prompt.

## Client Template Discovery

When the user says "按甲方模板", "你自己去找模板", or similar:

1. Ask the user to provide one of these safe entry points:
   - local file path
   - open browser tab
   - Google Drive / Docs / Sheets link
   - folder name or filename keyword
   - screenshot of the template
2. Inspect the template read-only.
3. Extract only structure and formatting requirements:
   - section names
   - metric columns
   - date format
   - naming conventions
   - chart/table layout
   - required narrative tone
4. Do not copy client-identifying content into reusable repo files.
5. Ask before writing into any cloud doc, spreadsheet, or shared file.

If no template is found or opened, use the default report structures below and
label the output as "default template".

## Client Template Adapter

Do not assume client report templates share one format. Standardize the
workflow, not the template. Every template-based report uses this flow:

1. **Inspect template read-only**: local XLSX/CSV, Google Sheet, Google Doc,
   open browser tab, or screenshot. Extract structure only.
2. **Map fields to the Ads standard data model**.
3. **Identify missing inputs** before filling.
4. **Fill a local draft** by default: Markdown table, CSV-ready table, or
   Google Sheets-ready table. Ask before writing into a cloud/shared template.
5. **Quality check**: dates, timezone, currency, formulas, required fields,
   missing backend/MMP/CRM metrics, and client-facing tone.

### Standard Data Model

Use these internal fields as the stable layer between changing client templates
and changing platform exports:

```text
date
platform
account_scope
campaign
ad_group_or_ad_set
creative_or_ad
geo
device
spend
impressions
clicks
ctr
cpc
installs
registrations
leads
qualified_leads
payments
purchases
revenue
value
cvr
cpa
cpi
cpl
roas
budget_pacing
day_over_day_change
week_over_week_change
risk_note
action
client_request
```

### Mapping Output

Always produce a mapping before filling an unfamiliar template:

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

### Persistent Private Mapping

If the user wants daily reuse, create or update `client-report-map.yaml` in the
current project directory. Use anonymized identifiers by default:

```yaml
client: anonymized-client-a
template_type: daily
date_format: YYYY-MM-DD
currency: USD
fields:
  消耗: spend
  展示: impressions
  点击: clicks
  激活: installs
  付费人数: payments
  付费成本: spend / payments
narrative:
  今日情况: executive_snapshot
  问题和动作: risk_and_action
required_external_inputs:
  - backend_payments
  - backend_revenue
```

Never store real client names, account IDs, campaign names, emails, or exact
live-account metrics in reusable template maps unless the user explicitly asks
for a private working file that requires them.

If `client-report-map.yaml` exists, read it first and use it as the suggested
mapping. If the current template structure changed, produce a diff-like note
and ask before updating the map.

## Daily Report Workflow

Collect:
- date range and timezone
- account/platform/campaign/ad group or asset group scope
- spend, impressions, clicks, CTR, CPC, conversions, CPA, revenue/value, ROAS
- high-value conversion metric if different from platform "Conversions"
- daily delta vs previous day or same weekday last week
- pacing: budget used, remaining budget, limited-by-budget warnings
- anomalies: spend spike/drop, CPA spike, tracking issue, approval issue
- actions taken or recommended next actions
- any existing `client-report-map.yaml` mapping if filling a known client
  template

For Google Ads, do not summarize performance by country alone. If a geo note is
included, show the campaign and ad group / asset group that drove the result, or
mark the geo conclusion as insufficiently diagnosed.

Default daily report structure:

```markdown
# Daily Ads Report

**Date:**
**Scope:**
**Objective:**

## Executive Snapshot
- Spend:
- Primary KPI:
- Efficiency:
- Main change:

## Platform / Campaign Table
| Platform | Campaign | Ad Group / Asset Group | Geo | Spend | Clicks | Conversions | Primary KPI | CPA/ROAS | Note |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |

## Key Changes
- Observed:
- Calculated:
- Inference:

## Risks
- Tracking:
- Budget:
- Delivery:
- Creative:

## Next Actions
1.
2.
3.
```

## Weekly Creative Report Workflow

Collect:
- date range and platform scope
- creative/ad/asset names or anonymized labels
- spend, impressions, clicks, CTR, CPC, conversions, CPA, CVR, value/ROAS
- video metrics when available: hook rate, 3s/ThruPlay/view rate, completion,
  hold rate, thumb-stop, watch time
- fatigue signals: CTR decline, CPA rise, frequency, creative age, spend with
  no high-value conversion
- winning angles, losing angles, format gaps, next production list

Default weekly creative report structure:

```markdown
# Weekly Creative Report

**Week:**
**Scope:**
**Objective:**

## Summary
- Winning angle:
- Weak angle:
- Fatigue signal:
- Next creative priority:

## Creative Leaderboard
| Rank | Creative | Angle | Format | Spend | CTR | CVR | Primary KPI | CPA/ROAS | Decision |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |

## Creative Diagnostics
- Hook:
- Message:
- Audience fit:
- Offer clarity:
- Landing-page match:

## Production Plan
1.
2.
3.
```

## Safety and Privacy

- Keep live account data in the current report only.
- Do not save real account names, account IDs, campaign names, ad names, client
  names, emails, or exact live-account metrics into skill files, README,
  examples, tests, or templates.
- Use anonymized labels in reusable examples: `Client A`, `Campaign A`,
  `Creative 01`, `Purchase`, `Qualified Lead`.
- Never send, share, upload, overwrite, or edit cloud reports without explicit
  action-time confirmation.
- If the user asks for a file output, create it locally unless they explicitly
  ask to write to a cloud document.

## Output Options

Offer the user one of these outputs:
- Markdown report
- CSV-style table
- Google Sheets-ready table
- client-facing summary
- internal action list
- PDF via `scripts/generate_report.py` for audit-style reports

When generating a PDF, follow the PDF report quality gate in `ads/SKILL.md`.
