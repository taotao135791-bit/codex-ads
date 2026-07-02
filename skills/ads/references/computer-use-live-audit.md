# Computer Use Live Audit Protocol

Use this reference whenever Codex Ads analyzes a live advertising dashboard
through Computer Use.

## Default Rule

Prefer live read-only inspection when the user is logged in or asks you to look
at their current ad account. Exports and screenshots are fallback inputs, not
the default, when Computer Use is available.

## Guided Access Script

Before a live UI audit, guide the user with a short message like this:

```text
请你自己打开广告后台并登录，切到要分析的账号和日期范围。
我只做只读检查：看表格、图表、诊断、目标和转化设置。
我不会改预算、暂停广告、应用建议、保存设置或提交任何表单。
如果下一步可能产生修改，我会先停下来问你确认。
```

If the user already said they are logged in and gave read-only permission,
proceed without repeating the full script, but keep the read-only boundary.

## Safety Boundary

Read-only actions are allowed:
- open or switch between ad platform pages
- read tables, charts, cards, diagnostics, recommendations, conversion actions,
  budgets, campaign settings, asset reports, change history, search terms,
  audiences, geo/device/network breakdowns, and billing/account-budget warnings
- use filters, date ranges, columns, segments, sorting, page navigation, and
  account selectors to inspect data
- take notes, calculate metrics, and summarize findings

Do not perform these without exact action-time confirmation:
- create, edit, pause, enable, remove, or delete campaigns, ads, assets, goals,
  conversion actions, audiences, keywords, negatives, budgets, bids, billing
  settings, or account access
- apply recommendations, dismiss warnings, submit forms, upload files, connect
  accounts, accept new permissions, or save settings
- send messages or reports to third parties from the UI

When unsure whether a UI control mutates state, treat it as write-risk and ask
before clicking.

## Privacy and Non-Retention

Live account data is for the current analysis only.

Do not write user/client-specific details into repo files, README examples,
tests, templates, skills, reports, or reusable docs unless the user explicitly
asks for a deliverable that must contain those details.

Never persist:
- account names, account IDs, customer IDs, emails, phone numbers, payment
  details, billing details, access/permission details, campaign names, ad group
  names, asset names, conversion action names, or exact live-account metrics
- screenshots or copied UI text that identify a specific client/account
- recommendations phrased as if they came from a named real client account

When examples are needed, use anonymized placeholders such as:
- `Example App`
- `Campaign A`
- `Purchase`
- `Target CPA`
- `High-value conversion`
- rounded or fictional numbers

## Live Audit Workflow

1. Confirm scope from the user's prompt: platform, product, country, objective,
   date range, and target metric. If the user already gave enough context,
   proceed without re-asking.
2. Start with the overview page:
   - date range and timezone
   - total spend, impressions, clicks, conversions, revenue/value
   - account/campaign diagnostics and recommendations
   - budget-limited or learning/limited status warnings
3. Inspect campaign table:
   - campaign name, status, budget, bid strategy, target CPA/ROAS if visible
   - cost, conversions, cost/conversion, conversion value, install/lead/purchase events
   - identify winners, losers, zero-conversion spend, and overlap
4. Inspect conversion goals/actions:
   - primary vs secondary optimization
   - account-level goal inclusion
   - duplicate events or parallel SDK/Firebase/MMP events
   - tracking status, conversion windows, count method, value
5. Inspect segmentation:
   - country/region, device, network/placement, search terms or categories,
     asset groups/creatives, audience, schedule, new vs returning if available
6. Calculate the user's real KPI, not just the platform headline metric:
   - purchase CPA, qualified lead CPA, MER, ROAS, CAC, trial-to-purchase,
     install-to-purchase, or the user's stated goal
7. Produce a practical action plan:
   - what to freeze/limit
   - what to scale carefully
   - what data/goal setup must be fixed first
   - what to tell the client if this is an agency/代投 account

## Evidence Language

Use clear labels:
- **Observed:** directly visible in the UI.
- **Calculated:** computed from observed numbers.
- **Inference:** likely cause based on observed data.
- **Recommendation:** next action, kept read-only unless user approves changes.

If a page is managed by another account or permissions are limited, state the
manager account or permission issue explicitly and recommend what the owner or
manager account must verify.
