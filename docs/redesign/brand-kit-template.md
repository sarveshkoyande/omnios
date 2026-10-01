# Brand Kit — reusable template

Status: thinking draft (2026-09-30). Informed by building the Cablivi kit from its 2026 Global
Brand Plan deck.

## Why

The Cablivi kit mixed two kinds of content:

1. **Brand facts** that every brand has, in the same shape: company, molecule, indication, label,
   competitors, audiences.
2. **This year's plan**: FIND / TREAT / MAINTAIN, the 288 → 354 M€ growth frame and the 14
   activities. These are specific to one brand plan and one year, so they can't be a template.

The Brand Kit should be the **template**: the same sections for every brand, filled mostly from
**public, authoritative sources** where possible. The plan-specific content becomes a
**Brand Plan** layer attached to the kit, summarised at the top but not treated as kit structure.

## Page order

1. **Identity header** (template)
2. **Key objectives** (template shape, one or more per brand)
3. **Product profile**: molecule, mechanism, structure, label (template, external sources)
4. **Competition** (template; key section, not an afterthought)
5. **Positioning & message** (template)
6. **Evidence & references** (template)
7. **Voice & tone** (template)
8. **Brand plan summary**: strategic imperatives, growth frame and KPIs, from the current plan
   (plan layer, varies by brand and year)

The activation plan (activities, channels, timing) **leaves the Brand Kit**. It belongs to the
Engagement plan and Campaign plans, which already consume it.

Personas, Compliance guardrails and Market intelligence stay as their own pages (already split).

---

## 1. Identity header (template)

| Field | Example (Cablivi) | Source |
|---|---|---|
| Brand name | Cablivi | User / plan |
| Company | Sanofi | FDA label (labeler) |
| Generic (INN) | caplacizumab | FDA label |
| Lifecycle stage | Launch / Growth / Mature / LoE | User (confirm) |
| Therapy area | Rare haematology | NIH MeSH tree (disease category) |
| Condition | Purpura, Thrombotic Thrombocytopenic | NIH MeSH descriptor |
| Territories | US, EU, JP … | User |
| Approval dates | US FDA 2019; EU EMA 2018 | Drugs@FDA, EMA EPAR |

Shown as compact labels under the brand name (Company · Lifecycle · Therapy area), as today.

## 2. Key objectives (template, **multiple**)

The objective is key and there can be several. Each entry is shaped the same way:

| Field | Example |
|---|---|
| Objective | Treat 100% of aTTP events frontline |
| Measure (KPI) | Frontline use 35% → 50% (naive) |
| Target date | Q4 2026 |
| Priority | Primary / Secondary |
| Owner / source | Brand plan 2026, slide 23 |

The template holds the **shape**; each brand fills it with its own objectives. Cablivi has three
because its plan has three imperatives; another brand might have one or five.

## 3. Product profile (template, external sources)

| Field | Source | Notes |
|---|---|---|
| Drug class / modality | FDA label, MeSH pharmacological action | Small molecule, monoclonal antibody, nanobody, gene therapy … |
| Mechanism of action | FDA label §12.1 | Cablivi: anti-vWF, blocks vWF–platelet interaction |
| **Chemical / molecular structure** | PubChem (small molecules), IUPHAR / UniProt / DrugBank (biologics) | Small molecule: formula, weight, 2D structure image. Biologic: molecule type, target, size (Cablivi ≈ 28 kDa bivalent nanobody); no 2D structure |
| Route & dosing | FDA label §2 | IV bolus then daily SC |
| Approved indication (exact wording) | FDA label §1 / EMA SmPC 4.1 | Feeds Compliance guardrails |
| Boxed warning / key safety | FDA label §5, §6 | Feeds guardrails and fair balance |
| Label version / date | DailyMed SPL version | So we can alert when the label changes |

## 4. Competition (template, key)

For each competitor or alternative:

| Field | Example |
|---|---|
| Name / class | Plasma exchange + immunosuppression (standard of care); rADAMTS13 (pipeline) |
| Type | Standard of care / Direct / Pipeline / Off-label |
| Status | Marketed, Phase 3, expected ≥2029 |
| How we differ | Adds microthrombi inhibition on top of PEX |
| Threat level | High / Medium / Low (user) |
| Source | ClinicalTrials.gov, FDA, brand plan |

Pipeline competitors can come from ClinicalTrials.gov, searched by condition.

## 5. Positioning & message (template)

Positioning statement, Big Idea, core claim, message pillars (claim + evidence) and key messages
per audience. Filled from the brand plan; every claim links to a reference in section 6.

## 6. Evidence & references (template)

Pivotal trials (ClinicalTrials.gov NCT IDs), key publications (PubMed PMIDs) and guidelines, each
marked promo-eligible or not.

## 7. Voice & tone (template)

Tone pillars, words to use and avoid, brand personality. Usually from the brand team; rarely in
public sources.

## 8. Brand plan summary (plan layer, **not** template)

Shown near the top as "Current plan: 2026 Global Brand Plan":

- **Strategic imperatives**: whatever the plan defines (FIND / TREAT / MAINTAIN for Cablivi).
  They're shown as the plan's own list, not fixed template slots.
- **Growth frame**: sales/patient forecast and growth split.
- **KPIs**: they link back to Key objectives (section 2).

A brand can hold several plans over time (2025, 2026 …); the kit shows the active one.

---

## External sources to wire

| Source | What we pull | Access |
|---|---|---|
| openFDA / DailyMed | Label sections, labeler, version, boxed warning | Free REST API |
| Drugs@FDA | Approval dates, application number | Free |
| **NIH MeSH** | Condition descriptor, tree (therapy area), pharmacological action | Free API (id.nlm.nih.gov) |
| PubChem | Formula, weight, structure image (small molecules) | Free PUG-REST |
| UniProt / IUPHAR | Target protein, biologic details | Free |
| ClinicalTrials.gov | Pivotal and competitor trials | Free API v2 |
| PubMed | Key publications | Free E-utilities |
| EMA EPAR | EU indication and approval | Public pages |

The rules from earlier conversations apply:

- Understanding free text is done by the LLM only, never regex.
- Anything not found shows "Needs input", never a guess.
- Every field records its source and fetch date.

## Decisions (2026-09-30)

1. **The uploaded brand plan is the source of truth.** Where the plan covers a field (lifecycle
   stage, objectives, positioning, competitors …), its value wins. Public sources (FDA, MeSH,
   PubChem …) fill what the plan doesn't cover and serve as a cross-check. A conflict is shown
   side by side, e.g. "Plan says X · FDA label says Y", and the plan value is kept until the user
   changes it. Lifecycle stage comes from the plan; approval history is only a fallback suggestion.
2. **The agent proposes competitor threat levels,** with a one-line reason and its sources; the user
   confirms or changes them.
3. **A brand can have several plans active at once** (e.g. Global 2026 and US 2026). The kit shows
   a plan switcher and defaults to the most recent Global plan. Each plan owns its imperatives,
   growth frame and KPIs.
4. **Plan content is not treated as confidential.** The local-only restriction on Cablivi's kit
   can be lifted: it may live in the normal kit store and be committed/shared like other kits.

**Source precedence:** brand plan → user edits → public sources → agent suggestion (always marked
"to confirm").

## Next steps

1. Restructure the Brand Kit page into sections 1–8; move the activation plan out.
2. Add Key objectives (multiple) and a Competition section to the kit schema.
3. Build a public-source fetcher for Cablivi: openFDA + MeSH + PubChem/UniProt, then review.
4. Re-run for one more real brand to prove the template holds.

## Additions (2026-09-30, review round 2)

Template sections added after reviewing the Cablivi kit:

- **Unmet need** (after Identity): a one-line summary, headline disease facts (mortality,
  incidence, age, current treatment rates), and a gaps table (gap · what happens today · who it
  affects). Source: brand plan; epidemiology can be cross-checked in PubMed.
- **Voice & tone** (expanded): personality, register, reading level, **say-this-not-that
  principles**, tone by audience, preferred terms (use / instead of), never-say list. Drafted from
  the plan, marked "to confirm".
- **Market access**: value story, access barriers, launches by country.
- **Tables instead of cards**: key objectives, message matrix, messages by persona (message ·
  content we have · content to develop), competition as a side-by-side grid with our brand first
  (type · status · strength · weakness · how we win · threat), evidence and references.

Still to do: approved-claims library with ISI (fair-balance block); channel preferences by
audience; events calendar (congresses, awareness days, data read-outs); KOLs and patient groups;
visual identity; completeness score per section.
