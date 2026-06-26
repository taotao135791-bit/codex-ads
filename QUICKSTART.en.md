# Codex Ads Quick Start

This guide is for day-to-day use by ad optimizers. **You do not need to type slash commands.** Copy one of the prompts below into Codex.

## First Use

Start Codex and say:

```text
I want to use Codex Ads for ad optimization. Default to read-only account review. Do not change ad platform settings. If I ask for daily reports, weekly creative reports, or client updates, ask where the client template is first.
```

If the ad dashboard is already open:

```text
I am logged into the ad dashboard. Please review the current account in read-only mode. Tell me which pages you need to inspect first, and do not change any settings.
```

## Ten Everyday Prompts

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
