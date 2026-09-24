-- =====================================================================================
-- Omni OS — Campaign & Content Data Model
-- =====================================================================================
-- Relational schema for campaigns and their content supply chain: modular content,
-- an atomic-claims library, and a claim<->reference substantiation graph, plus a
-- Digital-Asset-Management (DAM) asset catalogue that points at binary objects held in
-- the blob store (strategy/blob_store.py).
--
-- Design follows current pharma content best practice (see the vault note
-- "Omni OS — Campaign & Content Data Model + Industry Best Practices"):
--   * Modular content: reusable modules pre-approved once by MLR, each carrying a
--     material number and business rules, then assembled into many assets (Veeva
--     PromoMats pattern; ~70% claim reuse reported post-adoption).
--   * Atomic claims: every claim is a first-class, individually-approved object with a
--     status lifecycle and expiry, substantiated by one or more linked references
--     (claim-to-source traceability is the #1 driver of MLR rework when missing).
--   * DAM + taxonomy: assets carry standardized metadata + controlled-vocabulary tags
--     so modules are findable across functions/markets.
--   * Audit trail: every MLR/PRC review decision is recorded (compliance requirement).
--
-- Written in ANSI-ish SQL that runs as-is on SQLite (the tool's engine). Portability
-- notes for Oracle PL/SQL / PostgreSQL are inline as "-- ORA:" comments (VARCHAR2/CLOB,
-- sequences vs AUTOINCREMENT, TIMESTAMP types). IDs are surrogate INTEGER PKs; natural
-- keys (material_number, mlr_code) are UNIQUE.
-- =====================================================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------------ reference data ----

-- Client organisations (Bayer, Ipsen, ...). ORA: VARCHAR2(120).
CREATE TABLE IF NOT EXISTS client (
    id           INTEGER PRIMARY KEY,          -- ORA: NUMBER GENERATED ALWAYS AS IDENTITY
    name         TEXT NOT NULL UNIQUE
);

-- Brand -> fixed therapy area (mirrors config/client_brands.json). A brand maps to one
-- therapy area; the variable dimension is the indication (below).
CREATE TABLE IF NOT EXISTS brand (
    id            INTEGER PRIMARY KEY,
    client_id     INTEGER REFERENCES client(id),
    name          TEXT NOT NULL UNIQUE,
    generic_name  TEXT,
    therapy_area  TEXT,
    lifecycle_key TEXT                          -- launch | growth | mature | loe
);

CREATE TABLE IF NOT EXISTS indication (
    id         INTEGER PRIMARY KEY,
    brand_id   INTEGER NOT NULL REFERENCES brand(id) ON DELETE CASCADE,
    label      TEXT NOT NULL,
    UNIQUE (brand_id, label)
);

-- Controlled-vocabulary taxonomy term (channel, audience, message-theme, market, ...).
CREATE TABLE IF NOT EXISTS taxonomy_term (
    id         INTEGER PRIMARY KEY,
    dimension  TEXT NOT NULL,                   -- e.g. 'channel','audience','theme','market','asset_type'
    term       TEXT NOT NULL,
    UNIQUE (dimension, term)
);

-- ------------------------------------------------------------------ blob manifest -----

-- Manifest for the content-addressed blob store. `blob_key` is the sha256 of the bytes;
-- `storage_uri` abstracts location (local file today: file://data/blobs/<key>; swap for
-- an azure://container/<key> or s3://bucket/<key> URI when moving to cloud blob storage).
CREATE TABLE IF NOT EXISTS blob (
    blob_key      TEXT PRIMARY KEY,             -- sha256 hex
    mime_type     TEXT,
    byte_size     INTEGER,
    original_name TEXT,
    storage_uri   TEXT NOT NULL,
    created_at    TEXT NOT NULL                 -- ISO-8601 UTC; ORA: TIMESTAMP WITH TIME ZONE
);

-- Blob *bytes*, used only on the disk-free Postgres backend (blob_store.py branches on
-- db.IS_PG). On local SQLite the bytes stay on the filesystem under data/blobs/ and this
-- table is unused. BLOB translates to BYTEA on Postgres (see strategy/db.py to_pg_ddl).
CREATE TABLE IF NOT EXISTS blob_data (
    blob_key      TEXT PRIMARY KEY,             -- sha256 hex; matches blob.blob_key
    data          BLOB NOT NULL                 -- the raw bytes; ORA: BLOB, PG: BYTEA
);

-- ------------------------------------------------------------------ references --------

-- A source that can substantiate claims. source_type keeps provenance explicit.
CREATE TABLE IF NOT EXISTS ref_source (
    id           INTEGER PRIMARY KEY,
    source_type  TEXT NOT NULL,                 -- label|clinicaltrials|pubmed|dailymed|data_on_file|congress|guideline
    citation     TEXT NOT NULL,                 -- human-readable citation / title
    url          TEXT,
    external_id  TEXT,                          -- PMID, NCT number, SPL setid, ...
    annotation   TEXT,                          -- reviewer annotation / relevant excerpt
    blob_key     TEXT REFERENCES blob(blob_key),-- optional stored PDF of the source
    created_at   TEXT NOT NULL,
    UNIQUE (source_type, external_id)
);

-- ------------------------------------------------------------------ claims library ---

-- Atomic, individually-approved claim. This IS the claims library. claim_status drives
-- the MLR lifecycle; expires_at supports periodic re-substantiation.
CREATE TABLE IF NOT EXISTS claim (
    id              INTEGER PRIMARY KEY,
    brand_id        INTEGER REFERENCES brand(id),
    indication_id   INTEGER REFERENCES indication(id),
    text            TEXT NOT NULL,
    claim_type      TEXT NOT NULL DEFAULT 'efficacy', -- efficacy|safety|rtb|isi|fair_balance|moa|access|other
    claim_status    TEXT NOT NULL DEFAULT 'draft',    -- draft|in_review|approved|expired|retired
    material_number TEXT UNIQUE,                       -- MLR material number once approved
    mlr_code        TEXT,                              -- PRC/MLR job code
    approved_at     TEXT,
    expires_at      TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_claim_brand   ON claim(brand_id);
CREATE INDEX IF NOT EXISTS ix_claim_status  ON claim(claim_status);

-- Claim <-> reference substantiation (M:N). Every promotional claim must resolve to at
-- least one approved reference; the anchor/locator records exactly where in the source.
CREATE TABLE IF NOT EXISTS claim_reference (
    claim_id     INTEGER NOT NULL REFERENCES claim(id) ON DELETE CASCADE,
    ref_id       INTEGER NOT NULL REFERENCES ref_source(id) ON DELETE CASCADE,
    locator      TEXT,                          -- page/figure/table anchor within the source
    PRIMARY KEY (claim_id, ref_id)
);

-- ------------------------------------------------------------------ modular content --

-- A reusable content module: pre-approved once, assembled into many assets. Carries its
-- own material number + business rules (Veeva PromoMats modular-content pattern).
CREATE TABLE IF NOT EXISTS content_module (
    id              INTEGER PRIMARY KEY,
    brand_id        INTEGER REFERENCES brand(id),
    indication_id   INTEGER REFERENCES indication(id),
    name            TEXT NOT NULL,
    module_type     TEXT NOT NULL DEFAULT 'text', -- text|visual|claim_block|isi|reference_block|cta
    status          TEXT NOT NULL DEFAULT 'draft',-- draft|in_review|approved|expired|retired
    material_number TEXT UNIQUE,
    business_rules  TEXT,                         -- when/where this module may be used
    blob_key        TEXT REFERENCES blob(blob_key),
    created_at      TEXT NOT NULL
);

-- Which claims a module carries (M:N) -> gives claim-level traceability into every asset.
CREATE TABLE IF NOT EXISTS module_claim (
    module_id  INTEGER NOT NULL REFERENCES content_module(id) ON DELETE CASCADE,
    claim_id   INTEGER NOT NULL REFERENCES claim(id) ON DELETE CASCADE,
    PRIMARY KEY (module_id, claim_id)
);

-- ------------------------------------------------------------------ DAM assets -------

-- Digital-asset catalogue (the "Map Existing Content" audit, Sheet 8). Binary lives in
-- the blob store; this row is the searchable metadata record.
CREATE TABLE IF NOT EXISTS content_asset (
    id            INTEGER PRIMARY KEY,
    brand_id      INTEGER REFERENCES brand(id),
    indication_id INTEGER REFERENCES indication(id),
    file_name     TEXT,
    title         TEXT,
    asset_format  TEXT,                          -- email|detail_aid|banner|video|pdf|webpage|...
    branded       INTEGER,                       -- 1 branded, 0 unbranded (SQLite bool)
    target_group  TEXT,                          -- archetype/persona the asset targets
    description   TEXT,
    url           TEXT,
    id_code       TEXT,                          -- content ID / veeva id
    blob_key      TEXT REFERENCES blob(blob_key),
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS asset_module (        -- assets are assembled from modules (M:N)
    asset_id   INTEGER NOT NULL REFERENCES content_asset(id) ON DELETE CASCADE,
    module_id  INTEGER NOT NULL REFERENCES content_module(id) ON DELETE CASCADE,
    PRIMARY KEY (asset_id, module_id)
);

-- Generic tag bridge (any taggable entity -> taxonomy term), so modules/assets/claims
-- are findable across the same controlled vocabulary.
CREATE TABLE IF NOT EXISTS entity_tag (
    entity_type INTEGER,                          -- see note below; use TEXT in practice
    entity_kind TEXT NOT NULL,                    -- 'asset'|'module'|'claim'|'campaign'
    entity_id   INTEGER NOT NULL,
    term_id     INTEGER NOT NULL REFERENCES taxonomy_term(id) ON DELETE CASCADE,
    PRIMARY KEY (entity_kind, entity_id, term_id)
);

-- ------------------------------------------------------------------ campaigns --------

CREATE TABLE IF NOT EXISTS campaign (
    id             INTEGER PRIMARY KEY,
    project_id     TEXT,                          -- links back to projects.db (the chat/plan)
    brand_id       INTEGER REFERENCES brand(id),
    indication_id  INTEGER REFERENCES indication(id),
    name           TEXT NOT NULL,
    lifecycle_key  TEXT,
    persona        TEXT,
    journey_stage  TEXT,
    cx_maturity    TEXT,                          -- Simple|Medium|Complex
    objective      TEXT,
    total_budget   REAL,
    status         TEXT NOT NULL DEFAULT 'draft', -- draft|in_review|approved|live|closed
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_campaign_brand ON campaign(brand_id);

-- Brand > Engagement Plan > Campaign > Flow (docs/plans/2026-09-24-1400-feat-brand-hierarchy-ia-plan.md).
-- A brand has many engagement plans (e.g. one per quarter); a campaign belongs to one
-- (campaign.engagement_plan_id, added by strategy/campaign_store.init_db since existing
-- databases predate it); a campaign has many flows. Brand identity is brand.kit_key, the
-- config/brand_kits.json key, also added by init_db.
CREATE TABLE IF NOT EXISTS engagement_plan (
    id            INTEGER PRIMARY KEY,
    brand_id      INTEGER NOT NULL REFERENCES brand(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    period_start  TEXT,                          -- optional ISO date
    period_end    TEXT,                          -- optional ISO date
    status        TEXT NOT NULL DEFAULT 'active',-- active|closed
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_engagement_plan_brand ON engagement_plan(brand_id);

CREATE TABLE IF NOT EXISTS flow (
    id              INTEGER PRIMARY KEY,
    campaign_id     INTEGER NOT NULL REFERENCES campaign(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    origin          TEXT NOT NULL DEFAULT 'manual',-- journey|campaign_plan|manual|legacy_layout
    status          TEXT NOT NULL DEFAULT 'draft', -- draft|built|confirmed
    base_json       TEXT,                          -- rules-built CampaignFlow with block codes
    ops_json        TEXT,                          -- kept structured edits, in order
    draft_ops_json  TEXT,                          -- pending edit awaiting keep/undo
    dropped_json    TEXT,                          -- kept edits a rebuild could not reapply
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_flow_campaign ON flow(campaign_id);

-- Immutable versioned snapshot of the generated plan (md + html live in the blob store).
CREATE TABLE IF NOT EXISTS campaign_version (
    id              INTEGER PRIMARY KEY,
    campaign_id     INTEGER NOT NULL REFERENCES campaign(id) ON DELETE CASCADE,
    version_no      INTEGER NOT NULL,
    plan_blob_key   TEXT REFERENCES blob(blob_key),  -- markdown plan
    result_blob_key TEXT REFERENCES blob(blob_key),  -- full result JSON
    created_at      TEXT NOT NULL,
    UNIQUE (campaign_id, version_no)
);

CREATE TABLE IF NOT EXISTS campaign_segment (
    id            INTEGER PRIMARY KEY,
    campaign_id   INTEGER NOT NULL REFERENCES campaign(id) ON DELETE CASCADE,
    persona       TEXT,
    abcd_json     TEXT,                          -- ABCD distribution
    ladder_json   TEXT,                          -- adoption/scientific ladder distribution
    digital_json  TEXT                           -- digital-preference distribution
);

CREATE TABLE IF NOT EXISTS campaign_message (
    id            INTEGER PRIMARY KEY,
    campaign_id   INTEGER NOT NULL REFERENCES campaign(id) ON DELETE CASCADE,
    topic         TEXT NOT NULL,
    ord           INTEGER,
    claim_id      INTEGER REFERENCES claim(id)   -- optional link into the claims library
);

CREATE TABLE IF NOT EXISTS campaign_channel (
    id            INTEGER PRIMARY KEY,
    campaign_id   INTEGER NOT NULL REFERENCES campaign(id) ON DELETE CASCADE,
    channel       TEXT NOT NULL,
    share_pct     REAL,
    budget_amount REAL,
    pp_npp        TEXT                            -- PP | NPP
);

CREATE TABLE IF NOT EXISTS campaign_kpi (
    id            INTEGER PRIMARY KEY,
    campaign_id   INTEGER NOT NULL REFERENCES campaign(id) ON DELETE CASCADE,
    kpi_type      TEXT,                           -- leading|lagging|operational
    metric        TEXT NOT NULL
);

-- ------------------------------------------------------------------ MLR audit trail --

-- Every review decision on a claim / module / asset — the compliance audit trail.
CREATE TABLE IF NOT EXISTS review_record (
    id           INTEGER PRIMARY KEY,
    entity_kind  TEXT NOT NULL,                  -- 'claim'|'module'|'asset'
    entity_id    INTEGER NOT NULL,
    action       TEXT NOT NULL,                  -- submitted|approved|rejected|expired|withdrawn
    reviewer     TEXT,
    decision_at  TEXT NOT NULL,
    notes        TEXT
);
CREATE INDEX IF NOT EXISTS ix_review_entity ON review_record(entity_kind, entity_id);

-- ------------------------------------------------------------------ market intel ------

-- Per-brand market analysis + lifecycle-stage assessment (loaded from
-- config/brand_market_intel.json by strategy/brand_lifecycle.py). One row per brand; the
-- lifecycle_stage here is the analyst-assessed stage with supporting evidence, distinct
-- from brand.lifecycle_key (which is the roster default used to seed a chat). List-valued
-- fields (evidence, catalysts, competitors) are stored as JSON text for portability.
CREATE TABLE IF NOT EXISTS brand_market_intel (
    id                INTEGER PRIMARY KEY,
    brand_id          INTEGER REFERENCES brand(id),
    brand_name        TEXT NOT NULL UNIQUE,       -- natural key so intel loads even before a brand row exists
    lifecycle_stage   TEXT NOT NULL,              -- launch | growth | mature | loe
    stage_confidence  TEXT,                       -- high | medium | low
    momentum          TEXT,                       -- accelerating | steady | declining
    evidence_json     TEXT,                       -- JSON array of grounded evidence points
    catalysts_json    TEXT,                       -- JSON array of near-term catalysts
    competitors_json  TEXT,                       -- JSON array of main competitors
    loe_horizon       TEXT,
    whitespace        TEXT,
    campaign_posture  TEXT,                        -- recommended omnichannel posture for the stage
    as_of             TEXT,
    updated_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_market_intel_stage ON brand_market_intel(lifecycle_stage);

-- ------------------------------------------------------------------ award campaigns --

-- Award-winning marketing campaigns relevant to the roster (loaded from
-- config/brand_campaign_awards.json by strategy/awards_store.py). Captures why a campaign
-- won, its core message, and a description of the hero creative -- creative-inspiration
-- reference for the Brand Engagement Plan's precedent section. Linked to the roster by
-- brand, therapy_area or client. List-valued source_urls stored as JSON text.
CREATE TABLE IF NOT EXISTS campaign_award (
    id                INTEGER PRIMARY KEY,
    award_id          TEXT NOT NULL UNIQUE,       -- stable slug from the JSON
    title             TEXT NOT NULL,
    client            TEXT,
    brand             TEXT,
    therapy_area      TEXT,
    roster_link       TEXT,                        -- brand | therapy_area | client | industry
    roster_link_note  TEXT,
    festival          TEXT,
    award             TEXT,
    tier              TEXT,                         -- Grand Prix | Grand | Gold | Silver | Bronze | Finalist
    year              INTEGER,
    agency            TEXT,
    why_awarded       TEXT,
    key_message       TEXT,
    creative_summary  TEXT,
    images_description TEXT,
    source_urls_json  TEXT,
    updated_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_award_ta    ON campaign_award(therapy_area);
CREATE INDEX IF NOT EXISTS ix_award_brand ON campaign_award(brand);
CREATE INDEX IF NOT EXISTS ix_award_client ON campaign_award(client);

-- ------------------------------------------------------------------ convenience view --

-- Unsubstantiated approved claims (an approved claim with no linked reference) — the MLR
-- risk flag a dashboard should surface.
CREATE VIEW IF NOT EXISTS v_unsubstantiated_claims AS
SELECT c.id, c.text, c.claim_status, c.brand_id
FROM claim c
LEFT JOIN claim_reference cr ON cr.claim_id = c.id
WHERE cr.claim_id IS NULL AND c.claim_status = 'approved';
