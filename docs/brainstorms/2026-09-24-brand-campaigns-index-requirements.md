---
title: Brand Campaigns Index - Requirements
type: feat
date: 2026-09-24
topic: brand-campaigns-index
artifact_contract: ce-unified-plan/v1
artifact_readiness: requirements-complete
product_contract_source: brainstorm (written by hand in the ce-brainstorm format; the skill was not available in the session)
origin: docs/ideation/2026-09-24-brand-campaign-engagement-plan-ia-ideation.html, idea 1 ("Give the brand a first-class campaigns table")
execution: none (requirements only; no Planning Contract yet)
---

# Brand Campaigns Index - Requirements

## Goal Capsule

- **Objective:** For any brand, one call lists all of its campaigns: formal plans from the orchestrator and ad-hoc flows from the Brand Journey.
- **Means:** Make the existing `campaign` table in `campaigns.db` the single campaign index. Tie it to the brand kit's identity and write to it from both the orchestrator and the Journey. No second campaigns table.
- **Product authority:** This covers the data model, one read API and a backfill of existing data only. Navigation, naming, dashboards and creation flows are later ideas (2 to 7) that build on it.
- **Readiness:** Requirements complete. The user settled all four open questions on 2026-09-24, and this is ready for a Planning Contract.

---

## Product Contract

### Summary

Today you cannot list a brand's campaigns.
Formal plans and Journey flows are stored in different places with different ideas of what a "brand" is, and nothing connects them.
This work gives every campaign one record, tied to one brand identity, so later work (navigation, the rollup dashboard, the naming fix) has something to stand on.

### Problem Frame

The ideation says no `brand_id` exists anywhere and no campaigns table exists. Reading the code corrects part of that:

- **A campaign table already exists.** `db/campaign_content_schema.sql` defines `campaign` (with `brand_id`, `project_id`, `status`) and `campaign_version`, in `campaigns.db`. `campaign_store.persist_campaign_from_result()` writes a row when an orchestrator plan finishes its Deploy phase (`app/server.py`, the Deploy branch of the plan stream). `strategy/dashboard.py` already counts campaigns per brand from it.
- **But only finished formal plans reach it.** A project gets a campaign row only after Deploy. In-progress projects are invisible. Brand Journey flows (`journey_flow` in `brand_journey.db`, one row per brand) never reach it.
- **Re-running a plan duplicates the campaign.** Each Deploy inserts a new `campaign` row, and `campaign_version.version_no` is always 1.
- **Three brand identities disagree.**
  1. The Cockpit and Journey use the brand kit key from `config/brand_kits.json` (`brand_kit.canonical_key`, case-insensitive).
  2. `campaigns.db` has its own `brand` table, matched by exact case-sensitive name and seeded from the market-intel roster (`config/client_brands.json`, `strategy/brand_lifecycle.py`).
  3. Orchestrator projects hold a free-typed `slots.brand` string inside `state_json` (`strategy/projects.py`).

  The same brand can appear as different rows, and a kit brand can have no `campaigns.db` row at all.

The missing piece is therefore not a table. It is one brand identity, and making both creation paths write to the table that already exists.
Today a plan's brand is typed or inferred from the intake chat (`slots.brand`), which is how the three identities drift apart. A plan should instead always be created inside a brand.

### Key Decisions

- **KD1. Reuse the existing `campaign` table; do not add a second one.** This corrects the ideation's premise. A new table would make a fourth place campaign-like data lives. (proposed — recommended: the table, its versions and the dashboard count already exist.) Governs R1 to R3.
- **KD2. The brand kit key is the one brand identity.** A campaign belongs to a brand kit (`config/brand_kits.json`), matched case-insensitively like the Journey. `campaigns.db`'s own `brand` rows keep their current uses (market intel, claims, content), but link to the kit key when a kit exists. (proposed — the Cockpit, the active surface, is already brand-kit-first.) Governs R4 to R6.
- **KD3. A plan is always created inside a brand.** It is started from an existing brand, so its brand is set at creation, never typed or inferred from chat. There is no "unassigned" campaign in the product. (session-settled: user-directed — "a plan is always created inside a brand"; chosen over storing no-kit plans unassigned or auto-creating a skeleton kit.) Governs R5, R5a.
- **KD4. A campaign exists from the moment the work starts, not only when it finishes.** With KD3, a plan campaign is created when the plan is created. A flow campaign is created when the Journey flow is first built. Status tracks progress. (session-settled: user-approved — chosen over creating it only when Deploy completes.) Governs R7, R8.
- **KD5. Re-running a plan adds a version, not a campaign.** One project maps to one campaign. (proposed.) Governs R10.
- **KD6. The Journey flow is the brand's one ad-hoc campaign for now.** The Journey stores one flow per brand today, and multi-flow per brand stays out of scope. (proposed.) Governs R11.
- **KD7. Kind names are internal and neutral: `plan` and `flow`.** The user-facing naming ("engagement plan" vs "campaign") is idea 2 and is not decided here. (proposed.) Governs R13.
- **KD8. Wiping a brand's Journey deletes its flow campaign.** (session-settled: user-directed — chosen over archiving it.) Governs R12.
- **KD9. Moving a plan to another brand closes its campaign and opens a new one.** The old brand keeps a closed record of it. (session-settled: user-directed — chosen over moving the same campaign.) Governs R7a.

### Actors

- A1. Brand marketer: creates plans and Journey flows and wants to see all of a brand's campaigns in one place.
- A2. Orchestrator: runs a phase-gated plan for a project (`strategy/orchestrator.py`, `app/server.py`).
- A3. Brand Journey: builds and edits one rules-built flow per brand (`strategy/brand_journey.py`).
- A4. Startup bootstrap: reseeds and backfills data idempotently on app start (`strategy/bootstrap.py`).

### Requirements

**Campaign index**

- R1. Each unit of campaign work has exactly one record, in the existing `campaign` table in `campaigns.db`. There is no second campaigns table.
- R2. Each record carries its brand (brand kit key), its kind (`plan` or `flow`), a link to its source (project id for `plan`, brand for `flow`), a name, a status, and created and updated times.
- R3. One read returns all of a brand's campaigns, both kinds, newest first.

**Brand identity**

- R4. A campaign's brand is the brand kit's canonical key, matched case-insensitively (the same rule as `brand_journey._key`).
- R5. A plan can only be created from an existing brand. Its brand is set at creation from that brand, not typed or inferred from the intake chat, and plan creation never creates a brand row or a brand kit.
- R5a. Projects that already exist with a brand matching no brand kit are legacy data. The backfill (R14) leaves them without a campaign and lists them in its log for a one-time cleanup. They do not appear under any brand.
- R6. `campaigns.db`'s existing `brand` rows keep working for market intel, claims and content. Where a brand kit exists with the same name (case-insensitive), the row is linked to it, so every campaign for that brand resolves to one identity.

**Lifecycle**

- R7. A `plan` campaign is created when the plan is created. Its status follows the project phase and becomes final when Deploy completes. That completion step is where `persist_campaign_from_result` writes today.
- R7a. If a plan is moved to a different brand, its current campaign is closed and stays listed under the old brand as closed. A new campaign opens under the new brand, and later versions attach to the new one.
- R8. A `flow` campaign is created when the brand's Journey flow is first built. Its status follows the Flow step: built, then confirmed.
- R9. Writing a campaign record never blocks or breaks plan generation or the Journey. A failure is logged and repaired on the next write or at startup, matching the app's best-effort idiom.
- R10. Re-running or regenerating a plan adds a new `campaign_version` to that project's campaign, with an incrementing version number. It never adds a second campaign.
- R11. A brand has at most one `flow` campaign while the Journey stores one flow per brand.
- R12. Rebuilding a brand's flow updates its existing `flow` campaign and never adds another. The only thing that wipes Journey data today is the developer script `scripts/reset_test_data.py`. It also deletes the brand's `flow` campaign.

**Naming**

- R13. `plan` and `flow` are internal values. This work adds no user-facing renames.

**Existing data**

- R14. On startup, a backfill runs idempotently and never deletes anything:
  - it links existing `campaign` rows to brand kits by name;
  - it creates `plan` campaigns for existing projects whose brand matches a brand kit and that have no campaign (others are handled by R5a);
  - it creates `flow` campaigns for brands with a built Journey flow;
  - it folds duplicate campaigns that came from re-runs of the same project into one campaign with numbered versions.

**Read API**

- R15. `GET /api/brands/{brand}/campaigns` returns that brand's campaigns: kind, name, status, source link, updated time. An unknown brand returns 404. Closed campaigns are included and marked closed.

### Key Flows

- F1. Formal plan inside a brand
  - **Trigger:** A1 starts a plan from a brand.
  - **Actors:** A1, A2
  - **Steps:** A `plan` campaign appears for that brand immediately. Its status advances with each phase. Deploy completion attaches the plan as a version.
  - **Outcome:** The brand's campaign list shows the plan from the start, and re-running it adds versions, not rows.
  - **Covered by:** R3, R4, R7, R10
- F2. Journey flow
  - **Trigger:** A1 builds the Flow step for a brand.
  - **Actors:** A1, A3
  - **Steps:** A `flow` campaign is created on first build and marked confirmed when the Flow step is confirmed.
  - **Outcome:** The same list shows the flow next to the brand's plans.
  - **Covered by:** R3, R8, R11
- F3. Plan moved to another brand
  - **Trigger:** A1 moves an in-progress plan from Oncomyra to Cardiovex.
  - **Actors:** A1, A2
  - **Steps:** Oncomyra's campaign for that plan is closed. A new campaign opens under Cardiovex, and the plan's later versions attach there.
  - **Outcome:** Both brands show an accurate history.
  - **Covered by:** R7a
- F4. First start after this ships
  - **Trigger:** The app starts against existing `projects.db`, `campaigns.db` and `brand_journey.db`.
  - **Actors:** A4
  - **Steps:** The R14 backfill runs.
  - **Outcome:** Every brand lists its past plans and its Journey flow. Legacy projects with no matching kit are logged, not attached. Running the backfill again changes nothing.
  - **Covered by:** R5a, R14

### Acceptance Examples

- AE1. **Covers R3, R7, R8.** **Given** Oncomyra has one finished plan, one plan in its Select phase, and a built Journey flow, **when** the brand's campaigns are listed, **then** three campaigns appear: two `plan`, one `flow`.
- AE2. **Covers R10.** **Given** a project's plan has been run to Deploy twice, **when** its brand's campaigns are listed, **then** there is one campaign for that project with versions 1 and 2.
- AE3. **Covers R5, R5a.** **Given** a new plan, **when** A1 creates it, **then** it can only be created from an existing brand and there is no brand name to type. **Given** a legacy project for "Oncomira" (no kit), **when** the backfill runs, **then** it gets no campaign, it is listed in the backfill log, and no "Oncomira" brand is created.
- AE3a. **Covers R7a.** **Given** a plan under Oncomyra, **when** A1 moves it to Cardiovex, **then** Oncomyra lists it as closed and Cardiovex lists a new open campaign for it.
- AE3b. **Covers R12.** **Given** a brand with a `flow` campaign, **when** `scripts/reset_test_data.py` wipes that brand's Journey, **then** the `flow` campaign is gone too.
- AE4. **Covers R9.** **Given** `campaigns.db` is unavailable, **when** A1 runs a plan phase or builds a Journey flow, **then** both succeed, and the missing campaign record appears after the next startup.
- AE5. **Covers R14.** **Given** existing data with duplicate campaign rows for one project, **when** the app starts twice, **then** the first start folds them into one campaign with versions, and the second start changes nothing.

### Scope Boundaries

- Navigation and the Brand > Campaign > Flow breadcrumb (idea 3).
- Renaming "engagement plan" or any user-facing copy (idea 2).
- A "+ New Campaign" creation fork (idea 4).
- Pinning the brand-kit version a campaign was built from (idea 5).
- Unifying the `CampaignFlow` and Journey flow schemas (idea 6).
- A per-brand campaigns dashboard or a sidebar count badge (idea 7). R15's API is what those will read.
- More than one Journey flow per brand.
- Where the "start a plan from a brand" entry point lives. Today plans start from the `frontend/` project home; choosing the surviving surface is idea 3, and the creation fork is idea 4. This work only requires that whichever entry exists binds the plan to an existing brand (R5).
- A UI for cleaning up legacy projects with no matching kit (R5a lists them; cleanup is manual).

### Dependencies / Assumptions

- `campaigns.db` is opened through `strategy/db.py`'s `connect("campaigns")`. Schema changes must work on SQLite and, where `DATABASE_URL` is set, Postgres.
- A project's brand is read from `slots.brand` in its `state_json` (`strategy/projects.py`).
- `brand_kit.canonical_key` stays the single case-insensitive resolver for brand kit names.
- The startup backfill follows the existing idempotent `load_x()` pattern (`strategy/brand_lifecycle.py`, `strategy/hcp_360.py`) and is called from `strategy/bootstrap.py`.

### Outstanding Questions

None. The four questions from the first draft were settled by the user on 2026-09-24:

- Q1. A plan with no brand kit → cannot arise: a plan is always created inside a brand (KD3, R5). Legacy data only: R5a.
- Q2. When a plan becomes a campaign → as soon as it has a brand, which with KD3 means at creation (KD4, R7).
- Q3. Wiping a brand's Journey → delete its flow campaign (KD8, R12).
- Q4. A plan moved to another brand → close the old campaign and open a new one (KD9, R7a).

### Sources / Research

- Ideation: `docs/ideation/2026-09-24-brand-campaign-engagement-plan-ia-ideation.html` (idea 1, with ideas 2 to 7 as the downstream scope boundaries).
- Existing campaign model: `db/campaign_content_schema.sql` (`brand`, `campaign`, `campaign_version`), `strategy/campaign_store.py` (`persist_campaign_from_result`, `_brand_id`, `campaign_counts_by_brand`), `strategy/dashboard.py`.
- Plan persistence call site: `app/server.py`, the Deploy branch of the plan stream.
- Projects: `strategy/projects.py` (`projects` table, `slots.brand` in `state_json`).
- Brand Journey: `strategy/brand_journey.py` (`_key`, `journey_flow`), `strategy/brand_kit.py` (`canonical_key`), `scripts/reset_test_data.py` (developer reset).
- Second brand roster: `config/client_brands.json`, `strategy/brand_lifecycle.py`.
