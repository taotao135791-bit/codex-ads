---
name: ads-levers
description: >-
  Agency constrained-scenario diagnosis for paid advertising operators. Use when KPI,
  product positioning, pricing, paywall, product roadmap, or business direction cannot be
  changed and the operator needs practical media-buying levers. Handles
  install-heavy/pay-light, registration-heavy/payment-light, lead-heavy/low-quality,
  low-CPI/poor-ROI, high-spend/no-revenue, payment KPI pressure, limited client
  permissions, and client-facing explanation needs.
---

# Agency Lever Diagnosis

Use this sub-skill when the operator is an agency or outsourced media buyer
with limited control over product, pricing, KPI definitions, or roadmap. The
goal is not to redesign the product. The goal is to find the strongest
controllable levers, prove what is outside media-buying control, and give the
operator clear internal and client-facing language.

## Core Rule

Do not optimize a shallow metric when the KPI is deeper.

Examples:
- Payment KPI: do not celebrate cheap installs if payment rate is weak.
- Qualified lead KPI: do not celebrate cheap leads if valid lead rate is weak.
- Revenue / ROAS KPI: do not celebrate CPA if order value or refund rate breaks
  the economics.

## Process

1. **State the constraint boundary**:
   - KPI: fixed or negotiable?
   - Product positioning: fixed or negotiable?
   - Pricing / paywall / offer: fixed or negotiable?
   - Product flow: fixed or negotiable?
   - Store page / landing page: editable, suggest-only, or locked?
   - Tracking events: editable, suggest-only, or locked?
   - Media levers: budget, geo, bid, optimization event, campaign / ad group
     or asset group, audience, placement, creative, copy, exclusions,
     remarketing, test cadence
2. **Validate data trust first**:
   - Does the deep event fire correctly?
   - Does platform data reconcile with backend / MMP / CRM data?
   - Are currency, value, deduplication, attribution window, and timezone right?
   - Is the account optimizing for the same event the business judges?
3. **Diagnose the mismatch**:
   - Traffic quality mismatch
   - Creative promise mismatch
   - Store / landing page expectation mismatch
   - Optimization event too shallow
   - Geo / device / placement quality issue
   - Product-side funnel loss after the media handoff
4. **Rank controllable levers before asking for product changes**.
5. **Output two versions**:
   - Internal operator action list
   - Client-facing explanation with evidence and requested support

## Permission Map

### Uncontrollable

- Product positioning
- Core product features
- Pricing
- Paywall or checkout architecture
- KPI definition
- Business model
- Product release cadence

Do not present these as direct operator actions. Present them only as evidence
or client-side dependencies.

### Partly Influenceable

- Store page or landing page copy
- Screenshot / app store asset direction
- Tracking event setup
- Offer framing
- Payment funnel evidence
- CRM / backend / MMP data access

Frame these as requests, tests, or client-side support items.

### Controllable

- Platform and campaign mix
- Geo / market allocation
- Budget pacing and reallocation
- Bid strategy and target
- Optimization event or proxy event
- Campaign / ad group / asset group structure
- Audience / placement / network exclusions
- Creative angle and copy pre-filtering
- Search terms / negatives / ASIN or keyword harvesting
- Remarketing windows
- Test sequencing
- Reporting narrative

These become the main action plan.

## Install-Heavy / Pay-Light Diagnosis

Use when installs, registrations, trials, or add-to-carts are high but payment
or subscription is low.

### First Checks

- Payment event is primary / included in optimization where possible
- Payment value, currency, and deduplication are correct
- Platform payment count is compared against backend / MMP payment count
- Geo, device, OS, placement, creative, campaign, and ad group / asset group
  are segmented by payment rate, not only install volume
- Current optimization event is identified: install, registration, trial,
  paywall view, subscribe, purchase, or value

### Likely Causes

- The platform is being rewarded for installers, not payers
- Creative attracts curiosity or free-intent users instead of high-intent users
- Cheap geos / placements produce installs but no payment density
- Store page or landing page creates install intent but weak payment expectation
- Paywall appears too late, too abruptly, or without enough value proof
- Payment volume is too low for direct purchase optimization, requiring a proxy

### Lever Order

1. Fix or verify payment tracking before changing media.
2. Segment spend by payment density: campaign, ad group / asset group, geo,
   device, OS, creative, placement, source, keyword / query where available.
   Do not collapse a country into one conclusion until winners and losers
   inside that country are separated.
3. Stop or cap low-CPI segments with zero or weak payment contribution.
4. Move optimization closer to payment. If payment volume is too low, use the
   deepest reliable proxy event: paywall view, trial start, checkout start,
   subscription intent, qualified registration, or high-value in-app action.
5. Rewrite creative to pre-filter for willingness to pay: value, use case,
   outcome, premium signal, price expectation, proof, and who it is not for.
6. Build remarketing from deep-intent users rather than all installers.
7. Ask the client for backend cohort data by campaign / ad group or asset
   group / country / creative if platform attribution is incomplete.

## Lead-Heavy / Low-Quality Diagnosis

Use when CPL is acceptable but valid lead, MQL, SQL, booking, or close rate is
weak.

Prioritize:
- Lead form quality fields and friction
- CRM feedback import or offline conversions
- Excluding low-quality sources / placements / audiences
- Copy that names price range, qualification, geography, or service boundary
- Landing page message match and trust proof
- Reporting valid lead rate, not only CPL

## Output Format

```markdown
# Agency Lever Diagnosis

## Constraint Boundary
- KPI:
- Cannot change:
- Partly influenceable:
- Controllable:

## Core Diagnosis
[One direct paragraph. Name the mismatch without blaming product or media by default.]

## Data Trust Checks
1.
2.
3.

## Operator Action Plan
| Priority | Lever | Action | Why | Risk | Evidence Needed |
| --- | --- | --- | --- | --- | --- |

## Stop / Scale Rules
- Stop or cap:
- Keep testing:
- Scale carefully:

## Client-Side Requests
1.
2.
3.

## Client-Facing Explanation
[Plain-language version suitable for account updates.]
```

## Client-Facing Tone

Use calm, evidence-based language:
- Say "the current data suggests" instead of "the product is bad".
- Say "we need backend confirmation" instead of "tracking is wrong" unless it
  is proven.
- Say "low-cost installs are not the same as paying users" when KPI is payment.
- Separate media actions from client-side dependencies.

## Default Client-Facing Paragraph

```text
Current performance suggests the issue is not only install volume, but the gap
between install users and paying users. We will first verify payment tracking,
then reduce spend from segments that bring low-cost installs without payment
contribution, and shift testing toward deeper events and creatives that
pre-filter for users with stronger purchase intent. To distinguish traffic
quality from post-install funnel loss, we also need backend or MMP payment data
by campaign, country, and creative where available.
```
