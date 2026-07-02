---
name: ads-google
description: >-
  Google Ads deep analysis covering Search, Performance Max, AI Max, Display, YouTube, and
  Demand Gen campaigns. Evaluates 80 checks across conversion tracking, wasted spend,
  account structure, keywords, ads, and settings. Includes AI Max (search-term-matching,
  AI Brief, text customization, FUE, brand exclusions) and Smart Bidding signals. Use when
  user says Google Ads, Google PPC, search ads, PMax, Performance Max, AI Max, AI Brief,
  broad match audit, Quality Score check, search terms audit, Smart Bidding, or Google
  campaign.
---

# Google Ads Deep Analysis

## Process

1. Collect Google Ads account data. Default to Computer Use read-only
   inspection of the live Google Ads UI when the user is logged in or asks you
   to look directly; otherwise use exports, screenshots, MCP/API data, Change
   History, and Search Terms Report.
2. If using Computer Use, read `ads/references/computer-use-live-audit.md`
   first. Inspect overview, campaign table, recommendations/diagnostics,
   conversion goals/actions, and relevant segments before drawing conclusions.
3. **Validate**: confirm data covers ≥30 days when possible and includes either
   Search Terms Report/API data or an explanation for why search-term data is
   unavailable.
4. **Validate learning-unit grain**: identify the optimization and learning
   unit before judging performance. Do not use country/geo totals as the
   decision unit.
5. Read `ads/references/google-audit.md` for full 80-check audit
6. Read `ads/references/benchmarks.md` for Google-specific benchmarks
7. Read `ads/references/scoring-system.md` for weighted scoring
8. Evaluate all applicable checks as PASS, WARNING, or FAIL
9. **Validate**: confirm all 80 checks evaluated before calculating score
10. Calculate Google Ads Health Score (0-100)
11. Generate findings report with action plan

## What to Analyze

### Conversion Tracking (25% weight)
- Google tag (gtag.js) installed and firing on all pages
- Enhanced Conversions active (hashed first-party data)
- Consent Mode v2 implemented (required for EU/EEA)
- Conversion actions mapped correctly (primary vs secondary)
- Offline conversion import configured (for lead gen)
- Server-side tagging via GTM (recommended for accuracy)
- Attribution model: data-driven preferred (last-click as fallback only)
- Conversion lag analysis (are conversions still trickling in?)

### Wasted Spend (20% weight)
- Search Terms Report reviewed (last 30 days minimum)
- Negative keyword coverage adequate (shared lists + campaign-level)
- Display placement audit (exclude low-quality sites)
- Invalid click rate within norms (<10%)
- Broad Match only used with Smart Bidding (NEVER without it)
- Brand/non-brand campaigns separated
- Geographic targeting precise (no wasted international spend)

**Negative Keyword Rules (critical: bad negatives kill campaigns):**
- NEVER suggest Broad Match negatives unless explicitly justified; they block too broadly
- Default to **Exact Match** `[keyword]` for specific irrelevant queries
- Use **Phrase Match** `"keyword"` for irrelevant intent patterns
- Source negatives from actual Search Terms Report irrelevant queries, NOT guesses
- Group into themed lists: Informational (how-to, DIY, what is), Job-seeker (jobs, careers, salary), Competitor (only if intentionally excluded), Free-intent (free, crack, torrent)
- Recommend **Shared Negative Lists** at the account level, not just campaign-level
- Review existing negatives for over-blocking (are any negatives accidentally blocking converting queries?)

### Account Structure (15% weight)
- Campaign-level organization follows business logic
- Ad groups themed tightly (15-20 keywords max per group)
- RSA ad groups have ≥3 active ads
- PMax campaigns structured correctly (asset groups, signals)
- SKAGs evaluated (migrate to themed groups if present)
- Campaign labels/naming conventions consistent

### Keywords (15% weight)
- Match type strategy appropriate (Exact → Phrase → Broad progression)
- Quality Score distribution (aim ≥7 average)
- Low QS keywords flagged (<5 = FAIL, 5-6 = WARNING)
- Keyword cannibalization check (same keywords in multiple campaigns)
- Impression share tracked for top keywords
- Keyword bid adjustments set for devices/locations/audiences

### Ads (15% weight)
- RSA: ≥8 unique headlines, ≥3 descriptions per ad group
- RSA: ad strength "Good" or "Excellent" (not "Poor" or "Average")
- Pin usage minimal and strategic (over-pinning reduces RSA flexibility)
- Ad extensions: sitelinks (≥4), callouts (≥4), structured snippets, image
- Dynamic keyword insertion used appropriately
- Ad copy includes CTA, value proposition, differentiators

### Settings (10% weight)
- ECPC (Enhanced CPC) flagged as deprecated. Migrate to full Smart Bidding (tCPA/tROAS/Maximize)
- Bid strategy appropriate for campaign maturity and goals
- Budget pacing: no campaigns limited by budget (unless intentional)
- Ad schedule aligned with business hours/conversion patterns
- Device bid adjustments set based on performance data
- Location targeting: "Presence" not "Presence or Interest"
- Network settings: Search Partners reviewed, Display opt-out for Search

## Learning Unit & Geo Segmentation Discipline

Google performance analysis must respect the unit that is actually learning or
being optimized. A country, region, or market is a segment, not a learning unit.
Never recommend pausing, scaling, or reallocating a country from country totals
alone.

Before making any geo, CPA, ROAS, or budget recommendation, identify the grain:

- **Search**: campaign, bid strategy / portfolio, ad group, keyword theme,
  search term, match type, device, conversion action
- **Performance Max**: campaign, asset group, listing group / product group,
  audience signal, search category, final URL, conversion action
- **App campaigns**: campaign, ad group / asset group, country, OS, device,
  optimization event, asset
- **Demand Gen / YouTube**: campaign, ad group, audience, asset, placement,
  device, conversion action

Geo analysis workflow:

1. Start with campaign and bid-strategy scope.
2. Break each country / region back down by ad group or asset group.
3. Separate winners and losers inside the same country before making a country
   recommendation.
4. Check whether a bad country total is caused by one weak ad group, keyword
   theme, asset group, device, or conversion action.
5. Check whether a good country total is being carried by one learning unit
   while other units are wasting spend.
6. State the confidence level and minimum data threshold before recommending
   a pause, cap, target change, or budget move.

Required wording in reports:
- **Observed**: country-level totals and unit-level breakdowns.
- **Calculated**: CPA/ROAS/CVR by campaign x ad group/asset group x geo.
- **Inference**: whether geo quality, learning-unit mix, creative/keyword mix,
  or tracking explains the result.

## GAQL & Data Accuracy

Before analyzing data, read `ads/references/gaql-notes.md` for known GAQL field incompatibilities,
deduplication patterns, and filter scope best practices. Key rules:

- Deduplicate keywords by `(ad_group_id + keyword_text + match_type)` before any analysis
- Only analyze ENABLED campaigns and ad groups (exclude paused/removed)
- Preserve `campaign_id`, `ad_group_id` or `asset_group_id`, geo, device, and
  conversion action dimensions until after learning-unit diagnostics are done
- Filter to keywords with impressions > 0 for theme coherence checks (G03)
- Apply legacy BMM heuristic: BROAD + Manual CPC = legacy BMM, not intentional broad (G17)
- Only flag wasted spend on terms with >$10 spend AND 0 conversions (G16)
- Count shared negative keyword lists alongside campaign-level negatives (G14/G15)

## Google Ads MCP Integration (Optional)

For automated data collection, connect the [Google Ads MCP server](https://github.com/googleads/google-ads-mcp):

- **Tools available**: `search` (GAQL queries), `list_accessible_customers`
- **Setup**: Configure in `.mcp.json` or Codex CLI MCP settings
- **Customer ID**: Extract from CODEX.md under Accounts > Google Ads, or ask the user
- **Fallback**: If MCP is not configured, fall back to manual data export (the default workflow)

When MCP is available, use it to pull Search Terms Reports, keyword data, conversion actions,
and campaign structure automatically instead of requiring manual exports.

## Computer Use Live UI Integration (Default When Available)

When Computer Use is available and the user is logged into Google Ads, prefer
live read-only UI inspection over asking for manual exports. Use it to inspect:

- Overview cards: date range, timezone, spend, clicks, conversions, value, major changes
- Campaign table: budget, status, bid strategy, cost, conversion columns, custom events, CPA/ROAS
- Recommendations and diagnostics: limited budget, campaign overlap, target constraints, tracking warnings
- Goals and conversion actions: primary/secondary, account-level inclusion, duplicate payment events, tracking status
- Segments: location, device, network, search terms/categories, assets,
  schedule, audience where visible, always tied back to campaign and ad group /
  asset group when the UI allows it

Never apply Google recommendations, edit targets, change budgets, pause/enable
campaigns, change goals, or save settings without exact confirmation. Reports
must mark UI-derived facts as **Observed**, calculations as **Calculated**, and
causal claims as **Inference**.

Before live inspection, guide the user to open the Google Ads account and date
range themselves, and state that the session is read-only. Never copy real
account IDs, campaign names, emails, payment details, or exact account metrics
into reusable repository docs, examples, tests, or skill files.

## PMax Deep Dive

If Performance Max campaigns exist, additionally evaluate:
- Asset group diversity (text, images, video, feeds)
- Audience signals configured (custom segments, lists, demographics)
- URL expansion settings reviewed (opt-out of irrelevant pages)
- Brand exclusions applied (prevent cannibalizing brand search), available for all advertisers
- Campaign-level negative keywords now available for ALL advertisers
- Search themes utilized (2024 feature)
- Final URL expansion: enabled or disabled with justification
- Insights tab reviewed (search categories, audience segments)

## AI Max for Search (2026)

AI Max layers broad match + keywordless targeting on existing Search campaigns.
14% avg conversion lift for non-retail brands at similar CPA/ROAS ([Google Ads blog, May 2025](https://blog.google/products/ads-commerce/google-ai-max-for-search-campaigns/)).
**DSA, ACA, and campaign-level broad match auto-migrate into AI Max by end of
September 2026**; new DSA campaign creation via the Google Ads API ends Sept
2026. Strong negative keyword lists are a hard prerequisite. Independent data
across 250+ campaigns shows more conservative real-world results (+13% median
revenue, +16% median CPA) — set expectations accordingly.

### Detection & API field

AI Max is enabled per-campaign via `ai_max_setting.enable_ai_max` (Google Ads
API v21+). Check the campaign's `ai_max_setting` resource for current state.

### Audit checklist

If AI Max for Search is available or active:
- **Field check**: `campaign.ai_max_setting.enable_ai_max = true` for eligible
  Search campaigns (or documented opt-out reason)
- **Broad Match + Smart Bidding combo verified** — AI Max effectively forces broad
  match expansion; without Smart Bidding (tCPA/tROAS/Maximize Conv) it bleeds spend
- **Search Term Matching** — review the `search_term_matching_type` distribution
  in the Search Terms Report (close variants vs broader matches); FAIL if the
  broader-match share exceeds 60% on a non-Smart-Bidding campaign
- **AI Brief configured** — Google's new structured brand context input. Audit
  for: business name, value prop (≤200 chars), target audience descriptor,
  forbidden topics / off-brand language list, regional / legal disclaimers
- **Text customization rules** — AI Max generates headline + description variants
  from the brief. Audit for: locked legal phrases, banned competitor names,
  approved disclaimer text, pin discipline on must-include claims
- **Final URL Expansion (FUE)** controls — confirm URL include/exclude lists
  prevent AI Max routing traffic to checkout-skip pages, password-gated pages,
  or 404s. Audit `url_expansion_opt_out` if you've explicitly disabled FUE
- **Brand exclusions applied** — campaign-level brand exclusion list to prevent
  cannibalizing brand search; same mechanism as PMax brand exclusions
- **Text disclaimers** (rolling out May 2026+) — if your vertical requires
  disclaimers (health, finance, legal, crypto), confirm Google's new structured
  text disclaimer field is populated
- **Budget impact** — AI Max can shift spend ±30% in the first 7 days. Confirm
  budget pacing rules and shared budgets won't starve adjacent campaigns
- **Negative keyword coverage** — AI Max broadens reach 3-5x; existing negative
  lists must scale. Reuse the negative keyword rules from the Wasted Spend section
  but apply at 3x the historical volume

### DSA Migration Pre-Flight Checklist

The Sept 2026 auto-migration moves Dynamic Search Ads, Automatically Created
Assets (ACA), and campaign-level broad-match Search campaigns into AI Max
whether or not the advertiser is ready. Run this pre-flight before the
migration deadline:

- [ ] **Inventory DSA campaigns** — query `campaign.advertising_channel_sub_type
      IN (SEARCH_DYNAMIC, ...)`. List campaign IDs, monthly spend, conversion
      volume so the migration can be staged by risk
- [ ] **Inventory ACA-enabled campaigns** — `campaign.ad_strength_settings`
      with auto-generated headlines enabled
- [ ] **Inventory campaign-level broad-match Search campaigns** without AI Max
      yet enabled — these will migrate by default
- [ ] **Tracking template audit** — DSAs often use `{lpurl}` ValueTrack
      parameters. Confirm tracking templates resolve correctly when AI Max
      generates a different final URL via FUE. Re-test parameter substitution
      with a synthetic AI Max landing URL
- [ ] **Negative keyword pre-staging** — pull the last 90 days of DSA search
      terms; pre-stage the irrelevant ones as Exact/Phrase negatives on a
      Shared Negative List before migration
- [ ] **AI Brief drafted** — write a draft Brief for each migrating campaign
      so Google has structured brand context at migration time, not generic
      crawled content
- [ ] **URL controls staged** — Final URL Expansion include/exclude lists
      prepared per campaign (especially for /careers, /admin, /thank-you,
      /404 paths that DSAs typically excluded by URL pattern rules)
- [ ] **Brand exclusion lists prepared** — campaign-level brand exclusion
      file (same format as PMax)
- [ ] **Bidding strategy migration** — Manual CPC and ECPC DSA campaigns
      MUST move to Smart Bidding before AI Max migration. Pre-stage tCPA or
      tROAS targets per migrating campaign
- [ ] **Conversion tracking pre-flight** — AI Max attribution relies heavily
      on Enhanced Conversions + Consent Mode V2; confirm both are active and
      verified per the Conversion Tracking section before migration
- [ ] **Reporting baseline** — capture 28-day pre-migration metrics (CTR,
      CVR, CPA, ROAS, Search Lost IS by rank/budget) so post-migration impact
      can be measured cleanly

Document the migration risk per campaign as **LOW** (Smart Bidding + strong
negatives + good AI Brief), **MEDIUM** (Smart Bidding but weak negatives or
no Brief), or **HIGH** (Manual CPC, weak negatives, generic Brief). Stage
migrations starting LOW → HIGH and pause MEDIUM/HIGH if conversion volume
drops >25% in the first 7 days.

## Demand Gen Campaigns

Replaced Video Action Campaigns (auto-upgrade began July 2025). Adding image
assets to a video-only campaign drives 20% more conversions at the same CPA
([Google Ads blog](https://blog.google/products/ads-commerce/video-action-campaigns-demand-gen-upgrade/)).
Frequency capping NOT supported.

If Demand Gen campaigns exist, evaluate:
- Video + image asset mix present (combined format drives 20% more conversions vs video-only at same CPA)
- Audience signals configured (custom segments, lookalikes)
- Conversion tracking aligned with upper/mid-funnel goals
- Note: frequency capping is not available. Monitor reach vs frequency manually

## Key Thresholds

| Metric | Pass | Warning | Fail |
|--------|------|---------|------|
| Quality Score (avg) | ≥7 | 5-6 | <5 |
| CTR (Search) | ≥6.66% | 3-6.66% | <3% |
| CVR (Search) | ≥7.52% | 3-7.52% | <3% |
| CPC (Search) | ≤$5.26 | $5.26-8.00 | >$8.00 |
| Wasted Spend | <10% | 10-20% | >20% |
| Ad Strength | Good+ | Average | Poor |
| Invalid Clicks | <5% | 5-10% | >10% |

## Output

### Google Ads Health Score

```
Google Ads Health Score: XX/100 (Grade: X)

Conversion Tracking: XX/100  ████████░░  (25%)
Wasted Spend:        XX/100  ██████████  (20%)
Account Structure:   XX/100  ███████░░░  (15%)
Keywords:            XX/100  █████░░░░░  (15%)
Ads:                 XX/100  ████████░░  (15%)
Settings:            XX/100  ██████████  (10%)
```

### Deliverables
- `GOOGLE-ADS-REPORT.md`: Full 80-check findings with pass/warning/fail
- Wasted spend estimate (monthly $ value)
- Quick Wins sorted by impact
- PMax-specific recommendations (if applicable)
- Keyword health matrix with QS, CTR, CVR per keyword group
