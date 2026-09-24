---
title: Brand / Campaign / Engagement Plan IA, Ideas 2 to 7 - Requirements
type: feat
date: 2026-09-24
topic: brand-campaign-engagement-plan-ia
artifact_contract: ce-unified-plan/v1
artifact_readiness: requirements-only
product_contract_source: brainstorm (written by hand in the ce-brainstorm format; the skill was not available in the session)
origin: docs/ideation/2026-09-24-brand-campaign-engagement-plan-ia-ideation.html, ideas 2 to 7
companion: docs/brainstorms/2026-09-24-brand-campaigns-index-requirements.md (idea 1)
execution: none (requirements only; no Planning Contract yet)
---

# Brand / Campaign / Engagement Plan IA, Ideas 2 to 7 - Requirements

## Goal Capsule

- **Objective:** Omni OS reads as one hierarchy: Brand, then its campaigns, then each campaign's plan or flow. It uses one vocabulary, one way to start a campaign, one navigation shell, and one flow representation. Every campaign can say which approved brand content it was built from.
- **Means:** Six changes that build on the campaigns index (idea 1): one naming model (idea 2), one breadcrumb shell (idea 3), a "+ New campaign" fork (idea 4), a kit snapshot per campaign (idea 5), one flow representation (idea 6), and a per-brand campaigns view (idea 7).
- **Product authority:** Requirements only. Each idea has its own section. A decision marked **proposed** needs the user's confirmation; the Decisions to Confirm list at the end gathers them.
- **Settled already (idea 1, user, 2026-09-24):** a plan is always created inside a brand; a plan campaign exists from creation; wiping a brand's Journey deletes its flow campaign; moving a plan to another brand closes the old campaign and opens a new one.

---

## Sequencing

```
Idea 1 (campaigns index) ─┬─> Idea 2 (naming) ─┬─> Idea 4 (+ New campaign fork) ─> Idea 5 (kit snapshot at creation)
                          │                    └─> Idea 3 (one breadcrumb shell)
                          ├─> Idea 7 (per-brand campaigns view; labels wait on idea 2)
                          └─> Idea 6 (one flow representation; independent of 2 to 4)
```

- Idea 2 comes first after idea 1, because ideas 3, 4 and 7 all put its words on screen.
- Idea 5's snapshot is stamped at creation, so it ships with or right after idea 4.
- Idea 6 touches storage only and can run in parallel.

## What the code shows (corrections to the ideation)

The ideation is mostly right about the problems. Checking its claims against the code (commit `33d8632`) changes these details:

| Idea | Ideation says | Code shows | Effect on requirements |
|---|---|---|---|
| 2 | "Engagement plan" appears only in 5 files | 42 mentions across 28 files: 20 backend modules, 7 `frontend/` views, `cockpit/src/agents.ts`, and `app/server.py` | The rename is wider than it looks. The requirements separate user-visible copy from internal identifiers. |
| 3 | Two apps: Cockpit and `frontend/` | Four front ends are served: `/` (`frontend/` built to `static/v2`, the default landing page), `/cockpit`, `/legacy` (old static JS, kept for rollback) and `/hcp360` (standalone data review page) | The shell decision covers `/` and `/cockpit`. `/legacy` and `/hcp360` are named explicitly. |
| 4 | Both back ends exist and just need routing | True. But a formal plan is created with only a name (`POST /api/projects`), and its brand is inferred later from the intake chat (`slots.brand`) | The fork must pass the brand into the plan at creation. The idea 1 decision already requires this. |
| 5 | `brand_ctx()` reads live kit state | True. The kit also has no version history at all: `brand_kit.kit_file_mtime()` is the only "last updated" signal, and it covers the whole `config/brand_kits.json` file | A snapshot cannot point at a "kit version" that doesn't exist. The requirements have the campaign carry its own copy. |
| 6 | `campaign_ops.py` and `brand_journey.py` build flow graphs independently | Both use the same builder. The Journey calls `campaign_ops.build_campaign_plan(brand_ctx(b), use_llm=False)` (`brand_journey.py:799`) and adds block codes and structured edits on top. What differs is storage and editing: projects save a converted `WorkflowDocument` as a full-document overwrite (`PATCH /api/projects/{pid}/campaign-plan-layout`), while the Journey stores the `CampaignFlow` plus an ordered list of kept operations | Unification is about one stored representation and one editing model, not one builder. |
| 7 | No rollup or cross-campaign view exists | A per-brand dashboard exists on the `frontend/` landing page (`strategy/dashboard.py`, `GET /api/home`), with campaign counts from `campaign_store.campaign_counts_by_brand()`. It covers the market-intel roster (`config/client_brands.json`), not brand kits. The Cockpit has none | Idea 7 adds a campaigns view per brand kit, and the old dashboard's count moves onto the idea 1 identity. |

---

## Idea 2. Resolve the "engagement plan" naming collision

### Summary

Today "engagement plan" names only the orchestrator's long narrative document. Users also think of a brand's whole programme, and of the Journey's flow, as their engagement plan.
One word should mean one thing.

### Key Decisions

- **N-KD1. Shape (a): Engagement Plan is the brand-level container above campaigns.** The orchestrator's document is renamed **Campaign Plan** and belongs to one campaign. A brand has one Engagement Plan: its brief and kit, plus the set of its campaigns. (proposed — shape (a) matches the Salesforce, Adobe and Veeva pattern in the ideation and fits "a plan is always created inside a brand". The ideation's shape (b), one object with a document view and a flow view, and shape (c), strict Engagement Plan → Campaign → Flow containment, are the alternatives. See D1.)
- **N-KD2. Rename the words users see; leave internal identifiers alone.** Routes, function names, database columns and prompt keys keep their current names. Only on-screen copy and exported documents change. (proposed — this contains the 28-file blast radius and keeps the change reversible.)
- **N-KD3. One glossary is the source of truth.** A short glossary sets every term (Brand, Engagement Plan, Campaign, Campaign Plan, Flow) and is used by UI copy, agent prompts and exports. (proposed.)

### Requirements

- N-R1. The product uses five terms with one meaning each:
  - **Brand** — the owning entity with its brand kit.
  - **Engagement Plan** — a brand's whole programme: its brief, kit and campaigns.
  - **Campaign** — one unit of work under a brand.
  - **Campaign Plan** — the orchestrator's phased narrative document for one campaign.
  - **Flow** — the channel-by-channel sequence for one campaign.
- N-R2. Every user-visible string that currently says "(Brand) Engagement Plan" for the orchestrator's document now says "Campaign Plan". This covers the 7 `frontend/` views, `cockpit/src/agents.ts`, exported documents (`strategy/plan_document.py`, `strategy/plan_export.py`) and agent narration.
- N-R3. Agent prompts that tell the model what it is writing use the new terms, so generated text doesn't reintroduce the old name.
- N-R4. "Engagement Plan" appears only where the brand-level programme is meant (N-R1). Until idea 3 or 7 gives it a screen, it appears nowhere.
- N-R5. Existing exported documents and saved plans keep working. Old plans re-render with the new title; no stored data is rewritten.
- N-R6. The glossary lives in one place in the repo, and both front ends and the agent prompts draw their labels from it.

### Acceptance Examples

- N-AE1. **Given** a finished orchestrator plan, **when** it is exported, **then** its title reads "Campaign Plan", not "Brand Engagement Plan".
- N-AE2. **Given** the renamed copy, **when** a search of user-visible strings and prompt text is run, **then** "engagement plan" appears only in the sense of N-R1.

### Scope Boundaries

- Renaming routes, modules, database columns or JSON keys.
- Building the Engagement Plan screen itself (ideas 3 and 7).

---

## Idea 3. One breadcrumb, Brand > Campaign > Flow, one shell

### Summary

There is one entry point and one navigable hierarchy instead of separate apps.
A breadcrumb shows where you are. The left nav re-scopes to the level you are at.

### Key Decisions

- **S-KD1. The Cockpit is the surviving shell.** It is already brand-first, has the Journey and the new visual design, and every recent change went there. The `frontend/` app's four-stage workspace (Planning, Orchestration, Operations, Reporting) becomes the Campaign Plan view inside it. (proposed — see D2; the alternative is to keep `frontend/` as the shell and add brands to it.)
- **S-KD2. Migrate in place, one level at a time.** Brand level first (the existing Cockpit), then Campaign level (idea 7's list plus a campaign page), then the Campaign Plan view. Until the Campaign Plan view is ported, it opens the existing `frontend/` workspace for that campaign's project, scoped by the breadcrumb. (proposed — avoids a big-bang rewrite of the largest UI.)
- **S-KD3. `/` becomes the Cockpit once the Campaign Plan view is reachable from it.** `/legacy` and `/hcp360` stay reachable as they are. (proposed.)

### Requirements

- S-R1. Every screen below the brand list shows a breadcrumb of the path from the brand, for example: Oncomyra › Q3 HCP launch › Flow. Each crumb is clickable.
- S-R2. There are three levels:
  - **Brand:** the workspace, Journey, and the list of campaigns (idea 7).
  - **Campaign:** the campaign's overview, with its Campaign Plan or Flow.
  - **Artifact:** the Campaign Plan document or the Flow.
- S-R3. The left nav shows the items for the current level: the brand list at the top, the brand's sections inside a brand, and the campaign's sections inside a campaign.
- S-R4. There is one entry point. Opening the app lands on the brand list, and every campaign and plan is reached from its brand.
- S-R5. Links and bookmarks to `/`, `/v2` and `/cockpit` keep working and land somewhere sensible in the new shell.
- S-R6. `/legacy` and `/hcp360` are untouched.
- S-R7. The browser back button follows the breadcrumb levels.

### Acceptance Examples

- S-AE1. **Given** Oncomyra has a Campaign Plan in its Select phase, **when** A1 opens the app, **then** they reach it by Oncomyra › campaign › Campaign Plan, with the breadcrumb visible at each step.
- S-AE2. **Given** a bookmark to `/v2`, **when** it is opened after the change, **then** it lands in the new shell, not on a broken page.

### Scope Boundaries

- Porting every `frontend/` stage into Cockpit components in one go (S-KD2 phases it).
- `/legacy` and `/hcp360`.

---

## Idea 4. "+ New campaign": formal Campaign Plan or ad-hoc Flow

### Summary

Inside a brand, one "+ New campaign" button asks one question: do you want a full phased Campaign Plan, or a quick Flow?
Both back ends already exist.

### Key Decisions

- **F-KD1. The button lives on the brand, and the brand is fixed at creation.** This follows the idea 1 decision "a plan is always created inside a brand". (session-settled: follows the user's idea 1 answer.)
- **F-KD2. Two choices, described by outcome, not by engine.**
  - "Full campaign plan — phased, reviewed at each step" runs the orchestrator.
  - "Quick flow — a ready-to-edit channel sequence" runs the rules-built flow.

  (proposed.)
- **F-KD3. A brand can have many campaigns of either kind.** This lifts the Journey's one-flow-per-brand limit for flows created through this button. The Journey's own Flow step stays as the brand's first flow. (proposed — see D3; it needs flow storage keyed by campaign, not by brand, which ties into idea 6.)

### Requirements

- F-R1. Every brand has a "+ New campaign" action, reachable from the brand level of the shell (idea 3), or from the Cockpit brand workspace until then.
- F-R2. The action asks for a campaign name and the choice in F-KD2, with one line explaining each option.
- F-R3. **Campaign Plan:** creates a project already bound to the brand, so the brand is never typed or inferred from chat. It creates the campaign record (idea 1) and opens the Campaign Plan at its first phase.
- F-R4. **Flow:** creates a campaign whose flow is built by rules from the brand's confirmed Brief, Audience and Message. It opens in the flow view with chat edits (the Journey's Flow step behaviour).
- F-R5. If the brand's Brief, Audience and Message are not yet confirmed, the Flow option says what is missing and links to those Journey steps instead of failing. The Campaign Plan option stays available.
- F-R6. The old way of starting a plan (the `frontend/` home intake) either goes away or asks for a brand first. No path creates a plan without a brand.
- F-R7. Both kinds appear immediately in the brand's campaign list (idea 7).

### Acceptance Examples

- F-AE1. **Given** Oncomyra with a confirmed Brief, Audience and Message, **when** A1 picks "Quick flow" and names it "Q4 reactivation", **then** a second flow campaign exists under Oncomyra, next to the Journey's flow.
- F-AE2. **Given** a brand whose Message is unconfirmed, **when** A1 picks "Quick flow", **then** they see "Needs: Message" with a link to that step, and no campaign is created.
- F-AE3. **Given** A1 picks "Full campaign plan", **when** the intake chat starts, **then** it does not ask which brand this is for.

### Scope Boundaries

- Converting one kind into the other after creation.
- Templates or cloning of past campaigns.

---

## Idea 5. Every campaign records the brand content it was built from

### Summary

A campaign records the exact brand kit, message and audience it was built from. You can then tell when the brand's approved content has changed since.
In pharma, this is the difference between "this email uses the approved claim" and not knowing.

### Key Decisions

- **P-KD1. Whole snapshot at creation, stored with the campaign.** The kit has no version history (see the corrections table), so the campaign stores its own copy of the brand content it used. Field-level citation and "locked vs local" fields are later refinements. (proposed — see D4. This is the ideation's own "simplest variant that closes the gap".)
- **P-KD2. New campaigns require a confirmed kit source.** A Flow needs a confirmed Brief, Audience and Message (see F-R5). A Campaign Plan snapshots whatever the brand kit holds at creation and flags it as unconfirmed if the Journey steps are not confirmed. (proposed.)
- **P-KD3. Drift is shown, not auto-fixed.** When the brand's content changes, campaigns built on the old content are flagged. Nothing is rebuilt automatically. (proposed.)

### Requirements

- P-R1. On creation, a campaign stores a snapshot of the brand content it uses:
  - the Brief answers (indication, lifecycle stage, objective, success measure, branded or unbranded);
  - the audiences and personas;
  - the message house (core claim, pillars, proof points);
  - the compliance kit (dos, don'ts, approved indication, safety reference);
  - when the snapshot was taken.
- P-R2. The snapshot never changes after creation. Regenerating a Campaign Plan (a new version under idea 1) takes a new snapshot for that version.
- P-R3. A campaign shows whether the brand's current content differs from its snapshot, and which parts: Brief, Audience, Message or Kit.
- P-R4. From a flagged campaign, A1 can see a side-by-side comparison of the snapshot and the current value for each changed field.
- P-R5. The flow builder and the Campaign Plan read brand content from the campaign's snapshot, not the live kit. A brand edit therefore never silently changes a campaign.
- P-R6. Campaigns created before this ships have no snapshot. They show "Built before content tracking", not a false "up to date".

### Acceptance Examples

- P-AE1. **Given** a flow campaign built when the core claim was "A", **when** the brand's claim is changed to "B", **then** the campaign is flagged "Message changed since this campaign was built", and its flow still shows "A".
- P-AE2. **Given** a Campaign Plan regenerated after the change, **when** its versions are compared, **then** version 1 carries "A" and version 2 carries "B".

### Scope Boundaries

- Field-level citation, "locked vs local" fields, and git-style branching of the kit.
- MLR approval workflow on the drift itself.

---

## Idea 6. One flow representation

### Summary

A campaign's flow is stored and edited the same way whether it came from a Campaign Plan or a quick Flow.
Today both are built by the same builder but diverge afterwards, so improvements to one don't reach the other.

### Key Decisions

- **U-KD1. Keep the Journey's model: a rules-built `CampaignFlow` plus an ordered list of structured edits, with stable block codes.** It is reproducible and auditable, and it survives rebuilds. The Campaign Plan's Operations stage moves onto it. (proposed — see D5; the alternative is the Operations stage's model, a freely edited `WorkflowDocument` saved as a full overwrite.)
- **U-KD2. Flows are keyed by campaign, not by brand or project.** This is what lets a brand have several flows (idea 4). (proposed.)

### Requirements

- U-R1. Every flow, from a Campaign Plan's Operations stage, the Journey's Flow step, or a quick Flow campaign (idea 4), is stored in one shape: the rules-built base, the ordered kept edits, any pending draft edit, and block codes.
- U-R2. Every flow is edited the same way: structured operations (add, remove, connect, change), from chat or from the canvas, landing as a draft to keep or undo.
- U-R3. Rebuilding any flow regenerates the base from its inputs and reapplies kept edits by block code. An edit whose target is gone is dropped and reported.
- U-R4. The canvas renders every flow with the same flow builder. Whether the canvas allows direct editing is decided once for all flows.
- U-R5. Existing saved Operations layouts (`campaign_plan_layout` on projects) keep opening. They are migrated to U-R1's shape; where a layout can't be expressed as a base plus operations, it is kept as a frozen base with no edit history, not discarded.
- U-R6. The Operations agent keeps its ability to change the flow by chat, now through U-R2's structured operations.

### Acceptance Examples

- U-AE1. **Given** a Campaign Plan's flow with blocks B1 to B6, **when** A1 adds a follow-up by chat and the plan is regenerated, **then** B1 to B6 keep their codes and the follow-up is reapplied.
- U-AE2. **Given** an existing project with a hand-edited Operations layout, **when** it is opened after migration, **then** the diagram looks the same.

### Scope Boundaries

- Changing the flow node vocabulary.
- Executing flows in a marketing-automation system.

---

## Idea 7. A brand's campaigns in one view

### Summary

Each brand shows all its campaigns in one place, both kinds, with status, and this is the brand level of the shell (idea 3).
The ideation's "N campaigns" badge on each brand in the sidebar comes with it.

### Key Decisions

- **R-KD1. Status and counts first; performance metrics later.** Nothing in the app measures campaign performance yet (no send or response data), so the first version rolls up status, not results. (proposed — the ideation's "rolled-up metrics" needs data that doesn't exist.)
- **R-KD2. The `frontend/` landing dashboard's campaign count reads from the idea 1 index.** The count then agrees with the brand's campaign list. (proposed.)

### Requirements

- R-R1. A brand's campaigns view lists every campaign of both kinds, using idea 2's words. Each row shows name, kind, status (draft, in progress, confirmed, closed), last updated time, and whether its content has drifted (idea 5).
- R-R2. The view can be filtered by kind and status and sorted by last updated.
- R-R3. Opening a campaign goes to its page at the Campaign level of the shell (idea 3).
- R-R4. The view shows a small summary: total campaigns, how many are in progress, and how many have drifted content.
- R-R5. Each brand in the sidebar shows its number of open campaigns.
- R-R6. The `frontend/` landing dashboard's campaign counts come from the same source as R-R1, so both agree.
- R-R7. A brand with no campaigns shows an empty state that leads to "+ New campaign" (idea 4).

### Acceptance Examples

- R-AE1. **Given** Oncomyra has two Campaign Plans (one closed) and one Flow, **when** A1 opens Oncomyra, **then** the view lists three campaigns, and the sidebar badge reads 2.
- R-AE2. **Given** the same data, **when** the `frontend/` landing dashboard loads, **then** its campaign count for Oncomyra matches.

### Scope Boundaries

- Campaign performance metrics such as reach, engagement or new patient starts.
- Cross-brand portfolio rollups.

---

## Decisions to Confirm

Each of these changes what gets built. The proposed answer is first:

- **D1 (idea 2).** Naming shape:
  - (a) Engagement Plan is the brand-level container, and the orchestrator's document becomes "Campaign Plan" (proposed);
  - (b) Campaign and Engagement Plan are one object with a document view and a flow view;
  - (c) strict Engagement Plan → Campaign → Flow containment.
- **D2 (idea 3).** Surviving shell: the Cockpit (proposed), or `frontend/`.
- **D3 (idea 4).** Can a brand have more than one flow campaign? Yes, through "+ New campaign" (proposed), or keep one flow per brand.
- **D4 (idea 5).** Provenance: a whole snapshot per campaign (proposed), or field-level citation from the start.
- **D5 (idea 6).** Flow model to standardise on: the Journey's rules-built base plus structured edits (proposed), or the Operations stage's freely edited document.

## Sources / Research

- Ideation: `docs/ideation/2026-09-24-brand-campaign-engagement-plan-ia-ideation.html`.
- Idea 1 requirements: `docs/brainstorms/2026-09-24-brand-campaigns-index-requirements.md`.
- Naming: `strategy/plan_document.py`, `strategy/plan_export.py`, `strategy/orchestrator.py`, `strategy/studio_run.py`, `cockpit/src/agents.ts`, and `frontend/src/workspace/{PlanDocument,PlanSummaryCard,SimplePlanSummary,Workspace}.tsx`.
- Shells and routes: `app/server.py` (`/`, `/v2`, `/cockpit`, `/legacy`, `/hcp360`), `cockpit/src/App.tsx`, `frontend/src/`.
- Plan creation: `app/server.py` `POST /api/projects` (name only), `slots.brand` in project state.
- Kit and provenance: `strategy/brand_kit.py` (`kit_file_mtime`, no version history), `strategy/brand_journey.py` (`brand_ctx`).
- Flows: `strategy/campaign_ops.py` (`build_campaign_plan`), `strategy/brand_journey.py` (flow at line 799, `FLOW_NODE_TYPES`, block codes, ops), `app/server.py` campaign-plan-layout routes, `frontend/src/workspace/stages/operations/flowbuilder/`.
- Dashboard: `strategy/dashboard.py`, `GET /api/home`, `strategy/campaign_store.py` (`campaign_counts_by_brand`).
