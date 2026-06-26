---
name: ads
description: "Multi-platform paid advertising audit and optimization skill for agency operators. Analyzes Google, Meta, YouTube, LinkedIn, TikTok, Microsoft, Apple, and Amazon Ads. Handles constrained agency scenarios where KPI, product positioning, pricing, or product roadmap cannot be changed, especially install-heavy/pay-light, lead-heavy/low-quality, low-CPI/poor-ROI, and limited-lever accounts. Also automates repetitive agency operations: daily patrols, anomaly triage, client replies, creative request briefs, report cleanup, client template adaptation, changelogs, and meeting summaries. 250+ checks with scoring, parallel agents, industry templates, AI creative generation, attribution and server-side tracking deep dives."
argument-hint: "audit | google | meta | youtube | linkedin | tiktok | microsoft | apple | amazon | attribution | tracking | creative | landing | budget | levers | patrol | anomaly | client-reply | creative-request | clean-report | adapt-template | changelog | meeting | plan <type> | competitor | math | test | report | daily | creative-weekly | dna <url> | create | generate | photoshoot"
license: MIT
tested_date: 2026-05-17
tested_with: codex-cli v2.x
---

# Ads: Multi-Platform Paid Advertising Audit & Optimization

Comprehensive ad account analysis across all major platforms (Google, Meta,
LinkedIn, TikTok, Microsoft, Apple, Amazon). Orchestrates 25 specialized
sub-skills and 10 agents (6 audit + 4 creative).

## Natural Language First

Users do not need to invoke slash commands. Treat natural-language requests
like "只读看一下这个广告账户", "帮我出日报", "按甲方模板做素材周报",
"安装很多支付很少但 KPI 不能改", "帮我做每日巡检", "整理素材需求单",
"适配这个甲方日报模板", "review this Google Ads account", or "prepare a
client update" as valid Ads skill invocations. Route the request to the
matching sub-skill internally.

## Default Live-Data Mode: Computer Use First

When the user asks to analyze a live ad account, diagnose performance, inspect
Google Ads / Meta Ads / TikTok Ads Manager / other ad dashboards, or says they
are logged in, default to **Computer Use-assisted read-only analysis** before
asking for exports.

Default behavior:
- Use Computer Use to inspect the user's already-open or logged-in ad platform
  UI when available.
- For daily operations such as `/ads patrol`, `/ads anomaly`,
  `/ads creative-request`, `/ads changelog`, and template-based reporting,
  still default to Computer Use first when the work depends on live dashboard
  state or opened client templates.
- Before live inspection, guide the user to open the ad dashboard themselves,
  choose the correct account, set the date range, and state read-only access.
- Stay read-only: view pages, filters, tables, charts, diagnostics, goals,
  conversion actions, assets, and reports; do not create, edit, pause, enable,
  delete, apply recommendations, change budgets, change bids, submit forms, or
  save settings unless the user explicitly confirms that exact action.
- If Computer Use is unavailable, not installed, not authorized, or the user is
  not logged in, fall back to exports, screenshots, pasted metrics, or MCP/API
  data.
- Load `references/computer-use-live-audit.md` before any live UI analysis and
  follow its read-only checklist.
- In final reports, separate **observed in UI** facts from **inferred** causes
  and recommendations.
- Never persist user/client-specific account details, account IDs, campaign
  names, emails, payment information, or live-account metrics into repository
  files, templates, examples, tests, or documentation. Use anonymized examples
  only.

## Optimizer Style Profiles

Before any audit, daily report, weekly creative report, budget review, or client
summary, look in the current working directory for one of these files:

- `CODEX_ADS_OPTIMIZER.md`
- `optimizer-profile.md`
- `.codex-ads-optimizer.md`

If present, read it and adapt the analysis to the optimizer's judgment style:
core KPIs, kill/scale rules, risk tolerance, preferred account-reading order,
creative evaluation heuristics, and client reporting tone.

If the user asks to customize the skill for their own experience, create or
update `CODEX_ADS_OPTIMIZER.md` locally. Do not include real client account
names, IDs, emails, campaign names, or exact live-account metrics unless the
user explicitly asks for a private working file that needs those details.

Optimizer profiles guide judgment, but they never override safety, privacy,
platform policy, or the read-only Computer Use boundary.

## Agency Constraint Mode

Codex Ads is optimized for agency operators who usually cannot change product
positioning, pricing, KPI definitions, payment flow, roadmap, or commercial
model. Do not default to "fix the product" advice. When the user says KPI
cannot change, product direction is fixed, install volume is high but payment
is low, leads are plentiful but low quality, CPI is good but ROI is poor, or
the operator has few levers, route to `ads-levers`.

In constrained scenarios, separate the problem into:
- **Uncontrollable**: product positioning, core features, pricing, paywall,
  KPI definition, business model, release cadence
- **Partly influenceable**: store page / landing page copy, event setup,
  creative direction, offer framing, product-side funnel evidence
- **Controllable by media buying**: platform, geo, budget, bid strategy,
  optimization event, audience / placement, creative angle, copy pre-filter,
  exclusions, remarketing, test cadence, reporting narrative

The output must protect operator judgment: do not celebrate cheap installs or
cheap leads when the KPI is payment, qualified lead, revenue, ROAS, or LTV.
Use evidence to distinguish media-side traffic quality from product-side funnel
loss, and provide both internal action items and client-facing wording.

## Quick Reference

| Command | What it does |
|---------|-------------|
| `/ads audit` | Full multi-platform audit with parallel subagent delegation |
| `/ads google` | Google Ads deep analysis (Search, PMax, YouTube) |
| `/ads meta` | Meta Ads deep analysis (FB, IG, Advantage+) |
| `/ads youtube` | YouTube Ads specific analysis |
| `/ads linkedin` | LinkedIn Ads deep analysis (B2B, Lead Gen) |
| `/ads tiktok` | TikTok Ads deep analysis (Creative, Shop, Smart+) |
| `/ads microsoft` | Microsoft/Bing Ads deep analysis (Copilot, Import) |
| `/ads amazon` | Amazon Ads deep analysis (Sponsored Products / Brands / Display, ACOS / TACOS) |
| `/ads attribution` | Cross-platform attribution audit (AdAttributionKit, GA4, Consent Mode V2, MMP) |
| `/ads tracking` | Server-side tracking pipeline audit (sGTM, CAPI Gateway, dedup, hit ratio) |
| `/ads creative` | Cross-platform creative quality audit |
| `/ads landing` | Landing page quality assessment for ad campaigns |
| `/ads budget` | Budget allocation and bidding strategy review |
| `/ads levers` | Agency constrained-scenario diagnosis: find controllable levers when KPI/product cannot change |
| `/ads patrol` | Daily account patrol: catch spend, conversion, delivery, approval, and tracking issues |
| `/ads anomaly` | Triage sudden metric changes before changing budgets or bids |
| `/ads client-reply` | Convert internal findings into client-safe explanations |
| `/ads creative-request` | Turn performance gaps into design/video/UGC request briefs |
| `/ads clean-report` | Clean exported tables and normalize metrics for reports |
| `/ads adapt-template` | Map any client report template to the standard Ads data model before filling |
| `/ads changelog` | Record and summarize optimization changes for review and protection |
| `/ads meeting` | Build weekly/monthly meeting summaries from reports and actions |
| `/ads plan <business-type>` | Strategic ad plan with industry templates |
| `/ads apple` | Apple Ads deep analysis |
| `/ads competitor` | Competitor ad intelligence analysis |
| `/ads math` | PPC financial calculator (CPA, ROAS, break-even, budget forecasting) |
| `/ads test` | A/B test design (hypothesis, significance, duration, sample size) |
| `/ads report` | PDF audit report generation for client deliverables |
| `/ads daily` | Guided daily performance report export |
| `/ads creative-weekly` | Guided weekly creative performance report |
| `/ads dna <url>` | Extract brand DNA from website, outputs `brand-profile.json` |
| `/ads create` | Generate campaign concepts + copy briefs, outputs `campaign-brief.md` |
| `/ads generate` | Generate AI ad images from brief, outputs to `ad-assets/` |
| `/ads photoshoot` | Product photography in 5 styles (Studio, Floating, Ingredient, In Use, Lifestyle) |

## Context Intake (Required: Always Do This First)

Before any audit or analysis, collect this context. Without it, benchmarks will
be generic and recommendations may be wrong for the user's situation.

Ask these questions upfront (combine into one message):

1. **Industry / Business type**: Which best describes you?
   SaaS · E-commerce · Local Service · B2B Enterprise · Info Products · Mobile App ·
   Real Estate · Healthcare · Finance · Agency · Other
2. **Monthly ad spend**: Total budget and per-platform breakdown (approximate is fine)
3. **Primary goal**: Sales / Revenue · Leads / Demos · App Installs · Calls · Brand
4. **Active platforms**: Which platforms are you advertising on?

If the user provides data upfront (e.g. "audit my Google Ads, I spend $5k/mo on SaaS"),
extract context from that and proceed without re-asking.

Use the provided context to:
- Select the correct industry benchmarks from `references/benchmarks.md`
- Apply budget-appropriate recommendations (e.g. Smart Bidding requires 15+ conv/month)
- Calibrate severity scoring (a $500/mo account has different priorities than $50k/mo)

## 10-Principle Thinking Framework

Every command in this skill operates under a shared thinking discipline:
**OBSERVE × 2 (External + Internal) → LISTEN → THINK → CONNECT × 2 (Lateral + System) → FEEL → ACCEPT → CREATE → GROW**.

Before producing any audit, plan, or creative output, load
`references/thinking-framework.md` and let it shape the analysis — not as a
checklist, but as a mindset gate. The framework is what separates a
number-crunching report from a strategic deliverable. When the work feels
weak, identify which of the ten principles is being skipped and engage it
before continuing.

## Orchestration Logic

When the user invokes `/ads audit`, delegate to subagents in parallel:
1. **Collect context** (see Context Intake above; do this first)
2. Collect account data. Prefer Computer Use read-only inspection of live
   dashboards when available; otherwise use exports, screenshots, pasted
   metrics, MCP/API data
3. Detect business type and identify active platforms
4. Spawn subagents via Task tool with `context: fork`: audit-google, audit-meta, audit-creative, audit-tracking, audit-budget, audit-compliance
5. **Validate**: verify each subagent returned valid JSON scores with required fields before aggregating
6. Collect results and generate unified report with Ads Health Score (0-100)
7. Create prioritized action plan with Quick Wins

For individual commands (`/ads google`, `/ads meta`, `/ads amazon`,
`/ads attribution`, `/ads tracking`, etc.), load the relevant sub-skill
directly. Still collect context first if not already provided.

**Wave 2 sub-skills run standalone (no dedicated agent yet):** `ads-amazon`,
`ads-attribution`, and `ads-server-side-tracking`. See the Wave 3 backlog at
the bottom of the Subagents section for the planned paired audit agents.

## Creative Workflow

Sequential pipeline (each step is independently runnable):
1. `/ads dna <url>` → `brand-profile.json` in current directory
2. `/ads create` → reads profile + optional audit results → `campaign-brief.md`
3. `/ads generate` → reads brief + profile → `ad-assets/` directory
4. `/ads photoshoot` → standalone or reads profile for style injection

Requires `GOOGLE_API_KEY` (Gemini default) or `ADS_IMAGE_PROVIDER` + matching key.
If API key is missing, `/ads generate` and `/ads photoshoot` display setup
instructions and exit; they never fail silently.

## Industry Detection

Detect business type from ad account signals:
- **SaaS**: trial_start/demo_request events, pricing page targeting, long attribution windows
- **E-commerce**: purchase events, product catalog/feed, Shopping/PMax campaigns
- **Local Service**: call extensions, location targeting, store visits, directions events
- **B2B Enterprise**: LinkedIn Ads active, ABM lists, high CPA tolerance ($50+), long sales cycle
- **Info Products**: webinar/course funnels, lead gen forms, low-ticket offers
- **Mobile App**: app install campaigns, in-app events, deep linking
- **Real Estate**: listing feeds, property-specific landing pages, geo-heavy targeting
- **Healthcare**: HIPAA compliance flags, healthcare-specific ad policies
- **Finance**: Special Ad Categories declared, financial products compliance
- **Agency**: multiple client accounts, white-label reporting needs
- **Marketplace Seller (Amazon / Walmart 3P)**: ASIN-level catalogs, ACOS / TACOS metrics, Sponsored Products / Brands / Display spend mix, Brand Registry indicators

## Quality Gates

Hard rules (never violate these):
- Never recommend Broad Match without Smart Bidding (Google)
- 3x Kill Rule: flag any ad group/campaign with CPA >3x target for pause
- Budget sufficiency: Meta ≥5x CPA per ad set, TikTok ≥50x CPA per ad group
- Learning phase: never recommend edits during active learning phase
- Compliance: always check Special Ad Categories for housing/employment/credit/finance
- Creative: never run silent video ads on TikTok (sound-on platform)
- Attribution: default to 7-day click / 1-day view (Meta), data-driven (Google)
- Andromeda creative diversity: Flag Meta accounts with <10 genuinely distinct creatives
- Privacy infrastructure gate: Always verify tracking stack (Consent Mode V2, CAPI, Events API, AdAttributionKit) before making optimization recommendations
- PDF report quality gate: When generating reports via `/ads report`, always use `scripts/generate_report.py` with `--check` first. Reports must have: clean layout with no overlapping elements, proper margins (0.75in), word-wrapped table cells (no clipping), all charts/images sized within page boundaries, page numbers and section dividers, captions on every visual, and zero empty sections. Run `--check` before `--output` and fix any warnings before delivering the PDF

## Reference Files

Load these on-demand as needed; do NOT load all at startup.

**Path resolution:** All references are installed at `~/.codex/skills/ads/references/`.
When sub-skills or agents reference `ads/references/*.md`, resolve to
`~/.codex/skills/ads/references/*.md`.

- `references/thinking-framework.md`: 10-Principle Thinking Framework (OBSERVE/LISTEN/THINK/CONNECT/FEEL/ACCEPT/CREATE/GROW) — load before any audit, plan, or creative output
- `references/scoring-system.md`: Weighted scoring algorithm and grading thresholds
- `references/benchmarks.md`: Industry benchmarks by platform (CPC, CTR, CVR, ROAS)
- `references/bidding-strategies.md`: Bidding decision trees per platform
- `references/budget-allocation.md`: Platform selection matrix, scaling rules, MER
- `references/platform-specs.md`: Creative specifications across all platforms
- `references/conversion-tracking.md`: Pixel, CAPI, EMQ, ttclid implementation
- `references/compliance.md`: Regulatory requirements, ad policies, privacy
- `references/google-audit.md`: 80-check Google Ads audit checklist (G01-G61 + 19 hyphenated v1.5+ checks; verified via tests/fixtures/check-catalog.yaml)
- `references/meta-audit.md`: 50-check Meta Ads audit checklist (M01-M40 + 10 hyphenated v1.5+ checks)
- `references/linkedin-audit.md`: 27-check LinkedIn Ads audit checklist (L01-L25 + 2 hyphenated v1.5+ checks)
- `references/tiktok-audit.md`: 28-check TikTok Ads audit checklist (T01-T25 + 3 hyphenated v1.5+ checks)
- `references/microsoft-audit.md`: 24-check Microsoft Ads audit checklist (MS01-MS20 + 4 hyphenated v1.5+ checks)
- `references/brand-dna-template.md`: Brand DNA schema and extraction guide
- `references/image-providers.md`: Provider config (Gemini/OpenAI/Stability/Replicate)
- `references/google-creative-specs.md`: PMax/RSA/YouTube generation-ready specs
- `references/meta-creative-specs.md`: Feed/Reels/Stories specs + safe zones
- `references/linkedin-creative-specs.md`: Single image/video B2B constraints
- `references/tiktok-creative-specs.md`: 9:16 only + safe zone overlay
- `references/youtube-creative-specs.md`: Skippable/Bumper/Shorts/Thumbnail
- `references/microsoft-creative-specs.md`: Multimedia Ads + RSA subset
- `references/gaql-notes.md`: GAQL field compatibility, deduplication patterns, filter scope best practices
- `references/voice-to-style.md`: Brand voice axis to visual attribute mapping for image generation
- `references/copy-frameworks.md`: 6 ad copy frameworks (AIDA, PAS, BAB, 4P, FAB, Star-Story-Solution)

## Scoring Methodology

### Ads Health Score (0-100)

Per-platform score using weighted algorithm from `references/scoring-system.md`.
Cross-platform aggregate weighted by budget share:

```
Aggregate = Sum(Platform_Score x Platform_Budget_Share)
```

### Grading

| Grade | Score | Action Required |
|-------|-------|-----------------|
| A | 90-100 | Minor optimizations only |
| B | 75-89 | Some improvement opportunities |
| C | 60-74 | Notable issues need attention |
| D | 40-59 | Significant problems present |
| F | <40 | Urgent intervention required |

### Priority Levels

- **Critical**: Revenue/data loss risk (fix immediately)
- **High**: Significant performance drag (fix within 7 days)
- **Medium**: Optimization opportunity (fix within 30 days)
- **Low**: Best practice, minor impact (backlog)

## Sub-Skills

This skill orchestrates 25 specialized sub-skills:

1. **ads-audit**: Full multi-platform audit with parallel delegation
2. **ads-google**: Google Ads deep analysis (Search, PMax, AI Max, YouTube)
3. **ads-meta**: Meta Ads deep analysis (FB, IG, Threads, Advantage+, Andromeda + GEM + Lattice)
4. **ads-youtube**: YouTube Ads specific analysis (Demand Gen, CTV, Shorts)
5. **ads-linkedin**: LinkedIn Ads deep analysis
6. **ads-tiktok**: TikTok Ads deep analysis (post-USDS-divestiture)
7. **ads-microsoft**: Microsoft/Bing Ads deep analysis
8. **ads-apple**: Apple Ads deep analysis (AdAttributionKit, dual attribution)
9. **ads-amazon**: Amazon Ads deep analysis (Sponsored Products / Brands / Display, ACOS / TACOS) — *Wave 2*
10. **ads-attribution**: Cross-platform attribution audit (AdAttributionKit, GA4, Consent Mode V2, MMP, server-side stitching) — *Wave 2*
11. **ads-server-side-tracking**: Server-side tracking pipeline audit (sGTM, CAPI Gateway, dedup, hit ratio, PII hashing) — *Wave 2*
12. **ads-creative**: Cross-platform creative quality audit + Entity-ID retrieval scoring
13. **ads-landing**: Landing page quality for ad campaigns
14. **ads-budget**: Budget allocation and bidding strategy
15. **ads-levers**: Agency constrained-scenario diagnosis for limited-permission operators
16. **ads-ops**: Daily agency operations: patrols, anomalies, client replies, creative requests, report cleanup, template adaptation, changelogs, meetings
17. **ads-plan**: Strategic ad planning with industry templates
18. **ads-competitor**: Competitor ad intelligence
19. **ads-math**: PPC financial calculator (CPA, ROAS, break-even, LTV:CAC)
20. **ads-test**: A/B test design (hypothesis, significance, sample size)
21. **ads-report**: Daily report export, weekly creative report, and client-template guided reporting
22. **ads-dna**: Brand DNA extraction from website URL
23. **ads-create**: Campaign concepts, copy decks, creative briefs
24. **ads-generate**: AI image generation with pluggable providers
25. **ads-photoshoot**: Product photography in 5 professional styles

## Subagents

For parallel analysis during full audits:
- `audit-google`: Google Ads checks (G01-G61 + 19 hyphenated v1.5+ IDs = 80 total; incl. AI Max)
- `audit-meta`: Meta Ads checks (M01-M40 + 10 hyphenated v1.5+ IDs = 50 total; incl. Andromeda + Entity-ID clustering)
- `audit-creative`: Creative quality for LinkedIn, TikTok, Microsoft (plus cross-platform creative-diversity scoring for Andromeda Entity-ID retrieval)
- `audit-tracking`: Conversion tracking health across all platforms
- `audit-budget`: Budget, bidding, structure for LinkedIn, TikTok, Microsoft
- `audit-compliance`: Compliance, settings, performance across all platforms
- `creative-strategist`: Campaign concepts from brand profile + audit results (Opus, maxTurns: 25)
- `visual-designer`: Image generation with brand injection via generate_image.py (Sonnet, maxTurns: 30)
- `copy-writer`: Headlines, CTAs, primary text within platform limits (Sonnet, maxTurns: 20)
- `format-adapter`: Asset dimension validation and spec compliance reporting (Haiku, maxTurns: 15)

**Wave 3 backlog (planned, not yet shipped):**
- `audit-amazon`: Amazon Sponsored Products / Brands / Display + DSP audit (currently invoked via `ads-amazon` sub-skill standalone)
- `audit-attribution`: Cross-platform attribution audit (currently invoked via `ads-attribution` sub-skill standalone)
- `audit-server-side`: Server-side tracking pipeline audit (currently invoked via `ads-server-side-tracking` sub-skill standalone)

Once these land, `/ads audit` will dispatch all three in parallel alongside the existing six.
