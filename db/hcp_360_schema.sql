-- =====================================================================================
-- Omni OS — HCP 360 Data Model
-- =====================================================================================
-- Six tables holding synthetic HCP (healthcare provider) 360 data -- demographics,
-- channel affinity, content affinity, TRx therapeutic history, day/time preferences and
-- target-list/writer status -- all joined by NPI (National Provider Identifier). Loaded
-- from the committed JSON seed files under config/hcp_360/ by strategy/hcp_360.py
-- (load_hcp_360(), idempotent).
--
-- This mirrors an Oracle 19c schema originally designed for the same reference data
-- (see plsql/01_ddl.sql in this conversation's deliverables) -- table/column names match
-- 1:1 so the two are interchangeable; "-- ORA:" comments note the Oracle type. Written in
-- SQLite here since that's this app's engine (strategy/db.py).
-- =====================================================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------------ 1. demographic ----
-- ORA: NUMBER(10) NPI, VARCHAR2 text columns, DATE/TIMESTAMP WITH TIME ZONE -> stored
-- here as ISO-8601 TEXT (matches how the JSON already encodes them).
CREATE TABLE IF NOT EXISTS hcp_demographic_data__dlm (
    datasourceobject__c              TEXT,
    datasource__c                    TEXT,
    internalorganization__c          TEXT,     -- always NULL in reference data
    kq_npi_number__c                 INTEGER,  -- always NULL in reference data
    address__c                       TEXT,
    age__c                           INTEGER,
    ama_no_contact__c                TEXT,
    ama_pdrp_date__c                 TEXT,
    ama_pdrp_flag__c                 TEXT,
    city__c                          TEXT,
    credential_desc__c               TEXT,
    email__c                         TEXT,
    first_name__c                    TEXT,
    full_name__c                     TEXT,
    gender__c                        TEXT,
    last_name__c                     TEXT,
    last_refresh_date__c             TEXT,
    me_number__c                     TEXT,     -- always NULL in reference data
    npi_number__c                    INTEGER PRIMARY KEY,
    phone_number__c                  TEXT,
    practitioner_type_desc__c        TEXT,
    primary_corp_specialty_desc__c   TEXT,     -- always NULL in reference data
    primary_specialty_description__c TEXT,
    rel_id__c                        TEXT,     -- always NULL in reference data
    spi_number__c                    TEXT,     -- always NULL in reference data
    state_code__c                    TEXT,
    state_name__c                    TEXT,     -- always NULL in reference data
    zip_code__c                      INTEGER
);

-- ------------------------------------------------------------- 2. channel affinity ----
CREATE TABLE IF NOT EXISTS global_channel_affinity_and_preference (
    datasourceobject__c     TEXT,
    datasource__c            TEXT,
    internalorganization__c  TEXT,
    kq_npi_number__c         INTEGER,
    digitalscore_raw__c      INTEGER,
    ehrscore_raw__c          INTEGER,
    emailscore_raw__c        INTEGER,
    last_refresh_date__c     TEXT,
    npi_number__c             INTEGER PRIMARY KEY REFERENCES hcp_demographic_data__dlm(npi_number__c),
    preferred_channel__c     TEXT,
    progscore_raw__c         INTEGER,
    telescore_raw__c         INTEGER
);

-- -------------------------------------------------------------- 3. content affinity ---
CREATE TABLE IF NOT EXISTS global_content_affinity_score_data (
    datasourceobject__c                    TEXT,
    datasource__c                          TEXT,
    internalorganization__c                TEXT,
    kq_npi_num__c                          INTEGER,
    last_refresh_date__c                   TEXT,
    month__c                               TEXT,
    most_preferred_content_tag__c          TEXT,
    npi_num__c                             INTEGER PRIMARY KEY REFERENCES hcp_demographic_data__dlm(npi_number__c),
    second_most_preferred_content_tag__c   TEXT,
    third_most_preferred_content_tag__c    TEXT
);

-- --------------------------------------------------------- 4. TRx therapeutic data ----
-- 1-3 rows per HCP (not one-to-one), so no PK on npi_number__c -- indexed instead.
CREATE TABLE IF NOT EXISTS tbl_trx_therapeutic_data__dlm (
    datasourceobject__c    TEXT,
    datasource__c           TEXT,
    internalorganization__c TEXT,
    kq_npi_number__c        INTEGER,
    bb_usc_desc2__c         TEXT,
    last_refresh_date__c    TEXT,
    npi_number__c            INTEGER REFERENCES hcp_demographic_data__dlm(npi_number__c),
    trx_count__c             INTEGER
);
CREATE INDEX IF NOT EXISTS ix_trx_npi ON tbl_trx_therapeutic_data__dlm (npi_number__c);

-- -------------------------------------------------------- 5. day/time preference -----
-- 5 channels (ehr, email, prog, rte, tele) x 9 rank fields each.
CREATE TABLE IF NOT EXISTS global_day_time_preference_data (
    datasourceobject__c                          TEXT,
    datasource__c                                 TEXT,
    internalorganization__c                       TEXT,
    kq_npi_num__c                                 INTEGER,
    last_refresh_date__c                          TEXT,
    month__c                                      TEXT,
    npi_num__c                                    INTEGER PRIMARY KEY REFERENCES hcp_demographic_data__dlm(npi_number__c),
    most_preferred_day_ehr__c                     TEXT,
    most_preferred_day_session_ehr__c             TEXT,
    most_preferred_session_ehr__c                 TEXT,
    second_most_preferred_day_ehr__c              TEXT,
    second_most_preferred_day_session_ehr__c      TEXT,
    second_most_preferred_session_ehr__c          TEXT,
    third_most_preferred_day_ehr__c               TEXT,
    third_most_preferred_day_session_ehr__c       TEXT,
    third_most_preferred_session_ehr__c           TEXT,
    most_preferred_day_email__c                   TEXT,
    most_preferred_day_session_email__c           TEXT,
    most_preferred_session_email__c               TEXT,
    second_most_preferred_day_email__c            TEXT,
    second_most_preferred_day_session_email__c    TEXT,
    second_most_preferred_session_email__c        TEXT,
    third_most_preferred_day_email__c             TEXT,
    third_most_preferred_day_session_email__c     TEXT,
    third_most_preferred_session_email__c         TEXT,
    most_preferred_day_prog__c                    TEXT,
    most_preferred_day_session_prog__c            TEXT,
    most_preferred_session_prog__c                TEXT,
    second_most_preferred_day_prog__c             TEXT,
    second_most_preferred_day_session_prog__c     TEXT,
    second_most_preferred_session_prog__c         TEXT,
    third_most_preferred_day_prog__c              TEXT,
    third_most_preferred_day_session_prog__c      TEXT,
    third_most_preferred_session_prog__c          TEXT,
    most_preferred_day_rte__c                     TEXT,
    most_preferred_day_session_rte__c             TEXT,
    most_preferred_session_rte__c                 TEXT,
    second_most_preferred_day_rte__c              TEXT,
    second_most_preferred_day_session_rte__c      TEXT,
    second_most_preferred_session_rte__c          TEXT,
    third_most_preferred_day_rte__c               TEXT,
    third_most_preferred_day_session_rte__c       TEXT,
    third_most_preferred_session_rte__c           TEXT,
    most_preferred_day_tele__c                    TEXT,
    most_preferred_day_session_tele__c            TEXT,
    most_preferred_session_tele__c                TEXT,
    second_most_preferred_day_tele__c             TEXT,
    second_most_preferred_day_session_tele__c     TEXT,
    second_most_preferred_session_tele__c         TEXT,
    third_most_preferred_day_tele__c              TEXT,
    third_most_preferred_day_session_tele__c      TEXT,
    third_most_preferred_session_tele__c          TEXT
);

-- ------------------------------------------------------------------- 6. TL / writer ---
CREATE TABLE IF NOT EXISTS tbl_tl_data__dlm (
    datasourceobject__c                          TEXT,
    datasource__c                                 TEXT,
    internalorganization__c                       TEXT,
    kq_npi_id__c                                  INTEGER,
    acc_affiliation_units_tier_non_writers__c     INTEGER,
    ama_no_contact__c                             TEXT,
    besponsa_writer__c                            INTEGER,
    bosulif_writers__c                            INTEGER,
    brand__c                                      TEXT,
    digital_affinity__c                           TEXT,
    duavee_writer__c                              INTEGER,
    estring_writer__c                             INTEGER,
    eucrisa_writers__c                            INTEGER,
    last_refresh_date__c                          TEXT,
    market_trx_tier__c                            TEXT,
    mylotarg_writer__c                            INTEGER,
    npi_id__c                                     INTEGER PRIMARY KEY REFERENCES hcp_demographic_data__dlm(npi_number__c),
    nsclc_trx_tier__c                             TEXT,
    number_of_brands_writer__c                    INTEGER,
    practitioner_first_name__c                    TEXT,   -- '0' sentinel or real, polymorphic
    practitioner_last_name__c                     TEXT,   -- '0' sentinel or real, polymorphic
    practitioner_state__c                         TEXT,   -- '0' sentinel or real, polymorphic
    premarin_writer__c                            INTEGER,
    prempro_writer__c                             INTEGER,
    primary_specialty_desc__c                     TEXT,
    product_trx_tier__c                           TEXT,
    rep_potential__c                              TEXT,
    rep_tier__c                                   TEXT,
    revenue_potential__c                          INTEGER,
    ros1_trx_tier__c                              TEXT,
    segment__c                                    TEXT,
    writing_persona__c                            TEXT,
    xalkori_writer__c                             INTEGER
);
