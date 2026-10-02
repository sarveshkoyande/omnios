# Engagement Plan — design thinking

Status: thinking draft (2026-10-02, updated with decisions). Not built yet.

## Decisions (2026-10-02)

1. **Period:** 6 months by default; the user can choose a shorter or longer period (e.g. 3 months).
2. **One brand per engagement plan.** No multi-brand or franchise plans.
3. **New object.** The existing engagement-plan records in Brands & Campaigns stay as they are;
   the engagement plan described here is created fresh and stored separately.
4. **Budget is relative** (weights / % split across objectives, audiences, channels), not money.
5. **Second industry: financial services — investment banking.** Closest to pharma: heavily
   regulated, every client communication passes a compliance gate (like MLR), and audiences are
   professionals whose behaviour must shift (like HCPs).
6. **The agent works like the Briefing Agent and Segmentation Planner** (the MR !1 agents): a
   visible step bar, ask only what's genuinely missing (max 3 questions), review assumptions,
   produce a versioned document, then confirm before anything is created. See "How the agent
   builds it".

## What it is

The **engagement plan** answers *what we will do over the next ~6 months, and why*:

- which audiences to engage,
- what each should think or do differently by the end,
- through which campaigns,
- with which messages,
- through which channels,
- in what order,
- and how we'll know it worked.

It does **not** go inside a single campaign; the Campaign plan, Flow and Brief do that. The
engagement plan is the **portfolio view**: the set of campaigns, and the reasoning that connects
them back to the brand's goals.

```
Brand plan (annual strategy: why the brand exists, imperatives, growth)
  └─ Engagement plan (next 6 months: who, what change, which campaigns, when)   ← this doc
       └─ Campaign plan (one campaign: objective, audience, messages, channels, timing)
            ├─ Flow (the journey diagram)
            └─ Brief (what an agency builds)
```

Rule of thumb: **if it's about one campaign, it belongs in the campaign plan. If it's about how
campaigns relate to each other and to the goal, it belongs here.**

## The questions it must answer

A universal set; the wording changes by industry, the questions don't.

| # | Question | Plain meaning |
|---|---|---|
| 1 | **Where are we now?** | Starting point: baseline KPIs, what happened last period, what changed in the market |
| 2 | **What must change in 6 months?** | 2-4 measurable objectives, each tied to a brand goal |
| 3 | **Who has to change?** | Priority audiences/segments, and how many people are in each |
| 4 | **From what to what?** | Each audience's current belief or behaviour → the target one (the "shift") |
| 5 | **What will move them?** | The message per audience and the proof behind it |
| 6 | **Through which campaigns?** | The campaign portfolio: each campaign owns one shift for one audience |
| 7 | **Where and how often?** | Channel mix and contact frequency, per audience |
| 8 | **When?** | Sequence on a 6-month timeline, around fixed moments (events, launches, seasons, data releases) |
| 9 | **With what?** | Budget and content split, what exists vs what must be made |
| 10 | **How will we know?** | KPIs per objective, leading indicators per campaign, review points |
| 11 | **What could go wrong?** | Risks, dependencies, compliance gates, and what we'd do |

## Sections (the template)

### 1. Plan frame
Period (start–end; default 6 months, user can change), scope (one brand, market(s)), owner, which brand plan it serves,
version and status (draft / in review / approved / live / closed).

### 2. Situation & baseline
- KPI baseline table (metric · today · source · date)
- What changed since last period (market, competition, data, regulation)
- Lessons from last period's campaigns (what worked, what to stop)

### 3. Objectives (2-4)
Each: objective · KPI · baseline → target · by when · which brand goal/imperative it serves ·
owner. Objectives are outcomes, not activities ("Frontline use 35% → 50%", not "Run 3 webinars").

### 4. Audience priorities
Priority segments with size, value and readiness. For each: why now, and whether we're **winning
new, growing, keeping or winning back** (the lifecycle lens works in every industry).

### 5. The shift map (the heart of the plan)
A grid of **audience × objective**. Each cell holds:

| Field | Example |
|---|---|
| From (today's belief/behaviour) | "Waits for ADAMTS13 before treating" |
| To (target belief/behaviour) | "Treats at clinical diagnosis" |
| Barrier | Cost concern; wants more benefit/risk data |
| Message that moves it | "Favourable benefit/risk upon frontline treatment" |
| Proof | Capla1000, ISTH guideline |
| Moment that matters | At clinical diagnosis |

Empty cells are allowed and meaningful: not every audience matters for every objective.

### 6. Campaign portfolio
The campaigns that deliver the shifts. Each: name · type (awareness / acquisition / adoption /
retention / win-back / launch / event) · audience · shift(s) it owns · core message · lead
channels · start–end · budget · KPI · status. **Each campaign becomes a Campaign plan.**
Coverage check: every shift in the map is owned by at least one campaign; flag the orphans.

### 7. Channel & frequency plan
Per audience: channel mix (owned / paid / earned / sales or field), contact frequency cap, and
how campaigns share it so the same person isn't hit by three campaigns in one week.

### 8. Timeline
A 6-month Gantt: campaigns as bars, fixed moments as markers (congresses, launches, seasonal
peaks, data read-outs, holidays, budget cut-offs), review points as milestones.

### 9. Budget & resources
**Relative** split (weights / %) by objective, audience and channel — no currency; content needed (have / adapt / create) with lead
times; who does what.

### 10. Measurement & governance
KPI tree (objective → campaign KPIs → leading indicators), data sources and refresh cadence,
monthly review, and the rule for reallocating budget mid-plan.

### 11. Risks & dependencies
Each risk with likelihood, impact, owner and mitigation; dependencies such as approvals, data,
launches and partners.

## Across industries

The structure is universal; only the vocabulary and the constraints change.

| Concept | Pharma | **Investment banking** (2nd framework) | Retail / D2C | B2B SaaS | Automotive |
|---|---|---|---|---|---|
| Audience | HCPs, patients, payers | Corporate clients (CFOs, treasurers, boards), institutional investors, coverage bankers | Shoppers, members | Buyers, users, champions | Intenders, owners, dealers |
| Typical shift | "Wait to treat" → "treat frontline" | "Uses us for one product" → "mandates us for the next deal" | One-off → repeat buyer | Trial → paid seat | Considering → test drive |
| Fixed moments | Congresses, label changes, data read-outs | Earnings seasons, deal windows, investor conferences, rate decisions, fiscal year-end | Seasons, sales events, holidays | Product launches, renewals, fiscal year-end | Model launches, motor shows |
| Gatekeeper | MLR, regulators | Compliance review, information barriers (Chinese walls), regulators (SEC/FINRA, FCA) | Brand, legal | Legal, security | Dealer network, brand |
| Main constraint | Fair balance, on-label only | Fair and balanced communications, no MNPI, suitability, record-keeping | Margin, stock | Sales capacity | Inventory, dealer readiness |
| Lifecycle lens | Find / Treat / Maintain | Originate / Win mandate / Expand wallet share | Acquire / Grow / Retain | Land / Expand / Renew | Attract / Convert / Loyalty |

How Omni handles it: a **framework file per industry** (`config/frameworks/engagement_<industry>.json`)
defining the section labels, the lifecycle lens, typical shifts, channel list, fixed-moment
types and gatekeeper steps. The page and the agent read the framework, so adding an industry is
config, not code — the same way the Campaign Planner reads `campaign_spine.json`.

## How the agent builds it

Modelled on the Briefing Agent and Segmentation Planner (MR !1): a step bar across the top, a
conversation on the left, the document on the right, versions, and nothing is created until you
confirm. Their philosophy, applied here:

- **Read first, ask last.** The agent reads every source before asking anything.
- **Only ask what's genuinely missing**, max 3 questions per round, consolidated.
- **Show assumptions, don't hide them.** Up to 3 impactful assumptions, each one you can accept
  or override.
- **Auto-assume switch** to skip questions and go straight to a draft.
- **Confirm before creating.** Campaign plans are only created when you approve the portfolio.

### Steps (the step bar)

| # | Step | What happens | What it asks you (only if missing) |
|---|---|---|---|
| 1 | **Frame** | Pick brand; period defaults to 6 months; the agent pulls the active brand plan and Brand IQ | Period if not 6 months; market scope |
| 2 | **Read** | Gathers objectives, KPIs, personas, messages, compliance gates, fixed moments, last period's results — shown as a grounding list with sources | — |
| 3 | **Clarify** | Asks up to 3 questions about real gaps | e.g. "Which objective matters most if they compete for the same audience?"; "Any campaigns already committed this period?"; "Relative budget weight per objective?" |
| 4 | **Assumptions** | Lists up to 3 impactful assumptions to accept or change | e.g. "Assuming patients are reached only via the support programme, not paid media" |
| 5 | **Draft plan** | Writes the engagement plan: objectives, shift map, portfolio, timeline, relative budget, KPIs, risks — every item sourced | Refine in chat ("move the webinar to Q1", "drop the TW launch") |
| 6 | **Check** | Coverage (every shift owned), audience overload (frequency collisions), budget vs objectives, compliance lead times — issues listed, each clickable | Fix or accept each issue |
| 7 | **Create campaigns** | Shows the campaigns it will create; on confirm, creates each as a Campaign plan pre-filled with audience, shift, message and timing | Confirm / deselect campaigns |

Each step streams progress like the MR !1 agents; the document is versioned (view, compare,
restore, export). When the model is unavailable, the agent stops with a plain message (rules R1/R2).

### Where each answer comes from

**Single input: Brand IQ.** The engagement plan never reads the brand plan document directly.
The brand plan is imported into Brand IQ once — brand facts into the Brand Kit, Personas and
Market Intelligence pages, and the year's plan (imperatives, KPIs, activities, forecast) into
Brand IQ's **plan layer**. A new brand plan becomes a new plan in Brand IQ; engagement plans built
on an older one are flagged "based on an older brand plan — review". If Brand IQ lacks something,
the engagement plan shows the gap and links to the Brand IQ page to fix it, rather than inventing it.

```
Brand plan document ─import─▶ Brand IQ (facts + plan layer) ─▶ Engagement plan ─▶ Campaign plans
```

| Comes from (all inside Brand IQ unless noted) | Fills |
|---|---|
| **Active plan** (Brand IQ plan layer, from the uploaded brand plan) | Objectives, imperatives, KPIs and baselines, planned activities, calendar |
| **Brand Kit** | Positioning, messages, proof, unmet need, competition |
| **Personas** | Audiences, behaviours, barriers, moments that matter, tone, channels |
| **Compliance** | Gatekeeper steps, channel rules, approval lead times for the timeline |
| **Market Intelligence** | Sizes, forecast, what has worked (proof points), KOLs, trial footprint |
| **Last period's campaigns** (Omni's own artifacts, outside Brand IQ) | Baseline performance, lessons |
| **You** (only via Clarify / Assumptions, outside Brand IQ) | Period, priorities between objectives, relative budget, anything not written down |

Rules that apply here as everywhere: free text is understood by the LLM only; no LLM means an
honest message, never a guess; every field names its source.

## For Cablivi, as a sanity check

Period Q4 2026 – Q1 2027 (6 months), Global.

| Objective | Shift (audience) | Campaigns |
|---|---|---|
| ER/ICU awareness 64% → 85% | Diagnosers: "non-specific symptoms" → "think TTP, treat as emergency" | ER/ICU See & Think; GO DOCTOR! localisation; ER/ICU webinar |
| Frontline use 35% → 50% (naive) | Treater-Cautioner: "wait for ADAMTS13" → "treat at clinical diagnosis" | Capla1000 frontline campaign; treater best-practice webinar; China KOL tour |
| Treatment duration ≥ 35 days | Patients and caregivers: "feel better, stop" → "finish the course" | Stay the Course patient onboarding; early-termination mini-webinar |
| Launch excellence (TW, TR, CN) | New-market treaters: "unaware" → "first use" | Market launch campaigns |

Fixed moments in the period: ASH (December), International TTP Day carry-over, Rare Disease Day
(February), ISTH abstracts, Mayari read-out (if label changes).

## Visuals reused from the classic brand overview

The classic brand overview (`#/b/<brand>`, `cockpit/src/components/hierarchy/BrandOverview.tsx`)
already draws four visuals in its plan detail card. Their numbers there are **seeded
placeholders** (the `seeded()` helper). In the engagement plan we reuse the **look**, fed with
real data only; where data is missing the visual shows "Needs input", never a placeholder.

| Visual (component) | In the engagement plan | Real data from |
|---|---|---|
| **Funnel** (`HcpFunnel` — tapering nested trapezoids) | **Audience funnel per priority audience**, stages = the industry framework's lifecycle lens (pharma: Aware → Engaged → Considering → Prescribing / Treating per label; investment banking: Covered → Engaged → Pitched → Mandated). One funnel per audience, with **today** (baseline) and **target** overlaid so the shift is visible | Brand IQ: Market Intelligence sizes, Personas, plan KPIs and baselines (e.g. Cablivi: 64% ER/ICU awareness → 85%; frontline 35% → 50%) |
| **Budget bars** (`PlanBudget`) | **Relative budget split** — bars by objective, audience or campaign (toggle), in % not money | The plan's relative weights (decision 4) |
| **Campaign timeline** (`CampaignTimeline`) | The **Timeline tab**: campaigns as bars over the 6-month period, fixed moments as markers, frequency collisions highlighted | Portfolio + fixed moments from Brand IQ / framework |
| **Plan history** (`PlanHistory` — short narrative) | **"Where we are now"** narrative at the top of Overview, written from real baselines and last period's results, each fact cited | Brand IQ + last period's campaign artifacts |

Implementation note: lift `HcpFunnel` / `PlanBudget` / `CampaignTimeline` into shared
components that take data as props (no seeding inside), so the classic page and the engagement
plan render the same visuals; the classic page can keep passing its placeholders until it is
retired.

## UI sketch

A new **Engagement plans** entry under Brands & Campaigns (and a "+ New → Start an engagement
plan" that's live instead of "Coming soon"). One page with tabs:

- **Overview**: "where we are now" narrative, frame, objectives with progress, audience funnels (today → target), a health line ("2 shifts have no campaign").
- **Shift map**: the audience × objective grid; click a cell to edit.
- **Portfolio**: campaign table with status; each row opens or creates its Campaign plan.
- **Timeline**: Gantt with fixed moments and frequency-collision warnings.
- **Budget & measurement**: relative budget bars and the KPI tree.
- **Risks**.

Same visual language as Brand IQ and the agent workspace; the result is a versioned artifact
like the others, so history, compare, export and Refine come for free.

## Open questions

1. Investment banking: which brand-plan equivalent do we start from (a coverage plan, a
   product/desk plan)? A sample document would help as the Cablivi deck did.
2. Should the engagement plan's campaigns appear in the existing Brands & Campaigns page, or
   only inside the new engagement plan page?

## Build phases

1. **Framework + data model**: `engagement_pharma.json`, new artifact type `engagement_plan`
   (separate from existing engagement-plan records), one brand per plan.
2. **Agent steps 1-5** (frame → read → clarify → assumptions → draft), the MR !1 way.
3. **Page**: Overview, Shift map and Portfolio tabs; "Create campaign plan" hand-off.
4. **Timeline & checks**: Gantt, coverage and frequency-collision checks.
5. **Investment banking framework** (`engagement_investment_banking.json`) and the industry switch.
6. **Tracking**: progress from campaign results.
