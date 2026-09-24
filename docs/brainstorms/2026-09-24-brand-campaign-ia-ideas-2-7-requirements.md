---
title: Brand / Engagement Plan / Campaign / Flow IA, Ideas 2 to 7 - Requirements
type: feat
date: 2026-09-24
topic: brand-campaign-engagement-plan-ia
artifact_contract: ce-unified-plan/v1
artifact_readiness: requirements-complete
product_contract_source: brainstorm (written by hand in the ce-brainstorm format; the skill was not available in the session)
origin: docs/ideation/2026-09-24-brand-campaign-engagement-plan-ia-ideation.html, ideas 2 to 7
companion: docs/brainstorms/2026-09-24-brand-campaigns-index-requirements.md (idea 1, the hierarchy's data model)
execution: none (requirements only; no Planning Contract yet)
---

# Brand / Engagement Plan / Campaign / Flow IA, Ideas 2 to 7 - Requirements

## Goal Capsule

- **Objective:** Omni OS reads as one hierarchy: **Brand › Engagement Plan › Campaign › Flow**. It uses one vocabulary, one navigation shell (the Cockpit), and one way to create each level. Every campaign can say which approved brand content it was built from, and every flow is stored and edited the same way.
- **Means:** Six changes on top of idea 1's hierarchy: naming (2), breadcrumb shell (3), creation at each level (4), kit snapshot per campaign (5), one flow model (6), and a brand overview (7).
- **Product authority:** Requirements complete. The user settled the model and every decision on 2026-09-24, and this is ready for a Planning Contract.

### The model (user, 2026-09-24)

```
Brand                      ← brief + brand kit (outside every engagement plan)
 └─ Engagement Plan  ×N    ← e.g. one per quarter
     └─ Campaign     ×N    ← may have one Campaign Plan (the orchestrator's phased document)
         └─ Flow     ×N
```

Settled decisions:

- **D1. Naming.** "Engagement Plan" is a container under the brand, but the brief and kit stay outside it. A brand has many engagement plans. The orchestrator's document is renamed "Campaign Plan".
- **D2. Shell.** The Cockpit becomes the one shell.
- **D3. Multiplicity.** A brand has many engagement plans, each has many campaigns, and each campaign has many flows.
- **D4. Provenance.** A whole snapshot of the brand content per campaign.
- **D5. Flow model.** Every flow uses a rules-built base plus structured edits.
- **From idea 1:** everything is created inside its parent; a campaign exists from creation; wiping the Journey deletes what it built; moving to another brand closes the old record and opens a new one.

---

## Sequencing

```
Idea 1 (hierarchy + index) ─┬─> Idea 2 (naming) ─┬─> Idea 4 (create at each level) ─> Idea 5 (snapshot at campaign creation)
                            │                    └─> Idea 3 (breadcrumb shell)
                            ├─> Idea 6 (one flow model, flows keyed by campaign; needed before idea 4's "+ New flow")
                            └─> Idea 7 (brand overview; labels wait on idea 2)
```

## What the code shows (corrections to the ideation)

| Idea | Ideation says | Code shows (commit `474799d`) | Effect on requirements |
|---|---|---|---|
| 2 | "Engagement plan" appears only in 5 files | 42 mentions across 28 files: 20 backend modules, 7 `frontend/` views, `cockpit/src/agents.ts`, `app/server.py` | User-visible copy and internal identifiers are handled separately. |
| 3 | Two apps: Cockpit and `frontend/` | Four front ends are served: `/` (`frontend/`, the default landing page), `/cockpit`, `/legacy` (old static JS) and `/hcp360` (data review page) | The shell covers `/` and `/cockpit`. `/legacy` and `/hcp360` are named explicitly. |
| 4 | Both back ends exist and just need routing | True. But `POST /api/projects` takes only a name, and the brand is inferred later from the intake chat | Creation binds each level to its parent up front. |
| 5 | `brand_ctx()` reads live kit state | True, and the kit has no version history: `brand_kit.kit_file_mtime()` (the whole file's modified time) is the only "last updated" signal | The campaign carries its own copy; there is no kit version to point at. |
| 6 | Two independent flow builders | One builder: the Journey calls `campaign_ops.build_campaign_plan(brand_ctx(b), use_llm=False)` (`brand_journey.py:799`). Only storage and editing differ: projects save a `WorkflowDocument` as a full overwrite (`PATCH /api/projects/{pid}/campaign-plan-layout`); the Journey stores a `CampaignFlow` plus kept operations, one per brand | Unification is one stored shape and one editing model, keyed by flow. |
| 7 | No rollup view exists | The `frontend/` landing page has a per-brand dashboard (`strategy/dashboard.py`, `GET /api/home`) with campaign counts, for the market-intel roster, not brand kits. The Cockpit has none | The brand overview is new in the Cockpit, and the old dashboard's count moves onto idea 1's identity. |

---

## Idea 2. One vocabulary

### Summary

Today "engagement plan" names only the orchestrator's document, while users also mean a period's programme of campaigns.
Each word should mean one thing, matching the user's model.

### Key Decisions

- **N-KD1. Six terms, one meaning each** (N-R1). "Engagement Plan" is the period container, and "Campaign Plan" is the orchestrator's document. (session-settled: user-directed, D1.)
- **N-KD2. Rename what users see; leave internal identifiers alone.** Routes, function names, database columns and prompt keys keep their names. Only on-screen copy, exported documents and generated text change. (proposed — contains the 28-file blast radius and keeps the change reversible.)
- **N-KD3. One glossary is the source of truth**, used by the UI copy of both front ends, agent prompts and exports. (proposed.)

### Requirements

- N-R1. The product uses these terms:
  - **Brand** — the owning entity, with its brief and brand kit.
  - **Brand kit** — the brand's approved content: audiences, message house, compliance.
  - **Engagement Plan** — a brand's programme of campaigns for a period, for example "Q3 2026". A brand has many.
  - **Campaign** — one initiative inside an engagement plan.
  - **Campaign Plan** — the orchestrator's phased document for one campaign. It is optional.
  - **Flow** — one channel-by-channel sequence inside a campaign. A campaign has many.
- N-R2. Every user-visible "(Brand) Engagement Plan" that refers to the orchestrator's document now says "Campaign Plan". This covers the `frontend/` views, `cockpit/src/agents.ts`, exports (`strategy/plan_document.py`, `strategy/plan_export.py`) and agent narration.
- N-R3. Agent prompts describe what is being written with the new terms, so generated text doesn't bring the old name back.
- N-R4. "Engagement Plan" appears only for the period container (N-R1).
- N-R5. Existing saved and exported plans keep working and re-render with the new title. No stored data is rewritten.
- N-R6. The glossary lives in one place, and both front ends and the prompts draw their labels from it.

### Acceptance Examples

- N-AE1. **Given** a finished orchestrator plan, **when** it is exported, **then** its title reads "Campaign Plan".
- N-AE2. **Given** the new copy, **when** user-visible strings and prompts are searched, **then** "engagement plan" only ever means the period container.

### Scope Boundaries

- Renaming routes, modules, database columns or JSON keys.

---

## Idea 3. One shell with a four-level breadcrumb

### Summary

The Cockpit becomes the only entry point.
A breadcrumb shows where you are (Brand › Engagement Plan › Campaign › Flow), and the left nav re-scopes to the current level.

### Key Decisions

- **S-KD1. The Cockpit is the shell.** (session-settled: user-directed, D2.) The `frontend/` four-stage workspace (Planning, Orchestration, Operations, Reporting) becomes the Campaign Plan view inside a campaign.
- **S-KD2. Migrate one level at a time.**
  1. Brand level: exists today.
  2. Engagement Plan and Campaign levels: new, built on idea 1's reads.
  3. The Campaign Plan view.

  Until the Campaign Plan view is ported, opening it shows the existing `frontend/` workspace for that campaign's project, with the Cockpit breadcrumb above it. (proposed — avoids a big-bang rewrite of the largest UI.)
- **S-KD3. `/` becomes the Cockpit once a Campaign Plan is reachable from it.** `/legacy` and `/hcp360` stay as they are. (proposed.)

### Requirements

- S-R1. Every screen below the brand list shows the breadcrumb path, for example: Oncomyra › Q3 2026 › HCP launch › Email nurture. Each crumb is clickable.
- S-R2. The levels, and what each one shows:
  - **Brand:** overview (idea 7), brief and kit (the Journey), and its engagement plans.
  - **Engagement Plan:** its period, status and campaigns.
  - **Campaign:** its Campaign Plan, if any, and its flows.
  - **Flow**, or the **Campaign Plan** document.
- S-R3. The left nav shows the current level's items: brands at the top, a brand's engagement plans inside a brand, a plan's campaigns inside a plan, and a campaign's flows and Campaign Plan inside a campaign.
- S-R4. There is one entry point. The app lands on the brand list, and everything is reached through its parents.
- S-R5. Links and bookmarks to `/`, `/v2` and `/cockpit` keep working and land somewhere sensible.
- S-R6. `/legacy` and `/hcp360` are untouched.
- S-R7. The browser back button follows the levels.

### Acceptance Examples

- S-AE1. **Given** Oncomyra › Q3 2026 › HCP launch has a Campaign Plan in its Select phase, **when** A1 opens the app, **then** they reach it through those four levels, with the breadcrumb at each step.
- S-AE2. **Given** a bookmark to `/v2`, **when** it is opened after the change, **then** it lands in the Cockpit, not on a broken page.

### Scope Boundaries

- Porting every `frontend/` stage into Cockpit components in one go (S-KD2 phases it).
- `/legacy` and `/hcp360`.

---

## Idea 4. Create at each level

### Summary

Each level has one "+ New" action, and each new record is born inside its parent.
The ideation's "formal vs ad-hoc" fork becomes a choice when creating a campaign: with a Campaign Plan, or flows only.

### Key Decisions

- **F-KD1. Three actions:**
  - "+ New engagement plan" on a brand;
  - "+ New campaign" in an engagement plan;
  - "+ New flow" in a campaign.

  (session-settled: follows D3 and idea 1's "created inside its parent".)
- **F-KD2. A new campaign offers two starts, described by outcome, not by engine:**
  - "With a campaign plan — phased, reviewed at each step" starts the orchestrator.
  - "Flows only — go straight to channel sequences" starts with an empty flow list.

  A flows-only campaign can start a Campaign Plan later. (proposed.)
- **F-KD3. New flows are rules-built from the brand's confirmed Brief, Audience and Message**, then refined by structured edits (idea 6). (session-settled: D5.)

### Requirements

- F-R1. A brand has "+ New engagement plan", asking for a name and an optional period (see idea 1, Q6).
- F-R2. An engagement plan has "+ New campaign", asking for a name and the F-KD2 choice, with one line explaining each option.
- F-R3. **With a campaign plan:** creates the campaign and a project already bound to it, and opens the Campaign Plan at its first phase. The intake chat never asks for the brand.
- F-R4. A campaign has "+ New flow", asking for a name. It builds the flow by rules from the brand's confirmed Brief, Audience and Message (using the campaign's snapshot, idea 5) and opens it with chat edits.
- F-R5. If the brand's Brief, Audience or Message is not confirmed, "+ New flow" says what is missing and links to those Journey steps instead of failing. Creating engagement plans, campaigns and Campaign Plans stays available.
- F-R6. The old way of starting a plan (the `frontend/` home intake) goes away or starts by picking a brand, engagement plan and campaign. No path creates a plan outside the hierarchy.
- F-R7. Anything created appears immediately in its parent's list and the brand overview (idea 7).

### Acceptance Examples

- F-AE1. **Given** Oncomyra › Q3 2026 › HCP launch, **when** A1 adds flows "Email nurture" and "Rep follow-up", **then** the campaign lists both.
- F-AE2. **Given** a brand whose Message is unconfirmed, **when** A1 tries "+ New flow", **then** they see "Needs: Message" with a link to that step, and no flow is created.
- F-AE3. **Given** A1 creates a campaign "with a campaign plan", **when** the intake chat starts, **then** it does not ask which brand this is for.

### Scope Boundaries

- Templates, or cloning a past engagement plan or campaign.
- Converting a flow into a Campaign Plan or the other way round.

---

## Idea 5. Every campaign records the brand content it was built from

### Summary

A campaign records the exact brand content (brief, audiences, message, kit) it was built from, so you can tell when the brand's approved content changes afterwards.
Its flows and Campaign Plan read from that record, not the live kit.

### Key Decisions

- **P-KD1. Whole snapshot at campaign creation.** The kit has no version history, so the campaign stores its own copy. Field-level citation and "locked vs local" fields are later refinements. (session-settled: user-approved, D4 — chosen over field-level citation.)
- **P-KD2. Drift is shown, not auto-fixed.** (proposed.)
- **P-KD3. A campaign can take a new snapshot on request.** It then shows exactly what changed, and its flows are rebuilt from the new snapshot with their kept edits reapplied (idea 6). (proposed.)

### Requirements

- P-R1. When a campaign is created, it stores a snapshot of:
  - the brand's Brief answers;
  - its audiences and personas;
  - its message house (core claim, pillars, proof points);
  - its compliance kit (dos, don'ts, approved indication, safety reference);
  - when the snapshot was taken.
- P-R2. The snapshot never changes by itself. Each Campaign Plan version records which snapshot it used.
- P-R3. A campaign shows whether the brand's current content differs from its snapshot, and in which parts: Brief, Audience, Message or Kit.
- P-R4. From a flagged campaign, A1 can compare the snapshot and the current value for each changed field side by side, and choose "Update to current content" (P-KD3).
- P-R5. Flows and the Campaign Plan read brand content from the campaign's snapshot. A brand edit never silently changes a campaign.
- P-R6. Campaigns created before this ships show "Built before content tracking", not a false "up to date".

### Acceptance Examples

- P-AE1. **Given** a campaign built when the core claim was "A", **when** the brand's claim becomes "B", **then** the campaign is flagged "Message changed since this campaign was built", and its flows still use "A".
- P-AE2. **Given** A1 chooses "Update to current content", **when** its flows rebuild, **then** they use "B", and every kept edit whose target still exists is reapplied.

### Scope Boundaries

- Field-level citation, locked vs local fields, and git-style branching of the kit.
- MLR approval of the drift itself.

---

## Idea 6. One flow model, keyed by flow

### Summary

Every flow is stored and edited the same way, wherever it came from.
Both kinds are already built by the same builder; they diverge only in storage and editing.

### Key Decisions

- **U-KD1. The Journey's model, for all flows:** a rules-built base, an ordered list of kept structured edits, a pending draft edit, and stable block codes. (session-settled: user-directed, D5.) **Amended 2026-09-24 (user decision during build):** the Campaign Plan's Operations diagram keeps its full editor and is stored as a "document" flow of its campaign. Unifying it with the rules model is deferred. U-R5 and U-R7 below are superseded for Operations diagrams.
- **U-KD2. A flow is its own record inside a campaign.** It is no longer "the brand's flow" (Journey) or "the project's layout" (Operations stage). (session-settled: follows D3.)

### Requirements

- U-R1. Every flow stores:
  - its campaign;
  - its inputs (the campaign's snapshot, idea 5);
  - its rules-built base;
  - its ordered kept edits;
  - any pending draft edit;
  - its block codes.
- U-R2. Every flow is edited the same way: structured operations (add, remove, connect, change), from chat or the canvas, landing as a draft to keep or undo.
- U-R3. Rebuilding a flow regenerates the base from its inputs and reapplies kept edits by block code. An edit whose target is gone is dropped and reported.
- U-R4. Every flow renders in the same flow builder, with the same rule on whether the canvas edits directly.
- U-R5. Existing Operations-stage layouts (`campaign_plan_layout` on projects) become flows in their campaign and look the same. A layout that can't be expressed as a base plus edits is kept as a frozen base with no edit history, not discarded.
- U-R6. Each brand's existing Journey flow becomes a flow record in its campaign (idea 1, R20), keeping its block codes and kept edits.
- U-R7. The Operations agent keeps changing flows by chat, now through U-R2's structured operations.

### Acceptance Examples

- U-AE1. **Given** a flow with blocks B1 to B6, **when** A1 adds a follow-up by chat and the flow is rebuilt, **then** B1 to B6 keep their codes and the follow-up is reapplied.
- U-AE2. **Given** a project with a hand-edited Operations layout, **when** it opens after migration, **then** the diagram looks the same.

### Scope Boundaries

- Changing the flow node vocabulary.
- Executing flows in a marketing-automation system.

---

## Idea 7. Brand overview

### Summary

A brand's first screen shows everything under it: engagement plans, their campaigns and flows, and status rolled up child to parent.
This is the Brand level of the shell (idea 3).

### Key Decisions

- **R-KD1. Status and counts first; performance metrics later.** Nothing in the app measures campaign results yet (no send or response data). (proposed.)
- **R-KD2. Status rolls up child to parent.** A flow's status feeds its campaign, and a campaign's status feeds its engagement plan. (proposed.)
- **R-KD3. The `frontend/` landing dashboard's campaign count reads from idea 1's hierarchy**, so both agree. (proposed.)

### Requirements

- R-R1. The brand overview lists its engagement plans, newest period first. Each shows its period, status, number of campaigns, number of flows, and how many campaigns have drifted content (idea 5).
- R-R2. Expanding an engagement plan lists its campaigns: name, status, whether it has a Campaign Plan, number of flows, drift, and last updated time.
- R-R3. The overview shows a summary line: active engagement plans, open campaigns, total flows, and campaigns with drift.
- R-R4. Each brand in the sidebar shows its number of active engagement plans.
- R-R5. Filters: engagement plan status, campaign status, and "has drift".
- R-R6. A brand with no engagement plans shows an empty state leading to "+ New engagement plan".
- R-R7. The `frontend/` landing dashboard's counts match R-R1's.

### Acceptance Examples

- R-AE1. **Given** Oncomyra with "Q2 2026" (closed, 1 campaign) and "Q3 2026" (active, 2 campaigns, 5 flows), **when** A1 opens Oncomyra, **then** the overview lists both plans with those counts, and the sidebar badge reads 1.
- R-AE2. **Given** the same data, **when** the `frontend/` landing dashboard loads, **then** its counts for Oncomyra match.

### Scope Boundaries

- Campaign performance metrics (reach, engagement, new patient starts).
- Cross-brand portfolio rollups.

---

## Decisions

| # | Decision | Status |
|---|---|---|
| D1 | Naming: Engagement Plan is a container under the brand (brief and kit outside), and the orchestrator's document is "Campaign Plan" | Settled (user) |
| D2 | Shell: the Cockpit | Settled (user) |
| D3 | Multiplicity: many plans per brand, many campaigns per plan, many flows per campaign | Settled (user) |
| D4 | Provenance: a whole snapshot of the brand content per campaign | Settled (user) |
| D5 | Flow model: a rules-built base plus structured edits | Settled (user) |

Idea 1's Q5 to Q7 are also settled: the Journey's Flow step creates the brand's first engagement plan and campaign; a period is optional; existing work goes into one "Earlier work" plan per brand. No open decisions remain.

## Sources / Research

- Ideation: `docs/ideation/2026-09-24-brand-campaign-engagement-plan-ia-ideation.html`.
- Idea 1: `docs/brainstorms/2026-09-24-brand-campaigns-index-requirements.md`.
- Naming: `strategy/plan_document.py`, `strategy/plan_export.py`, `strategy/orchestrator.py`, `strategy/studio_run.py`, `cockpit/src/agents.ts`, `frontend/src/workspace/{PlanDocument,PlanSummaryCard,SimplePlanSummary,Workspace}.tsx`.
- Shells and routes: `app/server.py` (`/`, `/v2`, `/cockpit`, `/legacy`, `/hcp360`), `cockpit/src/App.tsx`, `frontend/src/`.
- Plan creation: `app/server.py` `POST /api/projects` (name only), `slots.brand` in project state.
- Kit and provenance: `strategy/brand_kit.py` (`kit_file_mtime`), `strategy/brand_journey.py` (`brand_ctx`).
- Flows: `strategy/campaign_ops.py` (`build_campaign_plan`), `strategy/brand_journey.py` (flow build at line 799, `FLOW_NODE_TYPES`, block codes, operations), `app/server.py` campaign-plan-layout routes, `frontend/src/workspace/stages/operations/flowbuilder/`.
- Dashboard: `strategy/dashboard.py`, `GET /api/home`, `strategy/campaign_store.py` (`campaign_counts_by_brand`).
