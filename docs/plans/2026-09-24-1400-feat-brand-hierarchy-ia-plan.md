---
title: Brand Hierarchy and IA (Brand > Engagement Plan > Campaign > Flow) - Plan
type: feat
date: 2026-09-24
topic: brand-campaign-engagement-plan-ia
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: docs/brainstorms/2026-09-24-brand-campaigns-index-requirements.md + docs/brainstorms/2026-09-24-brand-campaign-ia-ideas-2-7-requirements.md
execution: code
---

# Brand Hierarchy and IA - Plan

## Goal Capsule

- **Objective:** Omni OS works as one hierarchy, **Brand › Engagement Plan › Campaign › Flow**, in one shell (the Cockpit):
  - one vocabulary;
  - one way to create each level;
  - one flow model;
  - each campaign keeps a snapshot of the brand content it was built from.
- **Means:** 12 units in five phases:
  - A. Data model and backfill (U1 to U4).
  - B. One flow model (U5, U6).
  - C. Naming (U7).
  - D. Provenance (U8).
  - E. Cockpit shell, creation and overview (U9 to U12).
- **Product authority:** The two requirements docs are the Product Contract. Their R, N-, S-, F-, P-, U- and R-R requirement IDs are cited per unit below. The Product Contract wins on behaviour; the KTDs here win on mechanism.
- **Execution profile:** Deep. Each phase ends with the app working and every verify script green, and each phase can ship to `main` on its own.
- **Stop conditions:** Stop and report if:
  - `db.connect("campaigns")` can't add columns on the Postgres dialect with the idempotent `ALTER` idiom (KTD2);
  - the `frontend/` workspace can't be opened for one project from a URL without its own navigation (KTD10);
  - more than a handful of existing Operations layouts fail to render as frozen flows (KTD7).
- **Open blockers:** None. All product decisions were settled on 2026-09-24.

---

## Product Contract (summary)

The full contract lives in the two requirements docs. In short:

- Four levels. Each record has one parent and is always created inside it (idea 1, R1 and R8).
- The brief and brand kit stay on the Brand (R7).
- A campaign optionally has one Campaign Plan (the orchestrator's document) and any number of flows (R12).
- The Journey's Flow step creates the brand's first engagement plan and campaign (R22).
- An engagement plan's period is optional (R3).
- Existing work goes into one "Earlier work" engagement plan per brand (R20).
- Moving a campaign to another brand closes it and opens a new one (R16).
- Wiping a brand's Journey deletes the flows it created (R19).
- Naming uses six glossary terms, and only user-facing copy changes (N-R1 to N-R6).
- The Cockpit is the shell, with a four-level breadcrumb (S-R1 to S-R7).
- There is a "+ New" action at each level (F-R1 to F-R7).
- Each campaign keeps a whole snapshot of the brand content it was built from (P-R1 to P-R6).
- Every flow uses a rules-built base plus structured edits, keyed by flow (U-R1 to U-R7).
- The brand overview rolls up status and counts (R-R1 to R-R7).

---

## Planning Contract

### Key Technical Decisions

- **KTD1. Every hierarchy table lives in `campaigns.db`, next to `campaign`.** Engagement plans, flows and campaigns share one store and one connection (`db.connect("campaigns")`). Parent links can then be real foreign keys, and a tree read is one query. `brand_journey.db` keeps the Journey's answers, drafts, steps and turns only.
- **KTD2. Schema migration uses the idempotent idiom `projects.py` already uses.**
  - New tables (`engagement_plan`, `flow`) go into `db/campaign_content_schema.sql` as `CREATE TABLE IF NOT EXISTS`.
  - New columns go in through a guarded `ALTER TABLE ... ADD COLUMN` inside `campaign_store.init_db()`, swallowing "column exists" with a rollback. The new columns are:
    - `campaign.engagement_plan_id`, `campaign.closed_at`, `campaign.snapshot_json`, `campaign.snapshot_at`, `campaign.status_detail`;
    - `brand.kit_key`;
    - `campaign_version.snapshot_json`.
  - All columns land in U1, including idea 5's, so there is only one migration.
- **KTD3. A new `strategy/hierarchy.py` owns the hierarchy.** It handles engagement plan, campaign and flow create/read/move/close, tree reads, status roll-up and the backfill. `campaign_store.py` keeps the content model (claims, messages, assets). `persist_campaign_from_result` changes from "insert a campaign" to "attach a version to campaign X" (U2).
- **KTD4. Brand identity is `brand.kit_key`.**
  - Every hierarchy API takes a brand name and resolves it with `brand_kit.canonical_key`. An unknown brand returns 404.
  - Brand rows are fetched or created by `kit_key`, never by display name.
  - Existing roster rows get `kit_key` set when a kit with the same case-insensitive name exists (R11).
- **KTD5. Campaign status is derived and stored in `campaign.status`:**
  - `draft` on create;
  - `in_progress` once any Campaign Plan phase is approved or any flow exists;
  - `confirmed` when Deploy completes (plan campaigns) or every flow is confirmed (flows-only campaigns);
  - `closed` when moved to another brand (R16).

  An engagement plan is `active` until the user closes it. Roll-ups are computed on read, not stored.
- **KTD6. A flow is a row in `campaigns.db.flow`**, with these columns:
  - `id`, `campaign_id`, `name`, `origin` (`journey`, `campaign_plan`, `manual`, `legacy_layout`), `status`;
  - `base_json` (the rules-built `CampaignFlow` with block codes), `ops_json` (kept edits), `draft_ops_json`, `dropped_json`;
  - `created_at`, `updated_at`.

  The Journey's flow functions in `strategy/brand_journey.py` (build, turn, keep, undo, rebuild) are re-keyed from `brand` to `flow_id`, and read their inputs from the flow's campaign snapshot (KTD8). `journey_flow` and `journey_flow_draft` become read-only sources for the backfill and are then left unused.
- **KTD7 (revised 2026-09-24, user decision). The Operations editor stays as it is; its diagram is a "document" flow of the campaign.** Converting the Operations stage to the Journey's model would have removed its drag-and-drop palette, styling, layers, data fields, import/export, the agent's full redraw and the SFMC export's input. So:
  - `flow.kind` is `rules` (base plus structured edits: Journey and hand-added flows) or `document` (the Campaign Plan's `WorkflowDocument`);
  - a document flow ("Campaign Plan flow", `origin=campaign_plan`) points at `projects.campaign_plan_layout`, which stays the single copy. The editor, the Operations agent (`strategy/tab_chat.py`) and `strategy/sfmc_export.py` are unchanged;
  - `projects.save_project` creates the flow the first time a campaign-linked project saves a layout, and the backfill adds it for existing ones;
  - when a campaign is moved to another brand, its document flow keeps a frozen copy (`flow.layout_json`) and the new campaign gets its own;
  - rules-only operations (build, turn, keep, undo) refuse document flows with a clear message.

  Unifying the two models (recording editor changes as structured edits) is deferred.
- **KTD8. The snapshot is JSON of the kit fields plus the Journey answers, taken at campaign creation.**
  - `brand_journey.brand_ctx(brand)` is split into `ctx_from(kit, answers)` plus a thin wrapper, so a flow builds from `campaign.snapshot_json` instead of the live kit (P-R5).
  - Drift is a field-by-field comparison of the snapshot with the current kit and answers, grouped into Brief, Audience, Message and Kit (P-R3).
  - Each Campaign Plan version stores the snapshot it used (P-R2).
- **KTD9. The Cockpit gets hash routing with no new dependency:**
  - `#/b/{brand}`
  - `#/b/{brand}/p/{planId}`
  - `#/b/{brand}/p/{planId}/c/{campaignId}`
  - `#/b/{brand}/p/{planId}/c/{campaignId}/f/{flowId}` or `.../plan`

  A small `useRoute()` hook parses `location.hash`. The browser back button then follows the levels (S-R7), and the breadcrumb is derived from the route (S-R1).
- **KTD10. The Campaign Plan view embeds the `frontend/` workspace in an iframe until it is ported.**
  - `frontend/src/App.tsx` reads `?project={id}&embed=1` on load, opens that project's workspace directly, and hides its own top nav and home.
  - A new server route `GET /campaign-plan-view` serves `static/v2/index.html`, so the embed survives `/v2` becoming a redirect (KTD11).
  - It is same-origin, so no CORS work is needed.
- **KTD11. `/` switches to the Cockpit only in U12**, once a Campaign Plan is reachable from it. `/` and `/v2` then serve or redirect to the Cockpit, and `/legacy` and `/hcp360` are unchanged (S-R5, S-R6).
- **KTD12. The glossary is defined twice, and a check keeps the copies equal.**
  - `strategy/glossary.py`, for prompts and exports.
  - `frontend/src/glossary.ts`, for both front ends; the Cockpit imports it through the existing `@omni-frontend` Vite alias.

  A verify check compares the two, so neither drifts (N-R6).
- **KTD13. Plans are bound at creation, not inferred.** `POST /api/campaigns/{id}/campaign-plan` creates the project with `slots.brand` (plus therapy area, indication and lifecycle from the kit) already filled, and sets `campaign.project_id`. `strategy/conversation.py` only asks for the brand when `slots.brand` is empty (line 874), so the intake never asks for it (R13, F-AE3). Two things still change:
  - the opening message (`opening_message()`) takes the campaign's brand and names it;
  - the existing "reuse remembered details for {brand}?" offer (`recall_offered`) is left as is, because it is still useful. `POST /api/projects` without a campaign stays available only behind the embedded view's legacy path, until U12 removes the `frontend/` home intake (F-R6).

### Implementation Units

#### Phase A — Data model and backfill (idea 1)

**U1. Hierarchy schema and store**
- **Covers:** R1 to R8, R10, R11, R17, R18, R21 (store side).
- **Files:**
  - `db/campaign_content_schema.sql`: new `engagement_plan` and `flow` tables.
  - `strategy/campaign_store.py`: guarded `ALTER`s in `init_db` (KTD2).
  - `strategy/hierarchy.py` (new).
- **Work:**
  - Create, read and list for each level, each taking its parent id.
  - `tree(brand)`, `move_campaign(id, plan_id)` (same brand: move; other brand: close and open a new one, R16/R17), `close_plan`, and status derivation (KTD5).
  - Brand resolution by `kit_key` (KTD4).
- **Verification:** new `scripts/verify_brand_hierarchy.py`, which follows `verify_brand_journey.py`'s temp-`DATA_DIR` pattern. Checks:
  - create at each level, and a parent that doesn't exist is rejected;
  - the tree shape (AE1);
  - moving within a brand and across brands (AE4);
  - case-insensitive brand resolution;
  - `init_db` run twice is a no-op.

**U2. Campaign Plans bound to campaigns**
- **Covers:** R12 to R15, KTD13.
- **Files:**
  - `app/server.py`: `POST /api/campaigns/{id}/campaign-plan`, the phase-save hook, and the Deploy branch.
  - `strategy/campaign_store.py`: `persist_campaign_from_result(result, slots, plan_md, project_id, campaign_id)` attaches the next `version_no` to the campaign, with no insert.
  - `strategy/hierarchy.py`: a status update on each phase approval.
- **Verification:**
  - starting a plan from a campaign pre-fills `slots.brand`, and the intake doesn't ask for the brand (AE3);
  - two Deploys give versions 1 and 2 on one campaign (AE2);
  - a failing `campaigns.db` write doesn't break the plan stream (AE6: monkeypatch `db.connect` to raise).

**U3. Backfill**
- **Covers:** R9, R20.
- **Files:**
  - `strategy/hierarchy.py`: `backfill()`.
  - `strategy/bootstrap.py`: call it in `run()` after `seed_library`.
- **Work, idempotent:**
  1. Set `brand.kit_key` for roster rows that match a kit.
  2. Create one "Earlier work" engagement plan per kit brand that has anything to place.
  3. Link existing `campaign` rows to it.
  4. Fold duplicate campaigns from the same `project_id` into one campaign with ordered versions.
  5. Create campaigns for projects whose `slots.brand` matches a kit and that have no campaign.
  6. Log (never attach) projects that match no kit.

  Journey flows move in U5, and Operations layouts move in U6.
- **Verification:** a seeded fixture with duplicates, a no-kit project and a matching project. The first run produces the expected tree, the second run changes nothing (AE7), and the no-kit project appears in the returned log.

**U4. Hierarchy API**
- **Covers:** R6, R21.
- **Files:** `app/server.py`:
  - `GET /api/brands/{brand}/engagement-plans`, `POST` the same path;
  - `GET/POST /api/engagement-plans/{id}/campaigns`;
  - `GET /api/campaigns/{id}` (with its Campaign Plan and flows);
  - `POST /api/campaigns/{id}/move`;
  - `GET /api/brands/{brand}/tree`;
  - `PATCH` for renaming, period and closing.
- **Verification:** route checks with FastAPI's `TestClient` in `verify_brand_hierarchy.py`: 404 on an unknown brand or id, and closed records included and marked.

#### Phase B — One flow model (idea 6)

**U5. Flows keyed by flow id; the Journey writes into the hierarchy**
- **Covers:** U-R1 to U-R3, U-R6, R19, R22.
- **Files:**
  - `strategy/brand_journey.py`: flow functions re-keyed to `flow_id`, reading the campaign snapshot (KTD6, KTD8).
  - `app/server.py`: the Journey flow routes take a `flow_id`, and `GET /api/brands/{brand}/journey/flow` returns the brand's Journey flow id.
  - `cockpit/src/components/journey/FlowCanvas.tsx` and `cockpit/src/api.ts`.
  - `scripts/reset_test_data.py`: deletes `origin=journey` flows for the brand.
  - `strategy/hierarchy.py`: `backfill()` step 7, which turns each `journey_flow` row (plus its kept ops and draft) into a flow in the brand's campaign.
- **Work:**
  - The Journey's first flow build calls `hierarchy.ensure_first_campaign(brand)`. With no plans, that creates "First engagement plan" › "Launch campaign" with a snapshot. Otherwise the Flow step shows a plan and campaign picker, with "New campaign" (R22).
- **Verification:**
  - `verify_brand_journey.py`'s flow checks are updated to the flow-id API, and all of them stay green;
  - new checks cover the R22 first-plan creation, the backfill of an existing Journey flow (block codes and ops intact), and a reset deleting only Journey-made flows (AE5).

**U6. The Operations diagram as a flow of its campaign** (revised, KTD7)
- **Covers:** U-R5 (revised), U-R6 for Operations.
- **Files:**
  - `strategy/campaign_store.py`: `flow.kind` and `flow.layout_json`;
  - `strategy/hierarchy.py`: `ensure_plan_flow`, the freeze on a cross-brand move, and backfill step 5a;
  - `strategy/projects.py`: the save hook;
  - `strategy/brand_journey.py`: document flows are read-only through the flow API.
- **Verification:** in `verify_brand_hierarchy.py`:
  - one plan flow per campaign on repeated saves, and `GET /api/flows/{id}` returns the saved document;
  - rules-only operations return 400;
  - unlinked projects still save;
  - the old diagram is frozen on a cross-brand move;
  - the backfill is idempotent.

#### Phase C — Naming (idea 2)

**U7. Glossary and copy**
- **Covers:** N-R1 to N-R6.
- **Files:**
  - `strategy/glossary.py` and `frontend/src/glossary.ts` (new).
  - The user-facing strings in `frontend/src/views/HomeIntakeCard.tsx` and `frontend/src/workspace/{PlanDocument,PlanSummaryCard,SimplePlanSummary,Workspace}.tsx`, `planDocSkinCss.ts` and `stages/WorkflowStepper.tsx`.
  - `cockpit/src/agents.ts`.
  - Export titles in `strategy/plan_document.py` and `strategy/plan_export.py`.
  - The prompt text in `strategy/orchestrator.py`, `strategy/studio_run.py` and the other generating modules that name the artifact. Their identifiers are untouched (N-KD2).
- **Verification:**
  - a check that the two glossaries match;
  - a grep check that "engagement plan" appears in user-facing strings and prompts only in the N-R1 sense (N-AE2);
  - an export title reads "Campaign Plan" (N-AE1).

#### Phase D — Provenance (idea 5)

**U8. Campaign snapshot and drift**
- **Covers:** P-R1 to P-R6.
- **Files:**
  - `strategy/hierarchy.py`: snapshot on create, `drift(campaign_id)`, `refresh_snapshot(campaign_id)`, which rebuilds the campaign's flows with their kept ops reapplied.
  - `strategy/brand_journey.py`: `ctx_from(kit, answers)` (KTD8).
  - `app/server.py`: `GET /api/campaigns/{id}/drift` and `POST /api/campaigns/{id}/refresh-snapshot`.
  - U2's Deploy branch stores the snapshot on the version.
- **Verification:** P-AE1 (a claim change flags drift and the flow keeps the old claim), P-AE2 (a refresh rebuilds with the new claim and reapplies ops), and legacy campaigns report `built_before_tracking`.

#### Phase E — Cockpit shell, creation and overview (ideas 3, 4, 7)

**U9. Routing, breadcrumb and a nav that re-scopes**
- **Covers:** S-R1 to S-R4, S-R7.
- **Files:**
  - `cockpit/src/App.tsx`: routes replace the `view` state.
  - `cockpit/src/route.ts` (new, KTD9).
  - `cockpit/src/components/Breadcrumb.tsx` (new).
  - The rail in `App.tsx`: its items depend on the level.
  - `cockpit/src/cockpit.css`.
- **Verification:** a browser pass. Deep links to each level load directly, back and forward move between levels, and the breadcrumb crumbs navigate.

**U10. Brand overview**
- **Covers:** R-R1 to R-R7.
- **Files:**
  - `cockpit/src/components/BrandOverview.tsx` (new): plans, expandable campaigns, the summary line and filters.
  - The rail badge in `App.tsx`.
  - `strategy/dashboard.py`: campaign counts from `hierarchy` by `kit_key`.
- **Verification:** R-AE1 in the browser with seeded data, and R-AE2 (the `GET /api/home` counts match the tree).

**U11. Engagement plan and campaign pages, and "+ New" at each level**
- **Covers:** F-R1 to F-R5, F-R7.
- **Files:** `cockpit/src/components/{EngagementPlanPage,CampaignPage,NewCampaignDialog,NewFlowDialog}.tsx` (new), `cockpit/src/api.ts`, `cockpit/src/types.ts`.
- **Work:**
  - "+ New flow" checks the Brief, Audience and Message confirmation from the journey state and shows "Needs: …" links (F-R5).
  - Flow pages reuse `FlowCanvas` by `flow_id` (U5).
- **Verification:** F-AE1 and F-AE2 in the browser.

**U12. Campaign Plan view, one entry point, route switch**
- **Covers:** S-R5, S-R6, F-R6, KTD10, KTD11.
- **Files:**
  - `frontend/src/App.tsx`: the `?project&embed` entry.
  - `app/server.py`: `GET /campaign-plan-view`, plus `/` and `/v2` pointing to the Cockpit.
  - `cockpit/src/components/CampaignPlanView.tsx` (new): the iframe under the breadcrumb.
  - The `frontend/src/views/HomeIntakeCard.tsx` home intake is removed from the embedded path.
- **Verification:**
  - S-AE1 end to end: brand › plan › campaign › Campaign Plan, with no brand question in the intake;
  - S-AE2: `/v2` lands in the Cockpit;
  - `/legacy` and `/hcp360` are unchanged.
- **As built (2026-09-24, revised after user review):** the iframe embed (KTD10) was removed. Framing the old `frontend/` workspace inside the Cockpit mixed two UIs, which is what this work set out to end. The Campaign Plan is being rebuilt natively in the Cockpit, in stages:
  - **Stage 1 (done):** Planning & Strategy. The brief is captured through chat (`/api/chat`), the section-by-section Studio run (`/api/studio/stream`) resumes on reopen, the agent's asks are native cards answered through `/api/studio/answer`, and plan sections render with the plan's own document stylesheet (accent re-tinted), plus Word/PDF download (`cockpit/src/components/campaignplan/`).
  - **Stage 2:** the Operations diagram editor.
  - **Stage 3:** Orchestration (tasks, timeline, nudges).
  - **Stage 4:** Reporting.
  - **Not ported yet:** persona review, decision revision and the Decision Trail, plan editing, brief upload, and auto-assume.

  `/` serves the Cockpit. The Cockpit no longer links to or embeds `frontend/`. `/v2` still serves that app for its Home, Library and Prompt Library, and its intake can still start a plan outside a campaign, filed under "Earlier work" on save (F-R6 open).

### Sequencing and Shipping

```
A: U1 → U2 → U3 → U4        (the app works; the hierarchy exists behind the API)
B: U5 → U6                  (the Journey and Operations write flow rows)
C: U7                       (copy only; can run in parallel with B)
D: U8                       (needs U1's columns and U5's re-keyed flows)
E: U9 → U10 → U11 → U12     (UI; U12 flips `/` last)
```

Each phase is committed and pushed to `main` separately. The Cockpit build output (`app/static/cockpit`) and the `frontend/` build output (`app/static/v2`) are rebuilt and committed with any phase that changes them, because Render serves the committed bundles.

### Verification (every phase)

- `python scripts/verify_brand_journey.py` and `python scripts/verify_brand_hierarchy.py` pass.
- `python -m py_compile` passes on changed Python files.
- `cockpit/`: `npx tsc -b --noEmit`, `npm run lint` and `npm run build` pass.
- `frontend/`: `npx tsc -b --noEmit` and `npm run build` pass.
- UI phases (B's canvases and all of E) get a browser pass with Playwright against a local server with seeded data, run through the acceptance examples above. Test brands are created in a temp `DATA_DIR` or cleaned up afterwards, and `config/brand_kits.json` is restored.

### Risks

- **Journey flow re-keying (U5)** touches the most-tested code. Keep the old brand-keyed route shapes as thin wrappers that resolve the brand's Journey flow id until U11 lands, then remove them.
- **The Operations agent's switch to structured ops (U6)** changes how the only write-capable agent works. Keep its validation (`tab_chat.py`'s ported flowchart rules) running on the result of applying the ops.
- **Postgres** (`DATABASE_URL` set). Run U1's `init_db` twice against a Postgres URL when one is available; otherwise note it as unverified in the U1 commit.
- **Embedding `frontend/` (U12)**: if the workspace depends on its own top-level layout in ways `embed=1` can't hide cleanly, stop (see Stop conditions) and port the Planning stage first.

## Sources

- Requirements: `docs/brainstorms/2026-09-24-brand-campaigns-index-requirements.md`, `docs/brainstorms/2026-09-24-brand-campaign-ia-ideas-2-7-requirements.md`.
- Ideation: `docs/ideation/2026-09-24-brand-campaign-engagement-plan-ia-ideation.html`.
- Code:
  - `db/campaign_content_schema.sql`, `strategy/campaign_store.py`, `strategy/projects.py` (the `ALTER` idiom), `strategy/bootstrap.py`;
  - `strategy/brand_journey.py` (`brand_ctx`, flow functions, `journey_flow`), `strategy/campaign_ops.py`, `strategy/tab_chat.py`, `strategy/conversation.py` (`new_state`, slot filling);
  - `app/server.py` (`POST /api/projects`, the Deploy branch, campaign-plan-layout routes, page routes);
  - `frontend/src/App.tsx` (`openProjectId`), `cockpit/src/App.tsx`;
  - `strategy/dashboard.py`, `scripts/reset_test_data.py`, `scripts/verify_brand_journey.py`.
