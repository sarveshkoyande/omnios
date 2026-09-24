---
title: Brand Campaigns Index - Requirements
type: feat
date: 2026-09-24
topic: brand-campaigns-index
artifact_contract: ce-unified-plan/v1
artifact_readiness: requirements-only
product_contract_source: brainstorm (written by hand in the ce-brainstorm format; the skill was not available in the session)
origin: docs/ideation/2026-09-24-brand-campaign-engagement-plan-ia-ideation.html, idea 1 ("Give the brand a first-class campaigns table")
execution: none (requirements only; no Planning Contract yet)
---

# Brand Campaigns Index - Requirements

## Goal Capsule

- **Objective:** For any brand, one call lists all of its campaigns: formal plans from the orchestrator and ad-hoc flows from the Brand Journey.
- **Means:** Make the existing `campaign` table in `campaigns.db` the single campaign index. Tie it to the brand kit's identity and write to it from both the orchestrator and the Journey. No second campaigns table.
- **Product authority:** This covers the data model, one read API and a backfill of existing data only. Navigation, naming, dashboards and creation flows are later ideas (2 to 7) that build on it.
- **Readiness:** Requirements only. Key Decisions marked **proposed** need the user's confirmation before planning; see Outstanding Questions.

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

### Key Decisions

- **KD1. Reuse the existing `campaign` table; do not add a second one.** This corrects the ideation's premise. A new table would make a fourth place campaign-like data lives. (proposed — recommended: the table, its versions and the dashboard count already exist.) Governs R1 to R3.
- **KD2. The brand kit key is the one brand identity.** A campaign belongs to a brand kit (`config/brand_kits.json`), matched case-insensitively like the Journey. `campaigns.db`'s own `brand` rows keep their current uses (market intel, claims, content), but link to the kit key when a kit exists. (proposed — the Cockpit, the active surface, is already brand-kit-first.) Governs R4 to R6.
- **KD3. A plan with no matching brand kit is stored unassigned, not as a new brand.** Today a typo creates a new `brand` row silently. Unassigned campaigns stay listable and can be assigned later. (proposed — see Q1; the alternative is auto-creating a skeleton brand kit.) Governs R5.
- **KD4. A campaign exists from the moment the work starts, not only when it finishes.** A plan campaign is created when its project gets a brand. A flow campaign is created when the Journey flow is first built. Status tracks progress. (proposed — see Q2.) Governs R7, R8.
- **KD5. Re-running a plan adds a version, not a campaign.** One project maps to one campaign. (proposed.) Governs R10.
- **KD6. The Journey flow is the brand's one ad-hoc campaign for now.** The Journey stores one flow per brand today, and multi-flow per brand stays out of scope. (proposed.) Governs R11.
- **KD7. Kind names are internal and neutral: `plan` and `flow`.** The user-facing naming ("engagement plan" vs "campaign") is idea 2 and is not decided here. (proposed.) Governs R13.

### Actors

- A1. Brand marketer: creates plans and Journey flows and wants to see all of a brand's campaigns in one place.
- A2. Orchestrator: runs a phase-gated plan for a project (`strategy/orchestrator.py`, `app/server.py`).
- A3. Brand Journey: builds and edits one rules-built flow per brand (`strategy/brand_journey.py`).
- A4. Startup bootstrap: reseeds and backfills data idempotently on app start (`strategy/bootstrap.py`).

### Requirements

**Campaign index**

- R1. Each unit of campaign work has exactly one record, in the existing `campaign` table in `campaigns.db`. There is no second campaigns table.
- R2. Each record carries its brand (brand kit key, or unassigned), its kind (`plan` or `flow`), a link to its source (project id for `plan`, brand for `flow`), a name, a status, and created and updated times.
- R3. One read returns all of a brand's campaigns, both kinds, newest first.

**Brand identity**

- R4. A campaign's brand is the brand kit's canonical key, matched case-insensitively (the same rule as `brand_journey._key`).
- R5. A plan whose brand matches no brand kit is stored unassigned. It does not create a brand row or a brand kit. Unassigned campaigns can be listed on their own.
- R6. `campaigns.db`'s existing `brand` rows keep working for market intel, claims and content. Where a brand kit exists with the same name (case-insensitive), the row is linked to it, so every campaign for that brand resolves to one identity.

**Lifecycle**

- R7. A `plan` campaign is created when its project first has a brand. Its status follows the project phase and becomes final when Deploy completes. That completion step is where `persist_campaign_from_result` writes today.
- R8. A `flow` campaign is created when the brand's Journey flow is first built. Its status follows the Flow step: built, then confirmed.
- R9. Writing a campaign record never blocks or breaks plan generation or the Journey. A failure is logged and repaired on the next write or at startup, matching the app's best-effort idiom.
- R10. Re-running or regenerating a plan adds a new `campaign_version` to that project's campaign, with an incrementing version number. It never adds a second campaign.
- R11. A brand has at most one `flow` campaign while the Journey stores one flow per brand.
- R12. Resetting a brand's Journey archives its `flow` campaign instead of deleting it, so past campaigns stay auditable. (See Q3.)

**Naming**

- R13. `plan` and `flow` are internal values. This work adds no user-facing renames.

**Existing data**

- R14. On startup, a backfill runs idempotently and never deletes anything:
  - it links existing `campaign` rows to brand kits by name;
  - it creates `plan` campaigns for existing projects that have a brand but no campaign;
  - it creates `flow` campaigns for brands with a built Journey flow;
  - it folds duplicate campaigns that came from re-runs of the same project into one campaign with numbered versions.

**Read API**

- R15. `GET /api/brands/{brand}/campaigns` returns that brand's campaigns: kind, name, status, source link, updated time. An unknown brand returns 404. A separate read returns unassigned campaigns.

### Key Flows

- F1. Formal plan for a kit brand
  - **Trigger:** A1 starts a project and names a brand that has a kit.
  - **Actors:** A1, A2
  - **Steps:** A `plan` campaign appears for that brand as soon as the brand is known. Its status advances with each phase. Deploy completion attaches the plan as a version.
  - **Outcome:** The brand's campaign list shows the plan from the start, and re-running it adds versions, not rows.
  - **Covered by:** R3, R4, R7, R10
- F2. Journey flow
  - **Trigger:** A1 builds the Flow step for a brand.
  - **Actors:** A1, A3
  - **Steps:** A `flow` campaign is created on first build and marked confirmed when the Flow step is confirmed.
  - **Outcome:** The same list shows the flow next to the brand's plans.
  - **Covered by:** R3, R8, R11
- F3. Plan for a brand with no kit
  - **Trigger:** A1 runs a plan for "Cardiozen" but only "CardioZen" has a kit, or no kit exists at all.
  - **Actors:** A1, A2
  - **Steps:** Case-insensitive matching attaches it to "CardioZen" if that kit exists. Otherwise the campaign is stored unassigned.
  - **Outcome:** No stray brand rows, and nothing is lost.
  - **Covered by:** R4, R5
- F4. First start after this ships
  - **Trigger:** The app starts against existing `projects.db`, `campaigns.db` and `brand_journey.db`.
  - **Actors:** A4
  - **Steps:** The R14 backfill runs.
  - **Outcome:** Every brand lists its past plans and its Journey flow. Running the backfill again changes nothing.
  - **Covered by:** R14

### Acceptance Examples

- AE1. **Covers R3, R7, R8.** **Given** Oncomyra has one finished plan, one plan in its Select phase, and a built Journey flow, **when** the brand's campaigns are listed, **then** three campaigns appear: two `plan`, one `flow`.
- AE2. **Covers R10.** **Given** a project's plan has been run to Deploy twice, **when** its brand's campaigns are listed, **then** there is one campaign for that project with versions 1 and 2.
- AE3. **Covers R4, R5.** **Given** a kit exists for "Oncomyra" only, **when** plans are run for "oncomyra" and "Oncomira", **then** the first lists under Oncomyra and the second is unassigned. No new brand row is created for "Oncomira".
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
- A UI for assigning unassigned campaigns to a brand.

### Dependencies / Assumptions

- `campaigns.db` is opened through `strategy/db.py`'s `connect("campaigns")`. Schema changes must work on SQLite and, where `DATABASE_URL` is set, Postgres.
- A project's brand is read from `slots.brand` in its `state_json` (`strategy/projects.py`).
- `brand_kit.canonical_key` stays the single case-insensitive resolver for brand kit names.
- The startup backfill follows the existing idempotent `load_x()` pattern (`strategy/brand_lifecycle.py`, `strategy/hcp_360.py`) and is called from `strategy/bootstrap.py`.

### Outstanding Questions

Resolve these before a Planning Contract is written:

- Q1. **Plans for a brand with no kit (KD3, R5).** Store them unassigned (proposed), or auto-create a skeleton brand kit so every campaign has a brand?
- Q2. **When a plan becomes a campaign (KD4, R7).** When the project first has a brand (proposed), or only when Deploy completes, as today?
- Q3. **Journey reset (R12).** Archive the brand's flow campaign (proposed), or delete it along with the Journey data?
- Q4. **Brand changed mid-project.** If a project's brand is edited after its campaign exists, does the campaign move to the new brand (proposed), or does the old campaign close and a new one open?

### Sources / Research

- Ideation: `docs/ideation/2026-09-24-brand-campaign-engagement-plan-ia-ideation.html` (idea 1, with ideas 2 to 7 as the downstream scope boundaries).
- Existing campaign model: `db/campaign_content_schema.sql` (`brand`, `campaign`, `campaign_version`), `strategy/campaign_store.py` (`persist_campaign_from_result`, `_brand_id`, `campaign_counts_by_brand`), `strategy/dashboard.py`.
- Plan persistence call site: `app/server.py`, the Deploy branch of the plan stream.
- Projects: `strategy/projects.py` (`projects` table, `slots.brand` in `state_json`).
- Brand Journey: `strategy/brand_journey.py` (`_key`, `journey_flow`, reset), `strategy/brand_kit.py` (`canonical_key`).
- Second brand roster: `config/client_brands.json`, `strategy/brand_lifecycle.py`.
