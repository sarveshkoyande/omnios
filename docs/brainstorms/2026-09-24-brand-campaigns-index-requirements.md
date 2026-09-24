---
title: Brand Hierarchy Index (Brand > Engagement Plan > Campaign > Flow) - Requirements
type: feat
date: 2026-09-24
topic: brand-campaigns-index
artifact_contract: ce-unified-plan/v1
artifact_readiness: requirements-only
product_contract_source: brainstorm (written by hand in the ce-brainstorm format; the skill was not available in the session)
origin: docs/ideation/2026-09-24-brand-campaign-engagement-plan-ia-ideation.html, idea 1 ("Give the brand a first-class campaigns table"), revised to the user's four-level hierarchy
companion: docs/brainstorms/2026-09-24-brand-campaign-ia-ideas-2-7-requirements.md (ideas 2 to 7)
execution: none (requirements only; no Planning Contract yet)
---

# Brand Hierarchy Index - Requirements

## Goal Capsule

- **Objective:** Every piece of campaign work sits in one hierarchy. You can list a brand's engagement plans, a plan's campaigns, and a campaign's flows.
- **Means:** One brand identity (the brand kit) and three stored levels under it: Engagement Plan, Campaign, Flow. The existing `campaign` table in `campaigns.db` is reused for campaigns. The orchestrator and the Brand Journey both write into the hierarchy.
- **Product authority:** This covers the data model, read APIs and a backfill of existing data. Naming, navigation, creation screens, provenance, the flow model and the brand view are ideas 2 to 7 in the companion doc.
- **Readiness:** Requirements only. Three open questions remain (Q5 to Q7).

---

## Product Contract

### Summary

The user's model (2026-09-24):

```
Brand                      ← brief + brand kit live here, outside any engagement plan
 └─ Engagement Plan  ×N    ← e.g. one per quarter
     └─ Campaign     ×N
         └─ Flow     ×N
```

Today none of this can be listed.
Formal plans and Journey flows are stored in different places, each with its own idea of what a "brand" is, and nothing connects them.
This work gives each level one record and one parent, so every later idea has something to stand on.

### Problem Frame

The ideation says no `brand_id` exists anywhere and no campaigns table exists. Reading the code corrects part of that:

- **A campaign table already exists.** `db/campaign_content_schema.sql` defines `campaign` (with `brand_id`, `project_id`, `status`) and `campaign_version`, in `campaigns.db`. `campaign_store.persist_campaign_from_result()` writes a row when an orchestrator plan finishes its Deploy phase (`app/server.py`). `strategy/dashboard.py` already counts campaigns per brand from it.
- **Only finished formal plans reach it.** In-progress projects are invisible, and Brand Journey flows (`journey_flow` in `brand_journey.db`, one row per brand) never reach it.
- **Re-running a plan duplicates the campaign.** Each Deploy inserts a new `campaign` row, and `campaign_version.version_no` is always 1.
- **Three brand identities disagree.**
  1. The Cockpit and Journey use the brand kit key (`config/brand_kits.json`, `brand_kit.canonical_key`, case-insensitive).
  2. `campaigns.db` has its own `brand` table, matched by exact case-sensitive name and seeded from the market-intel roster (`config/client_brands.json`).
  3. Orchestrator projects hold a free-typed `slots.brand` inside `state_json` (`strategy/projects.py`).
- **Nothing groups campaigns into plans, and nothing lets a campaign hold several flows.** There is no Engagement Plan level at all. Flows are stored one per brand (Journey) or one per project (the Operations stage's `campaign_plan_layout`).
- **Plans are created with only a name.** `POST /api/projects` takes a name, and the brand is inferred later from the intake chat. This is how the brand identities drift apart.

### Key Decisions

- **KD1. Four levels: Brand › Engagement Plan › Campaign › Flow.** A brand has many engagement plans, a plan has many campaigns, and a campaign has many flows. (session-settled: user-directed — "brand has multiple engagement plans, one per quarter let's say, each has multiple campaigns, each campaign has multiple flows".) Governs R1 to R6.
- **KD2. The brief and brand kit belong to the Brand, outside every engagement plan.** The Brand Journey's Brief, Audience, Message and Kit steps stay brand-level. (session-settled: user-directed — "brief and kit stay outside engagement plan".) Governs R7.
- **KD3. Nothing exists without its parent.** An engagement plan is always created inside a brand, a campaign inside an engagement plan, and a flow inside a campaign. None of them has a typed or inferred parent, and there is no "unassigned" level. (session-settled: user-directed — "a plan is always created inside a brand", extended to each level by KD1.) Governs R8, R9.
- **KD4. The brand kit key is the one brand identity.** `campaigns.db`'s own `brand` rows keep their market-intel, claims and content uses, but link to the kit key when a kit exists. (proposed.) Governs R10, R11.
- **KD5. Reuse the existing `campaign` table for Campaigns.** Engagement Plan and Flow are new records; there is no second campaigns table. (proposed.) Governs R2.
- **KD6. The orchestrator's phased document belongs to a Campaign, as its Campaign Plan.** A campaign has at most one Campaign Plan, versioned, and any number of flows. (session-settled: follows the user's idea 2 answer — the orchestrator's document is renamed "Campaign Plan".) Governs R12, R13.
- **KD7. Every level exists from the moment it is created.** A campaign with a Campaign Plan appears when the plan starts, not when Deploy completes. (session-settled: user-approved.) Governs R14.
- **KD8. Re-running a Campaign Plan adds a version, not a campaign.** (proposed.) Governs R15.
- **KD9. Moving a campaign to another brand closes it and opens a new one.** The new campaign is placed in an engagement plan the user picks under the new brand. (session-settled: user-directed — chosen over moving the same record.) Governs R16.
- **KD10. Wiping a brand's Journey deletes the flows the Journey created.** (session-settled: user-directed — chosen over archiving them.) Governs R19.

### Actors

- A1. Brand marketer: creates engagement plans, campaigns and flows under a brand, and wants to see them together.
- A2. Orchestrator: runs a phased Campaign Plan for a campaign (`strategy/orchestrator.py`, `app/server.py`).
- A3. Brand Journey: sets up the brand's brief and kit, and builds rules-based flows (`strategy/brand_journey.py`).
- A4. Startup bootstrap: backfills existing data idempotently on app start (`strategy/bootstrap.py`).

### Requirements

**Hierarchy**

- R1. There are four levels: Brand, Engagement Plan, Campaign, Flow. Each record at a level has exactly one parent at the level above.
- R2. Campaigns are stored in the existing `campaign` table in `campaigns.db`. Engagement plans and flows get their own records. No level is stored in two places.
- R3. An engagement plan carries its brand, a name, an optional period (start and end dates, for example a quarter), a status (active or closed), and created and updated times.
- R4. A campaign carries its engagement plan, a name, a status (draft, in progress, confirmed, closed), whether it has a Campaign Plan, and created and updated times.
- R5. A flow carries its campaign, a name, how it was made (Journey, Campaign Plan's Operations stage, or added by hand), its status, and created and updated times.
- R6. One read returns any level's children, newest first:
  - a brand's engagement plans;
  - a plan's campaigns;
  - a campaign's flows and its Campaign Plan.

  One further read returns a brand's whole tree.
- R7. The brief and brand kit stay on the brand. No engagement plan, campaign or flow stores its own copy (except idea 5's provenance snapshot).

**Parents are fixed at creation**

- R8. An engagement plan can only be created from an existing brand, a campaign only from an existing engagement plan, and a flow only from an existing campaign. No parent is typed or inferred from chat, and creation never creates a brand row or brand kit.
- R9. Existing projects whose brand matches no brand kit are legacy data. The backfill (R20) leaves them out of the hierarchy and lists them in its log for a one-time cleanup.

**Brand identity**

- R10. A brand is the brand kit's canonical key, matched case-insensitively (the same rule as `brand_journey._key`).
- R11. `campaigns.db`'s existing `brand` rows keep working for market intel, claims and content. Where a brand kit has the same name (case-insensitive), the row links to it, so each brand resolves to one identity.

**Campaign Plans**

- R12. A campaign can have one Campaign Plan: the orchestrator's phased document, stored as today on a project and linked to the campaign. A campaign without one is valid and is just its flows.
- R13. Starting a Campaign Plan binds its project to the campaign at creation. The intake chat never asks which brand it is for.
- R14. A campaign with a Campaign Plan exists from the moment the plan is started. Its status follows the plan's phase and becomes final when Deploy completes.
- R15. Re-running or regenerating a Campaign Plan adds a new version, with an incrementing version number, to the same campaign. It never adds a campaign.

**Moves and removal**

- R16. Moving a campaign to another brand closes it, and it stays listed as closed under the old brand. A new campaign opens in an engagement plan the user picks under the new brand, and later Campaign Plan versions attach to the new one.
- R17. Moving a campaign to another engagement plan of the same brand just moves it.
- R18. Writing any hierarchy record never blocks or breaks plan generation or the Journey. A failure is logged and repaired on the next write or at startup, matching the app's best-effort idiom.
- R19. Wiping a brand's Journey data (today only the developer script `scripts/reset_test_data.py`) deletes the flows the Journey created, not the brand's other campaigns or flows.

**Existing data**

- R20. On startup, a backfill runs idempotently and never deletes anything:
  - it links existing `campaign` rows to brand kits by name;
  - it creates campaigns for existing projects whose brand matches a kit and that have none (others go to R9);
  - it turns each brand's existing Journey flow into a flow record in a campaign;
  - it folds duplicate campaigns from re-runs of one project into one campaign with numbered versions;
  - it places everything it links or creates in an engagement plan for that brand (see Q7).

**Read API**

- R21. `GET /api/brands/{brand}/engagement-plans`, `GET /api/engagement-plans/{id}/campaigns` and `GET /api/campaigns/{id}/flows` return each level. `GET /api/brands/{brand}/tree` returns the whole hierarchy. An unknown id returns 404. Closed records are included and marked closed.

### Key Flows

- F1. A quarter's plan with a formal campaign
  - **Trigger:** A1 creates "Q3 2026" under Oncomyra, adds a campaign, and starts its Campaign Plan.
  - **Actors:** A1, A2
  - **Steps:** The plan and campaign appear immediately. The Campaign Plan's phases move the campaign's status. Deploy attaches the plan as version 1.
  - **Outcome:** Oncomyra › Q3 2026 › the campaign, with its Campaign Plan and any flows.
  - **Covered by:** R1, R6, R12 to R14
- F2. Several flows in one campaign
  - **Trigger:** A1 adds a second and a third flow to a campaign.
  - **Actors:** A1, A3
  - **Steps:** Each flow is created inside the campaign.
  - **Outcome:** The campaign lists three flows.
  - **Covered by:** R5, R6, R8
- F3. Campaign moved to another brand
  - **Trigger:** A1 moves a campaign from Oncomyra to Cardiovex and picks Cardiovex's "Q3 2026" plan.
  - **Actors:** A1
  - **Steps:** Oncomyra's copy is closed, and a new campaign opens under Cardiovex › Q3 2026.
  - **Outcome:** Both brands show an accurate history.
  - **Covered by:** R16
- F4. First start after this ships
  - **Trigger:** The app starts against existing `projects.db`, `campaigns.db` and `brand_journey.db`.
  - **Actors:** A4
  - **Steps:** The R20 backfill runs.
  - **Outcome:** Every brand shows its past plans and Journey flow inside the hierarchy. Legacy no-kit projects are logged. Running the backfill again changes nothing.
  - **Covered by:** R9, R20

### Acceptance Examples

- AE1. **Covers R1, R6.** **Given** Oncomyra has plans "Q2 2026" and "Q3 2026", Q3 has two campaigns, and one of those has three flows, **when** Oncomyra's tree is read, **then** it returns exactly that shape.
- AE2. **Covers R15.** **Given** a Campaign Plan run to Deploy twice, **when** its campaign is read, **then** there is one campaign with versions 1 and 2.
- AE3. **Covers R8, R13.** **Given** a new Campaign Plan, **when** A1 starts it from a campaign, **then** the intake does not ask for the brand, and no brand can be typed.
- AE4. **Covers R16.** **Given** a campaign under Oncomyra › Q3, **when** A1 moves it to Cardiovex › Q3, **then** Oncomyra lists it as closed and Cardiovex lists a new open campaign.
- AE5. **Covers R19.** **Given** a brand whose Journey built one flow and whose campaigns have two hand-added flows, **when** `scripts/reset_test_data.py` wipes the brand's Journey, **then** only the Journey-built flow is deleted.
- AE6. **Covers R18.** **Given** `campaigns.db` is unavailable, **when** A1 runs a plan phase or builds a flow, **then** both succeed, and the missing records appear after the next startup.
- AE7. **Covers R20.** **Given** duplicate campaign rows for one project, **when** the app starts twice, **then** the first start folds them into one campaign with versions, and the second changes nothing.

### Scope Boundaries

- Naming and copy (idea 2), navigation (idea 3), creation screens (idea 4), provenance (idea 5), the flow storage and editing model (idea 6), and the brand view (idea 7) are in the companion doc. This doc's read APIs are what those use.
- A UI for cleaning up legacy no-kit projects (R9 lists them; cleanup is manual).

### Dependencies / Assumptions

- `campaigns.db` is opened through `strategy/db.py`'s `connect("campaigns")`. Schema changes must work on SQLite and, where `DATABASE_URL` is set, Postgres.
- A project's brand is read from `slots.brand` in its `state_json` (`strategy/projects.py`). This only matters for the backfill, since new plans are bound at creation.
- `brand_kit.canonical_key` stays the single case-insensitive resolver for brand kit names.
- The backfill follows the existing idempotent `load_x()` pattern (`strategy/brand_lifecycle.py`, `strategy/hcp_360.py`), called from `strategy/bootstrap.py`.

### Outstanding Questions

Settled by the user on 2026-09-24:

- Q1. A plan with no brand kit → cannot arise: everything is created inside its parent (KD3). Legacy data only: R9.
- Q2. When a formal plan appears → as soon as it starts (KD7).
- Q3. Wiping a brand's Journey → delete what the Journey created (KD10).
- Q4. Moving to another brand → close and open a new one (KD9).

Open:

- Q5. **The Journey's Flow step.** Now that flows live inside campaigns, should the Journey's Flow step create the brand's first engagement plan and campaign, and put its flow there (proposed)? Or should the Journey end at Kit, with every flow made inside a campaign?
- Q6. **Engagement plan period.** Is a period (for example a quarter) optional (proposed), or required on every engagement plan?
- Q7. **Where existing data goes.** Should the backfill put each brand's existing campaigns and Journey flow into one engagement plan named "Earlier work" (proposed), or into one plan per calendar quarter based on when each was created?

### Sources / Research

- Ideation: `docs/ideation/2026-09-24-brand-campaign-engagement-plan-ia-ideation.html`.
- Existing campaign model: `db/campaign_content_schema.sql` (`brand`, `campaign`, `campaign_version`), `strategy/campaign_store.py` (`persist_campaign_from_result`, `_brand_id`, `campaign_counts_by_brand`), `strategy/dashboard.py`.
- Plan creation and persistence: `app/server.py` (`POST /api/projects`, the Deploy branch of the plan stream).
- Projects: `strategy/projects.py` (`projects` table, `slots.brand`, `campaign_plan_layout`).
- Brand Journey: `strategy/brand_journey.py` (`_key`, `journey_flow`), `strategy/brand_kit.py` (`canonical_key`), `scripts/reset_test_data.py`.
- Second brand roster: `config/client_brands.json`, `strategy/brand_lifecycle.py`.
