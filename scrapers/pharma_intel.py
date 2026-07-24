"""Build structured pharma intelligence tables from public-source captures.

The scrapers populate `documents` and raw blobs. This module turns that document lake
into queryable warehouse tables for companies, therapy areas, oncology brands, public
sources, and campaign-award mentions.
"""
from __future__ import annotations

import json
import pathlib
import re
import sqlite3
import time
import csv
import html as html_lib
import io
import xml.etree.ElementTree as ET
from typing import Any

from storage import BASE_DIR, get_db

CONFIG_DIR = BASE_DIR / "config"

SCHEMA = """
CREATE TABLE IF NOT EXISTS pharma_source (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    access TEXT,
    url TEXT,
    ingest_enabled INTEGER NOT NULL DEFAULT 0,
    fields_json TEXT,
    reason_disabled TEXT,
    as_of TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pharma_company (
    company_id TEXT PRIMARY KEY,
    rank INTEGER,
    company TEXT NOT NULL,
    headquarters TEXT,
    revenue_usd TEXT,
    ranking_basis TEXT,
    source_url TEXT,
    as_of TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pharma_company_rank ON pharma_company(rank);

CREATE TABLE IF NOT EXISTS therapy_area_seed (
    therapy_area TEXT PRIMARY KEY,
    priority INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS oncology_brand_seed (
    brand TEXT PRIMARY KEY,
    priority INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS official_brand_site (
    site_id TEXT PRIMARY KEY,
    brand TEXT NOT NULL,
    generic_name TEXT,
    company TEXT,
    therapy_area TEXT,
    audience TEXT,
    url TEXT NOT NULL,
    as_of TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_official_brand_site_brand ON official_brand_site(brand);

CREATE TABLE IF NOT EXISTS brand_message (
    message_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    brand TEXT NOT NULL,
    company TEXT,
    therapy_area TEXT,
    audience TEXT,
    message_type TEXT,
    message_text TEXT NOT NULL,
    source_url TEXT,
    extraction_confidence TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_brand_message_brand ON brand_message(brand);
CREATE INDEX IF NOT EXISTS idx_brand_message_therapy ON brand_message(therapy_area);

CREATE TABLE IF NOT EXISTS regulatory_label_message (
    label_message_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    source_system TEXT NOT NULL,
    brand TEXT,
    generic_name TEXT,
    manufacturer TEXT,
    therapy_area TEXT,
    label_section TEXT,
    message_text TEXT NOT NULL,
    source_url TEXT,
    is_oncology_priority INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_label_message_brand ON regulatory_label_message(brand);
CREATE INDEX IF NOT EXISTS idx_label_message_section ON regulatory_label_message(label_section);
CREATE INDEX IF NOT EXISTS idx_label_message_therapy ON regulatory_label_message(therapy_area);

CREATE TABLE IF NOT EXISTS openfda_event_reaction_count (
    event_reaction_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    brand TEXT NOT NULL,
    reaction_term TEXT NOT NULL,
    reaction_count INTEGER NOT NULL DEFAULT 0,
    api_last_updated TEXT,
    source_url TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_openfda_event_reaction_brand ON openfda_event_reaction_count(brand);
CREATE INDEX IF NOT EXISTS idx_openfda_event_reaction_term ON openfda_event_reaction_count(reaction_term);

CREATE TABLE IF NOT EXISTS openfda_event_serious_count (
    event_serious_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    brand TEXT NOT NULL,
    serious_code TEXT NOT NULL,
    serious_label TEXT,
    report_count INTEGER NOT NULL DEFAULT 0,
    api_last_updated TEXT,
    source_url TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_openfda_event_serious_brand ON openfda_event_serious_count(brand);

CREATE TABLE IF NOT EXISTS openfda_drug_shortage (
    shortage_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    status TEXT,
    update_type TEXT,
    initial_posting_date TEXT,
    update_date TEXT,
    discontinued_date TEXT,
    package_ndc TEXT,
    generic_name TEXT,
    brand_names TEXT,
    manufacturer_names TEXT,
    company_name TEXT,
    availability TEXT,
    shortage_reason TEXT,
    related_info TEXT,
    contact_info TEXT,
    therapeutic_category TEXT,
    dosage_form TEXT,
    presentation TEXT,
    is_oncology_priority INTEGER NOT NULL DEFAULT 0,
    source_url TEXT,
    api_last_updated TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_openfda_shortage_status ON openfda_drug_shortage(status);
CREATE INDEX IF NOT EXISTS idx_openfda_shortage_generic ON openfda_drug_shortage(generic_name);
CREATE INDEX IF NOT EXISTS idx_openfda_shortage_oncology ON openfda_drug_shortage(is_oncology_priority);

CREATE TABLE IF NOT EXISTS openfda_drug_recall (
    recall_record_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    matched_brand TEXT,
    query_term TEXT,
    term_type TEXT,
    recall_number TEXT,
    classification TEXT,
    status TEXT,
    recalling_firm TEXT,
    voluntary_mandated TEXT,
    product_type TEXT,
    product_description TEXT,
    reason_for_recall TEXT,
    distribution_pattern TEXT,
    code_info TEXT,
    initial_firm_notification TEXT,
    recall_initiation_date TEXT,
    report_date TEXT,
    termination_date TEXT,
    center_classification_date TEXT,
    source_url TEXT,
    api_last_updated TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_openfda_recall_brand ON openfda_drug_recall(matched_brand);
CREATE INDEX IF NOT EXISTS idx_openfda_recall_classification ON openfda_drug_recall(classification);
CREATE INDEX IF NOT EXISTS idx_openfda_recall_status ON openfda_drug_recall(status);
CREATE INDEX IF NOT EXISTS idx_openfda_recall_report_date ON openfda_drug_recall(report_date);

CREATE TABLE IF NOT EXISTS openfda_ndc_product (
    ndc_product_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    matched_brand TEXT,
    query_term TEXT,
    query_field TEXT,
    product_ndc TEXT,
    brand_name TEXT,
    generic_name TEXT,
    labeler_name TEXT,
    product_type TEXT,
    marketing_category TEXT,
    application_number TEXT,
    dosage_form TEXT,
    route TEXT,
    active_ingredients TEXT,
    pharm_class TEXT,
    dea_schedule TEXT,
    listing_expiration_date TEXT,
    marketing_start_date TEXT,
    marketing_end_date TEXT,
    finished INTEGER,
    source_url TEXT,
    api_last_updated TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_openfda_ndc_brand ON openfda_ndc_product(matched_brand);
CREATE INDEX IF NOT EXISTS idx_openfda_ndc_product_ndc ON openfda_ndc_product(product_ndc);
CREATE INDEX IF NOT EXISTS idx_openfda_ndc_labeler ON openfda_ndc_product(labeler_name);

CREATE TABLE IF NOT EXISTS openfda_ndc_package (
    ndc_package_id TEXT PRIMARY KEY,
    ndc_product_id TEXT NOT NULL,
    source_document_id INTEGER NOT NULL,
    matched_brand TEXT,
    product_ndc TEXT,
    package_ndc TEXT,
    package_description TEXT,
    marketing_start_date TEXT,
    marketing_end_date TEXT,
    sample INTEGER,
    source_url TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_openfda_ndc_package_brand ON openfda_ndc_package(matched_brand);
CREATE INDEX IF NOT EXISTS idx_openfda_ndc_package_ndc ON openfda_ndc_package(package_ndc);

CREATE TABLE IF NOT EXISTS rxnorm_concept (
    rxnorm_concept_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    matched_brand TEXT,
    query_term TEXT,
    term_type TEXT,
    rxcui TEXT NOT NULL,
    name TEXT,
    synonym TEXT,
    tty TEXT,
    language TEXT,
    suppress TEXT,
    umlscui TEXT,
    related_concept_count INTEGER NOT NULL DEFAULT 0,
    historical_ndc_count INTEGER NOT NULL DEFAULT 0,
    source_url TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rxnorm_concept_brand ON rxnorm_concept(matched_brand);
CREATE INDEX IF NOT EXISTS idx_rxnorm_concept_rxcui ON rxnorm_concept(rxcui);
CREATE INDEX IF NOT EXISTS idx_rxnorm_concept_tty ON rxnorm_concept(tty);

CREATE TABLE IF NOT EXISTS rxnorm_related_concept (
    rxnorm_related_id TEXT PRIMARY KEY,
    source_rxnorm_concept_id TEXT NOT NULL,
    matched_brand TEXT,
    source_rxcui TEXT NOT NULL,
    related_rxcui TEXT NOT NULL,
    related_name TEXT,
    related_synonym TEXT,
    related_tty TEXT,
    language TEXT,
    suppress TEXT,
    umlscui TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rxnorm_related_brand ON rxnorm_related_concept(matched_brand);
CREATE INDEX IF NOT EXISTS idx_rxnorm_related_source ON rxnorm_related_concept(source_rxcui);
CREATE INDEX IF NOT EXISTS idx_rxnorm_related_rxcui ON rxnorm_related_concept(related_rxcui);
CREATE INDEX IF NOT EXISTS idx_rxnorm_related_tty ON rxnorm_related_concept(related_tty);

CREATE TABLE IF NOT EXISTS fda_srlc_labeling_change (
    srlc_change_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    matched_brand TEXT,
    query_term TEXT,
    drug_name TEXT,
    active_ingredient TEXT,
    application_number TEXT,
    application_type TEXT,
    supplement_date TEXT,
    database_updated TEXT,
    detail_url TEXT,
    text_excerpt TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fda_srlc_brand ON fda_srlc_labeling_change(matched_brand);
CREATE INDEX IF NOT EXISTS idx_fda_srlc_drug ON fda_srlc_labeling_change(drug_name);
CREATE INDEX IF NOT EXISTS idx_fda_srlc_supplement_date ON fda_srlc_labeling_change(supplement_date);

CREATE TABLE IF NOT EXISTS nci_drug_dictionary_entry (
    nci_drug_entry_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    matched_brand TEXT,
    query_term TEXT,
    term_type TEXT,
    term_id TEXT,
    nci_concept_id TEXT,
    nci_concept_name TEXT,
    name TEXT,
    pretty_url_name TEXT,
    first_letter TEXT,
    term_name_type TEXT,
    definition_text TEXT,
    drug_info_summary_url TEXT,
    alias_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nci_drug_brand ON nci_drug_dictionary_entry(matched_brand);
CREATE INDEX IF NOT EXISTS idx_nci_drug_term_id ON nci_drug_dictionary_entry(term_id);
CREATE INDEX IF NOT EXISTS idx_nci_drug_concept ON nci_drug_dictionary_entry(nci_concept_id);

CREATE TABLE IF NOT EXISTS nci_drug_dictionary_alias (
    nci_drug_alias_id TEXT PRIMARY KEY,
    nci_drug_entry_id TEXT NOT NULL,
    matched_brand TEXT,
    alias_type TEXT,
    alias_name TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nci_drug_alias_brand ON nci_drug_dictionary_alias(matched_brand);
CREATE INDEX IF NOT EXISTS idx_nci_drug_alias_name ON nci_drug_dictionary_alias(alias_name);

CREATE TABLE IF NOT EXISTS nci_drug_information_summary (
    nci_drug_info_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    matched_brand TEXT,
    query_term TEXT,
    nci_concept_name TEXT,
    title TEXT,
    us_brand_names TEXT,
    fda_approved TEXT,
    use_in_cancer TEXT,
    posted_date TEXT,
    updated_date TEXT,
    link_count INTEGER NOT NULL DEFAULT 0,
    source_url TEXT,
    text_excerpt TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nci_drug_info_brand ON nci_drug_information_summary(matched_brand);
CREATE INDEX IF NOT EXISTS idx_nci_drug_info_concept ON nci_drug_information_summary(nci_concept_name);
CREATE INDEX IF NOT EXISTS idx_nci_drug_info_updated ON nci_drug_information_summary(updated_date);

CREATE TABLE IF NOT EXISTS dailymed_label (
    setid TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    search_term TEXT,
    title TEXT,
    brand TEXT,
    generic_name TEXT,
    manufacturer TEXT,
    spl_version INTEGER,
    published_date TEXT,
    source_url TEXT,
    is_oncology_priority INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dailymed_label_brand ON dailymed_label(brand);
CREATE INDEX IF NOT EXISTS idx_dailymed_label_oncology ON dailymed_label(is_oncology_priority);

CREATE TABLE IF NOT EXISTS clinical_trial (
    nct_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    search_term TEXT,
    brief_title TEXT,
    official_title TEXT,
    overall_status TEXT,
    phases TEXT,
    study_type TEXT,
    primary_purpose TEXT,
    enrollment_count INTEGER,
    enrollment_type TEXT,
    lead_sponsor TEXT,
    lead_sponsor_class TEXT,
    collaborators TEXT,
    start_date TEXT,
    primary_completion_date TEXT,
    completion_date TEXT,
    last_update_post_date TEXT,
    source_url TEXT,
    is_oncology_priority INTEGER NOT NULL DEFAULT 0,
    is_top_pharma_sponsor INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trial_status ON clinical_trial(overall_status);
CREATE INDEX IF NOT EXISTS idx_trial_sponsor ON clinical_trial(lead_sponsor);
CREATE INDEX IF NOT EXISTS idx_trial_phase ON clinical_trial(phases);

CREATE TABLE IF NOT EXISTS clinical_trial_condition (
    trial_condition_id TEXT PRIMARY KEY,
    nct_id TEXT NOT NULL,
    condition TEXT NOT NULL,
    is_oncology_condition INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trial_condition_nct ON clinical_trial_condition(nct_id);
CREATE INDEX IF NOT EXISTS idx_trial_condition_text ON clinical_trial_condition(condition);

CREATE TABLE IF NOT EXISTS clinical_trial_intervention (
    trial_intervention_id TEXT PRIMARY KEY,
    nct_id TEXT NOT NULL,
    intervention_type TEXT,
    intervention_name TEXT NOT NULL,
    is_oncology_brand INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trial_intervention_nct ON clinical_trial_intervention(nct_id);
CREATE INDEX IF NOT EXISTS idx_trial_intervention_name ON clinical_trial_intervention(intervention_name);

CREATE TABLE IF NOT EXISTS clinical_trial_location (
    trial_location_id TEXT PRIMARY KEY,
    nct_id TEXT NOT NULL,
    facility TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    country TEXT,
    latitude REAL,
    longitude REAL,
    status TEXT,
    contact_name TEXT,
    contact_phone TEXT,
    contact_email TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trial_location_nct ON clinical_trial_location(nct_id);
CREATE INDEX IF NOT EXISTS idx_trial_location_country ON clinical_trial_location(country);
CREATE INDEX IF NOT EXISTS idx_trial_location_state ON clinical_trial_location(state);
CREATE INDEX IF NOT EXISTS idx_trial_location_facility ON clinical_trial_location(facility);

CREATE TABLE IF NOT EXISTS pubmed_article (
    pmid TEXT PRIMARY KEY,
    source_document_id INTEGER,
    search_terms TEXT,
    title TEXT,
    abstract TEXT,
    journal TEXT,
    publication_year INTEGER,
    publication_date TEXT,
    doi TEXT,
    source_url TEXT,
    is_oncology_priority INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pubmed_year ON pubmed_article(publication_year);
CREATE INDEX IF NOT EXISTS idx_pubmed_title ON pubmed_article(title);

CREATE TABLE IF NOT EXISTS pubmed_article_mesh (
    pubmed_mesh_id TEXT PRIMARY KEY,
    pmid TEXT NOT NULL,
    descriptor TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pubmed_mesh_pmid ON pubmed_article_mesh(pmid);
CREATE INDEX IF NOT EXISTS idx_pubmed_mesh_descriptor ON pubmed_article_mesh(descriptor);

CREATE TABLE IF NOT EXISTS pubmed_article_publication_type (
    pubmed_publication_type_id TEXT PRIMARY KEY,
    pmid TEXT NOT NULL,
    publication_type TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pubmed_pubtype_pmid ON pubmed_article_publication_type(pmid);
CREATE INDEX IF NOT EXISTS idx_pubmed_pubtype_type ON pubmed_article_publication_type(publication_type);

CREATE TABLE IF NOT EXISTS asco_abstract (
    abstract_number TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    conference TEXT,
    meeting_year INTEGER,
    presentation_start_date TEXT,
    presentation_end_date TEXT,
    presentation_time_zone TEXT,
    speaker_display_name TEXT,
    session_title TEXT,
    session_type TEXT,
    presentation_title TEXT,
    tracks TEXT,
    abstract_body TEXT,
    brand_mentions TEXT,
    is_oncology_priority INTEGER NOT NULL DEFAULT 0,
    source_url TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_asco_track ON asco_abstract(tracks);
CREATE INDEX IF NOT EXISTS idx_asco_oncology ON asco_abstract(is_oncology_priority);
CREATE INDEX IF NOT EXISTS idx_asco_title ON asco_abstract(presentation_title);

CREATE TABLE IF NOT EXISTS seer_cancer_stat (
    stat_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    cancer_site TEXT,
    therapy_area TEXT,
    estimated_new_cases_2026 INTEGER,
    percent_all_new_cases REAL,
    estimated_deaths_2026 INTEGER,
    percent_all_cancer_deaths REAL,
    five_year_relative_survival_percent REAL,
    source_url TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_seer_therapy_area ON seer_cancer_stat(therapy_area);
CREATE INDEX IF NOT EXISTS idx_seer_cases ON seer_cancer_stat(estimated_new_cases_2026);

CREATE TABLE IF NOT EXISTS search_interest_series (
    term TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    source_system TEXT NOT NULL,
    avg_interest REAL,
    max_interest INTEGER,
    latest_interest INTEGER,
    point_count INTEGER,
    first_date TEXT,
    latest_date TEXT,
    is_oncology_priority INTEGER NOT NULL DEFAULT 0,
    source_url TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_search_interest_avg ON search_interest_series(avg_interest);
CREATE INDEX IF NOT EXISTS idx_search_interest_oncology ON search_interest_series(is_oncology_priority);

CREATE TABLE IF NOT EXISTS search_interest_point (
    interest_point_id TEXT PRIMARY KEY,
    term TEXT NOT NULL,
    date TEXT NOT NULL,
    interest INTEGER,
    is_partial INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_search_interest_point_term ON search_interest_point(term);
CREATE INDEX IF NOT EXISTS idx_search_interest_point_date ON search_interest_point(date);

CREATE TABLE IF NOT EXISTS cms_open_payment_general (
    record_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    matched_brand TEXT NOT NULL,
    covered_recipient_type TEXT,
    covered_recipient_profile_id TEXT,
    covered_recipient_npi TEXT,
    recipient_name TEXT,
    recipient_city TEXT,
    recipient_state TEXT,
    recipient_country TEXT,
    recipient_primary_type TEXT,
    recipient_specialty TEXT,
    submitting_manufacturer TEXT,
    payment_manufacturer TEXT,
    total_amount_usd REAL,
    date_of_payment TEXT,
    form_of_payment TEXT,
    nature_of_payment TEXT,
    contextual_information TEXT,
    related_product_indicator TEXT,
    product_category_or_therapy_area TEXT,
    associated_product TEXT,
    program_year INTEGER,
    payment_publication_date TEXT,
    source_url TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cms_open_payment_brand ON cms_open_payment_general(matched_brand);
CREATE INDEX IF NOT EXISTS idx_cms_open_payment_npi ON cms_open_payment_general(covered_recipient_npi);
CREATE INDEX IF NOT EXISTS idx_cms_open_payment_specialty ON cms_open_payment_general(recipient_specialty);
CREATE INDEX IF NOT EXISTS idx_cms_open_payment_amount ON cms_open_payment_general(total_amount_usd);

CREATE TABLE IF NOT EXISTS opdp_enforcement_action (
    action_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    issued_date TEXT,
    company TEXT,
    product_issue TEXT,
    therapy_area TEXT,
    source_url TEXT,
    extraction_confidence TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_opdp_company ON opdp_enforcement_action(company);
CREATE INDEX IF NOT EXISTS idx_opdp_therapy ON opdp_enforcement_action(therapy_area);

CREATE TABLE IF NOT EXISTS opdp_letter_document (
    letter_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    issued_date TEXT,
    company TEXT,
    product_issue TEXT,
    therapy_area TEXT,
    text_excerpt TEXT,
    text_length INTEGER,
    pdf_blob_path TEXT,
    source_url TEXT,
    is_oncology_priority INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_opdp_letter_company ON opdp_letter_document(company);
CREATE INDEX IF NOT EXISTS idx_opdp_letter_therapy ON opdp_letter_document(therapy_area);
CREATE INDEX IF NOT EXISTS idx_opdp_letter_oncology ON opdp_letter_document(is_oncology_priority);

CREATE TABLE IF NOT EXISTS orange_book_product (
    ob_product_id TEXT PRIMARY KEY,
    ingredient TEXT,
    df_route TEXT,
    trade_name TEXT,
    applicant TEXT,
    strength TEXT,
    appl_type TEXT,
    appl_no TEXT,
    product_no TEXT,
    te_code TEXT,
    approval_date TEXT,
    rld TEXT,
    rs TEXT,
    product_type TEXT,
    applicant_full_name TEXT,
    is_oncology_priority INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ob_product_trade ON orange_book_product(trade_name);
CREATE INDEX IF NOT EXISTS idx_ob_product_appl ON orange_book_product(appl_no, product_no);

CREATE TABLE IF NOT EXISTS orange_book_patent (
    ob_patent_id TEXT PRIMARY KEY,
    appl_type TEXT,
    appl_no TEXT,
    product_no TEXT,
    patent_no TEXT,
    patent_expire_date TEXT,
    drug_substance_flag TEXT,
    drug_product_flag TEXT,
    patent_use_code TEXT,
    delist_flag TEXT,
    submission_date TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ob_patent_appl ON orange_book_patent(appl_no, product_no);

CREATE TABLE IF NOT EXISTS orange_book_exclusivity (
    ob_exclusivity_id TEXT PRIMARY KEY,
    appl_type TEXT,
    appl_no TEXT,
    product_no TEXT,
    exclusivity_code TEXT,
    exclusivity_date TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ob_excl_appl ON orange_book_exclusivity(appl_no, product_no);

CREATE TABLE IF NOT EXISTS drugs_fda_application (
    appl_no TEXT PRIMARY KEY,
    appl_type TEXT,
    sponsor_name TEXT,
    public_notes TEXT,
    is_top_pharma_sponsor INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_daf_application_sponsor ON drugs_fda_application(sponsor_name);

CREATE TABLE IF NOT EXISTS drugs_fda_product (
    daf_product_id TEXT PRIMARY KEY,
    appl_no TEXT NOT NULL,
    product_no TEXT,
    form TEXT,
    strength TEXT,
    reference_drug TEXT,
    drug_name TEXT,
    active_ingredient TEXT,
    reference_standard TEXT,
    marketing_status TEXT,
    te_code TEXT,
    is_oncology_priority INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_daf_product_drug ON drugs_fda_product(drug_name);
CREATE INDEX IF NOT EXISTS idx_daf_product_appl ON drugs_fda_product(appl_no, product_no);

CREATE TABLE IF NOT EXISTS drugs_fda_submission (
    daf_submission_id TEXT PRIMARY KEY,
    appl_no TEXT NOT NULL,
    submission_type TEXT,
    submission_no TEXT,
    submission_status TEXT,
    submission_status_date TEXT,
    review_priority TEXT,
    submission_class_code TEXT,
    submission_class_description TEXT,
    public_notes TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_daf_submission_appl ON drugs_fda_submission(appl_no);

CREATE TABLE IF NOT EXISTS drugs_fda_application_doc (
    daf_doc_id TEXT PRIMARY KEY,
    appl_no TEXT NOT NULL,
    submission_type TEXT,
    submission_no TEXT,
    doc_type TEXT,
    title TEXT,
    doc_url TEXT,
    doc_date TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_daf_doc_appl ON drugs_fda_application_doc(appl_no);

CREATE TABLE IF NOT EXISTS purple_book_product (
    pb_product_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    release_label TEXT,
    change_type TEXT,
    applicant TEXT,
    bla_number TEXT,
    proprietary_name TEXT,
    proper_name TEXT,
    license_type TEXT,
    strength TEXT,
    dosage_form TEXT,
    route_of_administration TEXT,
    product_presentation TEXT,
    marketing_status TEXT,
    licensure TEXT,
    approval_date TEXT,
    approval_date_iso TEXT,
    interchangeable_approval_date TEXT,
    ref_product_proper_name TEXT,
    ref_product_proprietary_name TEXT,
    supplement_number TEXT,
    submission_type TEXT,
    interchangeable_supplement_number TEXT,
    license_number TEXT,
    product_number TEXT,
    center TEXT,
    date_of_first_licensure TEXT,
    exclusivity_expiration_date TEXT,
    first_interchangeable_exclusivity_exp_date TEXT,
    ref_product_exclusivity_exp_date TEXT,
    orphan_exclusivity_exp_date TEXT,
    patent_list_provided TEXT,
    is_oncology_priority INTEGER NOT NULL DEFAULT 0,
    source_url TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pb_product_brand ON purple_book_product(proprietary_name);
CREATE INDEX IF NOT EXISTS idx_pb_product_bla ON purple_book_product(bla_number, product_number);

CREATE TABLE IF NOT EXISTS fda_oncology_approval (
    approval_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    approval_date TEXT,
    approval_date_iso TEXT,
    headline TEXT NOT NULL,
    summary TEXT,
    drug_or_regimen TEXT,
    brand_mentions TEXT,
    company_mentions TEXT,
    tumor_type TEXT,
    source_url TEXT,
    extraction_confidence TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fda_onc_approval_date ON fda_oncology_approval(approval_date);
CREATE INDEX IF NOT EXISTS idx_fda_onc_tumor ON fda_oncology_approval(tumor_type);

CREATE TABLE IF NOT EXISTS ema_medicine (
    ema_product_number TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    category TEXT,
    name_of_medicine TEXT,
    medicine_status TEXT,
    opinion_status TEXT,
    international_non_proprietary_name_common_name TEXT,
    active_substance TEXT,
    therapeutic_area_mesh TEXT,
    atc_code_human TEXT,
    pharmacotherapeutic_group_human TEXT,
    therapeutic_indication TEXT,
    accelerated_assessment TEXT,
    additional_monitoring TEXT,
    advanced_therapy TEXT,
    biosimilar TEXT,
    conditional_approval TEXT,
    exceptional_circumstances TEXT,
    generic TEXT,
    orphan_medicine TEXT,
    prime_priority_medicine TEXT,
    marketing_authorisation_holder TEXT,
    european_commission_decision_date TEXT,
    european_commission_decision_date_iso TEXT,
    opinion_adopted_date TEXT,
    marketing_authorisation_date TEXT,
    first_published_date TEXT,
    last_updated_date TEXT,
    medicine_url TEXT,
    is_oncology_priority INTEGER NOT NULL DEFAULT 0,
    is_top_pharma_holder INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ema_medicine_name ON ema_medicine(name_of_medicine);
CREATE INDEX IF NOT EXISTS idx_ema_medicine_holder ON ema_medicine(marketing_authorisation_holder);
CREATE INDEX IF NOT EXISTS idx_ema_medicine_therapy ON ema_medicine(therapeutic_area_mesh);

CREATE TABLE IF NOT EXISTS ema_medicine_document (
    ema_document_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    name TEXT,
    document_type TEXT,
    medicine_name TEXT,
    ema_product_number TEXT,
    status TEXT,
    consultation_date TEXT,
    first_published_date TEXT,
    first_published_date_iso TEXT,
    last_updated_date TEXT,
    last_updated_date_iso TEXT,
    reference_number TEXT,
    document_url TEXT,
    parsed_from_malformed_feed INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ema_doc_product ON ema_medicine_document(ema_product_number);
CREATE INDEX IF NOT EXISTS idx_ema_doc_medicine ON ema_medicine_document(medicine_name);
CREATE INDEX IF NOT EXISTS idx_ema_doc_type ON ema_medicine_document(document_type);

CREATE TABLE IF NOT EXISTS sec_company (
    cik TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    ticker TEXT,
    sec_name TEXT,
    sic TEXT,
    sic_description TEXT,
    fiscal_year_end TEXT,
    top_pharma_rank INTEGER,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sec_company_ticker ON sec_company(ticker);

CREATE TABLE IF NOT EXISTS sec_filing (
    filing_id TEXT PRIMARY KEY,
    cik TEXT NOT NULL,
    company TEXT,
    ticker TEXT,
    accession_number TEXT,
    filing_date TEXT,
    report_date TEXT,
    acceptance_datetime TEXT,
    form TEXT,
    primary_document TEXT,
    primary_doc_description TEXT,
    filing_url TEXT,
    is_strategy_relevant INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sec_filing_cik ON sec_filing(cik);
CREATE INDEX IF NOT EXISTS idx_sec_filing_form ON sec_filing(form);
CREATE INDEX IF NOT EXISTS idx_sec_filing_date ON sec_filing(filing_date);

CREATE TABLE IF NOT EXISTS sec_filing_brand_mention (
    sec_brand_mention_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    company TEXT,
    ticker TEXT,
    cik TEXT,
    form TEXT,
    filing_date TEXT,
    brand TEXT NOT NULL,
    mention_count INTEGER NOT NULL DEFAULT 0,
    context_snippet TEXT,
    filing_url TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sec_brand_mention_brand ON sec_filing_brand_mention(brand);
CREATE INDEX IF NOT EXISTS idx_sec_brand_mention_company ON sec_filing_brand_mention(company);

CREATE TABLE IF NOT EXISTS oncology_sales_company (
    company TEXT PRIMARY KEY,
    source_url TEXT,
    extracted_text TEXT,
    extraction_confidence TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaign_award_mention (
    mention_id TEXT PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    program TEXT,
    year INTEGER,
    category TEXT,
    tier TEXT,
    campaign TEXT,
    brand TEXT,
    company TEXT,
    agency TEXT,
    therapy_area TEXT,
    raw_line TEXT,
    source_url TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_campaign_award_mention_program ON campaign_award_mention(program, year);
CREATE INDEX IF NOT EXISTS idx_campaign_award_mention_therapy ON campaign_award_mention(therapy_area);
CREATE INDEX IF NOT EXISTS idx_campaign_award_mention_company ON campaign_award_mention(company);

CREATE TABLE IF NOT EXISTS pharma_intel_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL,
    sources INTEGER NOT NULL,
    companies INTEGER NOT NULL,
    therapy_areas INTEGER NOT NULL,
    oncology_brands INTEGER NOT NULL,
    oncology_sales_companies INTEGER NOT NULL,
    award_mentions INTEGER NOT NULL
);

CREATE VIEW IF NOT EXISTS v_oncology_award_mentions AS
SELECT
    year,
    program,
    category,
    tier,
    campaign,
    company,
    source_url
FROM campaign_award_mention
WHERE therapy_area='oncology'
ORDER BY year DESC, program, category, tier;

CREATE VIEW IF NOT EXISTS v_top_pharma_oncology_priority AS
SELECT
    pc.rank,
    pc.company,
    pc.headquarters,
    pc.revenue_usd,
    CASE WHEN osc.company IS NULL THEN 0 ELSE 1 END AS has_oncology_sales_source,
    osc.source_url AS oncology_sales_source_url
FROM pharma_company pc
LEFT JOIN oncology_sales_company osc ON lower(osc.company)=lower(pc.company)
ORDER BY pc.rank;

CREATE VIEW IF NOT EXISTS v_official_oncology_brand_messages AS
SELECT
    bm.brand,
    bm.company,
    bm.therapy_area,
    bm.audience,
    bm.message_type,
    bm.message_text,
    bm.source_url
FROM brand_message bm
ORDER BY bm.brand, bm.audience, bm.message_type, bm.message_text;

CREATE VIEW IF NOT EXISTS v_oncology_label_messages AS
SELECT
    brand,
    generic_name,
    manufacturer,
    label_section,
    message_text,
    source_url
FROM regulatory_label_message
WHERE is_oncology_priority=1
ORDER BY brand, label_section, message_text;

CREATE VIEW IF NOT EXISTS v_openfda_event_oncology_reactions AS
SELECT
    brand,
    reaction_term,
    reaction_count,
    api_last_updated,
    source_url
FROM openfda_event_reaction_count
ORDER BY reaction_count DESC, brand, reaction_term;

CREATE VIEW IF NOT EXISTS v_openfda_event_oncology_seriousness AS
SELECT
    brand,
    serious_code,
    serious_label,
    report_count,
    api_last_updated,
    source_url
FROM openfda_event_serious_count
ORDER BY brand, serious_code;

CREATE VIEW IF NOT EXISTS v_openfda_oncology_drug_shortages AS
SELECT
    status,
    update_type,
    initial_posting_date,
    update_date,
    generic_name,
    brand_names,
    manufacturer_names,
    company_name,
    availability,
    shortage_reason,
    related_info,
    therapeutic_category,
    presentation,
    source_url,
    api_last_updated
FROM openfda_drug_shortage
WHERE is_oncology_priority=1
ORDER BY status, generic_name, update_date DESC, package_ndc;

CREATE VIEW IF NOT EXISTS v_openfda_oncology_drug_recalls AS
SELECT
    matched_brand,
    query_term,
    term_type,
    recall_number,
    classification,
    status,
    recalling_firm,
    product_description,
    reason_for_recall,
    distribution_pattern,
    code_info,
    recall_initiation_date,
    report_date,
    termination_date,
    source_url,
    api_last_updated
FROM openfda_drug_recall
ORDER BY report_date DESC, matched_brand, classification, recall_number;

CREATE VIEW IF NOT EXISTS v_openfda_oncology_ndc_products AS
SELECT
    matched_brand,
    query_term,
    query_field,
    product_ndc,
    brand_name,
    generic_name,
    labeler_name,
    product_type,
    marketing_category,
    application_number,
    dosage_form,
    route,
    active_ingredients,
    listing_expiration_date,
    marketing_start_date,
    marketing_end_date,
    finished,
    source_url,
    api_last_updated
FROM openfda_ndc_product
ORDER BY matched_brand, brand_name, product_ndc;

CREATE VIEW IF NOT EXISTS v_openfda_oncology_ndc_packages AS
SELECT
    p.matched_brand,
    p.brand_name,
    p.generic_name,
    p.labeler_name,
    p.marketing_category,
    p.dosage_form,
    p.route,
    pkg.product_ndc,
    pkg.package_ndc,
    pkg.package_description,
    pkg.marketing_start_date,
    pkg.marketing_end_date,
    pkg.sample,
    pkg.source_url
FROM openfda_ndc_package pkg
JOIN openfda_ndc_product p ON p.ndc_product_id=pkg.ndc_product_id
ORDER BY p.matched_brand, p.brand_name, pkg.package_ndc;

CREATE VIEW IF NOT EXISTS v_rxnorm_oncology_concepts AS
SELECT
    matched_brand,
    query_term,
    term_type,
    rxcui,
    name,
    synonym,
    tty,
    related_concept_count,
    historical_ndc_count,
    source_url
FROM rxnorm_concept
ORDER BY matched_brand, term_type, name, rxcui;

CREATE VIEW IF NOT EXISTS v_rxnorm_oncology_related_concepts AS
SELECT
    matched_brand,
    source_rxcui,
    related_rxcui,
    related_name,
    related_synonym,
    related_tty,
    suppress
FROM rxnorm_related_concept
ORDER BY matched_brand, source_rxcui, related_tty, related_name;

CREATE VIEW IF NOT EXISTS v_fda_srlc_oncology_labeling_changes AS
SELECT
    matched_brand,
    query_term,
    drug_name,
    active_ingredient,
    application_number,
    application_type,
    supplement_date,
    database_updated,
    detail_url,
    text_excerpt
FROM fda_srlc_labeling_change
ORDER BY supplement_date DESC, database_updated DESC, matched_brand, drug_name;

CREATE VIEW IF NOT EXISTS v_nci_oncology_drug_dictionary AS
SELECT
    matched_brand,
    query_term,
    term_type,
    term_id,
    nci_concept_id,
    nci_concept_name,
    name,
    term_name_type,
    definition_text,
    drug_info_summary_url,
    alias_count
FROM nci_drug_dictionary_entry
ORDER BY matched_brand, term_type, nci_concept_name, term_id;

CREATE VIEW IF NOT EXISTS v_nci_oncology_drug_information_summaries AS
SELECT
    matched_brand,
    query_term,
    nci_concept_name,
    title,
    us_brand_names,
    fda_approved,
    use_in_cancer,
    posted_date,
    updated_date,
    source_url,
    text_excerpt
FROM nci_drug_information_summary
ORDER BY matched_brand, nci_concept_name, title;

CREATE VIEW IF NOT EXISTS v_dailymed_oncology_priority AS
SELECT
    brand,
    generic_name,
    manufacturer,
    spl_version,
    published_date,
    title,
    source_url
FROM dailymed_label
WHERE is_oncology_priority=1
ORDER BY brand, published_date DESC, title;

CREATE VIEW IF NOT EXISTS v_oncology_message_campaign_evidence AS
SELECT
    'award_campaign' AS evidence_type,
    COALESCE(NULLIF(brand, ''), NULL) AS brand,
    COALESCE(NULLIF(company, ''), NULL) AS company,
    NULL AS audience,
    category AS subtype,
    program AS program_or_source,
    year,
    category,
    tier,
    campaign AS campaign_or_title,
    raw_line AS message_text,
    source_url
FROM campaign_award_mention
WHERE therapy_area='oncology'
UNION ALL
SELECT
    'official_brand_message' AS evidence_type,
    brand,
    company,
    audience,
    message_type AS subtype,
    'official brand site' AS program_or_source,
    NULL AS year,
    NULL AS category,
    extraction_confidence AS tier,
    message_type AS campaign_or_title,
    message_text,
    source_url
FROM brand_message
UNION ALL
SELECT
    'fda_label_message' AS evidence_type,
    brand,
    manufacturer AS company,
    NULL AS audience,
    label_section AS subtype,
    source_system AS program_or_source,
    NULL AS year,
    NULL AS category,
    NULL AS tier,
    label_section AS campaign_or_title,
    message_text,
    source_url
FROM regulatory_label_message
WHERE is_oncology_priority=1
UNION ALL
SELECT
    'sec_annual_filing_mention' AS evidence_type,
    brand,
    company,
    NULL AS audience,
    form AS subtype,
    'SEC annual filing' AS program_or_source,
    CAST(substr(filing_date, 1, 4) AS INTEGER) AS year,
    NULL AS category,
    NULL AS tier,
    form || ' ' || filing_date AS campaign_or_title,
    context_snippet AS message_text,
    filing_url AS source_url
FROM sec_filing_brand_mention
ORDER BY evidence_type, brand, company, year DESC;

CREATE VIEW IF NOT EXISTS v_oncology_clinical_trials AS
SELECT
    t.nct_id,
    t.brief_title,
    t.overall_status,
    t.phases,
    t.study_type,
    t.primary_purpose,
    t.enrollment_count,
    t.lead_sponsor,
    t.lead_sponsor_class,
    t.is_top_pharma_sponsor,
    t.start_date,
    t.primary_completion_date,
    t.last_update_post_date,
    COUNT(DISTINCT l.trial_location_id) AS location_count,
    GROUP_CONCAT(DISTINCT l.country) AS countries,
    GROUP_CONCAT(DISTINCT CASE WHEN l.country='United States' THEN l.state END) AS us_states,
    GROUP_CONCAT(DISTINCT l.facility) AS facilities,
    GROUP_CONCAT(DISTINCT c.condition) AS conditions,
    GROUP_CONCAT(DISTINCT i.intervention_name) AS interventions,
    t.source_url
FROM clinical_trial t
LEFT JOIN clinical_trial_condition c ON c.nct_id=t.nct_id
LEFT JOIN clinical_trial_intervention i ON i.nct_id=t.nct_id
LEFT JOIN clinical_trial_location l ON l.nct_id=t.nct_id
WHERE t.is_oncology_priority=1
GROUP BY t.nct_id, t.brief_title, t.overall_status, t.phases, t.study_type, t.primary_purpose,
         t.enrollment_count, t.lead_sponsor, t.lead_sponsor_class, t.is_top_pharma_sponsor,
         t.start_date, t.primary_completion_date, t.last_update_post_date, t.source_url
ORDER BY t.last_update_post_date DESC, t.nct_id;

CREATE VIEW IF NOT EXISTS v_oncology_clinical_trial_locations AS
SELECT
    t.nct_id,
    t.brief_title,
    t.overall_status,
    t.phases,
    t.lead_sponsor,
    l.facility,
    l.city,
    l.state,
    l.zip,
    l.country,
    l.latitude,
    l.longitude,
    l.status,
    t.source_url
FROM clinical_trial t
JOIN clinical_trial_location l ON l.nct_id=t.nct_id
WHERE t.is_oncology_priority=1
ORDER BY l.country, l.state, l.city, l.facility, t.nct_id;

CREATE VIEW IF NOT EXISTS v_oncology_pubmed_articles AS
SELECT
    a.pmid,
    a.publication_year,
    a.title,
    a.journal,
    a.search_terms,
    GROUP_CONCAT(DISTINCT m.descriptor) AS mesh_terms,
    GROUP_CONCAT(DISTINCT p.publication_type) AS publication_types,
    a.source_url
FROM pubmed_article a
LEFT JOIN pubmed_article_mesh m ON m.pmid=a.pmid
LEFT JOIN pubmed_article_publication_type p ON p.pmid=a.pmid
WHERE a.is_oncology_priority=1
GROUP BY a.pmid, a.publication_year, a.title, a.journal, a.search_terms, a.source_url
ORDER BY a.publication_year DESC, a.pmid DESC;

CREATE VIEW IF NOT EXISTS v_asco_oncology_abstracts AS
SELECT
    abstract_number,
    meeting_year,
    presentation_start_date,
    speaker_display_name,
    session_title,
    session_type,
    presentation_title,
    tracks,
    brand_mentions,
    source_url
FROM asco_abstract
WHERE is_oncology_priority=1
ORDER BY presentation_start_date DESC, abstract_number;

CREATE VIEW IF NOT EXISTS v_seer_oncology_market_context AS
SELECT
    cancer_site,
    therapy_area,
    estimated_new_cases_2026,
    percent_all_new_cases,
    estimated_deaths_2026,
    percent_all_cancer_deaths,
    five_year_relative_survival_percent,
    source_url
FROM seer_cancer_stat
ORDER BY estimated_new_cases_2026 DESC, cancer_site;

CREATE VIEW IF NOT EXISTS v_oncology_search_interest AS
SELECT
    term,
    avg_interest,
    max_interest,
    latest_interest,
    point_count,
    first_date,
    latest_date,
    source_url
FROM search_interest_series
WHERE is_oncology_priority=1
ORDER BY avg_interest DESC, max_interest DESC, term;

CREATE VIEW IF NOT EXISTS v_cms_open_payments_oncology AS
SELECT
    matched_brand AS brand,
    program_year,
    COUNT(*) AS payment_count,
    ROUND(SUM(COALESCE(total_amount_usd, 0)), 2) AS total_amount_usd,
    COUNT(DISTINCT covered_recipient_npi) AS distinct_recipient_npis,
    COUNT(DISTINCT recipient_specialty) AS distinct_specialties,
    source_url
FROM cms_open_payment_general
GROUP BY matched_brand, program_year, source_url
ORDER BY total_amount_usd DESC, payment_count DESC, matched_brand;

CREATE VIEW IF NOT EXISTS v_cms_open_payments_top_recipients AS
SELECT
    matched_brand AS brand,
    program_year,
    covered_recipient_npi,
    recipient_name,
    recipient_state,
    recipient_specialty,
    COUNT(*) AS payment_count,
    ROUND(SUM(COALESCE(total_amount_usd, 0)), 2) AS total_amount_usd,
    source_url
FROM cms_open_payment_general
GROUP BY matched_brand, program_year, covered_recipient_npi, recipient_name, recipient_state, recipient_specialty, source_url
ORDER BY total_amount_usd DESC, payment_count DESC, recipient_name;

CREATE VIEW IF NOT EXISTS v_oncology_brand_evidence_summary AS
SELECT
    b.brand,
    COALESCE((SELECT COUNT(*) FROM brand_message bm WHERE lower(bm.brand)=lower(b.brand)), 0) AS official_brand_message_count,
    COALESCE((SELECT COUNT(*) FROM regulatory_label_message lm WHERE lower(lm.brand)=lower(b.brand)), 0) AS label_message_count,
    COALESCE((SELECT COUNT(*) FROM dailymed_label dl WHERE lower(dl.search_term)=lower(b.brand) OR lower(dl.brand)=lower(b.brand)), 0) AS dailymed_label_count,
    COALESCE((SELECT COUNT(DISTINCT t.nct_id)
              FROM clinical_trial t
              LEFT JOIN clinical_trial_intervention i ON i.nct_id=t.nct_id
              WHERE lower(t.search_term)=lower(b.brand)
                 OR lower(i.intervention_name)=lower(b.brand)
                 OR instr(lower(i.intervention_name), lower(b.brand)) > 0), 0) AS clinical_trial_count,
    COALESCE((SELECT COUNT(DISTINCT a.pmid)
              FROM pubmed_article a
              WHERE lower(a.search_terms)=lower(b.brand)
                 OR instr(lower(a.search_terms), lower(b.brand)) > 0
                 OR instr(lower(a.title), lower(b.brand)) > 0
                 OR instr(lower(a.abstract), lower(b.brand)) > 0), 0) AS pubmed_article_count,
    COALESCE((SELECT COUNT(*) FROM asco_abstract aa
              WHERE instr(lower(aa.brand_mentions), lower(b.brand)) > 0
                 OR instr(lower(aa.presentation_title), lower(b.brand)) > 0
                 OR instr(lower(aa.abstract_body), lower(b.brand)) > 0), 0) AS asco_abstract_count,
    COALESCE((SELECT COUNT(*) FROM campaign_award_mention am
              WHERE lower(am.brand)=lower(b.brand)
                 OR instr(lower(am.campaign), lower(b.brand)) > 0
                 OR instr(lower(am.raw_line), lower(b.brand)) > 0), 0) AS award_mention_count,
    COALESCE((SELECT COUNT(*) FROM fda_oncology_approval fa
              WHERE instr(lower(fa.brand_mentions), lower(b.brand)) > 0
                 OR instr(lower(fa.headline), lower(b.brand)) > 0
                 OR instr(lower(fa.summary), lower(b.brand)) > 0), 0) AS fda_oncology_approval_count,
    COALESCE((SELECT COUNT(*) FROM drugs_fda_product dp WHERE lower(dp.drug_name)=lower(b.brand)), 0) AS drugs_fda_product_count,
    COALESCE((SELECT COUNT(*) FROM orange_book_product ob WHERE lower(ob.trade_name)=lower(b.brand)), 0) AS orange_book_product_count,
    COALESCE((SELECT COUNT(*) FROM purple_book_product pb
              WHERE lower(pb.proprietary_name)=lower(b.brand)
                 OR lower(pb.ref_product_proprietary_name)=lower(b.brand)), 0) AS purple_book_product_count,
    COALESCE((SELECT COUNT(*) FROM ema_medicine em WHERE lower(em.name_of_medicine)=lower(b.brand)), 0) AS ema_medicine_count,
    COALESCE((SELECT COUNT(*) FROM sec_filing_brand_mention sm WHERE lower(sm.brand)=lower(b.brand)), 0) AS sec_annual_filing_mention_count,
    COALESCE((SELECT COUNT(*) FROM search_interest_series si WHERE lower(si.term)=lower(b.brand)), 0) AS search_interest_series_count,
    COALESCE((SELECT COUNT(*) FROM cms_open_payment_general op WHERE lower(op.matched_brand)=lower(b.brand)), 0) AS open_payment_count,
    COALESCE((SELECT COUNT(*) FROM openfda_event_reaction_count er WHERE lower(er.brand)=lower(b.brand)), 0) AS adverse_event_reaction_count,
    COALESCE((SELECT COUNT(*) FROM openfda_drug_shortage ds
              WHERE instr(lower(ds.brand_names), lower(b.brand)) > 0
                 OR instr(lower(ds.generic_name), lower(b.brand)) > 0
                 OR instr(lower(ds.presentation), lower(b.brand)) > 0), 0) AS drug_shortage_count,
    COALESCE((SELECT COUNT(*) FROM openfda_drug_recall dr WHERE lower(dr.matched_brand)=lower(b.brand)), 0) AS drug_recall_count,
    COALESCE((SELECT COUNT(*) FROM openfda_ndc_product np WHERE lower(np.matched_brand)=lower(b.brand)), 0) AS ndc_product_count,
    COALESCE((SELECT COUNT(*) FROM rxnorm_concept rc WHERE lower(rc.matched_brand)=lower(b.brand)), 0) AS rxnorm_concept_count,
    COALESCE((SELECT COUNT(*) FROM fda_srlc_labeling_change slc WHERE lower(slc.matched_brand)=lower(b.brand)), 0) AS srlc_labeling_change_count,
    COALESCE((SELECT COUNT(*) FROM nci_drug_dictionary_entry nd WHERE lower(nd.matched_brand)=lower(b.brand)), 0) AS nci_drug_dictionary_count,
    COALESCE((SELECT COUNT(*) FROM nci_drug_information_summary ni WHERE lower(ni.matched_brand)=lower(b.brand)), 0) AS nci_drug_info_summary_count,
    (
        COALESCE((SELECT COUNT(*) FROM brand_message bm WHERE lower(bm.brand)=lower(b.brand)), 0) +
        COALESCE((SELECT COUNT(*) FROM regulatory_label_message lm WHERE lower(lm.brand)=lower(b.brand)), 0) +
        COALESCE((SELECT COUNT(*) FROM dailymed_label dl WHERE lower(dl.search_term)=lower(b.brand) OR lower(dl.brand)=lower(b.brand)), 0) +
        COALESCE((SELECT COUNT(DISTINCT t.nct_id)
                  FROM clinical_trial t
                  LEFT JOIN clinical_trial_intervention i ON i.nct_id=t.nct_id
                  WHERE lower(t.search_term)=lower(b.brand)
                     OR lower(i.intervention_name)=lower(b.brand)
                     OR instr(lower(i.intervention_name), lower(b.brand)) > 0), 0) +
        COALESCE((SELECT COUNT(DISTINCT a.pmid)
                  FROM pubmed_article a
                  WHERE lower(a.search_terms)=lower(b.brand)
                     OR instr(lower(a.search_terms), lower(b.brand)) > 0
                     OR instr(lower(a.title), lower(b.brand)) > 0
                     OR instr(lower(a.abstract), lower(b.brand)) > 0), 0) +
        COALESCE((SELECT COUNT(*) FROM asco_abstract aa
                  WHERE instr(lower(aa.brand_mentions), lower(b.brand)) > 0
                     OR instr(lower(aa.presentation_title), lower(b.brand)) > 0
                     OR instr(lower(aa.abstract_body), lower(b.brand)) > 0), 0) +
        COALESCE((SELECT COUNT(*) FROM campaign_award_mention am
                  WHERE lower(am.brand)=lower(b.brand)
                     OR instr(lower(am.campaign), lower(b.brand)) > 0
                     OR instr(lower(am.raw_line), lower(b.brand)) > 0), 0) +
        COALESCE((SELECT COUNT(*) FROM fda_oncology_approval fa
                  WHERE instr(lower(fa.brand_mentions), lower(b.brand)) > 0
                     OR instr(lower(fa.headline), lower(b.brand)) > 0
                     OR instr(lower(fa.summary), lower(b.brand)) > 0), 0) +
        COALESCE((SELECT COUNT(*) FROM drugs_fda_product dp WHERE lower(dp.drug_name)=lower(b.brand)), 0) +
        COALESCE((SELECT COUNT(*) FROM orange_book_product ob WHERE lower(ob.trade_name)=lower(b.brand)), 0) +
        COALESCE((SELECT COUNT(*) FROM purple_book_product pb
                  WHERE lower(pb.proprietary_name)=lower(b.brand)
                     OR lower(pb.ref_product_proprietary_name)=lower(b.brand)), 0) +
        COALESCE((SELECT COUNT(*) FROM ema_medicine em WHERE lower(em.name_of_medicine)=lower(b.brand)), 0) +
        COALESCE((SELECT COUNT(*) FROM sec_filing_brand_mention sm WHERE lower(sm.brand)=lower(b.brand)), 0) +
        COALESCE((SELECT COUNT(*) FROM search_interest_series si WHERE lower(si.term)=lower(b.brand)), 0) +
        COALESCE((SELECT COUNT(*) FROM cms_open_payment_general op WHERE lower(op.matched_brand)=lower(b.brand)), 0) +
        COALESCE((SELECT COUNT(*) FROM openfda_event_reaction_count er WHERE lower(er.brand)=lower(b.brand)), 0) +
        COALESCE((SELECT COUNT(*) FROM openfda_drug_shortage ds
                  WHERE instr(lower(ds.brand_names), lower(b.brand)) > 0
                     OR instr(lower(ds.generic_name), lower(b.brand)) > 0
                     OR instr(lower(ds.presentation), lower(b.brand)) > 0), 0) +
        COALESCE((SELECT COUNT(*) FROM openfda_drug_recall dr WHERE lower(dr.matched_brand)=lower(b.brand)), 0)
        +
        COALESCE((SELECT COUNT(*) FROM openfda_ndc_product np WHERE lower(np.matched_brand)=lower(b.brand)), 0)
        +
        COALESCE((SELECT COUNT(*) FROM rxnorm_concept rc WHERE lower(rc.matched_brand)=lower(b.brand)), 0)
        +
        COALESCE((SELECT COUNT(*) FROM fda_srlc_labeling_change slc WHERE lower(slc.matched_brand)=lower(b.brand)), 0)
        +
        COALESCE((SELECT COUNT(*) FROM nci_drug_dictionary_entry nd WHERE lower(nd.matched_brand)=lower(b.brand)), 0)
        +
        COALESCE((SELECT COUNT(*) FROM nci_drug_information_summary ni WHERE lower(ni.matched_brand)=lower(b.brand)), 0)
    ) AS total_evidence_count
FROM oncology_brand_seed b
ORDER BY total_evidence_count DESC, b.brand;

CREATE VIEW IF NOT EXISTS v_opdp_oncology_enforcement AS
SELECT
    issued_date,
    company,
    product_issue,
    source_url
FROM opdp_enforcement_action
WHERE therapy_area='oncology'
ORDER BY issued_date DESC, company, product_issue;

CREATE VIEW IF NOT EXISTS v_opdp_oncology_letter_documents AS
SELECT
    issued_date,
    company,
    product_issue,
    text_excerpt,
    text_length,
    pdf_blob_path,
    source_url
FROM opdp_letter_document
WHERE is_oncology_priority=1
ORDER BY issued_date DESC, company, product_issue;

CREATE VIEW IF NOT EXISTS v_orange_book_oncology_priority AS
SELECT
    p.trade_name,
    p.ingredient,
    p.applicant_full_name,
    p.appl_type,
    p.appl_no,
    p.product_no,
    p.approval_date,
    p.rld,
    p.rs,
    COUNT(DISTINCT pat.patent_no) AS patent_count,
    MAX(pat.patent_expire_date) AS latest_patent_expire_date,
    COUNT(DISTINCT ex.exclusivity_code || ':' || ex.exclusivity_date) AS exclusivity_count,
    MAX(ex.exclusivity_date) AS latest_exclusivity_date
FROM orange_book_product p
LEFT JOIN orange_book_patent pat ON pat.appl_no=p.appl_no AND pat.product_no=p.product_no
LEFT JOIN orange_book_exclusivity ex ON ex.appl_no=p.appl_no AND ex.product_no=p.product_no
WHERE p.is_oncology_priority=1
GROUP BY p.trade_name, p.ingredient, p.applicant_full_name, p.appl_type, p.appl_no, p.product_no, p.approval_date, p.rld, p.rs
ORDER BY p.trade_name, p.appl_no, p.product_no;

CREATE VIEW IF NOT EXISTS v_drugs_fda_oncology_priority AS
SELECT
    p.drug_name,
    p.active_ingredient,
    a.sponsor_name,
    a.appl_type,
    p.appl_no,
    p.product_no,
    p.marketing_status,
    p.reference_drug,
    p.reference_standard,
    MAX(s.submission_status_date) AS latest_submission_status_date,
    COUNT(DISTINCT s.daf_submission_id) AS submission_count,
    COUNT(DISTINCT d.daf_doc_id) AS document_count
FROM drugs_fda_product p
LEFT JOIN drugs_fda_application a ON a.appl_no=p.appl_no
LEFT JOIN drugs_fda_submission s ON s.appl_no=p.appl_no
LEFT JOIN drugs_fda_application_doc d ON d.appl_no=p.appl_no
WHERE p.is_oncology_priority=1
GROUP BY p.drug_name, p.active_ingredient, a.sponsor_name, a.appl_type, p.appl_no, p.product_no,
         p.marketing_status, p.reference_drug, p.reference_standard
ORDER BY p.drug_name, p.appl_no, p.product_no;

CREATE VIEW IF NOT EXISTS v_purple_book_oncology_priority AS
SELECT
    proprietary_name,
    proper_name,
    applicant,
    bla_number,
    product_number,
    change_type,
    marketing_status,
    licensure,
    approval_date,
    approval_date_iso,
    date_of_first_licensure,
    exclusivity_expiration_date,
    orphan_exclusivity_exp_date,
    ref_product_proprietary_name,
    ref_product_proper_name,
    patent_list_provided,
    source_url
FROM purple_book_product
WHERE is_oncology_priority=1
ORDER BY proprietary_name, bla_number, product_number;

CREATE VIEW IF NOT EXISTS v_fda_oncology_approval_timeline AS
SELECT
    approval_date,
    approval_date_iso,
    headline,
    drug_or_regimen,
    brand_mentions,
    company_mentions,
    tumor_type,
    source_url
FROM fda_oncology_approval
ORDER BY approval_date_iso DESC, headline;

CREATE VIEW IF NOT EXISTS v_ema_oncology_priority AS
SELECT
    name_of_medicine,
    active_substance,
    therapeutic_area_mesh,
    pharmacotherapeutic_group_human,
    marketing_authorisation_holder,
    medicine_status,
    european_commission_decision_date,
    european_commission_decision_date_iso,
    orphan_medicine,
    prime_priority_medicine,
    conditional_approval,
    therapeutic_indication,
    medicine_url
FROM ema_medicine
WHERE is_oncology_priority=1
ORDER BY european_commission_decision_date_iso DESC, name_of_medicine;

CREATE VIEW IF NOT EXISTS v_ema_oncology_documents AS
SELECT
    m.name_of_medicine,
    m.active_substance,
    m.therapeutic_area_mesh,
    m.marketing_authorisation_holder,
    d.document_type,
    d.name AS document_name,
    d.status AS document_status,
    d.reference_number,
    d.first_published_date,
    d.last_updated_date,
    d.document_url
FROM ema_medicine_document d
JOIN ema_medicine m ON m.ema_product_number=d.ema_product_number
WHERE m.is_oncology_priority=1
ORDER BY d.last_updated_date_iso DESC, d.first_published_date_iso DESC, m.name_of_medicine, d.document_type;

CREATE VIEW IF NOT EXISTS v_sec_top_pharma_filings AS
SELECT
    sc.top_pharma_rank,
    sc.company,
    sc.ticker,
    sc.cik,
    sc.sec_name,
    sf.form,
    sf.filing_date,
    sf.report_date,
    sf.primary_document,
    sf.filing_url
FROM sec_company sc
JOIN sec_filing sf ON sf.cik=sc.cik
WHERE sf.is_strategy_relevant=1
ORDER BY sc.top_pharma_rank, sf.filing_date DESC, sf.form;

CREATE VIEW IF NOT EXISTS v_sec_oncology_brand_mentions AS
SELECT
    brand,
    company,
    ticker,
    form,
    filing_date,
    mention_count,
    context_snippet,
    filing_url
FROM sec_filing_brand_mention
ORDER BY filing_date DESC, brand, mention_count DESC;
"""

ONCOLOGY_TERMS = [
    "oncology",
    "hematology",
    "cancer",
    "tumor",
    "leukemia",
    "lymphoma",
    "myeloma",
    "carcinoma",
    "melanoma",
    "sarcoma",
    "prostate",
    "breast",
    "lung",
    "bladder",
    "renal",
    "nubeqa",
    "adcetris",
    "alymsys",
    "anktiva",
    "brukinsa",
    "tecentriq",
    "tevimbra",
    "turalio",
    "fyarro",
    "iclusig",
    "imdelltra",
    "pemazyre",
    "photofrin",
    "calquence",
    "fruzaqla",
    "tazverik",
]

AWARD_HEADER_RE = re.compile(
    r"^(?P<category>[A-Z0-9][A-Z0-9 /&+\-()'.,]+?)"
    r"(?:\s+(?P<tier>GOLD|SILVER|BRONZE))?\s+(?P<label>WINNER|FINALIST)(?:S)?\s*:?\s*$",
    re.IGNORECASE,
)
AWARD_SIMPLE_HEADER_RE = re.compile(
    r"^(BRAND OF THE YEAR|MOST INNOVATIVE NEW PRODUCT|PRODUCT LAUNCH OF THE YEAR|"
    r"COMPANY OF THE YEAR:[A-Z0-9 /&+\-()'.,]+|MARKETER OF THE YEAR|MARKETING TEAM OF THE YEAR)\s*:?\s*$",
    re.IGNORECASE,
)
PHARMA_CHOICE_MEDAL_RE = re.compile(r"^(?P<tier>GOLD|SILVER|BRONZE)\s*:\s*(?P<body>.+)$", re.IGNORECASE)
PHARMA_CHOICE_CATEGORY_RE = re.compile(r"^[A-Z][A-Z0-9 /&+\-()']{2,60}$")
FIERCE_ARTICLE_WINNER_RE = re.compile(r"^.+?\s+for\s+[\"\u201c?](?P<campaign>[^\"\u201d?]+)[\"\u201d?]\.?$", re.IGNORECASE)
AWARD_PHARMA_COMPANY_HINTS = [
    "Bristol Myers Squibb",
    "Gilead Sciences",
    "Acadia Pharmaceuticals",
    "Pacira BioSciences",
    "Bausch Health",
    "Sanofi",
    "Amgen",
    "Pfizer",
    "Novartis",
    "UCB",
    "Takeda Oncology",
    "Sumitomo Pharma",
]
MESSAGE_HINT_RE = re.compile(
    r"\b("
    r"indicated|approved|treatment|treat|first|only|combination|monotherapy|"
    r"overall survival|progression-free survival|response|support|resources|"
    r"NCCN|Category 1|biomarker|testing|patient|patients"
    r")\b",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
FDA_ONC_DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
FDA_ONC_HEADLINE_RE = re.compile(r"^FDA\s+(approves|grants|authorizes|updates)\b", re.IGNORECASE)
PAREN_MENTION_RE = re.compile(r"\(([^()]+)\)")
TUMOR_HINTS = [
    "breast cancer",
    "bladder cancer",
    "lung cancer",
    "non-small cell lung cancer",
    "renal cell carcinoma",
    "prostate cancer",
    "multiple myeloma",
    "lymphoma",
    "leukemia",
    "cholangiocarcinoma",
    "ovarian",
    "fallopian tube",
    "peritoneal cancer",
    "melanoma",
    "solid tumors",
    "hematologic malignancies",
    "colorectal cancer",
    "gastric",
    "esophageal",
    "endometrial",
]
OPDP_SKIP_LINES = {
    "Untitled Letter",
    "Promotional Material",
    "(PDF)",
    "None",
    "Close-Out Letter",
}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _ensure_columns(conn: sqlite3.Connection) -> None:
    table_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(fda_oncology_approval)").fetchall()
    }
    if table_columns and "approval_date_iso" not in table_columns:
        conn.execute("ALTER TABLE fda_oncology_approval ADD COLUMN approval_date_iso TEXT")


def _date_iso(value: str) -> str:
    value = value.strip()
    for date_format in ("%m/%d/%Y", "%Y-%m-%d", "%d-%b-%y", "%d-%b-%Y"):
        try:
            parsed = time.strptime(value, date_format)
            return time.strftime("%Y-%m-%d", parsed)
        except Exception:
            continue
    return ""


def _date_iso_eu(value: str) -> str:
    value = value.strip()
    for date_format in ("%d/%m/%Y", "%Y-%m-%d", "%d-%b-%y", "%d-%b-%Y", "%m/%d/%Y"):
        try:
            parsed = time.strptime(value, date_format)
            return time.strftime("%Y-%m-%d", parsed)
        except Exception:
            continue
    return ""


def _slug(value: str) -> str:
    value = value.lower().replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def _read_json(name: str) -> dict[str, Any]:
    return json.loads((CONFIG_DIR / name).read_text(encoding="utf-8"))


def _upsert_sources(conn: sqlite3.Connection) -> int:
    data = _read_json("public_pharma_intel_sources.json")
    count = 0
    for source in data.get("sources", []):
        conn.execute(
            """
            INSERT INTO pharma_source
                (source_id, name, category, access, url, ingest_enabled, fields_json, reason_disabled, as_of, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source_id) DO UPDATE SET
                name=excluded.name,
                category=excluded.category,
                access=excluded.access,
                url=excluded.url,
                ingest_enabled=excluded.ingest_enabled,
                fields_json=excluded.fields_json,
                reason_disabled=excluded.reason_disabled,
                as_of=excluded.as_of,
                updated_at=excluded.updated_at
            """,
            (
                source["id"],
                source["name"],
                source.get("category", ""),
                source.get("access", ""),
                source.get("url", ""),
                1 if source.get("ingest_enabled") else 0,
                json.dumps(source.get("fields", [])),
                source.get("reason_disabled", ""),
                data.get("as_of", ""),
                _now(),
            ),
        )
        count += 1
    return count


def _upsert_companies(conn: sqlite3.Connection) -> int:
    data = _read_json("top_pharma_companies_2025.json")
    count = 0
    for company in data.get("companies", []):
        company_id = _slug(company["company"])
        conn.execute(
            """
            INSERT INTO pharma_company
                (company_id, rank, company, headquarters, revenue_usd, ranking_basis, source_url, as_of, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(company_id) DO UPDATE SET
                rank=excluded.rank,
                company=excluded.company,
                headquarters=excluded.headquarters,
                revenue_usd=excluded.revenue_usd,
                ranking_basis=excluded.ranking_basis,
                source_url=excluded.source_url,
                as_of=excluded.as_of,
                updated_at=excluded.updated_at
            """,
            (
                company_id,
                company.get("rank"),
                company["company"],
                company.get("headquarters", ""),
                company.get("revenue_usd", ""),
                data.get("ranking_basis", ""),
                data.get("source_url", ""),
                data.get("as_of", ""),
                _now(),
            ),
        )
        count += 1
    return count


def _top_rank_by_company(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        row["company"].lower(): row["rank"]
        for row in conn.execute("SELECT company, rank FROM pharma_company").fetchall()
    }


def _upsert_seeds(conn: sqlite3.Connection) -> tuple[int, int]:
    data = _read_json("pharma_intel_seed_terms.json")
    for idx, therapy_area in enumerate(data.get("priority_therapy_areas", []), start=1):
        conn.execute(
            "INSERT INTO therapy_area_seed (therapy_area, priority, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(therapy_area) DO UPDATE SET priority=excluded.priority, updated_at=excluded.updated_at",
            (therapy_area, idx, _now()),
        )
    for idx, brand in enumerate(data.get("priority_oncology_brands", []), start=1):
        conn.execute(
            "INSERT INTO oncology_brand_seed (brand, priority, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(brand) DO UPDATE SET priority=excluded.priority, updated_at=excluded.updated_at",
            (brand, idx, _now()),
        )
    return len(data.get("priority_therapy_areas", [])), len(data.get("priority_oncology_brands", []))


def _upsert_brand_sites(conn: sqlite3.Connection) -> int:
    data = _read_json("official_oncology_brand_sites.json")
    count = 0
    for site in data.get("sites", []):
        site_id = _slug(f"{site['brand']}_{site.get('audience', '')}_{site['url']}")
        conn.execute(
            """
            INSERT INTO official_brand_site
                (site_id, brand, generic_name, company, therapy_area, audience, url, as_of, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(site_id) DO UPDATE SET
                brand=excluded.brand,
                generic_name=excluded.generic_name,
                company=excluded.company,
                therapy_area=excluded.therapy_area,
                audience=excluded.audience,
                url=excluded.url,
                as_of=excluded.as_of,
                updated_at=excluded.updated_at
            """,
            (
                site_id,
                site["brand"],
                site.get("generic", ""),
                site.get("company", ""),
                site.get("therapy_area", ""),
                site.get("audience", ""),
                site["url"],
                data.get("as_of", ""),
                _now(),
            ),
        )
        count += 1
    return count


def _load_blob(blob_path: str) -> str:
    path = BASE_DIR / blob_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _rows_from_tilde_text(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text), delimiter="~")
    return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]


def _rows_from_tab_text(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    out: list[dict[str, str]] = []
    for row in reader:
        clean: dict[str, str] = {}
        overflow: list[str] = []
        for k, v in row.items():
            if k is None:
                if isinstance(v, list):
                    overflow.extend(str(part).strip() for part in v if str(part).strip())
                elif v:
                    overflow.append(str(v).strip())
                continue
            clean[k.strip()] = str(v or "").strip()
        if overflow:
            clean["_overflow"] = "\t".join(overflow)
        out.append(clean)
    return out


def _purple_book_release_and_rows(text: str) -> tuple[str, list[dict[str, str]]]:
    lines = text.lstrip("\ufeff").splitlines()
    release_label = ""
    header_index = 0
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if idx == 0:
            release_label = stripped.split(",", 1)[0].strip()
        if stripped.startswith("N/R/U,"):
            header_index = idx
            break
    reader = csv.DictReader(io.StringIO("\n".join(lines[header_index:])))
    rows = [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]
    return release_label, rows


def _json_data_rows(text: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(text or "{}")
        data = payload.get("data", [])
        return [row for row in data if isinstance(row, dict)]
    except Exception:
        rows: list[dict[str, Any]] = []
        for line in text.splitlines():
            stripped = line.strip().rstrip(",")
            if not stripped.startswith('{"id"'):
                continue
            try:
                row = json.loads(stripped)
            except Exception:
                continue
            if isinstance(row, dict):
                row["_parsed_from_malformed_feed"] = 1
                rows.append(row)
        return rows


def _derive_therapy_area(text: str, fallback: str = "") -> str:
    lowered = text.lower()
    for term in ONCOLOGY_TERMS:
        if term in lowered:
            return "oncology"
    return fallback


def _contains_cancer_signal(text: str) -> bool:
    lowered = text.lower()
    cancer_terms = [
        "neoplasm",
        "cancer",
        "carcinoma",
        "leukemia",
        "leukaemia",
        "lymphoma",
        "myeloma",
        "melanoma",
        "sarcoma",
        "tumor",
        "tumour",
        "malignan",
        "glioma",
        "oncology",
        "antineoplastic",
    ]
    return any(term in lowered for term in cancer_terms)


def _trial_date(module: dict[str, Any], key: str) -> str:
    value = module.get(key, "")
    if isinstance(value, dict):
        return str(value.get("date", "")).strip()
    return str(value or "").strip()


def _split_intervention(value: str) -> tuple[str, str]:
    if ":" in value:
        intervention_type, name = value.split(":", 1)
        return intervention_type.strip(), name.strip()
    return "", value.strip()


def _xml_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split()).strip()


def _pubmed_date(article: ET.Element) -> tuple[int | None, str]:
    year = _xml_text(article.find(".//Journal/JournalIssue/PubDate/Year"))
    month = _xml_text(article.find(".//Journal/JournalIssue/PubDate/Month"))
    day = _xml_text(article.find(".//Journal/JournalIssue/PubDate/Day"))
    if not year:
        year = _xml_text(article.find(".//ArticleDate/Year"))
        month = _xml_text(article.find(".//ArticleDate/Month"))
        day = _xml_text(article.find(".//ArticleDate/Day"))
    try:
        year_int = int(year) if year else None
    except ValueError:
        year_int = None
    parts = [part for part in [year, month, day] if part]
    return year_int, "-".join(parts)


def _pubmed_doi(article: ET.Element) -> str:
    for article_id in article.findall(".//ArticleId"):
        if (article_id.attrib.get("IdType") or "").lower() == "doi":
            return _xml_text(article_id)
    return ""


def _is_ema_oncology_priority(row: dict[str, str], priority_brands: set[str]) -> int:
    name = row.get("name_of_medicine", "")
    if name.upper() in priority_brands:
        return 1
    atc_code = row.get("atc_code_human", "").upper()
    if atc_code.startswith(("L01", "L02")):
        return 1
    pharmacotherapeutic = row.get("pharmacotherapeutic_group_human", "").lower()
    if "antineoplastic" in pharmacotherapeutic:
        return 1
    text = " ".join(
        [
            name,
            row.get("international_non_proprietary_name_common_name", ""),
            row.get("active_substance", ""),
            row.get("therapeutic_area_mesh", ""),
            row.get("therapeutic_indication", ""),
        ]
    )
    return 1 if _contains_cancer_signal(text) else 0


def _extract_company_from_body(body: str) -> str:
    body_l = body.lower()
    if "gilead" in body_l:
        return "Gilead Sciences"
    for company in AWARD_PHARMA_COMPANY_HINTS:
        if company.lower() in body_l:
            return company
    if "â€¢" in body:
        bits = [bit.strip() for bit in body.split("â€¢") if bit.strip()]
        return bits[-1] if bits else ""
    agency_match = re.search(r"\bfor\s+(.+?)\.\s+Agency:", body, flags=re.IGNORECASE)
    if agency_match:
        return agency_match.group(1).strip()
    body_without_quotes = re.sub(r'"[^"]*"', "", body)
    for_match = re.search(r"(.+?)\s+for\s+", body_without_quotes, flags=re.IGNORECASE)
    if for_match:
        parties = for_match.group(1).strip()
        bits = re.split(r"\s+and\s+|,", parties)
        return bits[-1].strip() if bits else parties
    paren = re.search(r"\(([^)]+)\)", body_without_quotes)
    if paren:
        return paren.group(1).strip()
    bits = re.split(r"\s+-\s+|\s+and\s+|,", body_without_quotes)
    return bits[-1].strip() if bits else ""


def _extract_campaign_from_body(body: str) -> str:
    if "â€¢" in body:
        bits = [bit.strip() for bit in body.split("â€¢") if bit.strip()]
        return bits[0] if bits else body.strip()
    quoted = re.search(r"[\"\u201c?]([^\"\u201d?]+)[\"\u201d?]", body)
    if quoted:
        return quoted.group(1).strip()
    body = re.sub(r"\([^)]*\)", "", body).strip()
    bits = re.split(r"\s+-\s+|\s+and\s+", body)
    return bits[0].strip(" -")


FIERCE_SKIP_LINES = {
    "-->",
    ":",
    "Finalist",
    "Finalists",
    "VIEW WINNING CAMPAIGN",
    "VIEW WINNING DETAILS",
}


def _previous_fierce_category(lines: list[str], idx: int) -> str:
    cursor = idx - 1
    while cursor >= 0:
        candidate = lines[cursor].strip()
        if (
            candidate
            and candidate not in FIERCE_SKIP_LINES
            and candidate != "â€¢"
            and not candidate.startswith("Sponsored by")
            and not candidate.startswith("Category Sponsored")
        ):
            return candidate.strip(" :")
        cursor -= 1
    return ""


def _fierce_body_after(lines: list[str], idx: int, max_parts: int = 4) -> str:
    parts: list[str] = []
    cursor = idx + 1
    while cursor < len(lines):
        candidate = lines[cursor].strip()
        if not candidate or candidate in FIERCE_SKIP_LINES or candidate == "-->":
            cursor += 1
            continue
        if candidate.startswith("Sponsored by") or candidate.startswith("Category Sponsored"):
            cursor += 1
            continue
        if candidate in {"WINNER", "Badge of Honor", "Badge of Honor â€¢"}:
            break
        if cursor + 1 < len(lines) and lines[cursor + 1].startswith("Sponsored by"):
            break
        if parts and cursor + 2 < len(lines) and lines[cursor + 2].startswith("Sponsored by"):
            break
        if candidate.startswith("Stay Updated") or candidate in {"Connect", "Advertise", "Sponsorships", "Contact Us"}:
            break
        parts.append(candidate)
        if len(parts) >= max_parts:
            break
        cursor += 1
    body = " ".join(parts)
    body = re.sub(r"\s*â€¢\s*", " â€¢ ", body)
    return " ".join(body.split()).strip()


def _upsert_fierce_award_mentions(
    conn: sqlite3.Connection,
    doc: sqlite3.Row,
    *,
    program: str,
    year: int | None,
    lines: list[str],
) -> int:
    written = 0
    for line_no, line in enumerate(lines, start=1):
        if line not in {"WINNER", "Badge of Honor", "Badge of Honor â€¢"}:
            continue
        category = _previous_fierce_category(lines, line_no - 1)
        body = _fierce_body_after(lines, line_no - 1, max_parts=1 if line == "WINNER" else 4)
        if not category or len(body) < 3:
            continue
        _upsert_award_row(
            conn,
            mention_id=f"{doc['id']}_fierce_{line_no}",
            doc=doc,
            program=program,
            year=year,
            category=category,
            tier="WINNER" if line == "WINNER" else "BADGE OF HONOR",
            body=body,
        )
        written += 1
    return written


def _upsert_fierce_article_award_mentions(
    conn: sqlite3.Connection,
    doc: sqlite3.Row,
    *,
    program: str,
    year: int | None,
    lines: list[str],
) -> int:
    written = 0
    for idx, line in enumerate(lines[:-1]):
        category = line.strip(" :")
        body = ""
        body_idx = idx + 1
        while body_idx < len(lines):
            body = lines[body_idx].strip()
            if body:
                break
            body_idx += 1
        if (
            not category
            or len(category) > 90
            or category in FIERCE_SKIP_LINES
            or category.startswith(("Sponsored by", "Category Sponsored", "Read on", "Related"))
            or " " not in category
        ):
            continue
        if not FIERCE_ARTICLE_WINNER_RE.match(body):
            continue
        _upsert_award_row(
            conn,
            mention_id=f"{doc['id']}_fierce_article_{body_idx + 1}",
            doc=doc,
            program=program,
            year=year,
            category=category,
            tier="WINNER",
            body=body,
        )
        written += 1
    return written


def _upsert_award_row(
    conn: sqlite3.Connection,
    *,
    mention_id: str,
    doc: sqlite3.Row,
    program: str,
    year: int | None,
    category: str,
    tier: str,
    body: str,
) -> None:
    conn.execute(
        """
        INSERT INTO campaign_award_mention
            (mention_id, source_document_id, program, year, category, tier, campaign, brand,
             company, agency, therapy_area, raw_line, source_url, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(mention_id) DO UPDATE SET
            program=excluded.program,
            year=excluded.year,
            category=excluded.category,
            tier=excluded.tier,
            campaign=excluded.campaign,
            company=excluded.company,
            therapy_area=excluded.therapy_area,
            raw_line=excluded.raw_line,
            source_url=excluded.source_url,
            updated_at=excluded.updated_at
        """,
        (
            mention_id,
            doc["id"],
            program,
            year,
            category,
            tier,
            _extract_campaign_from_body(body),
            "",
            _extract_company_from_body(body),
            "",
            _derive_therapy_area(category + " " + body),
            body,
            doc["url"],
            _now(),
        ),
    )


def _upsert_award_mentions(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM campaign_award_mention")
    docs = conn.execute(
        "SELECT id, title, url, blob_path, metadata_json FROM documents WHERE source='awards'"
    ).fetchall()
    written = 0
    for doc in docs:
        metadata = json.loads(doc["metadata_json"] or "{}")
        program = metadata.get("program", "")
        year = metadata.get("year")
        text = _load_blob(doc["blob_path"])
        lines = [" ".join(line.split()) for line in text.splitlines()]
        if program.startswith("Fierce Pharma Marketing Awards"):
            written += _upsert_fierce_article_award_mentions(conn, doc, program=program, year=year, lines=lines)
            written += _upsert_fierce_award_mentions(conn, doc, program=program, year=year, lines=lines)
            continue
        last_category = ""
        for line_no, line in enumerate(lines, start=1):
            if not line or len(line) < 12:
                continue
            medal = PHARMA_CHOICE_MEDAL_RE.match(line)
            if medal and last_category:
                body = medal.group("body").strip()
                for candidate in lines[line_no:line_no + 4]:
                    candidate = candidate.strip()
                    if not candidate:
                        continue
                    if PHARMA_CHOICE_CATEGORY_RE.match(candidate) or PHARMA_CHOICE_MEDAL_RE.match(candidate):
                        break
                    if body.count('"') % 2 == 1 or body.endswith(("for", "for \"")):
                        body = f"{body} {candidate}".strip()
                _upsert_award_row(
                    conn,
                    mention_id=f"{doc['id']}_{line_no}",
                    doc=doc,
                    program=program,
                    year=year,
                    category=last_category,
                    tier=medal.group("tier").upper(),
                    body=body,
                )
                written += 1
                continue

            match = AWARD_HEADER_RE.match(line)
            simple = AWARD_SIMPLE_HEADER_RE.match(line)
            if not match and not simple:
                if PHARMA_CHOICE_CATEGORY_RE.match(line) and not re.search(r"\b(WINNER|FINALIST|GOLD|SILVER|BRONZE)\b", line, re.IGNORECASE):
                    last_category = line.strip(" :")
                continue
            if match:
                category = match.group("category").strip(" :")
                tier = (match.group("tier") or match.group("label")).upper()
            else:
                category = simple.group(1).strip(" :")
                tier = "WINNER"
            body = ""
            for candidate in lines[line_no:line_no + 5]:
                candidate = candidate.strip()
                if candidate:
                    body = candidate
                    break
            if len(body) < 4 or body.lower().startswith(("http", "www")):
                continue
            mention_id = f"{doc['id']}_{line_no}"
            _upsert_award_row(
                conn,
                mention_id=mention_id,
                doc=doc,
                program=program,
                year=year,
                category=category,
                tier=tier,
                body=body,
            )
            written += 1
    return written


def _upsert_oncology_sales_companies(conn: sqlite3.Connection) -> int:
    docs = conn.execute(
        "SELECT url, blob_path FROM documents WHERE source='public_web:pmlive_oncology_sales'"
    ).fetchall()
    companies = [row["company"] for row in conn.execute("SELECT company FROM pharma_company")]
    written = 0
    for doc in docs:
        text = _load_blob(doc["blob_path"])
        normalized = " ".join(text.split())
        for company in companies:
            match = re.search(re.escape(company), normalized, flags=re.IGNORECASE)
            if not match:
                continue
            start = max(0, match.start() - 120)
            end = min(len(normalized), match.end() + 240)
            excerpt = normalized[start:end]
            conn.execute(
                """
                INSERT INTO oncology_sales_company
                    (company, source_url, extracted_text, extraction_confidence, updated_at)
                VALUES (?,?,?,?,?)
                ON CONFLICT(company) DO UPDATE SET
                    source_url=excluded.source_url,
                    extracted_text=excluded.extracted_text,
                    extraction_confidence=excluded.extraction_confidence,
                    updated_at=excluded.updated_at
                """,
                (company, doc["url"], excerpt, "company_name_match", _now()),
            )
            written += 1
    return written


def _message_type(text: str) -> str:
    lowered = text.lower()
    if "indicated" in lowered or "approved" in lowered or "treat" in lowered:
        return "indication_or_approval"
    if "support" in lowered or "resources" in lowered or "savings" in lowered:
        return "support_or_access"
    if "survival" in lowered or "response" in lowered or "progression-free" in lowered:
        return "efficacy"
    if "nccn" in lowered or "category 1" in lowered or "biomarker" in lowered or "testing" in lowered:
        return "clinical_positioning"
    return "positioning"


def _candidate_message_lines(text: str, brand: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split()).strip(" -")
        if len(line) < 35 or len(line) > 420:
            continue
        if line.lower().startswith(("important safety information", "prescribing information", "privacy policy")):
            continue
        if brand.lower() not in line.lower() and not MESSAGE_HINT_RE.search(line):
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(line)
        if len(candidates) >= 12:
            break
    return candidates


def _clean_opdp_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    line = line.replace(" None", "").strip()
    line = re.sub(r"\s+Close-Out Letter\s*$", "", line).strip()
    line = re.sub(r"\s+\(PDF\)\s*$", "", line).strip()
    return line


def _is_opdp_skip(line: str) -> bool:
    clean = _clean_opdp_line(line)
    return (
        not clean
        or clean in OPDP_SKIP_LINES
        or clean.endswith("(PDF)")
        or clean.lower().startswith(("issued date", "office of prescription", "these letters are supplied"))
    )


def _upsert_opdp_actions(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM opdp_enforcement_action")
    docs = conn.execute(
        "SELECT id, url, blob_path FROM documents WHERE source='fda_opdp:untitled_letters'"
    ).fetchall()
    written = 0
    for doc in docs:
        lines = [_clean_opdp_line(line) for line in _load_blob(doc["blob_path"]).splitlines()]
        index = 0
        while index < len(lines):
            line = lines[index]
            if not DATE_RE.match(line):
                index += 1
                continue
            issued_date = line
            cursor = index + 1
            while cursor < len(lines) and _is_opdp_skip(lines[cursor]):
                cursor += 1
            if cursor >= len(lines):
                break
            company = lines[cursor]
            cursor += 1
            while cursor < len(lines) and _is_opdp_skip(lines[cursor]):
                cursor += 1
            if cursor >= len(lines):
                break
            product_issue = lines[cursor]
            if DATE_RE.match(product_issue):
                index = cursor
                continue
            action_id = _slug(f"{doc['id']}_{issued_date}_{company}_{product_issue}")[:120]
            conn.execute(
                """
                INSERT INTO opdp_enforcement_action
                    (action_id, source_document_id, issued_date, company, product_issue, therapy_area,
                     source_url, extraction_confidence, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(action_id) DO UPDATE SET
                    issued_date=excluded.issued_date,
                    company=excluded.company,
                    product_issue=excluded.product_issue,
                    therapy_area=excluded.therapy_area,
                    source_url=excluded.source_url,
                    extraction_confidence=excluded.extraction_confidence,
                    updated_at=excluded.updated_at
                """,
                (
                    action_id,
                    doc["id"],
                    issued_date,
                    company,
                    product_issue,
                    _derive_therapy_area(company + " " + product_issue),
                    doc["url"],
                    "fda_index_heuristic",
                    _now(),
                ),
            )
            written += 1
            index = cursor + 1
    return written


def _upsert_opdp_letter_documents(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM opdp_letter_document")
    docs = conn.execute(
        """
        SELECT id, external_id, url, blob_path, metadata_json
        FROM documents
        WHERE source='fda_opdp:untitled_letter_document'
        """
    ).fetchall()
    priority_brands = _priority_brand_set(conn)
    written = 0
    for doc in docs:
        metadata = json.loads(doc["metadata_json"] or "{}")
        issued_date = metadata.get("issued_date", "")
        company = metadata.get("company", "")
        product_issue = metadata.get("product_issue", "")
        pdf_blob_path = metadata.get("pdf_blob_path", "")
        text = _load_blob(doc["blob_path"]) if doc["blob_path"] else ""
        normalized_text = " ".join(text.split())
        haystack = f"{company} {product_issue} {normalized_text}".upper()
        is_oncology = _contains_cancer_signal(haystack) or any(brand in haystack for brand in priority_brands)
        conn.execute(
            """
            INSERT INTO opdp_letter_document
                (letter_id, source_document_id, issued_date, company, product_issue, therapy_area,
                 text_excerpt, text_length, pdf_blob_path, source_url, is_oncology_priority, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(letter_id) DO UPDATE SET
                source_document_id=excluded.source_document_id,
                issued_date=excluded.issued_date,
                company=excluded.company,
                product_issue=excluded.product_issue,
                therapy_area=excluded.therapy_area,
                text_excerpt=excluded.text_excerpt,
                text_length=excluded.text_length,
                pdf_blob_path=excluded.pdf_blob_path,
                source_url=excluded.source_url,
                is_oncology_priority=excluded.is_oncology_priority,
                updated_at=excluded.updated_at
            """,
            (
                str(doc["external_id"] or doc["id"]),
                doc["id"],
                issued_date,
                company,
                product_issue,
                _derive_therapy_area(f"{company} {product_issue} {normalized_text[:2000]}"),
                normalized_text[:1200],
                len(text),
                pdf_blob_path,
                doc["url"],
                1 if is_oncology else 0,
                _now(),
            ),
        )
        written += 1
    return written


def _priority_brand_set(conn: sqlite3.Connection) -> set[str]:
    return {
        row["brand"].upper()
        for row in conn.execute("SELECT brand FROM oncology_brand_seed").fetchall()
    }


def _top_company_terms(conn: sqlite3.Connection) -> set[str]:
    terms: set[str] = set()
    for row in conn.execute("SELECT company FROM pharma_company").fetchall():
        company = row["company"].upper()
        terms.add(company)
        for suffix in (" INC.", " INC", " PLC", " AG", " S.A.", " SA", " LTD", " CORPORATION", " CORP."):
            if company.endswith(suffix):
                terms.add(company[: -len(suffix)].strip())
    return terms


def _upsert_orange_book(conn: sqlite3.Connection) -> dict[str, int]:
    priority_brands = _priority_brand_set(conn)
    counts = {"orange_book_products": 0, "orange_book_patents": 0, "orange_book_exclusivities": 0}
    product_docs = conn.execute("SELECT blob_path FROM documents WHERE source LIKE 'orange_book:%products.txt'").fetchall()
    patent_docs = conn.execute("SELECT blob_path FROM documents WHERE source LIKE 'orange_book:%patent.txt'").fetchall()
    exclusivity_docs = conn.execute("SELECT blob_path FROM documents WHERE source LIKE 'orange_book:%exclusivity.txt'").fetchall()

    if product_docs:
        conn.execute("DELETE FROM orange_book_product")
        text = _load_blob(product_docs[-1]["blob_path"])
        for row in _rows_from_tilde_text(text):
            appl_no = row.get("Appl_No") or row.get("Appl No") or row.get("ApplNo") or ""
            product_no = row.get("Product_No") or row.get("Product No") or row.get("ProductNo") or ""
            trade_name = row.get("Trade_Name") or row.get("Trade Name") or ""
            ob_product_id = _slug(f"{appl_no}_{product_no}_{trade_name}")[:120]
            is_priority = 1 if trade_name.upper() in priority_brands else 0
            conn.execute(
                """
                INSERT INTO orange_book_product
                    (ob_product_id, ingredient, df_route, trade_name, applicant, strength, appl_type,
                     appl_no, product_no, te_code, approval_date, rld, rs, product_type,
                     applicant_full_name, is_oncology_priority, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(ob_product_id) DO UPDATE SET
                    ingredient=excluded.ingredient,
                    df_route=excluded.df_route,
                    trade_name=excluded.trade_name,
                    applicant=excluded.applicant,
                    strength=excluded.strength,
                    appl_type=excluded.appl_type,
                    appl_no=excluded.appl_no,
                    product_no=excluded.product_no,
                    te_code=excluded.te_code,
                    approval_date=excluded.approval_date,
                    rld=excluded.rld,
                    rs=excluded.rs,
                    product_type=excluded.product_type,
                    applicant_full_name=excluded.applicant_full_name,
                    is_oncology_priority=excluded.is_oncology_priority,
                    updated_at=excluded.updated_at
                """,
                (
                    ob_product_id,
                    row.get("Ingredient", ""),
                    row.get("DF;Route") or row.get("DF_Route") or row.get("Dosage Form;Route", ""),
                    trade_name,
                    row.get("Applicant", ""),
                    row.get("Strength", ""),
                    row.get("Appl_Type") or row.get("Appl Type", ""),
                    appl_no,
                    product_no,
                    row.get("TE_Code") or row.get("TE Code", ""),
                    row.get("Approval_Date") or row.get("Approval Date", ""),
                    row.get("RLD", ""),
                    row.get("RS", ""),
                    row.get("Type", ""),
                    row.get("Applicant_Full_Name") or row.get("Applicant Full Name", ""),
                    is_priority,
                    _now(),
                ),
            )
            counts["orange_book_products"] += 1

    if patent_docs:
        conn.execute("DELETE FROM orange_book_patent")
        text = _load_blob(patent_docs[-1]["blob_path"])
        for idx, row in enumerate(_rows_from_tilde_text(text), start=1):
            appl_no = row.get("Appl_No") or row.get("Appl No") or ""
            product_no = row.get("Product_No") or row.get("Product No") or ""
            patent_no = row.get("Patent_No") or row.get("Patent No") or ""
            ob_patent_id = _slug(f"{appl_no}_{product_no}_{patent_no}_{idx}")[:120]
            conn.execute(
                """
                INSERT INTO orange_book_patent
                    (ob_patent_id, appl_type, appl_no, product_no, patent_no, patent_expire_date,
                     drug_substance_flag, drug_product_flag, patent_use_code, delist_flag, submission_date, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(ob_patent_id) DO UPDATE SET
                    patent_expire_date=excluded.patent_expire_date,
                    drug_substance_flag=excluded.drug_substance_flag,
                    drug_product_flag=excluded.drug_product_flag,
                    patent_use_code=excluded.patent_use_code,
                    delist_flag=excluded.delist_flag,
                    submission_date=excluded.submission_date,
                    updated_at=excluded.updated_at
                """,
                (
                    ob_patent_id,
                    row.get("Appl_Type") or row.get("Appl Type", ""),
                    appl_no,
                    product_no,
                    patent_no,
                    row.get("Patent_Expire_Date_Text") or row.get("Patent_Expire_Date") or row.get("Patent Expire Date", ""),
                    row.get("Drug_Substance_Flag") or row.get("Drug Substance Flag", ""),
                    row.get("Drug_Product_Flag") or row.get("Drug Product Flag", ""),
                    row.get("Patent_Use_Code") or row.get("Patent Use Code", ""),
                    row.get("Delist_Flag") or row.get("Patent Delist Request Flag", ""),
                    row.get("Submission_Date") or row.get("Patent Submission Date", ""),
                    _now(),
                ),
            )
            counts["orange_book_patents"] += 1

    if exclusivity_docs:
        conn.execute("DELETE FROM orange_book_exclusivity")
        text = _load_blob(exclusivity_docs[-1]["blob_path"])
        for idx, row in enumerate(_rows_from_tilde_text(text), start=1):
            appl_no = row.get("Appl_No") or row.get("Appl No") or ""
            product_no = row.get("Product_No") or row.get("Product No") or ""
            code = row.get("Exclusivity_Code") or row.get("Exclusivity Code") or ""
            date = row.get("Exclusivity_Date") or row.get("Exclusivity Date") or ""
            ob_exclusivity_id = _slug(f"{appl_no}_{product_no}_{code}_{date}_{idx}")[:120]
            conn.execute(
                """
                INSERT INTO orange_book_exclusivity
                    (ob_exclusivity_id, appl_type, appl_no, product_no, exclusivity_code, exclusivity_date, updated_at)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(ob_exclusivity_id) DO UPDATE SET
                    exclusivity_code=excluded.exclusivity_code,
                    exclusivity_date=excluded.exclusivity_date,
                    updated_at=excluded.updated_at
                """,
                (
                    ob_exclusivity_id,
                    row.get("Appl_Type") or row.get("Appl Type", ""),
                    appl_no,
                    product_no,
                    code,
                    date,
                    _now(),
                ),
            )
            counts["orange_book_exclusivities"] += 1
    return counts


def _latest_doc(conn: sqlite3.Connection, source: str) -> str:
    row = conn.execute(
        "SELECT blob_path FROM documents WHERE source=? ORDER BY fetched_at DESC, id DESC LIMIT 1",
        (source,),
    ).fetchone()
    return row["blob_path"] if row else ""


def _lookup(rows: list[dict[str, str]], key_col: str, val_col: str) -> dict[str, str]:
    return {row.get(key_col, ""): row.get(val_col, "") for row in rows}


def _upsert_drugs_fda(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {
        "drugs_fda_applications": 0,
        "drugs_fda_products": 0,
        "drugs_fda_submissions": 0,
        "drugs_fda_application_docs": 0,
    }
    apps_path = _latest_doc(conn, "drugs_fda:applications_txt")
    products_path = _latest_doc(conn, "drugs_fda:products_txt")
    submissions_path = _latest_doc(conn, "drugs_fda:submissions_txt")
    docs_path = _latest_doc(conn, "drugs_fda:applicationdocs_txt")
    marketing_path = _latest_doc(conn, "drugs_fda:marketingstatus_txt")
    marketing_lookup_path = _latest_doc(conn, "drugs_fda:marketingstatus_lookup_txt")
    te_path = _latest_doc(conn, "drugs_fda:te_txt")
    submission_class_path = _latest_doc(conn, "drugs_fda:submissionclass_lookup_txt")
    doc_type_path = _latest_doc(conn, "drugs_fda:applicationsdocstype_lookup_txt")

    priority_brands = _priority_brand_set(conn)
    top_company_terms = _top_company_terms(conn)

    if apps_path:
        conn.execute("DELETE FROM drugs_fda_application")
        for row in _rows_from_tab_text(_load_blob(apps_path)):
            appl_no = row.get("ApplNo", "")
            sponsor = row.get("SponsorName", "")
            sponsor_upper = sponsor.upper()
            is_top = 1 if any(term and term in sponsor_upper for term in top_company_terms) else 0
            conn.execute(
                """
                INSERT INTO drugs_fda_application
                    (appl_no, appl_type, sponsor_name, public_notes, is_top_pharma_sponsor, updated_at)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(appl_no) DO UPDATE SET
                    appl_type=excluded.appl_type,
                    sponsor_name=excluded.sponsor_name,
                    public_notes=excluded.public_notes,
                    is_top_pharma_sponsor=excluded.is_top_pharma_sponsor,
                    updated_at=excluded.updated_at
                """,
                (appl_no, row.get("ApplType", ""), sponsor, row.get("ApplPublicNotes", ""), is_top, _now()),
            )
            counts["drugs_fda_applications"] += 1

    marketing_lookup = _lookup(_rows_from_tab_text(_load_blob(marketing_lookup_path)), "MarketingStatusID", "MarketingStatusDescription") if marketing_lookup_path else {}
    marketing_rows = _rows_from_tab_text(_load_blob(marketing_path)) if marketing_path else []
    marketing_by_product = {
        (row.get("ApplNo", ""), row.get("ProductNo", "")): marketing_lookup.get(row.get("MarketingStatusID", ""), row.get("MarketingStatusID", ""))
        for row in marketing_rows
    }
    te_by_product = {
        (row.get("ApplNo", ""), row.get("ProductNo", "")): row.get("TECode", "")
        for row in (_rows_from_tab_text(_load_blob(te_path)) if te_path else [])
    }

    if products_path:
        conn.execute("DELETE FROM drugs_fda_product")
        for row in _rows_from_tab_text(_load_blob(products_path)):
            appl_no = row.get("ApplNo", "")
            product_no = row.get("ProductNo", "")
            drug_name = row.get("DrugName", "")
            product_id = _slug(f"{appl_no}_{product_no}_{drug_name}")[:120]
            is_priority = 1 if drug_name.upper() in priority_brands else 0
            conn.execute(
                """
                INSERT INTO drugs_fda_product
                    (daf_product_id, appl_no, product_no, form, strength, reference_drug,
                     drug_name, active_ingredient, reference_standard, marketing_status, te_code,
                     is_oncology_priority, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(daf_product_id) DO UPDATE SET
                    form=excluded.form,
                    strength=excluded.strength,
                    reference_drug=excluded.reference_drug,
                    drug_name=excluded.drug_name,
                    active_ingredient=excluded.active_ingredient,
                    reference_standard=excluded.reference_standard,
                    marketing_status=excluded.marketing_status,
                    te_code=excluded.te_code,
                    is_oncology_priority=excluded.is_oncology_priority,
                    updated_at=excluded.updated_at
                """,
                (
                    product_id,
                    appl_no,
                    product_no,
                    row.get("Form", ""),
                    row.get("Strength", ""),
                    row.get("ReferenceDrug", ""),
                    drug_name,
                    row.get("ActiveIngredient", ""),
                    row.get("ReferenceStandard", ""),
                    marketing_by_product.get((appl_no, product_no), ""),
                    te_by_product.get((appl_no, product_no), ""),
                    is_priority,
                    _now(),
                ),
            )
            counts["drugs_fda_products"] += 1

    class_lookup = _lookup(_rows_from_tab_text(_load_blob(submission_class_path)), "SubmissionClassCodeID", "SubmissionClassCodeDescription") if submission_class_path else {}
    if submissions_path:
        conn.execute("DELETE FROM drugs_fda_submission")
        for row in _rows_from_tab_text(_load_blob(submissions_path)):
            appl_no = row.get("ApplNo", "")
            sub_type = row.get("SubmissionType", "")
            sub_no = row.get("SubmissionNo", "")
            class_id = row.get("SubmissionClassCodeID", "")
            sub_id = _slug(f"{appl_no}_{sub_type}_{sub_no}_{class_id}")[:120]
            conn.execute(
                """
                INSERT INTO drugs_fda_submission
                    (daf_submission_id, appl_no, submission_type, submission_no, submission_status,
                     submission_status_date, review_priority, submission_class_code,
                     submission_class_description, public_notes, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(daf_submission_id) DO UPDATE SET
                    submission_status=excluded.submission_status,
                    submission_status_date=excluded.submission_status_date,
                    review_priority=excluded.review_priority,
                    submission_class_code=excluded.submission_class_code,
                    submission_class_description=excluded.submission_class_description,
                    public_notes=excluded.public_notes,
                    updated_at=excluded.updated_at
                """,
                (
                    sub_id,
                    appl_no,
                    sub_type,
                    sub_no,
                    row.get("SubmissionStatus", ""),
                    row.get("SubmissionStatusDate", ""),
                    row.get("ReviewPriority", ""),
                    class_id,
                    class_lookup.get(class_id, ""),
                    row.get("SubmissionsPublicNotes", ""),
                    _now(),
                ),
            )
            counts["drugs_fda_submissions"] += 1

    doc_type_lookup = _lookup(_rows_from_tab_text(_load_blob(doc_type_path)), "ApplicationDocsType_Lookup_ID", "ApplicationDocsType_Lookup_Description") if doc_type_path else {}
    if docs_path:
        conn.execute("DELETE FROM drugs_fda_application_doc")
        for row in _rows_from_tab_text(_load_blob(docs_path)):
            doc_id = row.get("ApplicationDocsID", "")
            conn.execute(
                """
                INSERT INTO drugs_fda_application_doc
                    (daf_doc_id, appl_no, submission_type, submission_no, doc_type, title, doc_url, doc_date, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(daf_doc_id) DO UPDATE SET
                    doc_type=excluded.doc_type,
                    title=excluded.title,
                    doc_url=excluded.doc_url,
                    doc_date=excluded.doc_date,
                    updated_at=excluded.updated_at
                """,
                (
                    doc_id,
                    row.get("ApplNo", ""),
                    row.get("SubmissionType", ""),
                    row.get("SubmissionNo", ""),
                    doc_type_lookup.get(row.get("ApplicationDocsTypeID", ""), row.get("ApplicationDocsTypeID", "")),
                    row.get("ApplicationDocsTitle", ""),
                    row.get("ApplicationDocsURL", ""),
                    row.get("ApplicationDocsDate", ""),
                    _now(),
                ),
            )
            counts["drugs_fda_application_docs"] += 1
    return counts


def _upsert_purple_book(conn: sqlite3.Connection) -> int:
    doc = conn.execute(
        "SELECT id, url, blob_path FROM documents WHERE source='purple_book:latest_csv' ORDER BY fetched_at DESC, id DESC LIMIT 1"
    ).fetchone()
    if not doc:
        return 0

    priority_brands = _priority_brand_set(conn)
    release_label, rows = _purple_book_release_and_rows(_load_blob(doc["blob_path"]))
    conn.execute("DELETE FROM purple_book_product")
    written = 0
    for idx, row in enumerate(rows, start=1):
        bla_number = row.get("BLA Number", "")
        product_number = row.get("Product Number", "")
        proprietary_name = row.get("Proprietary Name", "")
        proper_name = row.get("Proper Name", "")
        ref_proprietary_name = row.get("Ref. Product Proprietary Name", "")
        ref_proper_name = row.get("Ref. Product Proper Name", "")
        brand_terms = {
            proprietary_name.upper(),
            ref_proprietary_name.upper(),
        }
        is_priority = 1 if priority_brands.intersection(brand_terms) else 0
        text_for_priority = " ".join([proprietary_name, proper_name, ref_proprietary_name, ref_proper_name])
        if not is_priority and _derive_therapy_area(text_for_priority) == "oncology":
            is_priority = 1
        approval_date = row.get("Approval Date", "")
        pb_product_id = _slug(f"{bla_number}_{product_number}_{proprietary_name}_{proper_name}_{idx}")[:140]
        conn.execute(
            """
            INSERT INTO purple_book_product
                (pb_product_id, source_document_id, release_label, change_type, applicant, bla_number,
                 proprietary_name, proper_name, license_type, strength, dosage_form, route_of_administration,
                 product_presentation, marketing_status, licensure, approval_date, approval_date_iso,
                 interchangeable_approval_date, ref_product_proper_name, ref_product_proprietary_name,
                 supplement_number, submission_type, interchangeable_supplement_number, license_number,
                 product_number, center, date_of_first_licensure, exclusivity_expiration_date,
                 first_interchangeable_exclusivity_exp_date, ref_product_exclusivity_exp_date,
                 orphan_exclusivity_exp_date, patent_list_provided, is_oncology_priority, source_url, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(pb_product_id) DO UPDATE SET
                release_label=excluded.release_label,
                change_type=excluded.change_type,
                applicant=excluded.applicant,
                bla_number=excluded.bla_number,
                proprietary_name=excluded.proprietary_name,
                proper_name=excluded.proper_name,
                license_type=excluded.license_type,
                strength=excluded.strength,
                dosage_form=excluded.dosage_form,
                route_of_administration=excluded.route_of_administration,
                product_presentation=excluded.product_presentation,
                marketing_status=excluded.marketing_status,
                licensure=excluded.licensure,
                approval_date=excluded.approval_date,
                approval_date_iso=excluded.approval_date_iso,
                interchangeable_approval_date=excluded.interchangeable_approval_date,
                ref_product_proper_name=excluded.ref_product_proper_name,
                ref_product_proprietary_name=excluded.ref_product_proprietary_name,
                supplement_number=excluded.supplement_number,
                submission_type=excluded.submission_type,
                interchangeable_supplement_number=excluded.interchangeable_supplement_number,
                license_number=excluded.license_number,
                product_number=excluded.product_number,
                center=excluded.center,
                date_of_first_licensure=excluded.date_of_first_licensure,
                exclusivity_expiration_date=excluded.exclusivity_expiration_date,
                first_interchangeable_exclusivity_exp_date=excluded.first_interchangeable_exclusivity_exp_date,
                ref_product_exclusivity_exp_date=excluded.ref_product_exclusivity_exp_date,
                orphan_exclusivity_exp_date=excluded.orphan_exclusivity_exp_date,
                patent_list_provided=excluded.patent_list_provided,
                is_oncology_priority=excluded.is_oncology_priority,
                source_url=excluded.source_url,
                updated_at=excluded.updated_at
            """,
            (
                pb_product_id,
                doc["id"],
                release_label,
                row.get("N/R/U", ""),
                row.get("Applicant", ""),
                bla_number,
                proprietary_name,
                proper_name,
                row.get("License Type", ""),
                row.get("Strength", ""),
                row.get("Dosage Form", ""),
                row.get("Route of Administration", ""),
                row.get("Product Presentation", ""),
                row.get("Marketing Status", ""),
                row.get("Licensure", ""),
                approval_date,
                _date_iso(approval_date),
                row.get("Inter. Approval Date", ""),
                ref_proper_name,
                ref_proprietary_name,
                row.get("Supplement Number", ""),
                row.get("Submission Type", ""),
                row.get("Inter. Supplement Number", ""),
                row.get("License Number", ""),
                product_number,
                row.get("Center", ""),
                row.get("Date of First Licensure", ""),
                row.get("Exclusivity Expiration Date", ""),
                row.get("First Interchangeable Exclusivity Exp. Date", ""),
                row.get("Ref. Product Exclusivity Exp. Date", ""),
                row.get("Orphan Exclusivity Exp. Date", ""),
                row.get("Patent List Provided", ""),
                is_priority,
                doc["url"],
                _now(),
            ),
        )
        written += 1
    return written


def _derive_tumor_type(text: str) -> str:
    lowered = text.lower()
    for hint in TUMOR_HINTS:
        if hint in lowered:
            return hint
    return _derive_therapy_area(text)


def _extract_parenthetical_mentions(summary: str) -> tuple[str, str]:
    brands: list[str] = []
    companies: list[str] = []
    for mention in PAREN_MENTION_RE.findall(summary):
        parts = [part.strip() for part in mention.split(",") if part.strip()]
        if len(parts) >= 2:
            brands.append(parts[0])
            companies.append(", ".join(parts[1:]))
    def _dedupe(items: list[str]) -> str:
        out: list[str] = []
        seen: set[str] = set()
        for item in items:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                out.append(item)
        return "; ".join(out)
    return _dedupe(brands), _dedupe(companies)


def _extract_drug_or_regimen(headline: str) -> str:
    text = re.sub(r"^FDA\s+(approves|grants|authorizes|updates)\s+", "", headline, flags=re.IGNORECASE)
    text = re.split(r"\s+for\s+", text, maxsplit=1, flags=re.IGNORECASE)[0]
    return text.strip()


def _upsert_fda_oncology_approvals(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM fda_oncology_approval")
    docs = conn.execute(
        "SELECT id, url, blob_path FROM documents WHERE source='fda_oncology_approvals:notifications'"
    ).fetchall()
    written = 0
    for doc in docs:
        lines = [" ".join(line.split()).strip() for line in _load_blob(doc["blob_path"]).splitlines()]
        idx = 0
        while idx < len(lines):
            headline = lines[idx]
            if not FDA_ONC_HEADLINE_RE.match(headline):
                idx += 1
                continue
            cursor = idx + 1
            summary_parts: list[str] = []
            approval_date = ""
            while cursor < len(lines):
                candidate = lines[cursor].strip()
                if not candidate:
                    cursor += 1
                    continue
                if FDA_ONC_DATE_RE.match(candidate):
                    approval_date = candidate
                    break
                if FDA_ONC_HEADLINE_RE.match(candidate):
                    break
                summary_parts.append(candidate)
                cursor += 1
            summary = " ".join(summary_parts).strip()
            if not approval_date or not summary:
                idx += 1
                continue
            brands, companies = _extract_parenthetical_mentions(summary)
            approval_id = _slug(f"{doc['id']}_{approval_date}_{headline}")[:120]
            conn.execute(
                """
                INSERT INTO fda_oncology_approval
                    (approval_id, source_document_id, approval_date, approval_date_iso, headline, summary, drug_or_regimen,
                     brand_mentions, company_mentions, tumor_type, source_url, extraction_confidence, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(approval_id) DO UPDATE SET
                    approval_date=excluded.approval_date,
                    approval_date_iso=excluded.approval_date_iso,
                    headline=excluded.headline,
                    summary=excluded.summary,
                    drug_or_regimen=excluded.drug_or_regimen,
                    brand_mentions=excluded.brand_mentions,
                    company_mentions=excluded.company_mentions,
                    tumor_type=excluded.tumor_type,
                    source_url=excluded.source_url,
                    extraction_confidence=excluded.extraction_confidence,
                    updated_at=excluded.updated_at
                """,
                (
                    approval_id,
                    doc["id"],
                    approval_date,
                    _date_iso(approval_date),
                    headline,
                    summary,
                    _extract_drug_or_regimen(headline),
                    brands,
                    companies,
                    _derive_tumor_type(headline + " " + summary),
                    doc["url"],
                    "fda_page_headline_summary_date",
                    _now(),
                ),
            )
            written += 1
            idx = cursor + 1
    return written


def _upsert_ema_medicines(conn: sqlite3.Connection) -> int:
    doc = conn.execute(
        "SELECT id, url, blob_path FROM documents WHERE source='ema_medicines:medicine_pages_json' ORDER BY fetched_at DESC, id DESC LIMIT 1"
    ).fetchone()
    if not doc:
        return 0

    rows = _json_data_rows(_load_blob(doc["blob_path"]))
    priority_brands = _priority_brand_set(conn)
    top_company_terms = _top_company_terms(conn)
    conn.execute("DELETE FROM ema_medicine")
    written = 0
    for idx, row in enumerate(rows, start=1):
        ema_product_number = row.get("ema_product_number") or _slug(f"ema_{idx}_{row.get('name_of_medicine', '')}")
        name = row.get("name_of_medicine", "")
        holder = row.get("marketing_authorisation_developer_applicant_holder", "")
        decision_date = row.get("european_commission_decision_date", "")
        atc_code = row.get("atc_code_human", "")
        is_priority = _is_ema_oncology_priority(row, priority_brands)
        holder_upper = holder.upper()
        is_top_holder = 1 if any(term and term in holder_upper for term in top_company_terms) else 0
        conn.execute(
            """
            INSERT INTO ema_medicine
                (ema_product_number, source_document_id, category, name_of_medicine, medicine_status, opinion_status,
                 international_non_proprietary_name_common_name, active_substance, therapeutic_area_mesh,
                 atc_code_human, pharmacotherapeutic_group_human, therapeutic_indication,
                 accelerated_assessment, additional_monitoring, advanced_therapy, biosimilar,
                 conditional_approval, exceptional_circumstances, generic, orphan_medicine,
                 prime_priority_medicine, marketing_authorisation_holder, european_commission_decision_date,
                 european_commission_decision_date_iso, opinion_adopted_date, marketing_authorisation_date,
                 first_published_date, last_updated_date, medicine_url, is_oncology_priority,
                 is_top_pharma_holder, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(ema_product_number) DO UPDATE SET
                source_document_id=excluded.source_document_id,
                category=excluded.category,
                name_of_medicine=excluded.name_of_medicine,
                medicine_status=excluded.medicine_status,
                opinion_status=excluded.opinion_status,
                international_non_proprietary_name_common_name=excluded.international_non_proprietary_name_common_name,
                active_substance=excluded.active_substance,
                therapeutic_area_mesh=excluded.therapeutic_area_mesh,
                atc_code_human=excluded.atc_code_human,
                pharmacotherapeutic_group_human=excluded.pharmacotherapeutic_group_human,
                therapeutic_indication=excluded.therapeutic_indication,
                accelerated_assessment=excluded.accelerated_assessment,
                additional_monitoring=excluded.additional_monitoring,
                advanced_therapy=excluded.advanced_therapy,
                biosimilar=excluded.biosimilar,
                conditional_approval=excluded.conditional_approval,
                exceptional_circumstances=excluded.exceptional_circumstances,
                generic=excluded.generic,
                orphan_medicine=excluded.orphan_medicine,
                prime_priority_medicine=excluded.prime_priority_medicine,
                marketing_authorisation_holder=excluded.marketing_authorisation_holder,
                european_commission_decision_date=excluded.european_commission_decision_date,
                european_commission_decision_date_iso=excluded.european_commission_decision_date_iso,
                opinion_adopted_date=excluded.opinion_adopted_date,
                marketing_authorisation_date=excluded.marketing_authorisation_date,
                first_published_date=excluded.first_published_date,
                last_updated_date=excluded.last_updated_date,
                medicine_url=excluded.medicine_url,
                is_oncology_priority=excluded.is_oncology_priority,
                is_top_pharma_holder=excluded.is_top_pharma_holder,
                updated_at=excluded.updated_at
            """,
            (
                ema_product_number,
                doc["id"],
                row.get("category", ""),
                name,
                row.get("medicine_status", ""),
                row.get("opinion_status", ""),
                row.get("international_non_proprietary_name_common_name", ""),
                row.get("active_substance", ""),
                row.get("therapeutic_area_mesh", ""),
                atc_code,
                row.get("pharmacotherapeutic_group_human", ""),
                row.get("therapeutic_indication", ""),
                row.get("accelerated_assessment", ""),
                row.get("additional_monitoring", ""),
                row.get("advanced_therapy", ""),
                row.get("biosimilar", ""),
                row.get("conditional_approval", ""),
                row.get("exceptional_circumstances", ""),
                row.get("generic", ""),
                row.get("orphan_medicine", ""),
                row.get("prime_priority_medicine", ""),
                holder,
                decision_date,
                _date_iso_eu(decision_date),
                row.get("opinion_adopted_date", ""),
                row.get("marketing_authorisation_date", ""),
                row.get("first_published_date", ""),
                row.get("last_updated_date", ""),
                row.get("medicine_url", ""),
                is_priority,
                is_top_holder,
                _now(),
            ),
        )
        written += 1
    return written


def _date_from_timestamp(value: str) -> str:
    if not value:
        return ""
    return _date_iso_eu(value[:10])


def _upsert_ema_documents(conn: sqlite3.Connection) -> int:
    doc = conn.execute(
        "SELECT id, url, blob_path FROM documents WHERE source='ema_medicines:epar_documents_json' ORDER BY fetched_at DESC, id DESC LIMIT 1"
    ).fetchone()
    if not doc:
        return 0

    rows = _json_data_rows(_load_blob(doc["blob_path"]))
    conn.execute("DELETE FROM ema_medicine_document")
    written = 0
    for idx, row in enumerate(rows, start=1):
        ema_document_id = str(row.get("id") or _slug(f"{row.get('ema_product_number', '')}_{row.get('name', '')}_{idx}"))
        first_published = row.get("first_published_date", "")
        last_updated = row.get("last_updated_date", "")
        conn.execute(
            """
            INSERT INTO ema_medicine_document
                (ema_document_id, source_document_id, name, document_type, medicine_name, ema_product_number,
                 status, consultation_date, first_published_date, first_published_date_iso,
                 last_updated_date, last_updated_date_iso, reference_number, document_url,
                 parsed_from_malformed_feed, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(ema_document_id) DO UPDATE SET
                source_document_id=excluded.source_document_id,
                name=excluded.name,
                document_type=excluded.document_type,
                medicine_name=excluded.medicine_name,
                ema_product_number=excluded.ema_product_number,
                status=excluded.status,
                consultation_date=excluded.consultation_date,
                first_published_date=excluded.first_published_date,
                first_published_date_iso=excluded.first_published_date_iso,
                last_updated_date=excluded.last_updated_date,
                last_updated_date_iso=excluded.last_updated_date_iso,
                reference_number=excluded.reference_number,
                document_url=excluded.document_url,
                parsed_from_malformed_feed=excluded.parsed_from_malformed_feed,
                updated_at=excluded.updated_at
            """,
            (
                ema_document_id,
                doc["id"],
                row.get("name", ""),
                row.get("type", ""),
                row.get("medicine_name", ""),
                row.get("ema_product_number", ""),
                row.get("status", ""),
                row.get("consultation_date", ""),
                first_published,
                _date_from_timestamp(first_published),
                last_updated,
                _date_from_timestamp(last_updated),
                row.get("reference_number", ""),
                row.get("document_url", ""),
                1 if row.get("_parsed_from_malformed_feed") else 0,
                _now(),
            ),
        )
        written += 1
    return written


def _filing_url(cik: str, accession: str, primary_document: str) -> str:
    compact_accession = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{compact_accession}/{primary_document}"


def _upsert_sec_edgar(conn: sqlite3.Connection) -> dict[str, int]:
    conn.execute("DELETE FROM sec_company")
    conn.execute("DELETE FROM sec_filing")
    counts = {"sec_companies": 0, "sec_filings": 0}
    config = _read_json("sec_top_pharma_companies.json")
    ranks = _top_rank_by_company(conn)
    forms_by_company = {item["company"]: set(item.get("forms", [])) for item in config.get("companies", [])}
    docs = conn.execute(
        "SELECT id, blob_path, metadata_json FROM documents WHERE source='sec_edgar:submissions'"
    ).fetchall()
    for doc in docs:
        metadata = json.loads(doc["metadata_json"] or "{}")
        company = metadata.get("company", "")
        ticker = metadata.get("ticker", "")
        cik = metadata.get("cik", "")
        data = json.loads(_load_blob(doc["blob_path"]) or "{}")
        conn.execute(
            """
            INSERT INTO sec_company
                (cik, company, ticker, sec_name, sic, sic_description, fiscal_year_end, top_pharma_rank, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(cik) DO UPDATE SET
                company=excluded.company,
                ticker=excluded.ticker,
                sec_name=excluded.sec_name,
                sic=excluded.sic,
                sic_description=excluded.sic_description,
                fiscal_year_end=excluded.fiscal_year_end,
                top_pharma_rank=excluded.top_pharma_rank,
                updated_at=excluded.updated_at
            """,
            (
                cik,
                company,
                ticker,
                data.get("name", ""),
                str(data.get("sic", "")),
                data.get("sicDescription", ""),
                data.get("fiscalYearEnd", ""),
                ranks.get(company.lower()),
                _now(),
            ),
        )
        counts["sec_companies"] += 1
        allowed_forms = forms_by_company.get(company, set())
        recent = (data.get("filings") or {}).get("recent") or {}
        forms = recent.get("form", [])
        for idx, form in enumerate(forms):
            accession = (recent.get("accessionNumber", []) or [""])[idx]
            primary_document = (recent.get("primaryDocument", []) or [""])[idx]
            filing_id = _slug(f"{cik}_{accession}_{primary_document}")[:120]
            filing_date = (recent.get("filingDate", []) or [""])[idx]
            is_strategy = 1 if form in allowed_forms else 0
            conn.execute(
                """
                INSERT INTO sec_filing
                    (filing_id, cik, company, ticker, accession_number, filing_date, report_date,
                     acceptance_datetime, form, primary_document, primary_doc_description,
                     filing_url, is_strategy_relevant, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(filing_id) DO UPDATE SET
                    filing_date=excluded.filing_date,
                    report_date=excluded.report_date,
                    acceptance_datetime=excluded.acceptance_datetime,
                    form=excluded.form,
                    primary_document=excluded.primary_document,
                    primary_doc_description=excluded.primary_doc_description,
                    filing_url=excluded.filing_url,
                    is_strategy_relevant=excluded.is_strategy_relevant,
                    updated_at=excluded.updated_at
                """,
                (
                    filing_id,
                    cik,
                    company,
                    ticker,
                    accession,
                    filing_date,
                    (recent.get("reportDate", []) or [""])[idx],
                    (recent.get("acceptanceDateTime", []) or [""])[idx],
                    form,
                    primary_document,
                    (recent.get("primaryDocDescription", []) or [""])[idx],
                    _filing_url(cik, accession, primary_document) if accession and primary_document else "",
                    is_strategy,
                    _now(),
                ),
            )
            counts["sec_filings"] += 1
    return counts


def _upsert_brand_messages(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM brand_message")
    docs = conn.execute(
        "SELECT id, url, blob_path, metadata_json FROM documents WHERE source LIKE 'brand_site:%'"
    ).fetchall()
    written = 0
    for doc in docs:
        metadata = json.loads(doc["metadata_json"] or "{}")
        brand = metadata.get("brand", "")
        if not brand:
            continue
        text = _load_blob(doc["blob_path"])
        for idx, message in enumerate(_candidate_message_lines(text, brand), start=1):
            message_id = f"{doc['id']}_{idx}"
            conn.execute(
                """
                INSERT INTO brand_message
                    (message_id, source_document_id, brand, company, therapy_area, audience, message_type,
                     message_text, source_url, extraction_confidence, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(message_id) DO UPDATE SET
                    brand=excluded.brand,
                    company=excluded.company,
                    therapy_area=excluded.therapy_area,
                    audience=excluded.audience,
                    message_type=excluded.message_type,
                    message_text=excluded.message_text,
                    source_url=excluded.source_url,
                    extraction_confidence=excluded.extraction_confidence,
                    updated_at=excluded.updated_at
                """,
                (
                    message_id,
                    doc["id"],
                    brand,
                    metadata.get("company", ""),
                    metadata.get("therapy_area", ""),
                    metadata.get("audience", ""),
                    _message_type(message),
                    message,
                    doc["url"],
                    "heuristic_public_text",
                    _now(),
                ),
            )
            written += 1
    return written


def _upsert_pubmed_articles(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {"pubmed_articles": 0, "pubmed_mesh_terms": 0, "pubmed_publication_types": 0}
    priority_brands = _priority_brand_set(conn)
    doc_lookup = {
        row["external_id"]: row
        for row in conn.execute(
            "SELECT id, external_id, search_term, url FROM documents WHERE source='pubmed' AND doc_type='journal_article'"
        ).fetchall()
    }
    article_rows: dict[str, dict[str, Any]] = {}
    pubmed_dir = BASE_DIR / "data" / "raw" / "pubmed"
    for path in sorted(pubmed_dir.glob("search_*.xml")):
        search_term = path.stem.removeprefix("search_").replace("_", " ").strip()
        try:
            root = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        for article in root.findall(".//PubmedArticle"):
            pmid = _xml_text(article.find(".//PMID"))
            if not pmid:
                continue
            row = article_rows.setdefault(
                pmid,
                {
                    "search_terms": set(),
                    "mesh_terms": set(),
                    "publication_types": set(),
                    "title": "",
                    "abstract": "",
                    "journal": "",
                    "publication_year": None,
                    "publication_date": "",
                    "doi": "",
                },
            )
            if search_term:
                row["search_terms"].add(search_term)
            row["title"] = row["title"] or _xml_text(article.find(".//ArticleTitle"))
            abstract_parts = [_xml_text(part) for part in article.findall(".//Abstract/AbstractText")]
            if abstract_parts and not row["abstract"]:
                row["abstract"] = " ".join(part for part in abstract_parts if part)
            row["journal"] = row["journal"] or _xml_text(article.find(".//Journal/Title"))
            year, pub_date = _pubmed_date(article)
            row["publication_year"] = row["publication_year"] or year
            row["publication_date"] = row["publication_date"] or pub_date
            row["doi"] = row["doi"] or _pubmed_doi(article)
            for descriptor in article.findall(".//MeshHeading/DescriptorName"):
                text = _xml_text(descriptor)
                if text:
                    row["mesh_terms"].add(text)
            for pub_type in article.findall(".//PublicationType"):
                text = _xml_text(pub_type)
                if text:
                    row["publication_types"].add(text)

    conn.execute("DELETE FROM pubmed_article_publication_type")
    conn.execute("DELETE FROM pubmed_article_mesh")
    conn.execute("DELETE FROM pubmed_article")
    for pmid, row in article_rows.items():
        search_terms = "; ".join(sorted(row["search_terms"]))
        mesh_terms = sorted(row["mesh_terms"])
        publication_types = sorted(row["publication_types"])
        doc = doc_lookup.get(pmid)
        source_document_id = doc["id"] if doc else None
        source_url = doc["url"] if doc else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        oncology_text = " ".join([search_terms, row["title"], row["abstract"], " ".join(mesh_terms)])
        is_priority = 1 if _contains_cancer_signal(oncology_text) else 0
        if not is_priority:
            is_priority = 1 if any(term.upper() in priority_brands for term in row["search_terms"]) else 0
        conn.execute(
            """
            INSERT INTO pubmed_article
                (pmid, source_document_id, search_terms, title, abstract, journal, publication_year,
                 publication_date, doi, source_url, is_oncology_priority, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(pmid) DO UPDATE SET
                source_document_id=excluded.source_document_id,
                search_terms=excluded.search_terms,
                title=excluded.title,
                abstract=excluded.abstract,
                journal=excluded.journal,
                publication_year=excluded.publication_year,
                publication_date=excluded.publication_date,
                doi=excluded.doi,
                source_url=excluded.source_url,
                is_oncology_priority=excluded.is_oncology_priority,
                updated_at=excluded.updated_at
            """,
            (
                pmid,
                source_document_id,
                search_terms,
                row["title"],
                row["abstract"],
                row["journal"],
                row["publication_year"],
                row["publication_date"],
                row["doi"],
                source_url,
                is_priority,
                _now(),
            ),
        )
        counts["pubmed_articles"] += 1
        for idx, descriptor in enumerate(mesh_terms, start=1):
            mesh_id = _slug(f"{pmid}_mesh_{idx}_{descriptor}")[:140]
            conn.execute(
                """
                INSERT INTO pubmed_article_mesh
                    (pubmed_mesh_id, pmid, descriptor, updated_at)
                VALUES (?,?,?,?)
                ON CONFLICT(pubmed_mesh_id) DO UPDATE SET
                    descriptor=excluded.descriptor,
                    updated_at=excluded.updated_at
                """,
                (mesh_id, pmid, descriptor, _now()),
            )
            counts["pubmed_mesh_terms"] += 1
        for idx, publication_type in enumerate(publication_types, start=1):
            pubtype_id = _slug(f"{pmid}_pubtype_{idx}_{publication_type}")[:140]
            conn.execute(
                """
                INSERT INTO pubmed_article_publication_type
                    (pubmed_publication_type_id, pmid, publication_type, updated_at)
                VALUES (?,?,?,?)
                ON CONFLICT(pubmed_publication_type_id) DO UPDATE SET
                    publication_type=excluded.publication_type,
                    updated_at=excluded.updated_at
                """,
                (pubtype_id, pmid, publication_type, _now()),
            )
            counts["pubmed_publication_types"] += 1
    return counts


def _upsert_asco_abstracts(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM asco_abstract")
    docs = conn.execute(
        """
        SELECT id, url, blob_path, metadata_json
        FROM documents
        WHERE source='asco:abstract_list_csv' AND doc_type='conference_abstract_csv'
        """
    ).fetchall()
    priority_brands = sorted(_priority_brand_set(conn))
    written = 0
    for doc in docs:
        metadata = json.loads(doc["metadata_json"] or "{}")
        try:
            reader = csv.DictReader(io.StringIO(_load_blob(doc["blob_path"])))
        except Exception:
            continue
        for row in reader:
            abstract_number = (row.get("AbstractNumber") or "").strip()
            if not abstract_number:
                continue
            title = (row.get("PresentationTitle") or "").strip()
            body = (row.get("AbstractBody") or "").strip()
            tracks = (row.get("Tracks") or "").strip()
            haystack = f"{title} {body} {tracks}".upper()
            brand_mentions = [
                brand for brand in priority_brands
                if re.search(rf"\b{re.escape(brand)}\b", haystack, flags=re.IGNORECASE)
            ]
            is_priority = 1 if brand_mentions or _contains_cancer_signal(haystack) else 0
            conn.execute(
                """
                INSERT INTO asco_abstract
                    (abstract_number, source_document_id, conference, meeting_year, presentation_start_date,
                     presentation_end_date, presentation_time_zone, speaker_display_name, session_title,
                     session_type, presentation_title, tracks, abstract_body, brand_mentions,
                     is_oncology_priority, source_url, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(abstract_number) DO UPDATE SET
                    source_document_id=excluded.source_document_id,
                    conference=excluded.conference,
                    meeting_year=excluded.meeting_year,
                    presentation_start_date=excluded.presentation_start_date,
                    presentation_end_date=excluded.presentation_end_date,
                    presentation_time_zone=excluded.presentation_time_zone,
                    speaker_display_name=excluded.speaker_display_name,
                    session_title=excluded.session_title,
                    session_type=excluded.session_type,
                    presentation_title=excluded.presentation_title,
                    tracks=excluded.tracks,
                    abstract_body=excluded.abstract_body,
                    brand_mentions=excluded.brand_mentions,
                    is_oncology_priority=excluded.is_oncology_priority,
                    source_url=excluded.source_url,
                    updated_at=excluded.updated_at
                """,
                (
                    abstract_number,
                    doc["id"],
                    metadata.get("conference", "ASCO Annual Meeting"),
                    metadata.get("year", 2026),
                    (row.get("PresentationStartDate") or "").strip(),
                    (row.get("PresentationEndDate") or "").strip(),
                    (row.get("PresentationTimeZone") or "").strip(),
                    (row.get("SpeakerDisplayName") or "").strip(),
                    (row.get("SessionTitle") or "").strip(),
                    (row.get("SessionType") or "").strip(),
                    title,
                    tracks,
                    body,
                    "; ".join(brand_mentions),
                    is_priority,
                    f"https://meetings.asco.org/abstracts-presentations/{abstract_number}",
                    _now(),
                ),
            )
            written += 1
    return written


def _upsert_seer_stats(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM seer_cancer_stat")
    docs = conn.execute(
        """
        SELECT id, external_id, url, metadata_json
        FROM documents
        WHERE source='seer:statfacts' AND doc_type='epidemiology_statfacts'
        """
    ).fetchall()
    written = 0
    for doc in docs:
        try:
            metadata = json.loads(doc["metadata_json"] or "{}")
        except Exception:
            metadata = {}
        conn.execute(
            """
            INSERT INTO seer_cancer_stat
                (stat_id, source_document_id, cancer_site, therapy_area, estimated_new_cases_2026,
                 percent_all_new_cases, estimated_deaths_2026, percent_all_cancer_deaths,
                 five_year_relative_survival_percent, source_url, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(stat_id) DO UPDATE SET
                source_document_id=excluded.source_document_id,
                cancer_site=excluded.cancer_site,
                therapy_area=excluded.therapy_area,
                estimated_new_cases_2026=excluded.estimated_new_cases_2026,
                percent_all_new_cases=excluded.percent_all_new_cases,
                estimated_deaths_2026=excluded.estimated_deaths_2026,
                percent_all_cancer_deaths=excluded.percent_all_cancer_deaths,
                five_year_relative_survival_percent=excluded.five_year_relative_survival_percent,
                source_url=excluded.source_url,
                updated_at=excluded.updated_at
            """,
            (
                doc["external_id"] or _slug(str(metadata.get("site", doc["id"]))),
                doc["id"],
                metadata.get("site", ""),
                metadata.get("therapy_area", ""),
                metadata.get("estimated_new_cases_2026"),
                metadata.get("percent_all_new_cases"),
                metadata.get("estimated_deaths_2026"),
                metadata.get("percent_all_cancer_deaths"),
                metadata.get("five_year_relative_survival_percent"),
                doc["url"],
                _now(),
            ),
        )
        written += 1
    return written


def _upsert_search_interest(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {"search_interest_series": 0, "search_interest_points": 0}
    priority_brands = _priority_brand_set(conn)
    docs = conn.execute(
        "SELECT id, search_term, url, blob_path, metadata_json FROM documents WHERE source='google_trends' AND doc_type='search_interest_timeseries'"
    ).fetchall()
    conn.execute("DELETE FROM search_interest_point")
    conn.execute("DELETE FROM search_interest_series")
    for doc in docs:
        term = doc["search_term"] or ""
        if not term:
            continue
        try:
            rows = json.loads(_load_blob(doc["blob_path"]) or "[]")
        except Exception:
            continue
        points: list[tuple[str, int | None, int]] = []
        for row in rows:
            date = str(row.get("date", ""))[:10]
            if not date:
                continue
            raw_interest = row.get(term)
            if raw_interest is None:
                for key, value in row.items():
                    if key not in {"date", "isPartial"}:
                        raw_interest = value
                        break
            try:
                interest = int(raw_interest) if raw_interest is not None else None
            except Exception:
                interest = None
            is_partial = 1 if row.get("isPartial") else 0
            points.append((date, interest, is_partial))
        interest_values = [interest for _, interest, _ in points if interest is not None]
        if not interest_values:
            continue
        avg_interest = round(sum(interest_values) / len(interest_values), 1)
        max_interest = max(interest_values)
        latest_date, latest_interest, _ = points[-1]
        metadata = json.loads(doc["metadata_json"] or "{}")
        is_priority = 1 if term.upper() in priority_brands or _contains_cancer_signal(term) else 0
        conn.execute(
            """
            INSERT INTO search_interest_series
                (term, source_document_id, source_system, avg_interest, max_interest, latest_interest,
                 point_count, first_date, latest_date, is_oncology_priority, source_url, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(term) DO UPDATE SET
                source_document_id=excluded.source_document_id,
                avg_interest=excluded.avg_interest,
                max_interest=excluded.max_interest,
                latest_interest=excluded.latest_interest,
                point_count=excluded.point_count,
                first_date=excluded.first_date,
                latest_date=excluded.latest_date,
                is_oncology_priority=excluded.is_oncology_priority,
                source_url=excluded.source_url,
                updated_at=excluded.updated_at
            """,
            (
                term,
                doc["id"],
                "Google Trends via pytrends",
                metadata.get("avg_interest_12mo", avg_interest),
                max_interest,
                latest_interest,
                len(points),
                points[0][0],
                latest_date,
                is_priority,
                doc["url"],
                _now(),
            ),
        )
        counts["search_interest_series"] += 1
        for date, interest, is_partial in points:
            point_id = _slug(f"{doc['id']}_{term}_{date}")[:140]
            conn.execute(
                """
                INSERT INTO search_interest_point
                    (interest_point_id, term, date, interest, is_partial, updated_at)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(interest_point_id) DO UPDATE SET
                    interest=excluded.interest,
                    is_partial=excluded.is_partial,
                    updated_at=excluded.updated_at
                """,
                (point_id, term, date, interest, is_partial, _now()),
            )
            counts["search_interest_points"] += 1
    return counts


OPEN_PAYMENT_PRODUCT_SLOTS = range(1, 6)


def _money(value: Any) -> float | None:
    try:
        return float(str(value or "").replace("$", "").replace(",", "").strip())
    except Exception:
        return None


def _first_matching_open_payment_product(row: dict[str, Any], brand: str) -> tuple[str, str]:
    brand_l = brand.lower()
    first_product = ""
    first_category = ""
    for slot in OPEN_PAYMENT_PRODUCT_SLOTS:
        product = str(row.get(f"name_of_drug_or_biological_or_device_or_medical_supply_{slot}") or "").strip()
        category = str(row.get(f"product_category_or_therapeutic_area_{slot}") or "").strip()
        if product and not first_product:
            first_product = product
            first_category = category
        if product and brand_l in product.lower():
            return product, category
    return first_product, first_category


def _upsert_open_payments(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM cms_open_payment_general")
    docs = conn.execute(
        """
        SELECT id, search_term, title, url, blob_path, metadata_json
        FROM documents
        WHERE source='cms_open_payments:general_payments'
          AND doc_type='open_payments_general_payments'
        """
    ).fetchall()
    written = 0
    for doc in docs:
        brand = (doc["search_term"] or "").strip()
        if not brand:
            continue
        try:
            payload = json.loads(_load_blob(doc["blob_path"]) or "{}")
        except Exception:
            continue
        for row in payload.get("rows", []):
            if not isinstance(row, dict):
                continue
            record_id = str(row.get("record_id") or "").strip()
            if not record_id:
                continue
            product, category = _first_matching_open_payment_product(row, brand)
            recipient_name = " ".join(
                str(row.get(key) or "").strip()
                for key in [
                    "covered_recipient_first_name",
                    "covered_recipient_middle_name",
                    "covered_recipient_last_name",
                ]
                if str(row.get(key) or "").strip()
            )
            try:
                program_year = int(row.get("program_year")) if row.get("program_year") else None
            except Exception:
                program_year = None
            conn.execute(
                """
                INSERT INTO cms_open_payment_general
                    (record_id, source_document_id, matched_brand, covered_recipient_type,
                     covered_recipient_profile_id, covered_recipient_npi, recipient_name,
                     recipient_city, recipient_state, recipient_country, recipient_primary_type,
                     recipient_specialty, submitting_manufacturer, payment_manufacturer,
                     total_amount_usd, date_of_payment, form_of_payment, nature_of_payment,
                     contextual_information, related_product_indicator, product_category_or_therapy_area,
                     associated_product, program_year, payment_publication_date, source_url, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(record_id) DO UPDATE SET
                    source_document_id=excluded.source_document_id,
                    matched_brand=excluded.matched_brand,
                    covered_recipient_type=excluded.covered_recipient_type,
                    covered_recipient_profile_id=excluded.covered_recipient_profile_id,
                    covered_recipient_npi=excluded.covered_recipient_npi,
                    recipient_name=excluded.recipient_name,
                    recipient_city=excluded.recipient_city,
                    recipient_state=excluded.recipient_state,
                    recipient_country=excluded.recipient_country,
                    recipient_primary_type=excluded.recipient_primary_type,
                    recipient_specialty=excluded.recipient_specialty,
                    submitting_manufacturer=excluded.submitting_manufacturer,
                    payment_manufacturer=excluded.payment_manufacturer,
                    total_amount_usd=excluded.total_amount_usd,
                    date_of_payment=excluded.date_of_payment,
                    form_of_payment=excluded.form_of_payment,
                    nature_of_payment=excluded.nature_of_payment,
                    contextual_information=excluded.contextual_information,
                    related_product_indicator=excluded.related_product_indicator,
                    product_category_or_therapy_area=excluded.product_category_or_therapy_area,
                    associated_product=excluded.associated_product,
                    program_year=excluded.program_year,
                    payment_publication_date=excluded.payment_publication_date,
                    source_url=excluded.source_url,
                    updated_at=excluded.updated_at
                """,
                (
                    record_id,
                    doc["id"],
                    brand,
                    row.get("covered_recipient_type", ""),
                    row.get("covered_recipient_profile_id", ""),
                    row.get("covered_recipient_npi", ""),
                    recipient_name,
                    row.get("recipient_city", ""),
                    row.get("recipient_state", ""),
                    row.get("recipient_country", ""),
                    row.get("covered_recipient_primary_type_1", ""),
                    row.get("covered_recipient_specialty_1", ""),
                    row.get("submitting_applicable_manufacturer_or_applicable_gpo_name", ""),
                    row.get("applicable_manufacturer_or_applicable_gpo_making_payment_name", ""),
                    _money(row.get("total_amount_of_payment_usdollars")),
                    row.get("date_of_payment", ""),
                    row.get("form_of_payment_or_transfer_of_value", ""),
                    row.get("nature_of_payment_or_transfer_of_value", ""),
                    row.get("contextual_information", ""),
                    row.get("related_product_indicator", ""),
                    category,
                    product,
                    program_year,
                    row.get("payment_publication_date", ""),
                    doc["url"],
                    _now(),
                ),
            )
            written += 1
    return written


def _upsert_clinical_trials(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {
        "clinical_trials": 0,
        "clinical_trial_conditions": 0,
        "clinical_trial_interventions": 0,
        "clinical_trial_locations": 0,
    }
    priority_brands = _priority_brand_set(conn)
    top_company_terms = _top_company_terms(conn)
    docs = conn.execute(
        "SELECT id, search_term, title, url, blob_path FROM documents WHERE source='clinicaltrials' AND doc_type='trial_record'"
    ).fetchall()
    conn.execute("DELETE FROM clinical_trial_location")
    conn.execute("DELETE FROM clinical_trial_intervention")
    conn.execute("DELETE FROM clinical_trial_condition")
    conn.execute("DELETE FROM clinical_trial")
    for doc in docs:
        try:
            study = json.loads(_load_blob(doc["blob_path"]) or "{}")
        except Exception:
            continue
        protocol = study.get("protocolSection", {})
        ident = protocol.get("identificationModule", {})
        status_mod = protocol.get("statusModule", {})
        sponsor_mod = protocol.get("sponsorCollaboratorsModule", {})
        conditions_mod = protocol.get("conditionsModule", {})
        design_mod = protocol.get("designModule", {})
        arms_mod = protocol.get("armsInterventionsModule", {})
        locations_mod = protocol.get("contactsLocationsModule", {})

        nct_id = ident.get("nctId", "")
        if not nct_id:
            continue
        conditions = [str(value).strip() for value in conditions_mod.get("conditions", []) if str(value).strip()]
        interventions_raw: list[str] = []
        for intervention in arms_mod.get("interventions", []) or []:
            name = str(intervention.get("name", "")).strip()
            if name:
                intervention_type = str(intervention.get("type", "")).strip()
                interventions_raw.append(f"{intervention_type}: {name}" if intervention_type else name)
        for arm in arms_mod.get("armGroups", []) or []:
            for name in arm.get("interventionNames", []) or []:
                if str(name).strip():
                    interventions_raw.append(str(name).strip())
        seen_interventions: set[str] = set()
        interventions: list[tuple[str, str]] = []
        for raw in interventions_raw:
            intervention_type, name = _split_intervention(raw)
            key = f"{intervention_type.lower()}::{name.lower()}"
            if name and key not in seen_interventions:
                seen_interventions.add(key)
                interventions.append((intervention_type, name))

        lead_sponsor = (sponsor_mod.get("leadSponsor") or {}).get("name", "")
        lead_sponsor_class = (sponsor_mod.get("leadSponsor") or {}).get("class", "")
        collaborators = "; ".join(
            collaborator.get("name", "")
            for collaborator in sponsor_mod.get("collaborators", []) or []
            if collaborator.get("name")
        )
        phases = "; ".join(design_mod.get("phases", []) or [])
        design_info = design_mod.get("designInfo", {})
        enrollment = design_mod.get("enrollmentInfo", {})

        condition_text = " ".join(conditions)
        intervention_text = " ".join(name for _, name in interventions)
        is_oncology = 1 if _contains_cancer_signal(" ".join([doc["search_term"] or "", doc["title"] or "", condition_text, intervention_text])) else 0
        if not is_oncology:
            is_oncology = 1 if any((doc["search_term"] or "").upper() == brand for brand in priority_brands) else 0
        if not is_oncology:
            is_oncology = 1 if any(name.upper() in priority_brands for _, name in interventions) else 0
        sponsor_upper = lead_sponsor.upper()
        is_top_sponsor = 1 if any(term and term in sponsor_upper for term in top_company_terms) else 0

        conn.execute(
            """
            INSERT INTO clinical_trial
                (nct_id, source_document_id, search_term, brief_title, official_title, overall_status,
                 phases, study_type, primary_purpose, enrollment_count, enrollment_type, lead_sponsor,
                 lead_sponsor_class, collaborators, start_date, primary_completion_date, completion_date,
                 last_update_post_date, source_url, is_oncology_priority, is_top_pharma_sponsor, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(nct_id) DO UPDATE SET
                source_document_id=excluded.source_document_id,
                search_term=excluded.search_term,
                brief_title=excluded.brief_title,
                official_title=excluded.official_title,
                overall_status=excluded.overall_status,
                phases=excluded.phases,
                study_type=excluded.study_type,
                primary_purpose=excluded.primary_purpose,
                enrollment_count=excluded.enrollment_count,
                enrollment_type=excluded.enrollment_type,
                lead_sponsor=excluded.lead_sponsor,
                lead_sponsor_class=excluded.lead_sponsor_class,
                collaborators=excluded.collaborators,
                start_date=excluded.start_date,
                primary_completion_date=excluded.primary_completion_date,
                completion_date=excluded.completion_date,
                last_update_post_date=excluded.last_update_post_date,
                source_url=excluded.source_url,
                is_oncology_priority=excluded.is_oncology_priority,
                is_top_pharma_sponsor=excluded.is_top_pharma_sponsor,
                updated_at=excluded.updated_at
            """,
            (
                nct_id,
                doc["id"],
                doc["search_term"],
                ident.get("briefTitle", doc["title"] or ""),
                ident.get("officialTitle", ""),
                status_mod.get("overallStatus", ""),
                phases,
                design_mod.get("studyType", ""),
                design_info.get("primaryPurpose", ""),
                enrollment.get("count"),
                enrollment.get("type", ""),
                lead_sponsor,
                lead_sponsor_class,
                collaborators,
                _trial_date(status_mod, "startDateStruct"),
                _trial_date(status_mod, "primaryCompletionDateStruct"),
                _trial_date(status_mod, "completionDateStruct"),
                _trial_date(status_mod, "lastUpdatePostDateStruct"),
                doc["url"],
                is_oncology,
                is_top_sponsor,
                _now(),
            ),
        )
        counts["clinical_trials"] += 1

        for idx, condition in enumerate(conditions, start=1):
            condition_id = _slug(f"{nct_id}_condition_{idx}_{condition}")[:140]
            is_condition_oncology = 1 if _contains_cancer_signal(condition) else 0
            conn.execute(
                """
                INSERT INTO clinical_trial_condition
                    (trial_condition_id, nct_id, condition, is_oncology_condition, updated_at)
                VALUES (?,?,?,?,?)
                ON CONFLICT(trial_condition_id) DO UPDATE SET
                    condition=excluded.condition,
                    is_oncology_condition=excluded.is_oncology_condition,
                    updated_at=excluded.updated_at
                """,
                (condition_id, nct_id, condition, is_condition_oncology, _now()),
            )
            counts["clinical_trial_conditions"] += 1

        for idx, (intervention_type, name) in enumerate(interventions, start=1):
            intervention_id = _slug(f"{nct_id}_intervention_{idx}_{intervention_type}_{name}")[:140]
            is_brand = 1 if name.upper() in priority_brands else 0
            conn.execute(
                """
                INSERT INTO clinical_trial_intervention
                    (trial_intervention_id, nct_id, intervention_type, intervention_name, is_oncology_brand, updated_at)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(trial_intervention_id) DO UPDATE SET
                    intervention_type=excluded.intervention_type,
                    intervention_name=excluded.intervention_name,
                    is_oncology_brand=excluded.is_oncology_brand,
                    updated_at=excluded.updated_at
                """,
                (intervention_id, nct_id, intervention_type, name, is_brand, _now()),
            )
            counts["clinical_trial_interventions"] += 1

        for idx, location in enumerate(locations_mod.get("locations", []) or [], start=1):
            if not isinstance(location, dict):
                continue
            facility = str(location.get("facility") or "").strip()
            city = str(location.get("city") or "").strip()
            state = str(location.get("state") or "").strip()
            country = str(location.get("country") or "").strip()
            if not any([facility, city, state, country]):
                continue
            geo = location.get("geoPoint") or {}
            contacts = location.get("contacts") or []
            contact = contacts[0] if contacts and isinstance(contacts[0], dict) else {}
            location_id = _slug(f"{nct_id}_location_{idx}_{facility}_{city}_{state}_{country}")[:160]
            conn.execute(
                """
                INSERT INTO clinical_trial_location
                    (trial_location_id, nct_id, facility, city, state, zip, country, latitude,
                     longitude, status, contact_name, contact_phone, contact_email, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(trial_location_id) DO UPDATE SET
                    facility=excluded.facility,
                    city=excluded.city,
                    state=excluded.state,
                    zip=excluded.zip,
                    country=excluded.country,
                    latitude=excluded.latitude,
                    longitude=excluded.longitude,
                    status=excluded.status,
                    contact_name=excluded.contact_name,
                    contact_phone=excluded.contact_phone,
                    contact_email=excluded.contact_email,
                    updated_at=excluded.updated_at
                """,
                (
                    location_id,
                    nct_id,
                    facility,
                    city,
                    state,
                    str(location.get("zip") or "").strip(),
                    country,
                    geo.get("lat"),
                    geo.get("lon"),
                    str(location.get("status") or "").strip(),
                    str(contact.get("name") or "").strip(),
                    str(contact.get("phone") or "").strip(),
                    str(contact.get("email") or "").strip(),
                    _now(),
                ),
            )
            counts["clinical_trial_locations"] += 1
    return counts


OPENFDA_LABEL_SECTIONS = {
    "indications_and_usage": "Indications and Usage",
    "boxed_warning": "Boxed Warning",
    "warnings_and_cautions": "Warnings and Cautions",
    "warnings": "Warnings",
    "contraindications": "Contraindications",
    "adverse_reactions": "Adverse Reactions",
    "use_in_specific_populations": "Use in Specific Populations",
}


def _openfda_first(openfda: dict[str, Any], key: str) -> str:
    value = openfda.get(key)
    if isinstance(value, list) and value:
        return str(value[0]).strip()
    if value:
        return str(value).strip()
    return ""


def _clean_label_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value


def _parse_dailymed_title(title: str) -> tuple[str, str, str]:
    title = title or ""
    manufacturer = ""
    manufacturer_match = re.search(r"\[([^\]]+)\]\s*$", title)
    if manufacturer_match:
        manufacturer = manufacturer_match.group(1).strip()
        title = title[: manufacturer_match.start()].strip()
    brand = title.split("(", 1)[0].strip(" -")
    generic = ""
    generic_match = re.search(r"\(([^)]+)\)", title)
    if generic_match:
        generic = generic_match.group(1).strip()
    return brand, generic, manufacturer


def _upsert_dailymed_labels(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM dailymed_label")
    priority_brands = _priority_brand_set(conn)
    docs = conn.execute(
        """
        SELECT id, external_id, search_term, title, url, blob_path, metadata_json
        FROM documents
        WHERE source='dailymed' AND doc_type='spl_label'
        """
    ).fetchall()
    written = 0
    for doc in docs:
        try:
            metadata = json.loads(doc["metadata_json"] or "{}")
        except Exception:
            metadata = {}
        title = metadata.get("title") or doc["title"] or ""
        brand, generic, manufacturer = _parse_dailymed_title(title)
        search_term = doc["search_term"] or ""
        haystack = f"{search_term} {title} {brand} {generic} {manufacturer}".upper()
        is_oncology = search_term.upper() in priority_brands or brand.upper() in priority_brands or _contains_cancer_signal(haystack)
        conn.execute(
            """
            INSERT INTO dailymed_label
                (setid, source_document_id, search_term, title, brand, generic_name, manufacturer,
                 spl_version, published_date, source_url, is_oncology_priority, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(setid) DO UPDATE SET
                source_document_id=excluded.source_document_id,
                search_term=excluded.search_term,
                title=excluded.title,
                brand=excluded.brand,
                generic_name=excluded.generic_name,
                manufacturer=excluded.manufacturer,
                spl_version=excluded.spl_version,
                published_date=excluded.published_date,
                source_url=excluded.source_url,
                is_oncology_priority=excluded.is_oncology_priority,
                updated_at=excluded.updated_at
            """,
            (
                doc["external_id"] or _slug(f"{doc['id']}_{title}")[:120],
                doc["id"],
                search_term,
                title,
                brand,
                generic,
                manufacturer,
                metadata.get("spl_version"),
                metadata.get("published_date", ""),
                doc["url"],
                1 if is_oncology else 0,
                _now(),
            ),
        )
        written += 1
    return written


SEC_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
SEC_ANY_TAG_RE = re.compile(r"<[^>]+>")


def _html_to_plain_text(value: str) -> str:
    value = SEC_TAG_RE.sub(" ", value or "")
    value = SEC_ANY_TAG_RE.sub(" ", value)
    value = html_lib.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _brand_context(text: str, brand: str) -> str:
    match = re.search(rf"\b{re.escape(brand)}\b", text, flags=re.IGNORECASE)
    if not match:
        return ""
    start = max(0, match.start() - 220)
    end = min(len(text), match.end() + 300)
    return text[start:end].strip()


def _upsert_sec_brand_mentions(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM sec_filing_brand_mention")
    brands = [row["brand"] for row in conn.execute("SELECT brand FROM oncology_brand_seed").fetchall()]
    docs = conn.execute(
        "SELECT id, url, blob_path, metadata_json FROM documents WHERE source='sec_edgar:annual_filing_document'"
    ).fetchall()
    written = 0
    for doc in docs:
        metadata = json.loads(doc["metadata_json"] or "{}")
        text = _html_to_plain_text(_load_blob(doc["blob_path"]))
        if not text:
            continue
        for brand in brands:
            matches = re.findall(rf"\b{re.escape(brand)}\b", text, flags=re.IGNORECASE)
            if not matches:
                continue
            mention_id = _slug(f"{doc['id']}_{brand}")[:140]
            conn.execute(
                """
                INSERT INTO sec_filing_brand_mention
                    (sec_brand_mention_id, source_document_id, company, ticker, cik, form, filing_date,
                     brand, mention_count, context_snippet, filing_url, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(sec_brand_mention_id) DO UPDATE SET
                    company=excluded.company,
                    ticker=excluded.ticker,
                    cik=excluded.cik,
                    form=excluded.form,
                    filing_date=excluded.filing_date,
                    brand=excluded.brand,
                    mention_count=excluded.mention_count,
                    context_snippet=excluded.context_snippet,
                    filing_url=excluded.filing_url,
                    updated_at=excluded.updated_at
                """,
                (
                    mention_id,
                    doc["id"],
                    metadata.get("company", ""),
                    metadata.get("ticker", ""),
                    metadata.get("cik", ""),
                    metadata.get("form", ""),
                    metadata.get("filing_date", ""),
                    brand,
                    len(matches),
                    _brand_context(text, brand),
                    doc["url"],
                    _now(),
                ),
            )
            written += 1
    return written


def _upsert_regulatory_label_messages(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM regulatory_label_message")
    priority_brands = _priority_brand_set(conn)
    docs = conn.execute(
        "SELECT id, title, url, blob_path FROM documents WHERE source='openfda' AND doc_type='drug_label'"
    ).fetchall()
    written = 0
    for doc in docs:
        try:
            label = json.loads(_load_blob(doc["blob_path"]) or "{}")
        except Exception:
            continue
        openfda = label.get("openfda", {})
        brand = _openfda_first(openfda, "brand_name") or doc["title"]
        generic = _openfda_first(openfda, "generic_name")
        manufacturer = _openfda_first(openfda, "manufacturer_name")
        brand_upper = brand.upper()
        indication_values = label.get("indications_and_usage", [])
        if isinstance(indication_values, str):
            indication_values = [indication_values]
        if not isinstance(indication_values, list):
            indication_values = []
        label_is_oncology = brand_upper in priority_brands or _contains_cancer_signal(
            " ".join([brand, generic, " ".join(str(value) for value in indication_values)])
        )
        for raw_section, section_name in OPENFDA_LABEL_SECTIONS.items():
            values = label.get(raw_section, [])
            if isinstance(values, str):
                values = [values]
            if not isinstance(values, list):
                continue
            for idx, message in enumerate(values, start=1):
                text = _clean_label_text(str(message))
                if len(text) < 20:
                    continue
                is_priority = 1 if label_is_oncology else 0
                therapy_area = "oncology" if is_priority else ""
                message_id = _slug(f"{doc['id']}_{raw_section}_{idx}_{brand}")[:140]
                conn.execute(
                    """
                    INSERT INTO regulatory_label_message
                        (label_message_id, source_document_id, source_system, brand, generic_name, manufacturer,
                         therapy_area, label_section, message_text, source_url, is_oncology_priority, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(label_message_id) DO UPDATE SET
                        brand=excluded.brand,
                        generic_name=excluded.generic_name,
                        manufacturer=excluded.manufacturer,
                        therapy_area=excluded.therapy_area,
                        label_section=excluded.label_section,
                        message_text=excluded.message_text,
                        source_url=excluded.source_url,
                        is_oncology_priority=excluded.is_oncology_priority,
                        updated_at=excluded.updated_at
                    """,
                    (
                        message_id,
                        doc["id"],
                        "openFDA drug label",
                        brand,
                        generic,
                        manufacturer,
                        therapy_area,
                        section_name,
                        text,
                        doc["url"],
                        is_priority,
                        _now(),
                    ),
                )
                written += 1
    return written


SERIOUSNESS_LABELS = {
    "1": "Serious",
    "2": "Non-serious",
}


def _upsert_openfda_event_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {"openfda_event_reaction_counts": 0, "openfda_event_serious_counts": 0}
    conn.execute("DELETE FROM openfda_event_reaction_count")
    conn.execute("DELETE FROM openfda_event_serious_count")
    docs = conn.execute(
        """
        SELECT id, search_term, url, blob_path, metadata_json
        FROM documents
        WHERE source='openfda:drug_event'
          AND doc_type='faers_adverse_event_counts'
        """
    ).fetchall()
    for doc in docs:
        brand = (doc["search_term"] or "").strip()
        if not brand:
            continue
        try:
            payload = json.loads(_load_blob(doc["blob_path"]) or "{}")
        except Exception:
            continue
        meta = payload.get("meta") or {}
        last_updated = str(meta.get("last_updated") or "")
        for idx, row in enumerate(payload.get("reaction_counts") or [], start=1):
            term = str(row.get("term") or "").strip()
            if not term:
                continue
            try:
                count = int(row.get("count") or 0)
            except Exception:
                count = 0
            event_reaction_id = _slug(f"{doc['id']}_{brand}_{idx}_{term}")[:140]
            conn.execute(
                """
                INSERT INTO openfda_event_reaction_count
                    (event_reaction_id, source_document_id, brand, reaction_term, reaction_count,
                     api_last_updated, source_url, updated_at)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(event_reaction_id) DO UPDATE SET
                    brand=excluded.brand,
                    reaction_term=excluded.reaction_term,
                    reaction_count=excluded.reaction_count,
                    api_last_updated=excluded.api_last_updated,
                    source_url=excluded.source_url,
                    updated_at=excluded.updated_at
                """,
                (event_reaction_id, doc["id"], brand, term, count, last_updated, doc["url"], _now()),
            )
            counts["openfda_event_reaction_counts"] += 1
        for row in payload.get("serious_counts") or []:
            code = str(row.get("term") or "").strip()
            if not code:
                continue
            try:
                count = int(row.get("count") or 0)
            except Exception:
                count = 0
            event_serious_id = _slug(f"{doc['id']}_{brand}_serious_{code}")[:140]
            conn.execute(
                """
                INSERT INTO openfda_event_serious_count
                    (event_serious_id, source_document_id, brand, serious_code, serious_label,
                     report_count, api_last_updated, source_url, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(event_serious_id) DO UPDATE SET
                    brand=excluded.brand,
                    serious_code=excluded.serious_code,
                    serious_label=excluded.serious_label,
                    report_count=excluded.report_count,
                    api_last_updated=excluded.api_last_updated,
                    source_url=excluded.source_url,
                    updated_at=excluded.updated_at
                """,
                (
                    event_serious_id,
                    doc["id"],
                    brand,
                    code,
                    SERIOUSNESS_LABELS.get(code, code),
                    count,
                    last_updated,
                    doc["url"],
                    _now(),
                ),
            )
            counts["openfda_event_serious_counts"] += 1
    return counts


def _list_text(values: Any) -> str:
    if isinstance(values, list):
        return "; ".join(str(value).strip() for value in values if str(value).strip())
    return str(values or "").strip()


def _upsert_openfda_drug_shortages(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM openfda_drug_shortage")
    docs = conn.execute(
        """
        SELECT id, url, blob_path, metadata_json
        FROM documents
        WHERE source='openfda:drug_shortages'
          AND doc_type='drug_shortage_records'
        """
    ).fetchall()
    written = 0
    for doc in docs:
        try:
            payload = json.loads(_load_blob(doc["blob_path"]) or "{}")
        except Exception:
            continue
        meta = payload.get("meta") or {}
        api_last_updated = str(meta.get("last_updated") or "")
        for idx, row in enumerate(payload.get("results") or [], start=1):
            if not isinstance(row, dict):
                continue
            openfda = row.get("openfda") or {}
            package_ndc = str(row.get("package_ndc") or "").strip()
            presentation = str(row.get("presentation") or "").strip()
            generic_name = str(row.get("generic_name") or "").strip()
            company_name = str(row.get("company_name") or "").strip()
            brand_names = _list_text(openfda.get("brand_name"))
            manufacturer_names = _list_text(openfda.get("manufacturer_name"))
            therapeutic_category = _list_text(row.get("therapeutic_category"))
            shortage_id = _slug(f"{doc['id']}_{package_ndc}_{generic_name}_{company_name}_{idx}")[:140]
            is_oncology = 1 if "oncology" in therapeutic_category.lower() or _contains_cancer_signal(
                " ".join([generic_name, brand_names, therapeutic_category, presentation])
            ) else 0
            conn.execute(
                """
                INSERT INTO openfda_drug_shortage
                    (shortage_id, source_document_id, status, update_type, initial_posting_date,
                     update_date, discontinued_date, package_ndc, generic_name, brand_names,
                     manufacturer_names, company_name, availability, shortage_reason, related_info,
                     contact_info, therapeutic_category, dosage_form, presentation, is_oncology_priority,
                     source_url, api_last_updated, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(shortage_id) DO UPDATE SET
                    status=excluded.status,
                    update_type=excluded.update_type,
                    initial_posting_date=excluded.initial_posting_date,
                    update_date=excluded.update_date,
                    discontinued_date=excluded.discontinued_date,
                    package_ndc=excluded.package_ndc,
                    generic_name=excluded.generic_name,
                    brand_names=excluded.brand_names,
                    manufacturer_names=excluded.manufacturer_names,
                    company_name=excluded.company_name,
                    availability=excluded.availability,
                    shortage_reason=excluded.shortage_reason,
                    related_info=excluded.related_info,
                    contact_info=excluded.contact_info,
                    therapeutic_category=excluded.therapeutic_category,
                    dosage_form=excluded.dosage_form,
                    presentation=excluded.presentation,
                    is_oncology_priority=excluded.is_oncology_priority,
                    source_url=excluded.source_url,
                    api_last_updated=excluded.api_last_updated,
                    updated_at=excluded.updated_at
                """,
                (
                    shortage_id,
                    doc["id"],
                    row.get("status", ""),
                    row.get("update_type", ""),
                    row.get("initial_posting_date", ""),
                    row.get("update_date", ""),
                    row.get("discontinued_date", ""),
                    package_ndc,
                    generic_name,
                    brand_names,
                    manufacturer_names,
                    company_name,
                    row.get("availability", ""),
                    row.get("shortage_reason", ""),
                    row.get("related_info", ""),
                    row.get("contact_info", ""),
                    therapeutic_category,
                    row.get("dosage_form", ""),
                    presentation,
                    is_oncology,
                    doc["url"],
                    api_last_updated,
                    _now(),
                ),
            )
            written += 1
    return written


def _upsert_openfda_drug_recalls(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM openfda_drug_recall")
    docs = conn.execute(
        """
        SELECT id, url, blob_path, metadata_json
        FROM documents
        WHERE source='openfda:drug_enforcement'
          AND doc_type='drug_recall_records'
        """
    ).fetchall()
    written = 0
    for doc in docs:
        try:
            payload = json.loads(_load_blob(doc["blob_path"]) or "{}")
            doc_meta = json.loads(doc["metadata_json"] or "{}")
        except Exception:
            continue
        meta = payload.get("meta") or {}
        api_last_updated = str(meta.get("last_updated") or doc_meta.get("last_updated") or "")
        matched_brand = str(doc_meta.get("brand") or "").strip()
        query_term = str(doc_meta.get("query_term") or "").strip()
        term_type = str(doc_meta.get("term_type") or "").strip()
        for idx, row in enumerate(payload.get("results") or [], start=1):
            if not isinstance(row, dict):
                continue
            recall_number = str(row.get("recall_number") or "").strip()
            product_description = str(row.get("product_description") or "").strip()
            recall_record_id = _slug(f"{matched_brand}_{recall_number or idx}_{query_term}")[:160]
            conn.execute(
                """
                INSERT INTO openfda_drug_recall
                    (recall_record_id, source_document_id, matched_brand, query_term, term_type,
                     recall_number, classification, status, recalling_firm, voluntary_mandated,
                     product_type, product_description, reason_for_recall, distribution_pattern,
                     code_info, initial_firm_notification, recall_initiation_date, report_date,
                     termination_date, center_classification_date, source_url, api_last_updated,
                     updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(recall_record_id) DO UPDATE SET
                    source_document_id=excluded.source_document_id,
                    matched_brand=excluded.matched_brand,
                    query_term=excluded.query_term,
                    term_type=excluded.term_type,
                    recall_number=excluded.recall_number,
                    classification=excluded.classification,
                    status=excluded.status,
                    recalling_firm=excluded.recalling_firm,
                    voluntary_mandated=excluded.voluntary_mandated,
                    product_type=excluded.product_type,
                    product_description=excluded.product_description,
                    reason_for_recall=excluded.reason_for_recall,
                    distribution_pattern=excluded.distribution_pattern,
                    code_info=excluded.code_info,
                    initial_firm_notification=excluded.initial_firm_notification,
                    recall_initiation_date=excluded.recall_initiation_date,
                    report_date=excluded.report_date,
                    termination_date=excluded.termination_date,
                    center_classification_date=excluded.center_classification_date,
                    source_url=excluded.source_url,
                    api_last_updated=excluded.api_last_updated,
                    updated_at=excluded.updated_at
                """,
                (
                    recall_record_id,
                    doc["id"],
                    matched_brand,
                    query_term,
                    term_type,
                    recall_number,
                    row.get("classification", ""),
                    row.get("status", ""),
                    row.get("recalling_firm", ""),
                    row.get("voluntary_mandated", ""),
                    row.get("product_type", ""),
                    product_description,
                    row.get("reason_for_recall", ""),
                    row.get("distribution_pattern", ""),
                    row.get("code_info", ""),
                    row.get("initial_firm_notification", ""),
                    row.get("recall_initiation_date", ""),
                    row.get("report_date", ""),
                    row.get("termination_date", ""),
                    row.get("center_classification_date", ""),
                    doc["url"],
                    api_last_updated,
                    _now(),
                ),
            )
            written += 1
    return written


def _active_ingredient_text(values: Any) -> str:
    if not isinstance(values, list):
        return ""
    parts: list[str] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        name = str(value.get("name") or "").strip()
        strength = str(value.get("strength") or "").strip()
        if name and strength:
            parts.append(f"{name} ({strength})")
        elif name:
            parts.append(name)
    return "; ".join(parts)


def _upsert_openfda_ndc(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {"openfda_ndc_products": 0, "openfda_ndc_packages": 0}
    conn.execute("DELETE FROM openfda_ndc_package")
    conn.execute("DELETE FROM openfda_ndc_product")
    docs = conn.execute(
        """
        SELECT id, url, blob_path, metadata_json
        FROM documents
        WHERE source='openfda:drug_ndc'
          AND doc_type='ndc_directory_records'
        """
    ).fetchall()
    for doc in docs:
        try:
            payload = json.loads(_load_blob(doc["blob_path"]) or "{}")
            doc_meta = json.loads(doc["metadata_json"] or "{}")
        except Exception:
            continue
        meta = payload.get("meta") or {}
        api_last_updated = str(meta.get("last_updated") or doc_meta.get("last_updated") or "")
        matched_brand = str(doc_meta.get("brand") or "").strip()
        query_term = str(doc_meta.get("query_term") or "").strip()
        query_field = str(doc_meta.get("query_field") or "").strip()
        for idx, row in enumerate(payload.get("results") or [], start=1):
            if not isinstance(row, dict):
                continue
            product_ndc = str(row.get("product_ndc") or "").strip()
            brand_name = str(row.get("brand_name") or "").strip()
            generic_name = str(row.get("generic_name") or "").strip()
            ndc_product_id = _slug(f"{matched_brand}_{product_ndc or idx}_{query_term}")[:160]
            conn.execute(
                """
                INSERT INTO openfda_ndc_product
                    (ndc_product_id, source_document_id, matched_brand, query_term, query_field,
                     product_ndc, brand_name, generic_name, labeler_name, product_type,
                     marketing_category, application_number, dosage_form, route,
                     active_ingredients, pharm_class, dea_schedule, listing_expiration_date,
                     marketing_start_date, marketing_end_date, finished, source_url,
                     api_last_updated, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(ndc_product_id) DO UPDATE SET
                    source_document_id=excluded.source_document_id,
                    matched_brand=excluded.matched_brand,
                    query_term=excluded.query_term,
                    query_field=excluded.query_field,
                    product_ndc=excluded.product_ndc,
                    brand_name=excluded.brand_name,
                    generic_name=excluded.generic_name,
                    labeler_name=excluded.labeler_name,
                    product_type=excluded.product_type,
                    marketing_category=excluded.marketing_category,
                    application_number=excluded.application_number,
                    dosage_form=excluded.dosage_form,
                    route=excluded.route,
                    active_ingredients=excluded.active_ingredients,
                    pharm_class=excluded.pharm_class,
                    dea_schedule=excluded.dea_schedule,
                    listing_expiration_date=excluded.listing_expiration_date,
                    marketing_start_date=excluded.marketing_start_date,
                    marketing_end_date=excluded.marketing_end_date,
                    finished=excluded.finished,
                    source_url=excluded.source_url,
                    api_last_updated=excluded.api_last_updated,
                    updated_at=excluded.updated_at
                """,
                (
                    ndc_product_id,
                    doc["id"],
                    matched_brand,
                    query_term,
                    query_field,
                    product_ndc,
                    brand_name,
                    generic_name,
                    row.get("labeler_name", ""),
                    row.get("product_type", ""),
                    row.get("marketing_category", ""),
                    row.get("application_number", ""),
                    row.get("dosage_form", ""),
                    _list_text(row.get("route")),
                    _active_ingredient_text(row.get("active_ingredients")),
                    _list_text(row.get("pharm_class")),
                    row.get("dea_schedule", ""),
                    row.get("listing_expiration_date", ""),
                    row.get("marketing_start_date", ""),
                    row.get("marketing_end_date", ""),
                    1 if row.get("finished") is True else 0,
                    doc["url"],
                    api_last_updated,
                    _now(),
                ),
            )
            counts["openfda_ndc_products"] += 1

            for package_idx, package in enumerate(row.get("packaging") or [], start=1):
                if not isinstance(package, dict):
                    continue
                package_ndc = str(package.get("package_ndc") or "").strip()
                if not package_ndc:
                    continue
                ndc_package_id = _slug(f"{ndc_product_id}_{package_ndc}_{package_idx}")[:180]
                conn.execute(
                    """
                    INSERT INTO openfda_ndc_package
                        (ndc_package_id, ndc_product_id, source_document_id, matched_brand,
                         product_ndc, package_ndc, package_description, marketing_start_date,
                         marketing_end_date, sample, source_url, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(ndc_package_id) DO UPDATE SET
                        ndc_product_id=excluded.ndc_product_id,
                        source_document_id=excluded.source_document_id,
                        matched_brand=excluded.matched_brand,
                        product_ndc=excluded.product_ndc,
                        package_ndc=excluded.package_ndc,
                        package_description=excluded.package_description,
                        marketing_start_date=excluded.marketing_start_date,
                        marketing_end_date=excluded.marketing_end_date,
                        sample=excluded.sample,
                        source_url=excluded.source_url,
                        updated_at=excluded.updated_at
                    """,
                    (
                        ndc_package_id,
                        ndc_product_id,
                        doc["id"],
                        matched_brand,
                        product_ndc,
                        package_ndc,
                        package.get("description", ""),
                        package.get("marketing_start_date", ""),
                        package.get("marketing_end_date", ""),
                        1 if package.get("sample") is True else 0,
                        doc["url"],
                        _now(),
                    ),
                )
                counts["openfda_ndc_packages"] += 1
    return counts


def _upsert_fda_srlc(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM fda_srlc_labeling_change")
    docs = conn.execute(
        """
        SELECT id, search_term, title, url, blob_path, metadata_json
        FROM documents
        WHERE source='fda:safety_labeling_changes'
          AND doc_type='srlc_detail_page'
        """
    ).fetchall()
    count = 0
    for doc in docs:
        try:
            metadata = json.loads(doc["metadata_json"] or "{}")
        except Exception:
            metadata = {}
        matched_brand = str(metadata.get("brand") or doc["search_term"] or "").strip()
        drug_name = str(metadata.get("drug_name") or "").strip()
        application_number = str(metadata.get("application_number") or "").strip()
        detail_url = str(metadata.get("detail_url") or doc["url"] or "").strip()
        if not matched_brand or not drug_name:
            continue
        detail_text = str(metadata.get("detail_text_excerpt") or "").strip()
        if not detail_text:
            detail_text = re.sub(r"\s+", " ", html_lib.unescape(_load_blob(doc["blob_path"]) or "")).strip()[:1200]
        change_id = _slug(f"{matched_brand}_{drug_name}_{application_number}_{metadata.get('supplement_date', '')}")[:180]
        conn.execute(
            """
            INSERT INTO fda_srlc_labeling_change
                (srlc_change_id, source_document_id, matched_brand, query_term, drug_name,
                 active_ingredient, application_number, application_type, supplement_date,
                 database_updated, detail_url, text_excerpt, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(srlc_change_id) DO UPDATE SET
                source_document_id=excluded.source_document_id,
                matched_brand=excluded.matched_brand,
                query_term=excluded.query_term,
                drug_name=excluded.drug_name,
                active_ingredient=excluded.active_ingredient,
                application_number=excluded.application_number,
                application_type=excluded.application_type,
                supplement_date=excluded.supplement_date,
                database_updated=excluded.database_updated,
                detail_url=excluded.detail_url,
                text_excerpt=excluded.text_excerpt,
                updated_at=excluded.updated_at
            """,
            (
                change_id,
                doc["id"],
                matched_brand,
                doc["search_term"],
                drug_name,
                metadata.get("active_ingredient", ""),
                application_number,
                metadata.get("application_type", ""),
                metadata.get("supplement_date", ""),
                metadata.get("database_updated", ""),
                detail_url,
                detail_text,
                _now(),
            ),
        )
        count += 1
    return count


def _upsert_nci_drug_dictionary(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {"nci_drug_dictionary_entries": 0, "nci_drug_dictionary_aliases": 0}
    conn.execute("DELETE FROM nci_drug_dictionary_alias")
    conn.execute("DELETE FROM nci_drug_dictionary_entry")
    docs = conn.execute(
        """
        SELECT id, search_term, url, blob_path, metadata_json
        FROM documents
        WHERE source='nci:drug_dictionary'
          AND doc_type='nci_drug_dictionary_entry'
        """
    ).fetchall()
    for doc in docs:
        try:
            payload = json.loads(_load_blob(doc["blob_path"]) or "{}")
            metadata = json.loads(doc["metadata_json"] or "{}")
        except Exception:
            continue
        term_id = str(payload.get("termId") or metadata.get("term_id") or "").strip()
        if not term_id:
            continue
        matched_brand = str(metadata.get("brand") or doc["search_term"] or "").strip()
        query_term = str(metadata.get("query_term") or "").strip()
        entry_id = _slug(f"{matched_brand}_{query_term}_{term_id}")[:180]
        definition = payload.get("definition") or {}
        drug_info = payload.get("drugInfoSummaryLink") or {}
        aliases = [alias for alias in payload.get("aliases") or [] if isinstance(alias, dict)]
        conn.execute(
            """
            INSERT INTO nci_drug_dictionary_entry
                (nci_drug_entry_id, source_document_id, matched_brand, query_term, term_type,
                 term_id, nci_concept_id, nci_concept_name, name, pretty_url_name,
                 first_letter, term_name_type, definition_text, drug_info_summary_url,
                 alias_count, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(nci_drug_entry_id) DO UPDATE SET
                source_document_id=excluded.source_document_id,
                matched_brand=excluded.matched_brand,
                query_term=excluded.query_term,
                term_type=excluded.term_type,
                term_id=excluded.term_id,
                nci_concept_id=excluded.nci_concept_id,
                nci_concept_name=excluded.nci_concept_name,
                name=excluded.name,
                pretty_url_name=excluded.pretty_url_name,
                first_letter=excluded.first_letter,
                term_name_type=excluded.term_name_type,
                definition_text=excluded.definition_text,
                drug_info_summary_url=excluded.drug_info_summary_url,
                alias_count=excluded.alias_count,
                updated_at=excluded.updated_at
            """,
            (
                entry_id,
                doc["id"],
                matched_brand,
                query_term,
                metadata.get("term_type", ""),
                term_id,
                payload.get("nciConceptId", ""),
                payload.get("nciConceptName", ""),
                payload.get("name", ""),
                payload.get("prettyUrlName", ""),
                payload.get("firstLetter", ""),
                payload.get("termNameType", ""),
                definition.get("text", "") if isinstance(definition, dict) else "",
                drug_info.get("uri", "") if isinstance(drug_info, dict) else "",
                len(aliases),
                _now(),
            ),
        )
        counts["nci_drug_dictionary_entries"] += 1
        for idx, alias in enumerate(aliases, start=1):
            alias_name = str(alias.get("name") or "").strip()
            if not alias_name:
                continue
            alias_id = _slug(f"{entry_id}_{alias.get('type', '')}_{alias_name}_{idx}")[:220]
            conn.execute(
                """
                INSERT INTO nci_drug_dictionary_alias
                    (nci_drug_alias_id, nci_drug_entry_id, matched_brand, alias_type,
                     alias_name, updated_at)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(nci_drug_alias_id) DO UPDATE SET
                    nci_drug_entry_id=excluded.nci_drug_entry_id,
                    matched_brand=excluded.matched_brand,
                    alias_type=excluded.alias_type,
                    alias_name=excluded.alias_name,
                    updated_at=excluded.updated_at
                """,
                (alias_id, entry_id, matched_brand, alias.get("type", ""), alias_name, _now()),
            )
            counts["nci_drug_dictionary_aliases"] += 1
    return counts


def _upsert_nci_drug_info(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM nci_drug_information_summary")
    docs = conn.execute(
        """
        SELECT id, search_term, url, metadata_json
        FROM documents
        WHERE source='nci:drug_information_summary'
          AND doc_type='nci_drug_information_summary'
        """
    ).fetchall()
    count = 0
    for doc in docs:
        try:
            metadata = json.loads(doc["metadata_json"] or "{}")
        except Exception:
            metadata = {}
        matched_brand = str(metadata.get("brand") or doc["search_term"] or "").strip()
        concept = str(metadata.get("nci_concept_name") or metadata.get("query_term") or "").strip()
        if not matched_brand or not concept:
            continue
        info_id = _slug(f"{matched_brand}_{concept}")[:180]
        conn.execute(
            """
            INSERT INTO nci_drug_information_summary
                (nci_drug_info_id, source_document_id, matched_brand, query_term,
                 nci_concept_name, title, us_brand_names, fda_approved, use_in_cancer,
                 posted_date, updated_date, link_count, source_url, text_excerpt, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(nci_drug_info_id) DO UPDATE SET
                source_document_id=excluded.source_document_id,
                matched_brand=excluded.matched_brand,
                query_term=excluded.query_term,
                nci_concept_name=excluded.nci_concept_name,
                title=excluded.title,
                us_brand_names=excluded.us_brand_names,
                fda_approved=excluded.fda_approved,
                use_in_cancer=excluded.use_in_cancer,
                posted_date=excluded.posted_date,
                updated_date=excluded.updated_date,
                link_count=excluded.link_count,
                source_url=excluded.source_url,
                text_excerpt=excluded.text_excerpt,
                updated_at=excluded.updated_at
            """,
            (
                info_id,
                doc["id"],
                matched_brand,
                metadata.get("query_term", ""),
                concept,
                metadata.get("title", ""),
                metadata.get("us_brand_names", ""),
                metadata.get("fda_approved", ""),
                metadata.get("use_in_cancer_excerpt", ""),
                metadata.get("posted_date", ""),
                metadata.get("updated_date", ""),
                int(metadata.get("link_count") or 0),
                doc["url"],
                metadata.get("text_excerpt", ""),
                _now(),
            ),
        )
        count += 1
    return count


def _historical_ndc_count(payload: dict[str, Any]) -> int:
    group = payload.get("historicalNdcConcept") or payload.get("historicalNdcTime") or payload
    if isinstance(group, dict):
        values = group.get("historicalNdc") or group.get("ndc") or []
        if isinstance(values, list):
            return len(values)
        if values:
            return 1
    return 0


def _upsert_rxnorm(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {"rxnorm_concepts": 0, "rxnorm_related_concepts": 0}
    conn.execute("DELETE FROM rxnorm_related_concept")
    conn.execute("DELETE FROM rxnorm_concept")
    docs = conn.execute(
        """
        SELECT id, url, blob_path
        FROM documents
        WHERE source='rxnav:rxnorm'
          AND doc_type='rxnorm_concept_records'
        """
    ).fetchall()
    for doc in docs:
        try:
            payload = json.loads(_load_blob(doc["blob_path"]) or "{}")
        except Exception:
            continue
        props = payload.get("properties") or {}
        related_groups = ((payload.get("related") or {}).get("allRelatedGroup") or {}).get("conceptGroup") or []
        related_rows: list[tuple[str, dict[str, Any]]] = []
        for group in related_groups:
            if not isinstance(group, dict):
                continue
            tty = str(group.get("tty") or "").strip()
            for concept in group.get("conceptProperties") or []:
                if isinstance(concept, dict):
                    related_rows.append((tty, concept))
        matched_brand = str(payload.get("brand") or "").strip()
        query_term = str(payload.get("query_term") or "").strip()
        term_type = str(payload.get("term_type") or "").strip()
        rxcui = str(props.get("rxcui") or payload.get("rxcui") or "").strip()
        if not rxcui:
            continue
        concept_id = _slug(f"{matched_brand}_{term_type}_{query_term}_{rxcui}")[:160]
        conn.execute(
            """
            INSERT INTO rxnorm_concept
                (rxnorm_concept_id, source_document_id, matched_brand, query_term, term_type,
                 rxcui, name, synonym, tty, language, suppress, umlscui, related_concept_count,
                 historical_ndc_count, source_url, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(rxnorm_concept_id) DO UPDATE SET
                source_document_id=excluded.source_document_id,
                matched_brand=excluded.matched_brand,
                query_term=excluded.query_term,
                term_type=excluded.term_type,
                rxcui=excluded.rxcui,
                name=excluded.name,
                synonym=excluded.synonym,
                tty=excluded.tty,
                language=excluded.language,
                suppress=excluded.suppress,
                umlscui=excluded.umlscui,
                related_concept_count=excluded.related_concept_count,
                historical_ndc_count=excluded.historical_ndc_count,
                source_url=excluded.source_url,
                updated_at=excluded.updated_at
            """,
            (
                concept_id,
                doc["id"],
                matched_brand,
                query_term,
                term_type,
                rxcui,
                props.get("name", ""),
                props.get("synonym", ""),
                props.get("tty", ""),
                props.get("language", ""),
                props.get("suppress", ""),
                props.get("umlscui", ""),
                len(related_rows),
                _historical_ndc_count(payload.get("historical_ndcs") or {}),
                doc["url"],
                _now(),
            ),
        )
        counts["rxnorm_concepts"] += 1
        for idx, (group_tty, concept) in enumerate(related_rows, start=1):
            related_rxcui = str(concept.get("rxcui") or "").strip()
            if not related_rxcui:
                continue
            related_id = _slug(f"{concept_id}_{related_rxcui}_{group_tty}_{idx}")[:180]
            conn.execute(
                """
                INSERT INTO rxnorm_related_concept
                    (rxnorm_related_id, source_rxnorm_concept_id, matched_brand, source_rxcui,
                     related_rxcui, related_name, related_synonym, related_tty, language,
                     suppress, umlscui, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(rxnorm_related_id) DO UPDATE SET
                    source_rxnorm_concept_id=excluded.source_rxnorm_concept_id,
                    matched_brand=excluded.matched_brand,
                    source_rxcui=excluded.source_rxcui,
                    related_rxcui=excluded.related_rxcui,
                    related_name=excluded.related_name,
                    related_synonym=excluded.related_synonym,
                    related_tty=excluded.related_tty,
                    language=excluded.language,
                    suppress=excluded.suppress,
                    umlscui=excluded.umlscui,
                    updated_at=excluded.updated_at
                """,
                (
                    related_id,
                    concept_id,
                    matched_brand,
                    rxcui,
                    related_rxcui,
                    concept.get("name", ""),
                    concept.get("synonym", ""),
                    concept.get("tty", "") or group_tty,
                    concept.get("language", ""),
                    concept.get("suppress", ""),
                    concept.get("umlscui", ""),
                    _now(),
                ),
            )
            counts["rxnorm_related_concepts"] += 1
    return counts


def build() -> dict[str, int]:
    conn = get_db()
    conn.row_factory = sqlite3.Row
    for view in [
        "v_oncology_award_mentions",
        "v_top_pharma_oncology_priority",
        "v_official_oncology_brand_messages",
        "v_oncology_label_messages",
        "v_openfda_event_oncology_reactions",
        "v_openfda_event_oncology_seriousness",
        "v_openfda_oncology_drug_shortages",
        "v_openfda_oncology_drug_recalls",
        "v_openfda_oncology_ndc_products",
        "v_openfda_oncology_ndc_packages",
        "v_rxnorm_oncology_concepts",
        "v_rxnorm_oncology_related_concepts",
        "v_fda_srlc_oncology_labeling_changes",
        "v_nci_oncology_drug_dictionary",
        "v_nci_oncology_drug_information_summaries",
        "v_dailymed_oncology_priority",
        "v_oncology_message_campaign_evidence",
        "v_oncology_clinical_trials",
        "v_oncology_clinical_trial_locations",
        "v_oncology_pubmed_articles",
        "v_asco_oncology_abstracts",
        "v_seer_oncology_market_context",
        "v_oncology_search_interest",
        "v_cms_open_payments_oncology",
        "v_cms_open_payments_top_recipients",
        "v_oncology_brand_evidence_summary",
        "v_opdp_oncology_enforcement",
        "v_opdp_oncology_letter_documents",
        "v_orange_book_oncology_priority",
        "v_drugs_fda_oncology_priority",
        "v_purple_book_oncology_priority",
        "v_fda_oncology_approval_timeline",
        "v_ema_oncology_priority",
        "v_ema_oncology_documents",
        "v_sec_top_pharma_filings",
        "v_sec_oncology_brand_mentions",
    ]:
        conn.execute(f"DROP VIEW IF EXISTS {view}")
    conn.executescript(SCHEMA)
    _ensure_columns(conn)
    try:
        counts: dict[str, int] = {}
        counts["sources"] = _upsert_sources(conn)
        counts["companies"] = _upsert_companies(conn)
        therapy_count, brand_count = _upsert_seeds(conn)
        counts["therapy_areas"] = therapy_count
        counts["oncology_brands"] = brand_count
        counts["official_brand_sites"] = _upsert_brand_sites(conn)
        counts["oncology_sales_companies"] = _upsert_oncology_sales_companies(conn)
        counts["award_mentions"] = _upsert_award_mentions(conn)
        counts["brand_messages"] = _upsert_brand_messages(conn)
        counts["dailymed_labels"] = _upsert_dailymed_labels(conn)
        counts.update(_upsert_pubmed_articles(conn))
        counts["asco_abstracts"] = _upsert_asco_abstracts(conn)
        counts["seer_cancer_stats"] = _upsert_seer_stats(conn)
        counts.update(_upsert_search_interest(conn))
        counts["cms_open_payment_general"] = _upsert_open_payments(conn)
        counts.update(_upsert_clinical_trials(conn))
        counts["regulatory_label_messages"] = _upsert_regulatory_label_messages(conn)
        counts.update(_upsert_openfda_event_counts(conn))
        counts["openfda_drug_shortages"] = _upsert_openfda_drug_shortages(conn)
        counts["openfda_drug_recalls"] = _upsert_openfda_drug_recalls(conn)
        counts.update(_upsert_openfda_ndc(conn))
        counts.update(_upsert_rxnorm(conn))
        counts["fda_srlc_labeling_changes"] = _upsert_fda_srlc(conn)
        counts.update(_upsert_nci_drug_dictionary(conn))
        counts["nci_drug_information_summaries"] = _upsert_nci_drug_info(conn)
        counts["opdp_enforcement_actions"] = _upsert_opdp_actions(conn)
        counts["opdp_letter_documents"] = _upsert_opdp_letter_documents(conn)
        counts.update(_upsert_orange_book(conn))
        counts.update(_upsert_drugs_fda(conn))
        counts["purple_book_products"] = _upsert_purple_book(conn)
        counts["fda_oncology_approvals"] = _upsert_fda_oncology_approvals(conn)
        counts["ema_medicines"] = _upsert_ema_medicines(conn)
        counts["ema_medicine_documents"] = _upsert_ema_documents(conn)
        counts.update(_upsert_sec_edgar(conn))
        counts["sec_filing_brand_mentions"] = _upsert_sec_brand_mentions(conn)
        conn.execute(
            """
            INSERT INTO pharma_intel_run
                (run_at, sources, companies, therapy_areas, oncology_brands, oncology_sales_companies, award_mentions)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                _now(),
                counts["sources"],
                counts["companies"],
                counts["therapy_areas"],
                counts["oncology_brands"],
                counts["oncology_sales_companies"],
                counts["award_mentions"],
            ),
        )
        conn.commit()
        return counts
    finally:
        conn.close()


if __name__ == "__main__":
    for key, value in build().items():
        print(f"{key}: {value}")



