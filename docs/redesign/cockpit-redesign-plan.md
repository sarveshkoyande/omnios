# Omni OS Cockpit — Redesign Plan (v1)

A living document: items are confirmed in review sessions and updated as the design evolves.
Reasoning for every decision (why, alternative considered, assumption/risk) is in
[decision-log.csv](decision-log.csv) — opens directly in Excel.

**Reference:** Jasper's app structure (grouped left nav + Home + one shared app-workspace
template). We borrow its **structure and density**, not its look.

**Safety net:** the pre-redesign state is committed and tagged `pre-redesign` (commit `2226208`).
All redesign work happens on the `redesign` branch and ships alongside the current Cockpit at a
separate route until approved.

**Status:** ✅ confirmed · ✅ v1 confirmed, expected to change · ⏸ deferred · ❌ dropped

---

## The planning hierarchy (the model everything else follows)

| Level | Horizon | Decides | Output |
|---|---|---|---|
| 1. Brand plan | Annual, refreshed ~quarterly | Situation & market, positioning, strategic pillars, message house & claims, customer universe, **segmentation framework**, **personas** | **Brand Kit** (stable input to everything below) |
| 2. Marketing engagement plan | ~3 months | Quarterly goals & KPIs, **priority segments (select + size)**, marketing mix, channel mix, **budget & cost**, **campaign portfolio** | Quarterly plan + campaign list |
| 3. Campaign plan | Per campaign | Dates, goal, **executable segment rules**, message ladder, every communication (day, channel, content, resend/exit), KPIs | Structured campaign (decision spine S0–S10) |
| 4. Flow plan | — | Nothing new — renders the campaign structure | Flow diagram / SFMC-ready structure |
| 5. Brief | — | Nothing new — readable projection of the campaign plan | Brief |

- **Segmentation** = data-driven (who, how many). **Persona** = human archetype of a segment
  (data + motivation, belief, emotion, barriers). Segment first, then humanise with a persona.
- The engagement plan stops at **select + size** segments; executable rules belong to the campaign.

---

## A. App shell & navigation — ✅

| ID | Change | Status |
|---|---|---|
| A1 | Short grouped nav: **+ New**, Home, My work, Brands & Campaigns, Chat | ✅ |
| A2 | **Brand IQ**: Brand Kits, Personas, Compliance Guardrails, Market Intelligence — for the active brand | ✅ |
| A3 | Favorites: pin apps, brands or campaigns | ✅ |
| A4 | Rail collapsible: icon-only, expands on hover | ✅ |
| A5 | User avatar + name at the bottom of the rail | ✅ |

## BR. Brand scope (N brands) — ✅

| ID | Change | Status |
|---|---|---|
| BR1 | Brand switcher at the top of the nav: search, Pinned, Recent, All brands | ✅ |
| BR2 | Default = most recently used brand; one brand → just its name | ✅ |
| BR3 | "All brands": cross-brand recent work tagged by brand; Brand IQ asks to pick one | ✅ |
| BR4 | Specific brand: Recent work, Brand IQ, Ask bar and app pre-fill scope to it | ✅ |
| BR5 | Apps can override the brand in App settings without changing the global selection | ✅ |
| BR6 | Brand IQ always shows the active brand's kit, personas, guardrails, intel | ✅ |

## B. Home — ✅

| ID | Change | Status |
|---|---|---|
| B1 | Home replaces the Agent Library as the landing page | ✅ |
| B2 | Greeting card + **Ask Omni anything…** bar (brand-aware) | ✅ |
| B3 | Quick actions **inside the Ask box**: type `/` for any agent (context chip, Send opens it); top three agents as one-click chips | ✅ (revised) |
| B4 | Categories row: the three phases with app counts, filters the grid | ✅ |
| B5 | **Agents** grid, 4 per row, full descriptions; NEW / COMING SOON tags (POPULAR once usage data exists) | ✅ (revised) |
| B6 | Recent work: brand · type · time, reopens where you left off | ✅ |
| B7 | Brand chips on Home (≤2 brands) | ❌ replaced by BR |

## C. App workspace (one template for every agent) — ✅

| ID | Change | Status |
|---|---|---|
| C1 | Two panels: inputs left (~420px), output right | ✅ |
| C2 | Top bar: editable title, save state, Share, Version history | ✅ |
| C3 | App header: icon, name, one line, ☆ favourite, Change app | ✅ |
| C4 | App settings row: Brand · Territory · Plan · Campaign (replaces the chat wizard) | ✅ |
| C5 | Input cards with status: empty / done / recommended-unconfirmed; pre-filled where known | ✅ |
| C6 | Recommended answer + option chips + one-line "why" per card | ✅ |
| C7 | Add more context chips | ✅ |
| C8 | Sticky Generate → Stop generating → Regenerate | ✅ |
| C9 | Right panel = **artifact viewer** for typed, schema-validated objects | ✅ |
| C10 | View tabs: Overview · Detail · Timeline · Diagram · Data (JSON) | ✅ |
| C11 | Structured editing only (fields, cells, pickers, timeline drag), schema-validated | ✅ |
| C12 | Check guidelines runs field-level compliance checks | ✅ |
| C13 | Refine drawer proposes structured changes as an accept/reject diff | ✅ |
| C14 | Hand-off to the next app with data; export JSON/CSV/SFMC/Visio + human PDF | ✅ |
| C15 | Auto-save every run to My work | ✅ |
| C16 | Versioning: compare and restore | ✅ |

## D. Specific agents — ✅ v1 (expected to change)

| ID | Change | Status |
|---|---|---|
| D1 | Briefing Agent on the new template; inputs from the decision spine; output is a projection of the campaign plan | ✅ v1 |
| D2 | Flow Planner on the same template | ✅ v1 |
| D3 | Flow Planner **only renders** campaign structure; per-segment view is a view, not a decision | ✅ v1 |
| D4 | Hand-off chain: Brand plan → Engagement plan → Campaign plan → (Flow, Brief) | ✅ v1 |
| D5 | Campaign Planner app owns spine S0–S10; Segmentation / Channel / Message agents own their stages | ✅ v1 |
| D6 | Brand plan + Engagement plan apps wait for M2; personas + segmentation framework live at Brand plan level | ✅ v1 |

## E. Visual style — ✅

| ID | Change | Status |
|---|---|---|
| E1 | Keep Omni's identity; **fewer curves** (radii ~6–10px) | ✅ |
| E2 | **Keep glassmorphism and the existing senior-approved look**; only tighten spacing and radii | ✅ |
| E3 | Purple only for primary actions, active nav and focus | ✅ |
| E4 | Tighter density: ~14px body, 12px secondary, 18–22px titles | ✅ |
| E5 | Status colours for status only; functional legends unchanged | ✅ |
| E6 | All changes through the tokens file | ✅ |

## F. Cleanup — ✅

| ID | Change | Status |
|---|---|---|
| F1 | Remove Launch → modal wizard and the brand/plan/campaign chat wizard | ✅ |
| F2 | Remove floating chat / reopen FABs (refine drawer replaces them) | ✅ |
| F3 | Stage 1 runs attach to the originating campaign (no duplicate campaigns) | ✅ |
| F4 | Retire the Agent Library page; one agent registry read by Home + workspace | ✅ |
| F5 | Remove illustrative filler; use empty states | ✅ |
| F6 | Track deferred items in this plan | ✅ |

## M. Frameworks & content model — ⏸ partly deferred

| ID | Change | Status |
|---|---|---|
| M1 | Every artifact has a framework spec: stages → decision → framework → data points (source + derive/confirm/ask) → feeds | ✅ principle |
| M2 | Define Brand plan + Engagement plan frameworks (pharma marketing mix / Customer·Content·Channel·Cadence) — **needs the team's real template** | ⏸ deferred |
| M3 | Each agent declares which stages it owns | ✅ principle |
| M4 | Input cards generated from data points (derive → pre-filled, confirm → recommended, ask → required) | ✅ principle |
| M5 | Artifact schema = framework decisions, with traceability | ✅ principle |
| M6 | Framework specs live as editable config (JSON/YAML) | ✅ principle |

**Interim:** campaign-level agents use the existing decision spine (`strategy/decision_spine.py`, S0–S11).

---

## Build order

Each phase ends with a live demo; the next phase starts only after approval. The new Cockpit is
built alongside the current one (under a `v3` route and a scoped `.v3` root class, so the new
spacing/radii never leak into the current look) until the final switch-over.

| Phase | Scope | Items | Review checkpoint |
|---|---|---|---|
| 0 | Foundation: v3 route, scoped tokens (fewer curves, tighter density, same glass look), single agent registry | E1–E6, F4 (registry) | Empty v3 frame renders; old Cockpit untouched |
| 1 | App shell: grouped nav, Brand IQ, Favorites, collapsible rail, avatar, brand switcher | A1–A5, BR1–BR6 | Navigate and switch brands |
| 2 | Home: greeting + Ask bar, quick actions, categories, apps grid, recent work | B1–B6 | Home feels right |
| 3 | Workspace inputs: layout, top bar, app header, App settings, framework-driven input cards (decision spine), Generate | C1–C8, M1, M3–M6 | Briefing Agent inputs pre-filled from the brand kit |
| 4 | Artifact viewer: view tabs, structured editing, auto-save, versions — with the brief artifact | C9–C11, C15, C16, D1 | Generate a real brief and edit it |
| 5 | Refine drawer (diffs), Check guidelines, hand-off + exports | C12–C14 | Refine and export a brief |
| 6 | Campaign Planner + Flow Planner on the template; fix duplicate campaigns | D2–D5, F3 | Campaign → Flow → Brief chain end to end |
| 7 | Cleanup and switch-over: remove old wizards/FABs/filler, make v3 the default | F1, F2, F5 | Sign-off; `pre-redesign` tag stays as rollback |
| Later | Brand plan + Engagement plan frameworks and apps | M2, D6 | Needs the team's template |

## Standing rules

| ID | Rule |
|---|---|
| R1 | No regex/keyword matching of user text anywhere; LLM-based matching only. Exceptions are confirmed with the user first. |
| R2 | If the LLM is unreachable, say so plainly and don't guess. |
| R3 | The brief-capture chat's keyword rules are converted to LLM-only in Phases 3-4. |

## Open questions

1. Does the team have a Brand plan / Engagement plan template to build M2 from?
