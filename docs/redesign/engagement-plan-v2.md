# Engagement Plan v2 — a pharma template for any brand (and a Brand IQ rethink)

Status: **built** (2026-10-02, steps 1-6 below; see 'Build status'). **Supersedes** the industry-agnostic parts of
`engagement-plan.md`; keeps its decisions on period, one brand per plan, relative budget and the
separate store. Not built yet.

## Why v2

Review of the v1 build (Cablivi run, 2026-10-02) found three problems:

1. **Pharma only.** The industry selector and the investment-banking framework go. Pharma is the
   product; breadth comes from covering *pharma brand situations*, not other industries.
2. **Cablivi-shaped.** The framework (Find / Treat / Maintain, an HCP "Aware → Prescribing" funnel),
   the agent prompts and even Brand IQ's extra sections were modelled on one rare, acute,
   hospital brand. A chronic primary-care brand or a multi-indication oncology brand doesn't fit.
3. **Superficial reasoning.** "Read, ≤3 gap questions, ≤3 assumptions, draft" fills gaps but never
   *diagnoses* the brand, never offers *strategic choices*, and never *stress-tests* the result.

## What the research says

Common practice in pharma brand and engagement planning, with sources at the end:

- **Patient flow ("leaky bucket") is the backbone of brand planning.** Brand teams track patients
  through diagnosis, treatment and persistence and look for where they drop out; patient-level
  data feeds market sizing, segmentation, treatment dynamics, adherence and competitive dynamics
  [1][2][3][4]. Drop-out points are concrete and measurable: time to diagnosis, time to
  therapy, prior-authorisation abandonment, enrolment friction (60%+ loss between eligible and
  enrolled in specialty) [1][3].
- **The biggest leak differs by brand:**
  - **Oncology:** the leak is often *testing*. About 20% of advanced NSCLC patients weren't PD-L1
    tested before first-line therapy, and fewer than 50% received all recommended biomarker
    tests [5][6].
  - **Cardio-renal-metabolic:** the leak is *treatment initiation*. SGLT2 inhibitors remain
    under-prescribed despite strong evidence, especially in primary care [7].
  - **Rare, acute:** the leak is *recognition and speed*, plus early stopping (Cablivi's own plan).
- **HCP engagement is planned on an adoption ladder.** Each HCP's step (e.g. awareness → belief
  → support, or innovators → laggards) decides which message and content they need. Omnichannel
  plans sequence channels to move people up the ladder and measure progression per stage [8][9][10].
- **STP drives the plan.** Segmentation feeds media planning, field call planning and content
  personalisation [9]. Segmentation now goes beyond specialty and volume to behaviour, e.g.
  digital-first vs rep-dependent [10]. Consent is its own ladder that limits what omnichannel can
  do [11].
- **The plan changes with lifecycle stage:**
  - **Launch:** awareness, positioning, rapid uptake.
  - **Growth:** expand use, new segments and indications.
  - **Maturity:** differentiate, defend and retain.
  - **LoE:** switch to a next-generation or reformulated product, and decide who should stay on
    the brand.
  - **Life extension:** new formulations, combinations and indications [12][13][14].
- **Organised customers matter as much as individual HCPs.** Engagement increasingly runs at
  enterprise level: health systems and payers, key account management, value-based pricing [15].

## 1. Brand situation model (replaces "industry")

Every brand is classified on three axes. The classification chooses which plan **modules**
apply, which funnel is used and which questions the agent asks.

| Axis | Values |
|---|---|
| **Lifecycle** | Pre-launch · Launch (0–2 y) · Growth · Maturity · Pre-LoE (≤3 y to LoE) · Post-LoE |
| **Therapy archetype** | Rare / acute · Oncology (biomarker-driven) · Chronic primary care · Specialty biologic / injectable · Vaccine · Biosimilar / generic-competing |
| **Access situation** | Open access · Restricted (prior auth / step edit) · Hospital / tender · Price-negotiated or HTA-limited |

Each archetype comes with defaults (editable in a framework file, not code):

| Archetype | Patient-flow stages (the funnel) | Typical biggest leaks | Audiences beyond the prescriber | Modules switched on |
|---|---|---|---|---|
| Rare / acute | Symptom → suspected → diagnosed → treated (right time) → treatment completed | Recognition, speed, early stopping | ER/ICU, reference centres, patient groups | Diagnosis acceleration, centre network |
| Oncology | Diagnosed → **tested** → biomarker-eligible → treated in line → stays on therapy | Testing, line-of-therapy choice | Pathologists, tumour boards, nurse navigators, payers | Testing, line-of-therapy, multi-indication |
| Chronic primary care | Prevalent → diagnosed → **eligible** → initiated → titrated → persistent → adherent | Initiation inertia, adherence | GPs, specialists, pharmacists, payers, patients | Initiation, adherence, specialist-to-GP referral |
| Specialty biologic | Diagnosed → referred → prescribed → **access approved** → started → persistent | Prior auth, hub enrolment | Payers, hub / specialty pharmacy, nurses | Access & hub, site-of-care |
| Vaccine | Eligible → recommended → **administered** → series completed | Recommendation, hesitancy, seasonality | Public health, pharmacists, parents | Recommendation, season timing |
| Biosimilar / LoE | On reference → switch considered → switched → retained | Switching, tenders | Procurement, payers, pharmacists | Switch / defend, tender calendar |

The **HCP adoption ladder** is universal across archetypes: Unaware → Aware → Interested →
Trialled → Adopter → Advocate. Each audience segment sits on a ladder rung; each campaign moves
named segments up named rungs.

## 2. The agent flow: diagnose → options → decide → draft → stress-test

Replaces "read, ≤3 questions, ≤3 assumptions, draft". It keeps the MR !1 style: a step bar, a
conversation, nothing created without your confirmation, and an honest stop with no model.

| # | Step | What the agent does | What you do |
|---|---|---|---|
| 1 | **Frame** | Brand, period (6 months default), markets | Confirm |
| 2 | **Classify** | Proposes lifecycle × archetype × access with evidence, e.g. "Approval 2014; 4 indications; Medicare-negotiated price from 2026 → Maturity / chronic / price-negotiated" | Confirm or correct |
| 3 | **Diagnose the bucket** | Fills the archetype's patient-flow stages with numbers from Brand IQ + public sources; shows the conversion at each stage, where data is missing, and the **top 2–3 leaks** | Confirm leaks; supply missing numbers if you have them |
| 4 | **Root causes** | For each top leak: which audience's belief / behaviour causes it, on which ladder rung they sit, the evidence (plan, research, market data) | Agree / adjust |
| 5 | **Strategic options** | 2–3 distinct options, e.g. "A: fix initiation in primary care", "B: deepen specialist use", "C: fix persistence", each with expected impact on the bucket, relative cost, risk, time to effect and what you give up | **Choose** (or mix) |
| 6 | **Draft** | Objectives tied to the chosen leaks, the shift map (audience × ladder move), the campaign portfolio, the timeline, the relative budget and the KPI tree, every item sourced | Refine in chat |
| 7 | **Feasibility** | Checks field capacity (calls / rep / month), relative budget vs objectives, content readiness and MLR lead time, consent reach per channel, audience fatigue (frequency caps) | Fix or accept each issue |
| 8 | **Red team** | Critiques its own plan: likely competitor response, weakest assumption, what makes it fail, the leading indicator that would show it early | Accept fixes |
| 9 | **Create campaigns** | On confirm, each campaign becomes a pre-filled Campaign plan | Confirm |

Questions are **generated from the diagnosis**, not from a generic list. For example: "Persistence
after 6 months has no data — do you have it?", or "Your plan targets cardiologists, but the leak
is GP initiation — intentional?". There's still a cap per round, but the questions are sharper.

## 3. Brand IQ rethink (also Cablivi-shaped today)

Today's Brand IQ extras (unmet need facts, Find / Treat / Maintain imperatives, a 3-stage patient
journey, a growth split, the KOL list from one condition) came from the Cablivi deck. v2 makes
Brand IQ a **core + archetype modules** structure.

**Core (every brand):**

- **Identity:** company, INN, class, approvals by region (FDA / EMA), lifecycle stage, LoE date.
- **Indications:** a **list**, not one string. Each indication has its population, line of
  therapy, biomarker or eligibility criteria, approval date and label text. Keytruda has dozens;
  Jardiance has T2D, HF and CKD.
- **Product profile:** MoA, structure, dosing, safety (FDA label, as today).
- **Patient flow:** the archetype's stages per indication, with numbers, source and date, plus
  gaps.
- **Audiences:**
  - HCP segments, with adoption-ladder position and behavioural / digital segment;
  - organised customers (health systems, payers);
  - patients and caregivers.
- **Competition:** per indication; standard of care, direct competitors, pipeline, generics and
  biosimilars.
- **Messages, evidence and claims:** per indication and per audience.
- **Compliance:** company SOPs, label and safety (as today).
- **Plans:** brand plans by year and scope (as today's plan layer).

**Modules switched on by archetype or lifecycle:**

| Module | For | Holds |
|---|---|---|
| Diagnosis acceleration | Rare / acute | Time to diagnosis, referral centres, red-flag symptoms |
| Testing & biomarkers | Oncology | Required tests per indication, testing rates, turnaround, labs |
| Initiation & adherence | Chronic | Eligible-but-untreated pool, titration, persistence curves, refill data |
| Access & hub | Specialty, price-negotiated | Formulary status, prior auth rules, hub enrolment, negotiated price impact |
| Multi-indication | Oncology, CRM | Per-indication priority, sequencing, cannibalisation |
| LoE & lifecycle | Pre/post-LoE | LoE dates by market, next-gen / reformulation (e.g. subcutaneous), switch strategy |
| Season / recommendation | Vaccines | Recommending bodies, season calendar |

**Public sources per module** extend today's FDA / MeSH / PubMed / ClinicalTrials.gov fetchers:

- **Indications:** the FDA label's indications section, already fetched and split per indication by the LLM.
- **Testing rates, adherence and epidemiology:** PubMed real-world evidence searches per indication (LLM-summarised with citations).
- **Guidelines:** recommendation status, e.g. ADA, ESC or NCCN; often paywalled, so cite rather than copy.
- **Pipeline competitors:** ClinicalTrials.gov per indication.

## 4. Three test brands (prove it isn't Cablivi-shaped)

| | Cablivi | Jardiance | Keytruda |
|---|---|---|---|
| Archetype | Rare / acute | Chronic primary care (cardio-renal-metabolic) | Oncology, biomarker-driven, multi-indication |
| Lifecycle | Growth | Maturity (multi-indication expansion done) | Maturity / pre-LoE (to verify) |
| Access | Hospital | Price-negotiated in US Medicare (to verify for the plan year) | Specialty / hospital, payer-managed |
| Funnel | Symptom → diagnosed → treated frontline → completed | Diagnosed T2D / HF / CKD → eligible → initiated → persistent → adherent | Diagnosed → tested (PD-L1, MSI-H…) → eligible → treated in line → stays on therapy |
| Likely biggest leak | Recognition, early stopping | Initiation in primary care [7] | Biomarker testing [5][6] |
| Key audiences | ER/ICU, haematologists | GPs, cardiologists, nephrologists, endocrinologists, pharmacists, patients | Oncologists, pathologists, tumour boards, nurse navigators, payers |
| Brand plan source | Uploaded deck | None: Brand IQ built from public sources only (label, PubMed, guidelines) | None: public sources only |
| What it tests | Plan-led brand | Multi-indication + adherence modules; public-source-only kit | Testing module, many indications, LoE |

**Jardiance and Keytruda have no uploaded brand plan.** That tests the honest path: the agent must
show "no brand plan — objectives proposed from the diagnosis, to confirm" rather than inventing
a plan. Facts marked *to verify* (LoE dates, price-negotiation timing) are fetched and cited at
build time, not assumed.

## 5. What changes from v1

| v1 | v2 |
|---|---|
| Industry selector (pharma / investment banking) | Removed; pharma only. Investment-banking framework deleted |
| One framework file, Cablivi-shaped | Archetype frameworks: one file per archetype, plus a lifecycle overlay |
| Funnel = HCP Aware → Prescribing | Funnel = archetype patient flow (per indication); HCP adoption ladder alongside |
| Objectives from the brand plan's list | Objectives from the diagnosed leaks (the brand plan confirms or overrides) |
| ≤3 gap questions, ≤3 assumptions | Classify → diagnose → root causes → options → decide; questions come from the diagnosis |
| No feasibility or critique | Feasibility check + red team before campaigns are created |
| Brand IQ: one indication, Cablivi extras | Brand IQ core + archetype modules; indications as a list |

## Build order (proposed)

1. **Brand IQ core:** indications as a list, archetype + lifecycle fields, the patient-flow block;
   migrate Cablivi.
2. **Archetype frameworks:** the six files (stages, ladder, modules, typical leaks, question bank);
   remove the industry selector and the investment-banking file.
3. **Jardiance and Keytruda Brand IQ** from public sources only: label indications, PubMed
   real-world rates, ClinicalTrials.gov pipeline.
4. **Agent v2 steps 2–5:** classify, diagnose bucket, root causes, options.
5. **Draft on the chosen option;** then feasibility and red team.
6. **Run all three brands;** compare plans side by side to confirm they differ for the right reasons.

## Open questions

1. Field capacity: do we have, or can we assume, rep numbers per brand for the feasibility
   check, or keep it relative?
2. Real-world rates from PubMed are global and dated: is "best available, cited, with year"
   acceptable for the bucket numbers?
3. For brands with many indications (Keytruda), plan per brand with indication priorities, or
   allow an engagement plan per indication?

## Sources

1. Doceree — The Specialty Patient You Lost in the Funnel: https://blog.doceree.com/the-specialty-patient-you-lost-in-the-funnel-a-walk-through-for-brand-teams
2. pharmaphorum — Understanding patient flow forecasting: https://pharmaphorum.com/patients/understanding-patient-flow-forecasting
3. Tellius — Patient Journey Analytics for Pharma: https://www.tellius.com/resources/blog/the-complete-guide-to-patient-journey-analytics-apld-analysis-and-lot-analytics-in-pharma
4. Brand planning with patient-level information (PDF): https://www.onlymedics.com/documents/brand-planning.pdf
5. Trends in Real-World Biomarker Testing in Advanced NSCLC (Future Oncology): https://www.tandfonline.com/doi/full/10.2217/fon-2022-0540
6. Biomarker testing and tissue journey in mNSCLC, US Oncology Network (Lung Cancer): https://www.sciencedirect.com/science/article/pii/S0169500222003737
7. AJMC — SGLT2 inhibitors… prescribers target uptake gaps: https://www.ajmc.com/view/sglt2-inhibitors-show-renal-benefits-in-hf-and-ckd-as-prescribers-target-uptake-gaps
8. Anthill — Best practices in pharma omnichannel engagement (adoption ladder): https://www.anthill.technology/insight/best-practices-omnichannel
9. Improvado — HCP Targeting & Segmentation in Pharma: https://improvado.io/blog/hcp-targeting-segmentation-pharma
10. IntuitionLabs — Managing and Tracking HCP Engagement (PDF): https://intuitionlabs.ai/pdfs/managing-and-tracking-hcp-engagement-in-modern-u-s-pharma-marketing.pdf
11. Indegene — The Consent Ladder in Pharma: https://www.indegene.com/what-we-think/reports/building-consent-for-omnichannel-pharma
12. Remap Consulting — The product life cycle: https://remapconsulting.com/hta/the-product-life-cycle/
13. EY — Navigating pharma loss of exclusivity: https://www.ey.com/en_us/insights/life-sciences/navigating-pharma-loss-of-exclusivity
14. OptimizeRx — Pharma marketing through the brand lifecycle: https://www.optimizerx.com/blog/pharma-marketing-success-commercial-brand-lifecycle
15. IQVIA — Pharma Brand Strategy / Innovating a Pharma Commercial Model: https://www.iqvia.com/locations/united-states/solutions/life-sciences/pharma-brand-strategy
16. FDA — Jardiance label (2025): https://www.accessdata.fda.gov/drugsatfda_docs/label/2025/204629s063lbl.pdf
17. NCBI Bookshelf — Clinical Review, Pembrolizumab (Keytruda): https://www.ncbi.nlm.nih.gov/books/NBK616198/

## Build status (2026-10-02)

| Step | State | Where |
|---|---|---|
| 1 Brand IQ core | Done: situation, indications list, patient flow, audience segments; shown on Brand Kit / Personas | `config/brand_kits.json`, `BrandKitPage.tsx` |
| 2 Archetype frameworks | Done as one file (6 archetypes + lifecycle + access); industry selector and investment banking removed | `config/frameworks/engagement_archetypes.json` |
| 3 Jardiance + Keytruda from public sources | Done: FDA label (brand-matched), Drugs@FDA (earliest original), MeSH, PubMed per-stage queries; figures verified match / proxy / reject | `strategy/brand_builder.py` |
| 4 Agent: classify, diagnose, root causes, options | Done | `strategy/engagement_agent.py` |
| 5 Draft on chosen option; feasibility + red team | Done (feasibility is deterministic; red team is model) | same |
| 6 Run all three brands | Done: Jardiance -> in-hospital HF initiation; Keytruda -> first-line uptake / AE-driven interruption; Cablivi -> frontline initiation | -- |

Known limits: openFDA's Jardiance label is the 2023 version (no CKD indication yet); PubMed figures
are best-available and often proxies; "Diagnosed" stages are usually gaps; Create campaign plan
does not yet pre-fill the Campaign Planner.
