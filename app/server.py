"""FastAPI backend for the Omni OS campaign-planning agent.

Serves the agentic three-pane front-end plus:
  - project CRUD (left rail)                    /api/projects ...
  - conversational slot-filling (center chat)   /api/chat
  - multi-agent research run as SSE (right rail) /api/run-stream
The original single-shot endpoints are kept for backward compatibility / scripting.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
import threading
import time

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

APP_DIR = pathlib.Path(__file__).resolve().parent
BASE_DIR = APP_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from strategy.engine import generate_strategy, list_persona_options, list_stage_options, market_landscape  # noqa: E402
from strategy.positioning import build_positioning_statement  # noqa: E402
from strategy.kpi import build_kpi_framework  # noqa: E402
from strategy.lifecycle import list_lifecycle_options  # noqa: E402
from strategy.autorun import run_full_analysis  # noqa: E402
from competitive.swot import build_swot  # noqa: E402
from strategy import projects as pstore  # noqa: E402
from strategy import brief_summary  # noqa: E402  (presentational â‰¤20-word brief-field summaries)
from strategy.conversation import (new_state, opening_message, interpret_message, llm_enabled,  # noqa: E402
                                   get_llm_status, ask_clarify_group, clarify_payload,
                                   extract_brief_from_text)
from strategy import orchestrator  # noqa: E402
from strategy import studio_run  # noqa: E402  (Sequential Plan Studio: section-by-section run, SSE v2)
from strategy import decision_spine  # noqa: E402  (spine registry + decision dependency graph)
from strategy.orchestrator import run_agents  # noqa: E402
from strategy import open_questions as open_questions_mod  # noqa: E402  (phase-gated reveal)
from strategy.document_intake import extract_text  # noqa: E402
from strategy import dashboard as dashboard_mod  # noqa: E402
from strategy import feed as feed_mod  # noqa: E402
from strategy import db  # noqa: E402  (KB is always local SQLite via LOCAL_ONLY_STORES; other stores still dual-dialect)
from strategy import campaign_store  # noqa: E402
from strategy import brand_memory  # noqa: E402
from strategy import blob_store  # noqa: E402  (serves real label images to the Claims Library)
from strategy import bootstrap  # noqa: E402  (first-boot seeding of an empty data disk)
from strategy import personas as personas_mod  # noqa: E402  (synthetic persona layer)
from strategy import persona_review as persona_review_mod  # noqa: E402
from strategy import plan_export  # noqa: E402  (Word/PDF export of the composed plan)
from strategy import plan_pdf  # noqa: E402  (pixel-faithful PDF via headless Chromium)
from strategy import sfmc_export  # noqa: E402  (Salesforce Marketing Cloud Journey Builder export bundle)
from strategy import hcp_360  # noqa: E402  (synthetic HCP 360: demographics/affinity/TRx/writer status)
from strategy import reporting_insights  # noqa: E402  (Reporting tab: KPI/funnel/demographic/tagging cards)
from strategy import tab_chat  # noqa: E402  (per-workspace-tab agent chat, incl. diagram-editing)
from strategy import orchestration_tasks  # noqa: E402  (Stage 2 setup-task checklist, derived from ctx)
from strategy import orchestration_schedule  # noqa: E402  (Engagement Orchestration timeline/critical-path/ROI)
from strategy import orchestration_connectors  # noqa: E402  (downstream connector abstraction + idempotent push)
from strategy import orchestration_store  # noqa: E402  (external bindings + stub downstream store)
from strategy import orchestration_sync  # noqa: E402  (two-way sync: inbound reconcile + conflict rules)
from strategy import orchestration_nudge  # noqa: E402  (Nudge agent: notify + auto-escalate)
from strategy import orchestration_gates  # noqa: E402  (Veeva/SFMC read/gate context: AFU expiry, send state)
from strategy import campaign_artifacts  # noqa: E402  (Campaign Strategy + Brief â€” the planning stage's two linked artifacts)
from strategy import brief_document  # noqa: E402  (the Campaign Brief as export markdown, for the Word/PDF download)
from strategy import campaign_ops  # noqa: E402  (Stage 3 on-demand campaign-flow (re)generation)
from strategy import process_knowledge  # noqa: E402  (Cognee-backed SME process grounding)
from strategy import cognee_feedback  # noqa: E402  (human feedback overlay for Cognee grounding)
from strategy.paths import data_path  # noqa: E402
from strategy.planning_v2 import pipeline as planning_v2_pipeline  # noqa: E402  (v2 Strategic-to-Tactical Planning Engine)
from strategy import prompt_library  # noqa: E402  (read-only catalog of the app's LLM system prompts, for the Prompt Library tab)

app = FastAPI(title="Omni OS Brand Engagement Planning Agent")


@app.on_event("startup")
def _seed_on_boot() -> None:
    """Seed an empty DATA_DIR (fresh persistent disk) with the committed KB + content
    library. Idempotent and non-blocking; a persistent disk makes this run only once."""
    try:
        print(f"[startup] bootstrap: {bootstrap.run(background=True)}")
    except Exception as e:  # noqa: BLE001 -- startup must never fail on seeding
        print(f"[startup] bootstrap skipped ({e})")


def _msg(role: str, text: str, extra: dict | None = None) -> dict:
    m = {"role": role, "text": text, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if extra:
        m.update(extra)
    return m


def _safe_filename(name: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9]+", "-", (name or "brand-engagement-plan").lower()).strip("-") or "brand-engagement-plan"


# Sections the Artefacts page can request independently so the (slow, ~40 COUNT
# queries) warehouse summary can be fetched in parallel and rendered progressively
# instead of blocking the whole page on one big call.
_PHARMA_INTEL_SECTIONS = ("totals", "mix", "brands", "sources")


def _pharma_intel_empty(section: str) -> dict:
    empty = {
        "available": False,
        "totals": {},
        "source_counts": [],
        "evidence_mix": [],
        "top_brands": [],
        "message_mix": [],
    }
    if section == "all":
        return empty
    return {"available": False, **{k: v for k, v in empty.items() if k != "available"}}


def _pharma_intel_summary(section: str = "all") -> dict:
    """Warehouse summary for the Artefacts page, backed by data/omni_kb.db.

    ``section`` restricts the work to one slice so the frontend can fan the
    query out into parallel, progressively-rendered requests:
      - ``totals``  -> the stat-tile counts
      - ``mix``     -> evidence_mix + message_mix bar lists
      - ``brands``  -> top-brand coverage table
      - ``sources`` -> indexed source-document bar list
      - ``all``     -> everything (backwards-compatible default)
    """
    want_totals = section in ("all", "totals")
    want_mix = section in ("all", "mix")
    want_brands = section in ("all", "brands")
    want_sources = section in ("all", "sources")

    conn = db.kb_connect()  # always local SQLite (LOCAL_ONLY_STORES), None if the KB file is missing/unseeded
    if conn is None:
        return _pharma_intel_empty(section)
    try:
        def scalar(sql: str) -> int:
            try:
                return int(conn.execute(sql).fetchone()[0] or 0)
            except Exception:
                return 0

        result: dict = {"available": True}

        if want_totals:
            result["totals"] = _pharma_intel_totals(conn, scalar)
        if want_sources:
            result["source_counts"] = _pharma_intel_source_counts(conn)
        if want_mix:
            result["evidence_mix"] = _pharma_intel_evidence_mix(scalar)
            result["message_mix"] = _pharma_intel_message_mix(conn)
        if want_brands:
            result["top_brands"] = _pharma_intel_top_brands(conn)
        return result
    finally:
        conn.close()


def _pharma_intel_totals(conn, scalar) -> dict:
    raw_dir = BASE_DIR / "data" / "raw"
    raw_file_count = sum(1 for path in raw_dir.rglob("*") if path.is_file()) if raw_dir.exists() else 0
    return {
        "documents": scalar("SELECT COUNT(*) FROM documents"),
        "raw_files": raw_file_count,
        "sources": scalar("SELECT COUNT(*) FROM pharma_source"),
        "companies": scalar("SELECT COUNT(*) FROM pharma_company"),
        "oncology_brands": scalar("SELECT COUNT(*) FROM oncology_brand_seed"),
        "award_mentions": scalar("SELECT COUNT(*) FROM campaign_award_mention"),
        "message_evidence": scalar("SELECT COUNT(*) FROM v_oncology_message_campaign_evidence"),
        "asco_abstracts": scalar("SELECT COUNT(*) FROM asco_abstract"),
        "clinical_trial_locations": scalar("SELECT COUNT(*) FROM v_oncology_clinical_trial_locations"),
        "seer_cancer_stats": scalar("SELECT COUNT(*) FROM seer_cancer_stat"),
        "opdp_letters": scalar("SELECT COUNT(*) FROM opdp_letter_document"),
        "open_payments": scalar("SELECT COUNT(*) FROM cms_open_payment_general"),
        "adverse_event_reactions": scalar("SELECT COUNT(*) FROM openfda_event_reaction_count"),
        "drug_shortages": scalar("SELECT COUNT(*) FROM openfda_drug_shortage WHERE is_oncology_priority=1"),
        "drug_recalls": scalar("SELECT COUNT(*) FROM openfda_drug_recall"),
        "ndc_products": scalar("SELECT COUNT(*) FROM openfda_ndc_product"),
        "ndc_packages": scalar("SELECT COUNT(*) FROM openfda_ndc_package"),
        "rxnorm_concepts": scalar("SELECT COUNT(*) FROM rxnorm_concept"),
        "rxnorm_related_concepts": scalar("SELECT COUNT(*) FROM rxnorm_related_concept"),
        "safety_labeling_changes": scalar("SELECT COUNT(*) FROM fda_srlc_labeling_change"),
        "nci_drug_dictionary_entries": scalar("SELECT COUNT(*) FROM nci_drug_dictionary_entry"),
        "nci_drug_dictionary_aliases": scalar("SELECT COUNT(*) FROM nci_drug_dictionary_alias"),
        "nci_drug_info_summaries": scalar("SELECT COUNT(*) FROM nci_drug_information_summary"),
    }


def _pharma_intel_source_counts(conn) -> list:
    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT source, COUNT(*) AS count
            FROM documents
            GROUP BY source
            ORDER BY count DESC, source
            LIMIT 16
            """
        )
    ]


def _pharma_intel_evidence_mix(scalar) -> list:
    return [
            {"label": "Official messages", "count": scalar("SELECT COUNT(*) FROM brand_message")},
            {"label": "FDA label sections", "count": scalar("SELECT COUNT(*) FROM regulatory_label_message WHERE is_oncology_priority=1")},
            {"label": "DailyMed SPLs", "count": scalar("SELECT COUNT(*) FROM v_dailymed_oncology_priority")},
            {"label": "Clinical trials", "count": scalar("SELECT COUNT(*) FROM v_oncology_clinical_trials")},
            {"label": "Clinical trial sites", "count": scalar("SELECT COUNT(*) FROM v_oncology_clinical_trial_locations")},
            {"label": "PubMed articles", "count": scalar("SELECT COUNT(*) FROM v_oncology_pubmed_articles")},
            {"label": "ASCO abstracts", "count": scalar("SELECT COUNT(*) FROM v_asco_oncology_abstracts")},
            {"label": "SEER cancer stats", "count": scalar("SELECT COUNT(*) FROM v_seer_oncology_market_context")},
            {"label": "Award rows", "count": scalar("SELECT COUNT(*) FROM v_oncology_award_mentions")},
            {"label": "OPDP letters", "count": scalar("SELECT COUNT(*) FROM v_opdp_oncology_letter_documents")},
            {"label": "SEC mentions", "count": scalar("SELECT COUNT(*) FROM v_sec_oncology_brand_mentions")},
            {"label": "Open Payments", "count": scalar("SELECT COUNT(*) FROM cms_open_payment_general")},
            {"label": "FAERS reactions", "count": scalar("SELECT COUNT(*) FROM openfda_event_reaction_count")},
            {"label": "Drug shortages", "count": scalar("SELECT COUNT(*) FROM v_openfda_oncology_drug_shortages")},
            {"label": "Drug recalls", "count": scalar("SELECT COUNT(*) FROM v_openfda_oncology_drug_recalls")},
            {"label": "NDC products", "count": scalar("SELECT COUNT(*) FROM v_openfda_oncology_ndc_products")},
            {"label": "NDC packages", "count": scalar("SELECT COUNT(*) FROM v_openfda_oncology_ndc_packages")},
            {"label": "RxNorm concepts", "count": scalar("SELECT COUNT(*) FROM v_rxnorm_oncology_concepts")},
            {"label": "RxNorm related", "count": scalar("SELECT COUNT(*) FROM v_rxnorm_oncology_related_concepts")},
            {"label": "Safety label changes", "count": scalar("SELECT COUNT(*) FROM v_fda_srlc_oncology_labeling_changes")},
            {"label": "NCI drug definitions", "count": scalar("SELECT COUNT(*) FROM v_nci_oncology_drug_dictionary")},
            {"label": "NCI drug summaries", "count": scalar("SELECT COUNT(*) FROM v_nci_oncology_drug_information_summaries")},
    ]


def _pharma_intel_message_mix(conn) -> list:
    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT evidence_type AS label, COUNT(*) AS count
            FROM v_oncology_message_campaign_evidence
            GROUP BY evidence_type
            ORDER BY count DESC, evidence_type
            """
        )
    ]


def _pharma_intel_top_brands(conn) -> list:
    try:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT brand, total_evidence_count, official_brand_message_count, label_message_count,
                       dailymed_label_count, clinical_trial_count, pubmed_article_count,
                       asco_abstract_count, award_mention_count, sec_annual_filing_mention_count,
                       open_payment_count, adverse_event_reaction_count, drug_shortage_count, drug_recall_count, ndc_product_count,
                       rxnorm_concept_count, srlc_labeling_change_count, nci_drug_dictionary_count, nci_drug_info_summary_count
                FROM v_oncology_brand_evidence_summary
                ORDER BY total_evidence_count DESC, brand
                LIMIT 12
                """
            )
        ]
    except Exception:
        return [
            {**dict(row), "open_payment_count": 0, "adverse_event_reaction_count": 0, "drug_shortage_count": 0, "drug_recall_count": 0, "ndc_product_count": 0, "rxnorm_concept_count": 0, "srlc_labeling_change_count": 0, "nci_drug_dictionary_count": 0, "nci_drug_info_summary_count": 0}
            for row in conn.execute(
                """
                SELECT brand, total_evidence_count, official_brand_message_count, label_message_count,
                       dailymed_label_count, clinical_trial_count, pubmed_article_count,
                       asco_abstract_count, award_mention_count, sec_annual_filing_mention_count
                FROM v_oncology_brand_evidence_summary
                ORDER BY total_evidence_count DESC, brand
                LIMIT 12
                """
            )
        ]


def _read_kb_blob(blob_path: str | None, max_chars: int = 12000) -> str:
    if not blob_path:
        return ""
    try:
        rel = pathlib.Path(blob_path)
        if rel.parts and rel.parts[0] == "data":
            rel = pathlib.Path(*rel.parts[1:])
        path = data_path(*rel.parts).resolve()
        path.relative_to(data_path().resolve())
        if not path.is_file():
            return ""
        raw = path.read_bytes()[: max_chars * 4]
        text = raw.decode("utf-8", errors="replace")
        return text[:max_chars]
    except Exception:
        return ""


def _artifact_item(row: sqlite3.Row, *, content_fields: list[str] | None = None) -> dict:
    data = dict(row)
    content = ""
    for field in content_fields or []:
        value = data.get(field)
        if value:
            content = str(value)
            break
    if not content:
        content = _read_kb_blob(data.get("blob_path") or data.get("pdf_blob_path"))
    meta_keys = [
        "brand",
        "company",
        "manufacturer",
        "source",
        "doc_type",
        "audience",
        "label_section",
        "therapy_area",
        "conference",
        "meeting_year",
        "journal",
        "publication_year",
        "program",
        "year",
        "category",
        "tier",
        "form",
        "filing_date",
        "cancer_site",
        "matched_brand",
        "recipient_name",
        "recipient_state",
        "recipient_specialty",
        "payment_manufacturer",
        "nature_of_payment",
        "associated_product",
        "program_year",
        "reaction_term",
        "reaction_count",
        "serious_label",
        "report_count",
        "api_last_updated",
        "status",
        "availability",
        "shortage_reason",
        "generic_name",
        "brand_names",
        "company_name",
        "query_term",
        "term_type",
        "recall_number",
        "classification",
        "status",
        "facility",
        "city",
        "state",
        "country",
        "location_count",
        "countries",
        "us_states",
        "product_ndc",
        "package_ndc",
        "brand_name",
        "generic_name",
        "labeler_name",
        "marketing_category",
        "dosage_form",
        "route",
        "application_number",
        "application_type",
        "supplement_date",
        "database_updated",
        "active_ingredient",
        "drug_name",
        "rxcui",
        "tty",
        "term_type",
        "related_concept_count",
        "historical_ndc_count",
        "related_rxcui",
        "related_tty",
        "recalling_firm",
        "report_date",
        "recall_initiation_date",
        "srlc_change_id",
        "term_id",
        "nci_concept_id",
        "nci_concept_name",
        "term_name_type",
        "alias_count",
        "us_brand_names",
        "fda_approved",
        "posted_date",
        "updated_date",
        "link_count",
    ]
    return {
        "id": str(data.get("id") or data.get("message_id") or data.get("label_message_id") or data.get("abstract_number") or data.get("nct_id") or data.get("pmid") or data.get("mention_id") or data.get("stat_id") or data.get("letter_id") or data.get("sec_brand_mention_id") or data.get("record_id") or data.get("external_id") or ""),
        "title": data.get("title") or data.get("presentation_title") or data.get("brief_title") or data.get("campaign") or data.get("product_issue") or data.get("recipient_name") or data.get("cancer_site") or data.get("brand") or data.get("source") or "Untitled artifact",
        "subtitle": data.get("source_url") or data.get("url") or data.get("filing_url") or "",
        "url": data.get("source_url") or data.get("url") or data.get("filing_url") or "",
        "content": str(content or "")[:12000],
        "metadata": {key: data.get(key) for key in meta_keys if data.get(key) not in (None, "")},
    }


def _pharma_intel_artifacts(kind: str, value: str = "", limit: int = 20) -> dict:
    conn = db.kb_connect()  # always local SQLite (LOCAL_ONLY_STORES), None if the KB file is missing/unseeded
    if conn is None:
        raise HTTPException(404, "knowledge base unavailable")
    limit = max(1, min(limit, 40))
    try:
        params: tuple = (limit,)
        title = value or kind.replace("_", " ").title()
        content_fields = ["message_text", "abstract_body", "abstract", "context_snippet", "text_excerpt", "raw_line", "contextual_information"]
        sql = """
            SELECT d.id, d.source, d.external_id, d.search_term, d.title, d.doc_type, d.url, d.blob_path, d.fetched_at
            FROM documents d
            ORDER BY d.fetched_at DESC, d.id DESC
            LIMIT ?
        """

        if kind == "source":
            if not value:
                raise HTTPException(400, "source drill-down requires a value")
            title = value
            params = (value, limit)
            sql = """
                SELECT d.id, d.source, d.external_id, d.search_term, d.title, d.doc_type, d.url, d.blob_path, d.fetched_at
                FROM documents d
                WHERE d.source=?
                ORDER BY d.fetched_at DESC, d.id DESC
                LIMIT ?
            """
        elif kind == "brand":
            if not value:
                raise HTTPException(400, "brand drill-down requires a value")
            title = value
            params = (value, value, value, value, limit)
            sql = """
                SELECT d.id, d.source, d.external_id, d.search_term, d.title, d.doc_type, d.url, d.blob_path, d.fetched_at
                FROM documents d
                WHERE lower(d.search_term)=lower(?)
                   OR lower(d.title)=lower(?)
                   OR EXISTS (SELECT 1 FROM brand_message bm WHERE bm.source_document_id=d.id AND lower(bm.brand)=lower(?))
                   OR EXISTS (SELECT 1 FROM regulatory_label_message lm WHERE lm.source_document_id=d.id AND lower(lm.brand)=lower(?))
                ORDER BY d.fetched_at DESC, d.id DESC
                LIMIT ?
            """
        elif kind in ("documents", "sources"):
            title = "Indexed source documents"
        elif kind == "official_messages":
            title = "Official messages"
            sql = """
                SELECT bm.*, d.title, d.blob_path, d.url
                FROM brand_message bm
                JOIN documents d ON d.id=bm.source_document_id
                ORDER BY bm.updated_at DESC, bm.brand, bm.message_id
                LIMIT ?
            """
        elif kind == "fda_label_sections":
            title = "FDA label sections"
            sql = """
                SELECT lm.*, d.title, d.blob_path, d.url
                FROM regulatory_label_message lm
                JOIN documents d ON d.id=lm.source_document_id
                WHERE lm.is_oncology_priority=1
                ORDER BY lm.updated_at DESC, lm.brand, lm.label_section
                LIMIT ?
            """
        elif kind == "dailymed_spls":
            title = "DailyMed SPLs"
            sql = """
                SELECT dl.*, d.blob_path, d.url
                FROM dailymed_label dl
                JOIN documents d ON d.id=dl.source_document_id
                WHERE dl.is_oncology_priority=1
                ORDER BY dl.published_date DESC, dl.brand
                LIMIT ?
            """
        elif kind == "clinical_trials":
            title = "Clinical trials"
            sql = """
                SELECT t.*, d.title, d.blob_path, d.url
                FROM clinical_trial t
                JOIN documents d ON d.id=t.source_document_id
                WHERE t.is_oncology_priority=1
                ORDER BY t.last_update_post_date DESC, t.nct_id
                LIMIT ?
            """
        elif kind == "clinical_trial_locations":
            title = "Clinical trial sites"
            content_fields = ["text_excerpt"]
            sql = """
                SELECT l.*, t.brief_title AS title, t.source_url AS url, d.blob_path,
                       ('Trial: ' || IFNULL(t.brief_title, '') || char(10) ||
                        'NCT ID: ' || IFNULL(t.nct_id, '') || char(10) ||
                        'Facility: ' || IFNULL(l.facility, '') || char(10) ||
                        'Location: ' || IFNULL(l.city, '') ||
                            CASE WHEN IFNULL(l.state, '') <> '' THEN ', ' || l.state ELSE '' END ||
                            CASE WHEN IFNULL(l.country, '') <> '' THEN ', ' || l.country ELSE '' END || char(10) ||
                        'Site status: ' || IFNULL(l.status, '') || char(10) ||
                        'Trial status: ' || IFNULL(t.overall_status, '') || char(10) ||
                        'Sponsor: ' || IFNULL(t.lead_sponsor, '')) AS text_excerpt
                FROM clinical_trial_location l
                JOIN clinical_trial t ON t.nct_id=l.nct_id
                JOIN documents d ON d.id=t.source_document_id
                WHERE t.is_oncology_priority=1
                ORDER BY l.country, l.state, l.city, l.facility, t.nct_id
                LIMIT ?
            """
        elif kind == "pubmed_articles":
            title = "PubMed articles"
            sql = """
                SELECT a.*, d.blob_path, d.url
                FROM pubmed_article a
                LEFT JOIN documents d ON d.id=a.source_document_id
                WHERE a.is_oncology_priority=1
                ORDER BY a.publication_year DESC, a.pmid DESC
                LIMIT ?
            """
        elif kind == "asco_abstracts":
            title = "ASCO abstracts"
            sql = """
                SELECT aa.*, d.title, d.blob_path, d.url
                FROM asco_abstract aa
                JOIN documents d ON d.id=aa.source_document_id
                WHERE aa.is_oncology_priority=1
                ORDER BY aa.presentation_start_date DESC, aa.abstract_number
                LIMIT ?
            """
        elif kind == "seer_cancer_stats":
            title = "SEER cancer stats"
            sql = """
                SELECT s.*, d.title, d.blob_path, d.url
                FROM seer_cancer_stat s
                JOIN documents d ON d.id=s.source_document_id
                ORDER BY s.estimated_new_cases_2026 DESC, s.cancer_site
                LIMIT ?
            """
        elif kind == "award_rows":
            title = "Award rows"
            sql = """
                SELECT cam.*, d.title, d.blob_path, d.url
                FROM campaign_award_mention cam
                JOIN documents d ON d.id=cam.source_document_id
                WHERE cam.therapy_area='oncology'
                ORDER BY cam.year DESC, cam.program, cam.category
                LIMIT ?
            """
        elif kind == "opdp_letters":
            title = "OPDP letters"
            sql = """
                SELECT old.*, d.title, d.blob_path, d.url
                FROM opdp_letter_document old
                JOIN documents d ON d.id=old.source_document_id
                WHERE old.is_oncology_priority=1
                ORDER BY old.issued_date DESC, old.company
                LIMIT ?
            """
        elif kind == "sec_mentions":
            title = "SEC mentions"
            sql = """
                SELECT sfm.*, d.title, d.blob_path, d.url
                FROM sec_filing_brand_mention sfm
                JOIN documents d ON d.id=sfm.source_document_id
                ORDER BY sfm.filing_date DESC, sfm.brand, sfm.mention_count DESC
                LIMIT ?
            """
        elif kind == "open_payments":
            title = "Open Payments"
            sql = """
                SELECT opg.*, d.title, d.blob_path, d.url
                FROM cms_open_payment_general opg
                JOIN documents d ON d.id=opg.source_document_id
                ORDER BY opg.total_amount_usd DESC, opg.matched_brand, opg.record_id
                LIMIT ?
            """
        elif kind == "faers_reactions":
            title = "FAERS reactions"
            sql = """
                SELECT er.*, er.reaction_term AS title, d.blob_path, d.url
                FROM openfda_event_reaction_count er
                JOIN documents d ON d.id=er.source_document_id
                ORDER BY er.reaction_count DESC, er.brand, er.reaction_term
                LIMIT ?
            """
        elif kind == "drug_shortages":
            title = "Drug shortages"
            sql = """
                SELECT ds.*, ds.generic_name AS title, d.blob_path, d.url
                FROM openfda_drug_shortage ds
                JOIN documents d ON d.id=ds.source_document_id
                WHERE ds.is_oncology_priority=1
                ORDER BY ds.status, ds.generic_name, ds.update_date DESC
                LIMIT ?
            """
        elif kind == "drug_recalls":
            title = "Drug recalls"
            content_fields = ["text_excerpt", "product_description", "reason_for_recall", "distribution_pattern", "code_info"]
            sql = """
                SELECT dr.*, dr.product_description AS title,
                       ('Product: ' || IFNULL(dr.product_description, '') || char(10) ||
                        'Reason: ' || IFNULL(dr.reason_for_recall, '') || char(10) ||
                        'Distribution: ' || IFNULL(dr.distribution_pattern, '') || char(10) ||
                        'Code info: ' || IFNULL(dr.code_info, '') || char(10) ||
                        'Firm: ' || IFNULL(dr.recalling_firm, '') || char(10) ||
                        'Recall number: ' || IFNULL(dr.recall_number, '') || char(10) ||
                        'Classification: ' || IFNULL(dr.classification, '') || char(10) ||
                        'Status: ' || IFNULL(dr.status, '') || char(10) ||
                        'Initiated: ' || IFNULL(dr.recall_initiation_date, '') || char(10) ||
                        'Reported: ' || IFNULL(dr.report_date, '')) AS text_excerpt,
                       d.blob_path, d.url
                FROM openfda_drug_recall dr
                JOIN documents d ON d.id=dr.source_document_id
                ORDER BY dr.report_date DESC, dr.matched_brand, dr.classification, dr.recall_number
                LIMIT ?
            """
        elif kind == "ndc_products":
            title = "NDC products"
            content_fields = ["text_excerpt"]
            sql = """
                SELECT np.*, COALESCE(NULLIF(np.brand_name, ''), NULLIF(np.product_ndc, ''), NULLIF(np.generic_name, ''), np.matched_brand) AS title,
                       ('Brand: ' || IFNULL(np.brand_name, '') || char(10) ||
                        'Generic: ' || IFNULL(np.generic_name, '') || char(10) ||
                        'Product NDC: ' || IFNULL(np.product_ndc, '') || char(10) ||
                        'Labeler: ' || IFNULL(np.labeler_name, '') || char(10) ||
                        'Marketing category: ' || IFNULL(np.marketing_category, '') || char(10) ||
                        'Application: ' || IFNULL(np.application_number, '') || char(10) ||
                        'Dosage form: ' || IFNULL(np.dosage_form, '') || char(10) ||
                        'Route: ' || IFNULL(np.route, '') || char(10) ||
                        'Active ingredients: ' || IFNULL(np.active_ingredients, '') || char(10) ||
                        'Marketing start: ' || IFNULL(np.marketing_start_date, '') || char(10) ||
                        'Listing expiration: ' || IFNULL(np.listing_expiration_date, '')) AS text_excerpt,
                       d.blob_path, d.url
                FROM openfda_ndc_product np
                JOIN documents d ON d.id=np.source_document_id
                ORDER BY np.matched_brand, np.brand_name, np.product_ndc
                LIMIT ?
            """
        elif kind == "ndc_packages":
            title = "NDC packages"
            content_fields = ["text_excerpt"]
            sql = """
                SELECT pkg.*, p.brand_name, p.generic_name, p.labeler_name, p.marketing_category,
                       p.dosage_form, p.route, pkg.package_ndc AS title,
                       ('Brand: ' || IFNULL(p.brand_name, '') || char(10) ||
                        'Generic: ' || IFNULL(p.generic_name, '') || char(10) ||
                        'Product NDC: ' || IFNULL(pkg.product_ndc, '') || char(10) ||
                        'Package NDC: ' || IFNULL(pkg.package_ndc, '') || char(10) ||
                        'Package: ' || IFNULL(pkg.package_description, '') || char(10) ||
                        'Labeler: ' || IFNULL(p.labeler_name, '') || char(10) ||
                        'Marketing category: ' || IFNULL(p.marketing_category, '') || char(10) ||
                        'Dosage form: ' || IFNULL(p.dosage_form, '') || char(10) ||
                        'Route: ' || IFNULL(p.route, '') || char(10) ||
                        'Package marketing start: ' || IFNULL(pkg.marketing_start_date, '')) AS text_excerpt,
                       d.blob_path, d.url
                FROM openfda_ndc_package pkg
                JOIN openfda_ndc_product p ON p.ndc_product_id=pkg.ndc_product_id
                JOIN documents d ON d.id=pkg.source_document_id
                ORDER BY p.matched_brand, p.brand_name, pkg.package_ndc
                LIMIT ?
            """
        elif kind == "rxnorm_concepts":
            title = "RxNorm concepts"
            content_fields = ["text_excerpt"]
            sql = """
                SELECT rc.*, COALESCE(NULLIF(rc.name, ''), rc.rxcui) AS title,
                       ('Matched brand: ' || IFNULL(rc.matched_brand, '') || char(10) ||
                        'Query term: ' || IFNULL(rc.query_term, '') || char(10) ||
                        'RxCUI: ' || IFNULL(rc.rxcui, '') || char(10) ||
                        'Name: ' || IFNULL(rc.name, '') || char(10) ||
                        'Term type: ' || IFNULL(rc.tty, '') || char(10) ||
                        'Synonym: ' || IFNULL(rc.synonym, '') || char(10) ||
                        'Related concepts: ' || IFNULL(rc.related_concept_count, 0) || char(10) ||
                        'Historical NDC count: ' || IFNULL(rc.historical_ndc_count, 0)) AS text_excerpt,
                       d.blob_path, d.url
                FROM rxnorm_concept rc
                JOIN documents d ON d.id=rc.source_document_id
                ORDER BY rc.matched_brand, rc.term_type, rc.name, rc.rxcui
                LIMIT ?
            """
        elif kind == "rxnorm_related":
            title = "RxNorm related concepts"
            content_fields = ["text_excerpt"]
            sql = """
                SELECT rr.*, rr.related_name AS title,
                       ('Matched brand: ' || IFNULL(rr.matched_brand, '') || char(10) ||
                        'Source RxCUI: ' || IFNULL(rr.source_rxcui, '') || char(10) ||
                        'Related RxCUI: ' || IFNULL(rr.related_rxcui, '') || char(10) ||
                        'Related name: ' || IFNULL(rr.related_name, '') || char(10) ||
                        'Related term type: ' || IFNULL(rr.related_tty, '') || char(10) ||
                        'Synonym: ' || IFNULL(rr.related_synonym, '') || char(10) ||
                        'Suppress: ' || IFNULL(rr.suppress, '')) AS text_excerpt,
                       NULL AS blob_path, '' AS url
                FROM rxnorm_related_concept rr
                ORDER BY rr.matched_brand, rr.source_rxcui, rr.related_tty, rr.related_name
                LIMIT ?
            """
        elif kind == "safety_labeling_changes":
            title = "Safety-related labeling changes"
            content_fields = ["text_excerpt"]
            sql = """
                SELECT slc.*, COALESCE(NULLIF(slc.drug_name, ''), slc.matched_brand) AS title,
                       ('Matched brand: ' || IFNULL(slc.matched_brand, '') || char(10) ||
                        'Drug name: ' || IFNULL(slc.drug_name, '') || char(10) ||
                        'Active ingredient: ' || IFNULL(slc.active_ingredient, '') || char(10) ||
                        'Application: ' || IFNULL(slc.application_type, '') || ' ' || IFNULL(slc.application_number, '') || char(10) ||
                        'Supplement date: ' || IFNULL(slc.supplement_date, '') || char(10) ||
                        'Database updated: ' || IFNULL(slc.database_updated, '') || char(10) || char(10) ||
                        IFNULL(slc.text_excerpt, '')) AS text_excerpt,
                       d.blob_path, COALESCE(NULLIF(slc.detail_url, ''), d.url) AS url
                FROM fda_srlc_labeling_change slc
                JOIN documents d ON d.id=slc.source_document_id
                ORDER BY slc.supplement_date DESC, slc.database_updated DESC, slc.matched_brand, slc.drug_name
                LIMIT ?
            """
        elif kind == "nci_drug_dictionary":
            title = "NCI drug definitions"
            content_fields = ["definition_text"]
            sql = """
                SELECT nd.*, COALESCE(NULLIF(nd.nci_concept_name, ''), NULLIF(nd.name, ''), nd.query_term) AS title,
                       d.blob_path, COALESCE(NULLIF(nd.drug_info_summary_url, ''), d.url) AS url
                FROM nci_drug_dictionary_entry nd
                JOIN documents d ON d.id=nd.source_document_id
                ORDER BY nd.matched_brand, nd.term_type, nd.nci_concept_name, nd.term_id
                LIMIT ?
            """
        elif kind == "nci_drug_info":
            title = "NCI drug summaries"
            content_fields = ["use_in_cancer", "text_excerpt"]
            sql = """
                SELECT ni.*, COALESCE(NULLIF(ni.title, ''), ni.nci_concept_name) AS title,
                       d.blob_path, ni.source_url AS url
                FROM nci_drug_information_summary ni
                JOIN documents d ON d.id=ni.source_document_id
                ORDER BY ni.matched_brand, ni.nci_concept_name, ni.title
                LIMIT ?
            """
        elif kind == "message_evidence":
            title = "Message evidence"
            sql = """
                SELECT evidence_type AS source, brand, company, audience, subtype AS doc_type,
                       campaign_or_title AS title, message_text, source_url AS url
                FROM v_oncology_message_campaign_evidence
                ORDER BY evidence_type, brand, campaign_or_title
                LIMIT ?
            """
        elif kind.startswith("message:"):
            evidence_type = kind.split(":", 1)[1]
            title = evidence_type
            params = (evidence_type, limit)
            sql = """
                SELECT evidence_type AS source, brand, company, audience, subtype AS doc_type,
                       campaign_or_title AS title, message_text, source_url AS url
                FROM v_oncology_message_campaign_evidence
                WHERE evidence_type=?
                ORDER BY brand, campaign_or_title
                LIMIT ?
            """
        else:
            raise HTTPException(400, f"unknown artifact kind '{kind}'")

        rows = conn.execute(sql, params).fetchall()
        return {"kind": kind, "value": value, "title": title, "items": [_artifact_item(row, content_fields=content_fields) for row in rows]}
    finally:
        conn.close()


def _freeze_project_state(state: dict) -> None:
    """'Close updates': lock the plan against further automatic adjustment (persona apply /
    per-section clarify updates), and force-close any clarify Q&A still in progress -- every
    remaining group is treated as answered so it can never resurface, even on a future full
    rerun of the agents."""
    state["plan_frozen"] = True
    groups = state.get("open_questions") or []
    idx = state.get("clarify_idx", 0)
    if idx < len(groups):
        resolved = set(state.get("clarify_resolved_ids") or [])
        resolved.update(g["id"] for g in groups[idx:])
        state["clarify_resolved_ids"] = sorted(resolved)
    state["clarify_idx"] = len(groups)
    state["awaiting_clarify"] = None


@app.get("/api/home")
def api_home():
    """Landing-page payload: per-brand performance dashboard + the ticker feed."""
    return {"dashboard": dashboard_mod.brand_performance(), "feed": feed_mod.build_feed()}


@app.get("/api/prompt-library")
def api_prompt_library():
    """Read-only catalog of every LLM system prompt / agent 'skill' in the app, pulled live
    from the running code (see strategy/prompt_library.py) -- for the Prompt Library tab."""
    return {"prompts": prompt_library.list_prompts()}


# ------------------------------------------------------------------ #
# Claims Library: browse the governed content library + its real assets
# ------------------------------------------------------------------ #

@app.get("/api/library")
def api_library():
    """Index of every brand holding library content, with claim/asset/image counts."""
    return campaign_store.library_brands()


@app.get("/api/library/{brand}")
def api_library_brand(brand: str):
    """One brand's full library: claims (with substantiating references), reusable modules,
    real label images and the rest of the DAM assets."""
    detail = campaign_store.brand_library_detail(brand)
    if not detail.get("found"):
        raise HTTPException(404, f"no library content for brand '{brand}'")
    return detail


@app.get("/api/blob/{blob_key}")
def api_blob(blob_key: str):
    """Serve raw bytes from the content-addressed blob store with the right Content-Type,
    so the library can render the real label images (and download other assets).
    Blob keys are sha256 hex, so content is immutable -- cache it hard."""
    if not (len(blob_key) == 64 and all(c in "0123456789abcdef" for c in blob_key.lower())):
        raise HTTPException(400, "blob_key must be a sha256 hex digest")
    meta = campaign_store.blob_meta(blob_key)
    data = blob_store.get(blob_key)
    if data is None or meta is None:
        raise HTTPException(404, "blob not found")
    return Response(content=data, media_type=meta.get("mime_type") or "application/octet-stream",
                    headers={"Cache-Control": "public, max-age=31536000, immutable",
                             "Content-Disposition": f'inline; filename="{meta.get("original_name") or blob_key}"'})


# ------------------------------------------------------------------ #
# Synthetic persona layer: pressure-test a finished plan against the
# audiences it is trying to reach.
# ------------------------------------------------------------------ #

@app.get("/api/personas")
def api_personas(project_id: str = ""):
    """Personas ranked by relevance to a project's plan (its therapy area / specialty), so the
    picker can pre-select the natural reviewers. With no project it matches on nothing (all
    become 'others')."""
    therapy_area = indication = ""
    if project_id:
        proj = pstore.get_project(project_id)
        if proj:
            slots = proj["state"]["slots"]
            therapy_area = (proj.get("result") or {}).get("therapy_area") or slots.get("therapy_area", "")
            indication = slots.get("indication", "")
    return personas_mod.match_to_plan(therapy_area, indication)


@app.get("/api/personas/{persona_id}")
def api_persona_detail(persona_id: str):
    """Full persona record (demographics, prescribing, channels, decision drivers, voice) --
    powers the picker's 'info' card."""
    p = personas_mod.get(persona_id)
    if not p:
        raise HTTPException(404, f"no persona '{persona_id}'")
    return p


class PersonaReviewRequest(BaseModel):
    project_id: str
    persona_ids: list[str]
    use_llm: bool = True


@app.post("/api/persona-review")
def api_persona_review(req: PersonaReviewRequest):
    """Run the finished plan past each selected persona and return their honest, in-character
    feedback. Persists the reviews on the project so they survive a reload."""
    proj = pstore.get_project(req.project_id)
    if not proj:
        raise HTTPException(404, "project not found")
    result = proj.get("result")
    if not result:
        raise HTTPException(400, "no plan to review yet â€” generate the plan first")
    chosen = [p for p in (personas_mod.get(pid) for pid in req.persona_ids) if p]
    if not chosen:
        raise HTTPException(400, "no valid personas selected")
    reviews = persona_review_mod.review_many(chosen, result, use_llm=req.use_llm)
    state = proj["state"]
    state["persona_reviews"] = reviews
    pstore.save_project(req.project_id, state=state)
    return {"reviews": reviews}


class PersonaApplyRequest(BaseModel):
    project_id: str
    persona_ids: list[str] = []   # empty -> use every persona from the last review batch


@app.post("/api/persona-apply")
def api_persona_apply(req: PersonaApplyRequest):
    """Automatically rebalance the plan's channel mix toward what the selected personas
    actually respond to, and re-render the plan document. Reuses the exact same compose_plan
    call the original run made -- run-stream snapshots the run's full ctx (server-side only,
    never sent to the client) precisely so this can happen without re-running the agents."""
    proj = pstore.get_project(req.project_id)
    if not proj:
        raise HTTPException(404, "project not found")
    state = proj["state"]
    if state.get("plan_frozen"):
        raise HTTPException(400, "updates are closed for this plan -- it's locked in")
    ctx = state.get("_plan_ctx")
    if not ctx:
        raise HTTPException(400, "this plan was generated before persona adjustments were "
                                  "supported -- regenerate the plan to enable this")
    reviews = state.get("persona_reviews") or []
    ids = req.persona_ids or [r["persona_id"] for r in reviews]
    chosen = [p for p in (personas_mod.get(pid) for pid in ids) if p]
    if not chosen:
        raise HTTPException(400, "no valid personas to apply")

    current_mix = persona_review_mod._plan_mix(proj["result"])
    adj = persona_review_mod.suggest_rebalance(chosen, current_mix)
    total_budget = ctx.get("budget") or 0
    ctx["budget_allocation"] = {
        b: {"pct": pct, "amount": round(total_budget * pct / 100, 2) if total_budget else None}
        for b, pct in adj["new_mix"].items()
    }
    # Keep the strategy-layer mix in step: the Campaign Brief (campaign_artifacts.py)
    # projects channel & journey from ctx["strategy"]["channel_mix_pct"], not from
    # budget_allocation â€” without this the brief keeps showing the pre-rebalance mix.
    ctx.setdefault("strategy", {})["channel_mix_pct"] = adj["new_mix"]
    result, plan_md, plan_html = orchestrator.recompose_plan(ctx)

    log_entry = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "persona_ids": ids,
                 "persona_names": [p["name"] for p in chosen], "changes": adj["changes"]}
    state.setdefault("persona_adjustments", []).append(log_entry)
    state["_plan_ctx"] = ctx
    pstore.save_project(req.project_id, state=state, result=result, plan_markdown=plan_md, plan_html=plan_html)
    return {"changes": adj["changes"], "new_mix": adj["new_mix"], "plan_html": plan_html, "plan_markdown": plan_md}


@app.post("/api/projects/{pid}/close-updates")
def api_close_updates(pid: str):
    """Lock the plan against further automatic adjustment (persona apply / per-section
    clarify updates) and force-close any clarify Q&A still in progress. Same effect as
    typing 'close updates' in chat -- exposed as a button too."""
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    state = proj["state"]
    _freeze_project_state(state)
    # Reveal every remaining toolkit phase on lock-in so nothing stays gated.
    ctx = state.get("_plan_ctx")
    plan_html = plan_markdown = result_for_save = None
    if ctx:
        state["revealed_phases"] = list(open_questions_mod.PHASE_ORDER)
        result_for_save, plan_markdown, plan_html = orchestrator.recompose_plan(ctx)
    pstore.save_project(pid, state=state, result=result_for_save,
                        plan_markdown=plan_markdown, plan_html=plan_html)
    return {"ok": True, "plan_frozen": True, "plan_html": plan_html, "plan_markdown": plan_markdown}


# ------------------------------------------------------------------ #
# Agentic workspace: projects + chat + streaming run
# ------------------------------------------------------------------ #

class NewProjectRequest(BaseModel):
    name: str = "Untitled plan"


class ChatRequest(BaseModel):
    project_id: str
    message: str


@app.get("/api/projects")
def api_list_projects():
    return pstore.list_projects()


def _campaign_id_name(pid: str) -> str:
    """Default plan name: a short, unique, human-readable campaign ID derived from the
    project's UUID. Every plan gets one at creation; the user can rename it any time via
    PATCH /api/projects/{pid}/name. We no longer auto-name from brand + indication."""
    return f"CMP-{pid[:6].upper()}"


@app.post("/api/projects")
def api_create_project(req: NewProjectRequest):
    state = new_state()
    messages = [_msg("agent", opening_message())]
    proj = pstore.create_project(req.name, state, messages)
    # Stamp a unique campaign ID as the default name unless the caller supplied a real one.
    if req.name.strip() in ("", "Untitled plan", "New plan"):
        proj = pstore.save_project(proj["id"], name=_campaign_id_name(proj["id"]))
    return proj


@app.get("/api/projects/{pid}")
def api_get_project(pid: str):
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    # Presentational only: attach short keyword summaries of the long brief fields so the
    # BriefCard shows a gist instead of echoing whole paragraphs from the deck. The stored
    # slots are untouched, so grounding still reads the full captured text.
    brief_summary.attach((proj.get("state") or {}).get("slots"))
    return proj


@app.delete("/api/projects/{pid}")
def api_delete_project(pid: str):
    pstore.delete_project(pid)
    return {"ok": True}


class RenameProjectRequest(BaseModel):
    name: str


@app.patch("/api/projects/{pid}/name")
def api_rename_project(pid: str, req: RenameProjectRequest):
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "name cannot be empty")
    proj = pstore.save_project(pid, name=name)
    if not proj:
        raise HTTPException(404, "project not found")
    return proj


class PlanContentRequest(BaseModel):
    html: str
    markdown: str


@app.post("/api/projects/{pid}/plan-content")
def api_save_plan_content(pid: str, req: PlanContentRequest):
    """Persist a manual edit made in the plan panel (each heading/paragraph/list item/simple
    table cell is directly editable in the UI). The client derives `markdown` from the same
    edited DOM client-side, so Word/PDF exports reflect the edit too. Note: a later clarify
    auto-update or persona 'apply feedback' recomposes the plan from the run's snapshotted
    state and will overwrite a manual edit -- there's no merge between the two."""
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    if not req.html.strip():
        raise HTTPException(400, "empty plan content")
    pstore.save_project(pid, plan_markdown=req.markdown, plan_html=req.html)
    return {"ok": True}


class CampaignPlanRegenerateRequest(BaseModel):
    document: dict | None = None


@app.post("/api/projects/{pid}/regenerate-campaign-plan-layout")
def api_regenerate_campaign_plan_layout_alias(pid: str, req: CampaignPlanRegenerateRequest):
    """Stable alias for the Stage 3 full diagram redraw endpoint.

    Kept separate from /campaign-plan-layout/regenerate because older reload
    workers have been observed serving a route table without that nested path.
    """
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    return tab_chat.regenerate_operations(pid, document=req.document)


@app.patch("/api/projects/{pid}/campaign-plan-layout")
def api_save_campaign_plan_layout(pid: str, req: dict):
    """Persist the Stage 3 diagram as a native workflow-tool document (Section 3 schema:
    pages/nodes/edges/groups/layers) -- a full overwrite of whatever was saved before,
    not an overlay. The frontend's flow builder is the only writer; the shape is
    intentionally untyped here since the builder owns and versions its own schema."""
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    pstore.save_project(pid, campaign_plan_layout=req)
    return {"ok": True}


@app.post("/api/projects/{pid}/orchestration-tasks/generate")
def api_generate_orchestration_tasks(pid: str, req: dict | None = None):
    """Derive the Stage 2 setup-task checklist from what Stage 1 already computed (the
    campaign-ops touchpoint/entry-criteria/decision-logic/segmentation skeleton, the message
    flow, and the Tactical Plan Â§26-33) and persist it. Overwrites -- called only from an
    explicit user action (the chat kickoff card's 'Use the Stage 1 plan' / upload-and-build
    choice, or the 'Regenerate from plan' button), never automatically on tab open, so it
    never silently clobbers a user's edits. Optional body {"extra_context": str} folds a
    user-supplied note or uploaded-document text into extra tasks on top of the derivation."""
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    ctx = proj["state"].get("_plan_ctx")
    if not ctx:
        raise HTTPException(400, "Stage 1 hasn't produced a plan yet -- run it before generating setup tasks.")
    extra_context = (req or {}).get("extra_context")
    tasks = orchestration_tasks.generate_tasks(ctx, extra_context=extra_context)
    pstore.save_project(pid, orchestration_tasks=tasks)
    return {"tasks": tasks}


@app.patch("/api/projects/{pid}/orchestration-tasks")
def api_save_orchestration_tasks(pid: str, req: dict):
    """Persist Stage 2's setup-task checklist -- a full overwrite of whatever was saved
    before, not an overlay. The frontend is the only writer (check/add/delete edits); the
    shape is intentionally untyped here, same as campaign-plan-layout above."""
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    tasks = req.get("tasks")
    if not isinstance(tasks, list):
        raise HTTPException(400, "expected {'tasks': [...]}")
    pstore.save_project(pid, orchestration_tasks=tasks)
    return {"ok": True}


@app.post("/api/projects/{pid}/orchestration-schedule")
def api_orchestration_schedule(pid: str, req: dict | None = None):
    """Engagement Orchestration timeline. Backward-schedules the project's saved orchestration
    activities from a go-live date (body {"go_live": "YYYY-MM-DD"}) -- or forward from a start date
    ({"start_date": ...}) if none is given -- and returns per-activity planned_start/planned_due +
    slack + critical-path flags, phase bands, feasibility, and the elapsed time-saved-vs-baseline
    ROI figure (PRD 6.4). Read-only compute; nothing is persisted. Activities saved before the
    activity model existed are enriched on the fly for back-compat."""
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    tasks = orchestration_tasks.ensure_enriched(proj.get("orchestration_tasks") or [])
    if not tasks:
        raise HTTPException(400, "No orchestration activities yet -- generate them before scheduling.")
    body = req or {}
    return orchestration_schedule.build_schedule(
        tasks, go_live=body.get("go_live"), start_date=body.get("start_date"))


@app.post("/api/projects/{pid}/orchestration/push")
def api_orchestration_push(pid: str, req: dict | None = None):
    """Idempotently push the project's orchestration activities to their routed downstream systems
    (PRD 6.5). Body: {"teams": [...]?, "go_live": "YYYY-MM-DD"?}. When go_live is given the
    activities are scheduled first so planned dates ride along to the downstream item. Re-pushing
    is safe -- unchanged activities are skipped, changed ones updated, never duplicated. Routes to
    a connector without credentials are recorded as 'unconfigured', not failed."""
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    tasks = orchestration_tasks.ensure_enriched(proj.get("orchestration_tasks") or [])
    if not tasks:
        raise HTTPException(400, "No orchestration activities yet -- generate them before pushing.")
    body = req or {}
    go_live = body.get("go_live")
    if go_live:
        tasks = orchestration_schedule.build_schedule(tasks, go_live=go_live)["activities"]
    return orchestration_connectors.push_activities(pid, tasks, teams=body.get("teams"))


@app.get("/api/projects/{pid}/orchestration/bindings")
def api_orchestration_bindings(pid: str):
    """List the project's external bindings (internal activity <-> downstream record) + their sync
    state, for the downstream-systems panel."""
    if not pstore.get_project(pid):
        raise HTTPException(404, "project not found")
    return {"bindings": orchestration_store.list_bindings(pid),
            "routing": orchestration_connectors.load_routing()}


@app.post("/api/projects/{pid}/orchestration/sync")
def api_orchestration_sync(pid: str):
    """Two-way sync inbound pass (PRD 6.6): reconcile downstream changes back into the project's
    activities using the conflict policy (external wins for status/completion; internal wins for
    dates), with loop prevention. Persists any applied changes and returns applied/conflicts + a
    tail of the sync-event log."""
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    tasks = orchestration_tasks.ensure_enriched(proj.get("orchestration_tasks") or [])
    res = orchestration_sync.reconcile_inbound(pid, tasks)
    if res["changed"]:
        pstore.save_project(pid, orchestration_tasks=tasks)
    return res


@app.post("/api/projects/{pid}/orchestration/simulate-external")
def api_orchestration_simulate_external(pid: str, req: dict):
    """Demo/verify only: flip a routed stub item as if a teammate updated it downstream, so the
    next sync visibly folds it back in. Body: {"activity_id": str, "status": "Done"?}. No-op for
    real vendor systems."""
    if not pstore.get_project(pid):
        raise HTTPException(404, "project not found")
    aid = req.get("activity_id")
    if not aid:
        raise HTTPException(400, "expected {'activity_id': ...}")
    item = orchestration_sync.simulate_external_change(pid, aid, status=req.get("status", "Done"))
    if not item:
        raise HTTPException(404, "no stub binding for that activity -- push it first.")
    return {"ok": True, "item": item}


@app.post("/api/projects/{pid}/orchestration/nudge/run")
def api_orchestration_nudge_run(pid: str, req: dict | None = None):
    """Run the Nudge agent (PRD 6.8). Schedules the activities (body {"go_live": ...}? else 8 weeks
    out) so due/critical state is current, evaluates every not-done activity, and raises/refreshes
    notifications (notify + auto-escalate). Returns created/escalated + the open notifications."""
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    tasks = orchestration_tasks.ensure_enriched(proj.get("orchestration_tasks") or [])
    if not tasks:
        raise HTTPException(400, "No orchestration activities yet -- generate them first.")
    body = req or {}
    scheduled = orchestration_schedule.build_schedule(tasks, go_live=body.get("go_live"))["activities"]
    if body.get("apply_gate_context"):
        # fold Veeva AFU-expiry / SFMC send-state onto activities so the expiry path can fire.
        orchestration_gates.apply_context(pid, scheduled)
    return orchestration_nudge.run_nudges(pid, scheduled)


@app.get("/api/projects/{pid}/orchestration/notifications")
def api_orchestration_notifications(pid: str, include_acked: bool = True):
    """List the project's nudge notifications for the notification centre."""
    if not pstore.get_project(pid):
        raise HTTPException(404, "project not found")
    return {"notifications": orchestration_store.list_notifications(pid, include_acked=include_acked),
            "policy": orchestration_nudge.load_policy()}


@app.post("/api/projects/{pid}/orchestration/notifications/ack")
def api_orchestration_notification_ack(pid: str, req: dict):
    """Acknowledge a notification (stops it being re-raised). Body: {"dedupe_key": str}."""
    if not pstore.get_project(pid):
        raise HTTPException(404, "project not found")
    key = req.get("dedupe_key")
    if not key:
        raise HTTPException(400, "expected {'dedupe_key': ...}")
    return {"ok": orchestration_store.ack_notification(pid, key)}


@app.get("/api/projects/{pid}/campaign-artifacts")
def api_campaign_artifacts(pid: str, enrich: bool = False):
    """The Planning stage's two linked artifacts â€” Campaign Strategy (decision records) +
    Campaign Brief (operational, hybrid agency-brief anatomy). Deterministic composition from
    the saved plan ctx; decision records are re-derived when not persisted, so this also works
    for projects planned before the decision spine existed."""
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    ctx = proj["state"].get("_plan_ctx")
    if not ctx:
        raise HTTPException(400, "Stage 1 hasn't produced a plan yet â€” run it before composing artifacts.")
    return campaign_artifacts.compose_artifacts(ctx, enrich=enrich)


@app.get("/api/pharma-intel/summary")
def api_pharma_intel_summary(section: str = "all"):
    """Read-only visual summary for the Artefacts page, backed by data/omni_kb.db.

    ``section`` (totals|mix|brands|sources|all) lets the frontend fan the summary
    out into parallel, progressively-rendered requests instead of one slow call.
    """
    section = section if section in _PHARMA_INTEL_SECTIONS else "all"
    return _pharma_intel_summary(section)


@app.get("/api/pharma-intel/artifacts")
def api_pharma_intel_artifacts(kind: str, value: str = "", limit: int = Query(default=20, ge=1, le=40)):
    """Representative scraped artifacts for drill-downs on the Artefacts page."""
    return _pharma_intel_artifacts(kind=kind, value=value, limit=limit)


@app.get("/api/cognee/status")
def api_cognee_status():
    """Status for the Cognee-backed SME process grounding layer."""
    return {
        "health": process_knowledge.health(),
        "topics": [{"key": key, "query_template": value} for key, value in process_knowledge.TOPICS.items()],
        "feedback": cognee_feedback.list_feedback(limit=20),
    }


@app.post("/api/cognee/probe")
def api_cognee_probe(req: dict):
    """Request-level inspection of the exact process-grounding queries and extracted guidance."""
    brand = str(req.get("brand") or "")
    therapy_area = str(req.get("therapy_area") or "")
    topics = req.get("topics") or list(process_knowledge.BRIEF_TOPICS)
    holder: dict = {}

    def _probe():
        try:
            holder["value"] = process_knowledge.diagnose_request(
                brand=brand,
                therapy_area=therapy_area,
                topics=topics,
                max_chars=1400,
            )
        except Exception as exc:  # noqa: BLE001
            holder["error"] = exc

    worker = threading.Thread(target=_probe, daemon=True)
    worker.start()
    worker.join(timeout=45)
    if worker.is_alive():
        return {
            "health": process_knowledge.health(),
            "brand": brand,
            "therapy_area": therapy_area,
            "enabled": process_knowledge.enabled(),
            "topics": [
                {
                    "topic": topic,
                    "query": process_knowledge.topic_query(topic, brand=brand, therapy_area=therapy_area),
                    "has_guidance": False,
                    "guidance": "",
                    "source": "Cognee probe timed out",
                    "feedback": cognee_feedback.matching_feedback(topic, brand=brand, therapy_area=therapy_area),
                }
                for topic in topics
            ],
            "elapsed_ms": 45000,
            "timeout": True,
            "error": "Cognee probe exceeded 45 seconds. The graph/LLM extraction path is enabled but not responding quickly.",
        }
    if "error" in holder:
        raise HTTPException(500, str(holder["error"]))
    return holder["value"]


@app.get("/api/cognee/feedback")
def api_cognee_feedback(limit: int = Query(default=50, ge=1, le=200)):
    return {"items": cognee_feedback.list_feedback(limit=limit)}


@app.post("/api/cognee/feedback")
def api_cognee_feedback_post(req: dict):
    try:
        record = cognee_feedback.add_feedback(req)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "record": record, "items": cognee_feedback.list_feedback(limit=20)}


@app.get("/api/projects/{pid}/orchestration/gate-context")
def api_orchestration_gate_context(pid: str):
    """Per-activity read/gate context from Veeva (AFU status/job code/expiry) + SFMC (send state)
    -- PRD F5.2. Read-only. Uses real providers when their credentials are set, else demonstrable
    stubs (unless ORCHESTRATION_GATES_LIVE=1)."""
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    tasks = orchestration_tasks.ensure_enriched(proj.get("orchestration_tasks") or [])
    return {"context": orchestration_gates.gate_context(pid, tasks)}


@app.post("/api/projects/{pid}/campaign-plan/generate")
def api_generate_campaign_plan(pid: str):
    """On-demand Stage 3 counterpart to orchestration-tasks/generate above: (re)compute the
    campaign-ops flow skeleton from the Stage 1 plan context. Called only from an explicit
    user action (the chat kickoff card), never automatically on tab open. Returns the raw
    CampaignFlow -- the frontend converts it to a WorkflowDocument and persists it via the
    existing campaign-plan-layout PATCH, same as the one-time fallback conversion already
    used when opening an older project that has no saved layout yet."""
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    ctx = proj["state"].get("_plan_ctx")
    if not ctx:
        raise HTTPException(400, "Stage 1 hasn't produced a plan yet -- run it before generating a campaign flow.")
    flow = campaign_ops.build_campaign_plan(ctx)
    return {"flow": flow}


@app.post("/api/projects/{pid}/campaign-plan-layout/regenerate")
def api_regenerate_campaign_plan_layout(pid: str, req: CampaignPlanRegenerateRequest):
    """Regenerate the Stage 3 workflow document from the saved brief plus chat context.

    Unlike campaign-plan/generate, this does not just rebuild the deterministic CampaignFlow
    skeleton. It asks the Campaign Operations agent to redraw the full WorkflowDocument from
    the project's saved planning brief and tab-chat history, then persists the replacement
    document if one is returned.
    """
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    return tab_chat.regenerate_operations(pid, document=req.document)


@app.post("/api/projects/{pid}/extract-text")
async def api_extract_project_text(pid: str, file: UploadFile = File(...)):
    """Generic document->text extraction for the Stage 2/3 chat kickoff's 'upload a document'
    path -- unlike /api/upload, this does NOT touch the project's brief slots; the caller
    (tab_chat's kickoff handling) decides what to do with the returned text."""
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    content = await file.read()
    try:
        text = extract_text(file.filename or "upload", content, max_chars=12000)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not text:
        raise HTTPException(400, "Could not extract any text from that file.")
    return {"text": text, "filename": file.filename}


class TabChatRequest(BaseModel):
    message: str
    document: dict | None = None


class AgentBriefRequest(BaseModel):
    stage_id: str
    brief_text: str
    source_name: str | None = None


class SfmcPushRequest(BaseModel):
    auth_base_uri: str
    client_id: str
    client_secret: str
    account_id: str | None = None
    scope: str | None = None
    entry_data_extension_id: str | None = None
    entry_event_definition_key: str | None = None
    email_asset_id: str | None = None
    sender_profile_id: str | None = None
    delivery_profile_id: str | None = None
    schema_version_id: str | None = None
    fire_test_event: bool = False
    contact_key: str | None = None
    contact_key_value: str | None = None


@app.get("/api/projects/{pid}/tab-chat/{stage_id}")
def api_tab_chat_history(pid: str, stage_id: str):
    """This tab's persisted chat transcript (see strategy/tab_chat.py) -- each workspace
    tab has its own agent identity and its own history, independent of the others."""
    if stage_id not in tab_chat.STAGE_AGENTS:
        raise HTTPException(404, f"unknown tab '{stage_id}'")
    return tab_chat.get_history(pid, stage_id)


@app.post("/api/projects/{pid}/tab-chat/{stage_id}")
def api_tab_chat_ask(pid: str, stage_id: str, req: TabChatRequest):
    """Send a message to this tab's agent. The Campaign Operations agent can return an
    updated diagram (`document`) when the request calls for a structural edit; the other
    three tabs answer grounded in the project's own plan content only."""
    if stage_id not in tab_chat.STAGE_AGENTS:
        raise HTTPException(404, f"unknown tab '{stage_id}'")
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    return tab_chat.ask(pid, stage_id, req.message, document=req.document)


@app.post("/api/projects/{pid}/agent-brief")
def api_agent_brief(pid: str, req: AgentBriefRequest):
    """Direct-agent kickoff from a pasted/uploaded brief.

    Stage 1's Studio remains the full sequential planning experience. This endpoint is the
    direct navigation path: when a user opens Orchestration, Operations, or Reporting first,
    the agent can still accept an initial brief and create the same persisted planning ctx
    that downstream generators already consume.
    """
    if req.stage_id not in tab_chat.STAGE_AGENTS:
        raise HTTPException(404, f"unknown tab '{req.stage_id}'")
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    brief_text = (req.brief_text or "").strip()
    if not brief_text:
        raise HTTPException(400, "brief_text is required")

    state = proj["state"]
    slots = state.setdefault("slots", {})
    extracted = extract_brief_from_text(brief_text)
    for key, val in (extracted.get("fields") or {}).items():
        if val not in (None, "", 0, False) and not slots.get(key):
            slots[key] = val
    slots["tactical_source_text"] = brief_text[:24000]
    slots["tactical_source_name"] = req.source_name or "Direct agent brief"
    if req.source_name:
        slots["notes"] = (slots.get("notes") or f"Source brief: {req.source_name}")

    brand = str(slots.get("brand") or "Brand").strip()
    therapy_area = str(slots.get("therapy_area") or slots.get("indication") or "oncology").strip()
    lifecycle_key = str(slots.get("lifecycle_key") or "growth").strip()
    try:
        budget = float(slots.get("budget") or 0)
    except (TypeError, ValueError):
        budget = 0.0
    indication = str(slots.get("indication") or "").strip()
    maturity_notes = str(slots.get("maturity_notes") or slots.get("notes") or "").strip()

    try:
        ctx = orchestrator.compute_core_ctx(
            brand,
            therapy_area,
            lifecycle_key,
            budget=budget,
            maturity_notes=maturity_notes,
            indication=indication,
            brief=slots,
        )
        ctx = orchestrator.fill_plan_ctx(ctx, lazy_grounding=True, fast=True)
        result, plan_markdown, plan_html = orchestrator.recompose_plan(ctx)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Could not build planning context from that brief: {exc}") from exc

    state["_plan_ctx"] = ctx
    state["phase"] = "done"
    state["studio_done"] = True
    state["revealed_phases"] = list(open_questions_mod.PHASE_ORDER)
    messages = proj["messages"]
    if req.stage_id == "planning":
        messages.append(_msg("user", brief_text))
        messages.append(_msg("agent", "Built the campaign strategy and brief from your direct brief."))
    else:
        tab_chat.append(pid, req.stage_id, "user", None, brief_text, kind="brief")

    tasks = None
    flow = None
    if req.stage_id == "orchestration":
        tasks = orchestration_tasks.generate_tasks(ctx, extra_context=brief_text)
        pstore.save_project(pid, orchestration_tasks=tasks)
        tab_chat.append(pid, req.stage_id, "assistant", req.stage_id,
                        "Built the setup-task checklist from your direct brief.", kind="brief")
    elif req.stage_id == "operations":
        plan = campaign_ops.build_campaign_plan(ctx)
        flow = plan.get("flow")
        tab_chat.append(pid, req.stage_id, "assistant", req.stage_id,
                        "Built the campaign engagement flow from your direct brief.", kind="brief")
    elif req.stage_id == "reporting":
        tab_chat.append(pid, req.stage_id, "assistant", req.stage_id,
                        "Built the measurement and reporting view from your direct brief.", kind="brief")

    name = proj["name"]
    if name in ("Untitled plan", "New plan"):
        name = _campaign_id_name(pid)
    pstore.save_project(pid, name=name, state=state, messages=messages,
                        result=result, plan_markdown=plan_markdown, plan_html=plan_html,
                        orchestration_tasks=tasks if tasks is not None else proj.get("orchestration_tasks"))
    brief_summary.attach(slots)
    return {
        "reply": {
            "planning": "Built the campaign strategy and brief from your direct brief.",
            "orchestration": "Built the setup-task checklist from your direct brief.",
            "operations": "Built the campaign engagement flow from your direct brief.",
            "reporting": "Built the measurement and reporting view from your direct brief.",
        }.get(req.stage_id, "Built from your brief."),
        "project": pstore.get_project(pid),
        "tasks": tasks,
        "flow": flow,
        "extracted": extracted.get("items") or [],
    }


@app.get("/api/projects/{pid}/reporting-insights")
def api_reporting_insights(pid: str, specialty: str | None = None, months: int = 6):
    """Reporting tab payload: stage-promotion funnel, delivery/engagement KPI cards, the
    email metrics funnel (e-delivery/open/CTR/CTOR/bounce/unsubscribe) with an exact current
    percentage and a monthly trend, real HCP-panel demographics, the UTM link/tagging matrix,
    and the A/B test design. `specialty` and `months` filter the email metrics block."""
    if not pstore.get_project(pid):
        raise HTTPException(404, "project not found")
    return reporting_insights.build(pid, specialty=specialty, months=months)


@app.get("/api/projects/{pid}/export.docx")
def api_export_docx(pid: str):
    proj = pstore.get_project(pid)
    if not proj or not proj.get("plan_markdown"):
        raise HTTPException(404, "no plan to export yet")
    data = plan_export.markdown_to_docx(proj["plan_markdown"], proj["name"])
    filename = _safe_filename(proj["name"]) + ".docx"
    return Response(content=data,
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/projects/{pid}/export.pdf")
def api_export_pdf(pid: str):
    proj = pstore.get_project(pid)
    if not proj or not proj.get("plan_markdown"):
        raise HTTPException(404, "no plan to export yet")
    # Prefer the pixel-faithful renderer (real HTML + the app's own CSS via headless
    # Chromium) so the PDF actually looks like the plan; fall back to the plain
    # reportlab-from-markdown renderer if Chromium isn't installed on this host, so the
    # export still works (with lower fidelity) rather than failing outright.
    try:
        if not proj.get("plan_html"):
            raise ValueError("no plan_html on this project")
        data = plan_pdf.render_plan_pdf(proj["plan_html"], proj["name"])
    except Exception as e:  # noqa: BLE001
        print(f"[export.pdf] Chromium renderer unavailable, using markdown fallback ({e})")
        data = plan_export.markdown_to_pdf(proj["plan_markdown"], proj["name"])
    filename = _safe_filename(proj["name"]) + ".pdf"
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _brief_markdown(pid: str) -> tuple[str, str]:
    """(markdown, base filename) for the composed Campaign Brief of this project."""
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    ctx = proj["state"].get("_plan_ctx")
    if not ctx:
        raise HTTPException(404, "no campaign brief yet — run Stage 1 first")
    brief = campaign_artifacts.compose_brief(ctx)
    name = _safe_filename(proj["name"]) + "-campaign-brief"
    return brief_document.brief_markdown(brief, proj["name"]), name


@app.get("/api/projects/{pid}/campaign-brief.docx")
def api_campaign_brief_docx(pid: str):
    """The Campaign Brief as a Word document — same converter as the plan export, so the two
    downloads read alike."""
    markdown, name = _brief_markdown(pid)
    data = plan_export.markdown_to_docx(markdown, name)
    return Response(content=data,
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{name}.docx"'})


@app.get("/api/projects/{pid}/campaign-brief.pdf")
def api_campaign_brief_pdf(pid: str):
    """The Campaign Brief as a PDF. Unlike the plan export there is no Chromium path here:
    the brief has no standalone HTML document to render, only React components, so the
    markdown renderer is the only renderer."""
    markdown, name = _brief_markdown(pid)
    data = plan_export.markdown_to_pdf(markdown, name)
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'})


@app.get("/api/projects/{pid}/export.sfmc.json")
def api_export_sfmc(pid: str):
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    try:
        bundle = sfmc_export.build_sfmc_bundle(proj)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    data = json.dumps(bundle, indent=2, ensure_ascii=False).encode("utf-8")
    filename = _safe_filename(proj["name"]) + ".sfmc.json"
    return Response(content=data, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.post("/api/projects/{pid}/export.sfmc.push")
def api_export_sfmc_push(pid: str, req: SfmcPushRequest):
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    config = sfmc_export.SFMCConfig(
        auth_base_uri=req.auth_base_uri,
        client_id=req.client_id,
        client_secret=req.client_secret,
        account_id=req.account_id,
        scope=req.scope,
        entry_data_extension_id=req.entry_data_extension_id,
        entry_event_definition_key=req.entry_event_definition_key,
        email_asset_id=req.email_asset_id,
        sender_profile_id=req.sender_profile_id,
        delivery_profile_id=req.delivery_profile_id,
        schema_version_id=req.schema_version_id,
        fire_test_event=req.fire_test_event,
        contact_key=req.contact_key,
        contact_key_value=req.contact_key_value,
    )
    try:
        result = sfmc_export.push_sfmc_journey(proj, config)
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e
    return result


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    proj = pstore.get_project(req.project_id)
    if not proj:
        raise HTTPException(404, "project not found")
    messages = proj["messages"]
    state = proj["state"]
    messages.append(_msg("user", req.message))

    # Snapshot whether the post-plan clarify Q&A was in progress BEFORE this turn, so we can
    # tell the client the exact turn it finishes on -- that's the moment the synthetic-persona
    # offer should appear (never before the brand team's open questions are captured). Also
    # snapshot which group ids were already resolved, and an id->title lookup, so we can tell
    # the client exactly which section(s) this turn just folded into the plan.
    prev_groups = state.get("open_questions") or []
    prev_idx = state.get("clarify_idx", 0)
    was_clarifying = bool(prev_groups) and prev_idx < len(prev_groups)
    prev_resolved = set(state.get("clarify_resolved_ids") or [])
    id_to_title = {g["id"]: g["title"] for g in prev_groups}

    state, reply, action = interpret_message(req.message, state)
    clarify = clarify_payload(state)  # non-None only while the post-plan clarify Q&A is active

    now_groups = state.get("open_questions") or []
    now_idx = state.get("clarify_idx", 0)
    now_clarifying = bool(now_groups) and now_idx < len(now_groups)
    clarify_just_completed = was_clarifying and not now_clarifying

    # When the user signs off a phase's questions, the NEXT toolkit phase's agents start next
    # (the front-end triggers /api/run-stream?phase=<next_phase>). Announce the hand-off in the
    # reply instead of the generic per-phase "that's everything" close. next_phase=None means
    # Deploy (the last phase) was just signed off, so the whole build is complete.
    next_phase = None
    if clarify_just_completed and not state.get("plan_frozen"):
        cur_phase = state.get("current_phase")
        if cur_phase in orchestrator.PHASE_ORDER:
            i = orchestrator.PHASE_ORDER.index(cur_phase)
            if i + 1 < len(orchestrator.PHASE_ORDER):
                next_phase = orchestrator.PHASE_ORDER[i + 1]
            if next_phase:
                reply = (f"âœ… **Phase {orchestrator.PHASE_NO[cur_phase]} Â· {orchestrator.PHASE_LABELS[cur_phase]}** "
                         f"is signed off and folded into the plan. Bringing the agents in for **Phase "
                         f"{orchestrator.PHASE_NO[next_phase]} Â· {orchestrator.PHASE_LABELS[next_phase]}** nowâ€¦")
            else:
                reply = ("âœ… **Phase 4 Â· Deploy the campaign** is signed off. That completes all four toolkit phases â€” "
                         "the plan is fully built and every section is live on the right. Pressure-test it with "
                         "synthetic personas next, or say **close updates** to lock it in.")

    messages.append(_msg("agent", reply, {"kind": "clarify", "clarify": clarify} if clarify else None))

    # 'update_plan': fold this clarify answer (or skip / skip-all) into the plan immediately --
    # no waiting for the whole Q&A to finish and no manual 'regenerate'. Recomposes from the
    # run's snapshotted ctx (never re-runs the agents); a project created before ctx snapshots
    # existed just skips this silently (plan_updated stays False).
    plan_updated = False
    plan_html = plan_markdown = None
    updated_sections: list[str] = []
    result_for_save = None
    if action == "update_plan":
        newly_resolved = set(state.get("clarify_resolved_ids") or []) - prev_resolved
        updated_sections = [id_to_title.get(gid, gid) for gid in newly_resolved]
        ctx = state.get("_plan_ctx")
        if ctx:
            ctx = orchestrator.refresh_after_clarify(
                ctx, state["slots"].get("maturity_notes", ""), set(state.get("clarify_resolved_ids") or []))
            # The plan is revealed up to the phase currently being validated -- driven by the
            # phased run, not the clarify cursor (each run seeds only its own phase's questions).
            cur_phase = state.get("current_phase", "align")
            revealed = orchestrator._phase_reveal(cur_phase)
            state["revealed_phases"] = sorted(revealed)
            result_for_save, plan_markdown, plan_html = orchestrator.recompose_plan(ctx, revealed_phases=revealed)
            state["_plan_ctx"] = ctx
            plan_updated = True
    elif action == "freeze":
        _freeze_project_state(state)
        # Locking the plan in reveals every remaining phase -- the user is done building,
        # so nothing stays locked once the document is finalized.
        ctx = state.get("_plan_ctx")
        if ctx:
            state["revealed_phases"] = list(open_questions_mod.PHASE_ORDER)
            result_for_save, plan_markdown, plan_html = orchestrator.recompose_plan(ctx)
            plan_updated = True

    # The plan keeps its unique campaign-ID name (or whatever the user renamed it to). We no
    # longer overwrite it with brand + indication; only backfill an ID if an older project is
    # still sitting on a placeholder name.
    name = proj["name"]
    slots = state["slots"]
    if name in ("Untitled plan", "New plan"):
        name = _campaign_id_name(req.project_id)

    pstore.save_project(req.project_id, name=name, state=state, messages=messages,
                        result=result_for_save, plan_markdown=plan_markdown, plan_html=plan_html)
    brief_summary.attach(slots)  # short keyword summaries for the BriefCard display
    return {"reply": reply, "slots": slots, "phase": state["phase"], "action": action, "name": name,
            "llm_status": get_llm_status(), "clarify": clarify, "clarify_just_completed": clarify_just_completed,
            "next_phase": next_phase,
            "plan_updated": plan_updated, "plan_html": plan_html, "plan_markdown": plan_markdown,
            "updated_sections": updated_sections, "plan_frozen": bool(state.get("plan_frozen"))}


@app.post("/api/upload")
async def api_upload(project_id: str = Form(...), file: UploadFile = File(...)):
    """Import a brand plan: extract the document text (PDF/DOCX/text), read the brief out of it
    (labelled facts + the connective/template extractor), pre-fill the brief slots, then feed it
    through the same interpret_message seam as a normal chat turn -- so an uploaded plan fills the
    engagement brief without any retyping. Returns a display list of exactly what was captured so
    the UI can show it back to the user."""
    proj = pstore.get_project(project_id)
    if not proj:
        raise HTTPException(404, "project not found")

    content = await file.read()
    try:
        full_text = extract_text(file.filename or "upload", content, max_chars=200_000)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not full_text:
        raise HTTPException(400, "Could not extract any text from that file.")
    print(f"[upload] {file.filename!r} extracted full_text length={len(full_text)} chars")

    messages = proj["messages"]
    state = proj["state"]
    slots = state["slots"]
    messages.append(_msg("user", f"ðŸ“Ž Uploaded **{file.filename}**"))

    # Keep the chat-turn prompt bounded -- a strategic-plan deck can run well past a sane
    # single-turn size, but brief/tactical extraction below reads the FULL document so labelled
    # facts (Molecule/Indication/Objective/...) that sit past this cutoff aren't silently dropped.
    text = full_text[:8000] + ("\n\n[...truncated...]" if len(full_text) > 8000 else "")
    slots["tactical_source_text"] = full_text[:24000]
    slots["tactical_source_name"] = file.filename

    # Read the brief out of the plan and pre-fill any still-empty slots. A captured budget also
    # marks budget as asked, so the dialog doesn't re-prompt for something the plan already gave.
    extracted = extract_brief_from_text(full_text)
    for key, val in extracted["fields"].items():
        if key == "budget":
            if val and not slots.get("budget"):
                slots["budget"] = val
                state["budget_asked"] = True
            continue
        if not slots.get(key):
            slots[key] = val

    # A document import is its own source of truth -- don't also surface the "I've planned
    # for this brand before" memory-recall prompt, which would contradict what was just read.
    state["recall_offered"] = True

    # Advance the dialog with the pre-filled slots in place -- it asks only for what the plan
    # left out (or kicks off the run, gated by the 'why this campaign' follow-up).
    prompt = (f"[The user uploaded a brand plan named \"{file.filename}\". Its details are already "
              f"captured in the brief; continue from there.]\n\n{text}")
    state, reply, action = interpret_message(prompt, state)
    messages.append(_msg("agent", reply))

    name = proj["name"]
    if name in ("Untitled plan", "New plan"):
        name = _campaign_id_name(project_id)

    pstore.save_project(project_id, name=name, state=state, messages=messages)
    brief_summary.attach(slots)  # short keyword summaries for the BriefCard display
    return {"reply": reply, "slots": slots, "phase": state["phase"], "action": action, "name": name,
            "llm_status": get_llm_status(), "filename": file.filename,
            "extracted": extracted["items"], "filled_count": len(extracted["items"])}


@app.get("/api/run-stream")
def api_run_stream(project_id: str, phase: str = "align"):
    proj = pstore.get_project(project_id)
    if not proj:
        raise HTTPException(404, "project not found")
    slots = proj["state"]["slots"]
    if phase not in orchestrator.PHASE_ORDER:
        phase = "align"

    def event_gen():
        messages = proj["messages"]
        state = proj["state"]
        result = None
        ctx_snapshot = None
        plan_md = plan_html = None
        try:
            # Show the team the INSTANT the phase starts -- before the (possibly 30-60s, on
            # Align, of live network calls) compute below -- so the client never sits on a
            # silent stream with nothing rendered. compute_plan_ctx runs every agent's work for
            # every phase once, up front, on Align; later phases replay the same ctx as theater.
            for ev in orchestrator.phase_open(phase):
                if ev["type"] == "narration":
                    messages.append(_msg("agent", ev["text"]))
                yield f"data: {json.dumps(ev)}\n\n"

            if phase == "align" or not state.get("_plan_ctx"):
                # compute_plan_ctx runs 30-60s+ of real network calls; run it on a background
                # thread and stream grounded banter in the meantime so the client never sits on
                # a silent connection (see orchestrator.precompute_heartbeat).
                done_event = threading.Event()
                ctx_holder: dict = {}

                def _compute_ctx():
                    try:
                        ctx_holder["ctx"] = orchestrator.compute_plan_ctx(
                            slots["brand"], slots["therapy_area"], slots["lifecycle_key"], slots["budget"],
                            slots.get("maturity_notes", ""), slots.get("indication", ""), brief=slots)
                    except Exception as exc:  # noqa: BLE001 - re-raised on the main thread below
                        ctx_holder["error"] = exc
                    finally:
                        done_event.set()

                compute_thread = threading.Thread(target=_compute_ctx, daemon=True)
                compute_thread.start()
                for ev in orchestrator.precompute_heartbeat(done_event):
                    yield f"data: {json.dumps(ev)}\n\n"
                compute_thread.join()
                if "error" in ctx_holder:
                    raise ctx_holder["error"]
                ctx = ctx_holder["ctx"]
            else:
                ctx = state["_plan_ctx"]

            for ev in orchestrator.run_phase(phase, ctx, opened=True):
                if ev["type"] == "narration":
                    messages.append(_msg("agent", ev["text"]))
                elif ev["type"] == "plan":
                    plan_md, plan_html = ev["markdown"], ev["html"]
                elif ev["type"] == "result":
                    result = ev["result"]
                    ctx_snapshot = ev.pop("ctx", None)  # server-only; stripped before the wire
                if ev["type"] == "done":
                    # Human gate: seed ONLY this phase's validation questions and ask the first,
                    # then the stream ends -- the next phase's agents don't start until the user
                    # signs off in chat (see the /api/chat 'next_phase' advance).
                    already_resolved = set(state.get("clarify_resolved_ids") or [])
                    phase_groups = [g for g in (result or {}).get("open_questions", [])
                                    if g.get("phase") == phase and g["id"] not in already_resolved]
                    state["open_questions"] = phase_groups
                    state["clarify_idx"] = 0
                    state["current_phase"] = phase
                    state["revealed_phases"] = sorted(orchestrator._phase_reveal(phase))
                    first_ask = ask_clarify_group(state)
                    payload = clarify_payload(state)
                    if first_ask:
                        messages.append(_msg("agent", first_ask, {"kind": "clarify", "clarify": payload}))
                        yield f"data: {json.dumps({'type': 'clarify', 'text': first_ask, 'clarify': payload})}\n\n"
                    # Carried in-band on 'done' so the client can gate the Stage 2-4 tabs on
                    # which toolkit phases have actually been signed off, rather than on
                    # whether *a* result exists (compute_plan_ctx computes every phase's data
                    # up front on Align, so a coarse "result exists" check unlocks everything
                    # in one shot -- the step-by-step reveal has to be enforced client-side).
                    ev["revealed_phases"] = state["revealed_phases"]
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as e:  # surface failures to the UI rather than hanging
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            state["phase"] = "done"
            if ctx_snapshot is not None:
                state["_plan_ctx"] = ctx_snapshot
            pstore.save_project(project_id, state=state, messages=messages,
                                result=result, plan_markdown=plan_md, plan_html=plan_html)
            # Persist the completed plan into the campaign & content data model only on the
            # final phase (Deploy) -- earlier phases are partial. Best-effort; never let a
            # persistence error break the streamed response.
            if result and phase == orchestrator.PHASE_ORDER[-1]:
                try:
                    campaign_store.persist_campaign_from_result(result, slots, plan_md or "", project_id)
                except Exception as e:  # noqa: BLE001
                    print(f"[campaign_store] persist failed: {e}")
                try:
                    brand_memory.save_brand_memory(slots.get("brand", ""), slots)
                except Exception as e:  # noqa: BLE001
                    print(f"[brand_memory] save failed: {e}")

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ------------------------------------------------------------------ #
# Sequential Plan Studio (SSE protocol v2) â€” the section-by-section run that
# drives Stage 1. The stream ENDS at every grounded ask; /api/studio/answer
# records the user's call and the client reopens the stream, which resumes
# from the persisted cursor -- a refresh or reconnect never skips a gate.
# ------------------------------------------------------------------ #
# project_id -> {"event": Event, "ctx": full-ctx-or-None}: the background fill_plan_ctx job
# started when the first (customer-group) ask is posed from the fast core ctx. The resume
# request waits on it (heartbeat meanwhile) so the heavy compute overlaps the user's answer time.
_STUDIO_FILL: dict[str, dict] = {}
# project_id -> auto-assume on/off. Deliberately in-memory and read live at EVERY ask (rather
# than persisted with the project or frozen as a stream-open argument): the checkbox is a
# mid-run toggle, and a running stream holds its own copy of `state`, so a DB write here would
# be both invisible to it and clobbered by its next save. The client re-sends the flag on each
# stream open, which is what makes it survive a restart.
_STUDIO_AUTO: dict[str, bool] = {}


@app.get("/api/studio/stream")
def api_studio_stream(project_id: str, auto_assume: bool = False):
    proj = pstore.get_project(project_id)
    if not proj:
        raise HTTPException(404, "project not found")
    slots = proj["state"]["slots"]
    _STUDIO_AUTO[project_id] = bool(auto_assume)

    def event_gen():
        state = proj["state"]
        messages = proj["messages"]
        plan_md = plan_html = None
        persisted = False

        def _persist_run_done():
            # Save BEFORE the "run_done" event reaches the client -- the frontend reacts to
            # that event by immediately fetching/using Stage 1's output (campaign-artifacts,
            # orchestration-tasks/generate, campaign-plan/generate), all of which read
            # `_plan_ctx` back from disk in a SEPARATE request. Persisting only in a `finally`
            # after the stream closes raced that fetch -- roughly half the time the very first
            # read landed before this save committed, producing a spurious "Stage 1 hasn't
            # produced a plan yet" even though the run had, in fact, just finished.
            nonlocal persisted
            result = None
            try:
                result = orchestrator._assemble_result(state["_plan_ctx"])
            except Exception as exc:  # noqa: BLE001 - never block persistence of what did succeed
                print(f"[studio] _assemble_result failed (final plan/brief may be incomplete): {exc}")
            pstore.save_project(project_id, state=state, messages=messages,
                                result=result, plan_markdown=plan_md, plan_html=plan_html)
            if result:
                try:
                    campaign_store.persist_campaign_from_result(result, slots, plan_md or "", project_id)
                except Exception as exc:  # noqa: BLE001
                    print(f"[campaign_store] persist failed: {exc}")
                try:
                    brand_memory.save_brand_memory(slots.get("brand", ""), slots)
                except Exception as exc:  # noqa: BLE001
                    print(f"[brand_memory] save failed: {exc}")
            persisted = True

        try:
            studio = state.setdefault("studio", {"idx": 0, "answers": {}, "await_ask": None})
            ctx = state.get("_plan_ctx")
            if ctx is None:
                # FIRST touch: pose the customer-group question from a sub-second CORE ctx and fill
                # the heavy remainder (market/strategy/grounding â€” minutes of network+LLM work) in
                # the BACKGROUND, so the first ask lands in seconds instead of behind the full compute.
                yield f"data: {json.dumps({'type': 'agents_init', 'agents': orchestrator.AGENT_ROSTER})}\n\n"
                ctx = orchestrator.compute_core_ctx(
                    slots["brand"], slots["therapy_area"], slots["lifecycle_key"], slots["budget"],
                    slots.get("maturity_notes", ""), slots.get("indication", ""), brief=slots)
                state["_plan_ctx"] = ctx
                _fill_job = {"event": threading.Event(), "ctx": None}
                _STUDIO_FILL[project_id] = _fill_job

                def _bg_fill(core=ctx, job=_fill_job):
                    try:
                        orchestrator.fill_plan_ctx(core, lazy_grounding=True, fast=True)
                        job["ctx"] = core
                    except Exception as exc:  # noqa: BLE001 - resume computes inline if this fails
                        print(f"[studio] background fill_plan_ctx failed: {exc!r}")
                    finally:
                        job["event"].set()

                threading.Thread(target=_bg_fill, daemon=True).start()
            elif ctx.get("_core_only"):
                # RESUME after the first ask: the heavy remainder is needed now (to draft the
                # customer-group section and everything after). Wait on the background fill with a
                # live heartbeat; compute inline if its job is gone (e.g. the server restarted).
                yield f"data: {json.dumps({'type': 'agents_init', 'agents': orchestrator.AGENT_ROSTER})}\n\n"
                _fill_job = _STUDIO_FILL.get(project_id)
                if _fill_job is None:
                    _fill_job = {"event": threading.Event(), "ctx": None}

                    def _fill_now(core=ctx, job=_fill_job):
                        try:
                            orchestrator.fill_plan_ctx(core, lazy_grounding=True, fast=True)
                            job["ctx"] = core
                        except Exception as exc:  # noqa: BLE001
                            job["error"] = exc
                        finally:
                            job["event"].set()

                    threading.Thread(target=_fill_now, daemon=True).start()
                for ev in orchestrator.precompute_heartbeat(_fill_job["event"]):
                    if ev["type"] == "agent":
                        yield f"data: {json.dumps({'type': 'chat', 'author': ev['id'], 'kind': 'turn', 'reply_to': '', 'text': ev['say']})}\n\n"
                    elif ev["type"] == "banter":
                        yield f"data: {json.dumps({'type': 'chat', 'author': ev['id'], 'kind': 'banter', 'reply_to': ev.get('to', ''), 'text': ev['text']})}\n\n"
                if _fill_job.get("error"):
                    raise _fill_job["error"]
                ctx = _fill_job.get("ctx") or ctx
                if ctx.get("_core_only"):  # background fill failed -> do it inline as a last resort
                    try:
                        orchestrator.fill_plan_ctx(ctx, lazy_grounding=True)
                    except Exception as exc:  # noqa: BLE001
                        print(f"[studio] inline fill fallback failed: {exc!r}")
                state["_plan_ctx"] = ctx
                _STUDIO_FILL.pop(project_id, None)
            # else: a fully-populated ctx is already cached -- use it as-is.

            # Panel narrowing set by a decision revision lives on state (ctx is rebuilt or
            # cached independently), so re-apply it to whichever ctx we ended up with. Without
            # this a filtered revision would re-size against the whole panel again.
            if state.get("segment_filters") is not None:
                ctx["segment_filters"] = state["segment_filters"]

            # Persist a viewable brief + plan snapshot as soon as the FULL ctx exists (skipped while
            # _core_only, since the heavy sections aren't computed yet). Cheap + local, so it re-runs
            # on each ask-resume to keep the saved plan fresh even if the reveal never finishes.
            if not ctx.get("_core_only"):
                try:
                    early_result, plan_md, plan_html = orchestrator.recompose_plan(ctx)
                    pstore.save_project(project_id, state=state, messages=messages,
                                        result=early_result, plan_markdown=plan_md, plan_html=plan_html)
                except Exception as exc:  # noqa: BLE001 - the reveal still runs even if the snapshot fails
                    print(f"[studio] early plan persist failed: {exc}")

            for ev in studio_run.stream(ctx, studio,
                                        auto_assume=lambda: _STUDIO_AUTO.get(project_id, False)):
                if ev["type"] == "chat":
                    messages.append(_msg("agent", ev["text"], {"kind": ev["kind"], "author": ev["author"]}))
                elif ev["type"] == "section_html":
                    # Persisted alongside the cursor so a completed build can be redisplayed
                    # statically on reopen instead of re-streaming the whole paced reveal.
                    sections = studio.setdefault("sections", [])
                    if not any(s["section_id"] == ev["section_id"] for s in sections):
                        sections.append({k: ev[k] for k in ("section_id", "num", "title", "owner", "html")})
                elif ev["type"] == "plan":
                    plan_md, plan_html = ev["markdown"], ev["html"]
                elif ev["type"] == "run_done":
                    state["studio_done"] = True
                    _persist_run_done()
                elif ev["type"] == "ask" and not ev.get("auto_assumed"):
                    # (An auto-assumed ask doesn't pause the stream, so there's no idle window
                    # to prefetch into -- this section drafts inline, immediately.)
                    # Warm grounding for THIS section (it drafts on resume) through the next ask,
                    # in the background while the user reads and answers, so the resume flows
                    # straight through (PRD: "think of the next while that input is coming in").
                    cur = studio["idx"]
                    if cur < len(studio_run.SEQUENCE):
                        threading.Thread(
                            target=studio_run.prefetch_grounding,
                            args=(slots.get("brand", ""), slots.get("therapy_area", ""), cur),
                            daemon=True,
                        ).start()
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as e:  # surface failures to the UI rather than hanging
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            # Fallback for paths that never reached run_done (an exception mid-stream, or the
            # client disconnecting early) -- still save whatever progress was made. A no-op
            # when _persist_run_done already ran above.
            if not persisted:
                pstore.save_project(project_id, state=state, messages=messages,
                                    plan_markdown=plan_md, plan_html=plan_html)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# --------------------------------------------------------------------------------------------- #
# Planning v2 -- Strategic-to-Tactical Planning Engine (Phase 7: UI wiring)
#
# Blocking by design: ingest/extract/enrich/gap-analysis/synthesis each make one or more real
# LLM calls that can take 30-90s. The start/finish endpoints are declared `async def` (because
# they read an UploadFile, which is itself async) but hand the actual blocking pipeline call to
# FastAPI's threadpool via `run_in_threadpool` so the event loop stays free for other requests
# meanwhile -- the same reason most of this file's OTHER endpoints are plain `def` (FastAPI
# threadpools those automatically); this one just also needs `await file.read()` first.
# --------------------------------------------------------------------------------------------- #
from fastapi.concurrency import run_in_threadpool  # noqa: E402


class PlanningV2AnswerRequest(BaseModel):
    field: str
    value: str


def _planning_v2_run_payload(run: planning_v2_pipeline.PlanningRun) -> dict:
    qs = run.pending_questions()
    return {
        "id": run.id,
        "stage": run.stage,
        "brand": run.strategic_context.brand.name if run.strategic_context else "",
        "questions": [g.model_dump(mode="json") for g in qs.questions],
        "deferred": [g.model_dump(mode="json") for g in qs.deferred],
        "assumptions": [g.model_dump(mode="json") for g in qs.assumptions],
        "strategic_context": run.strategic_context.model_dump(mode="json") if run.strategic_context else None,
        "tactical_plan": run.tactical_plan.model_dump(mode="json") if run.tactical_plan else None,
        "brb": run.brb.model_dump(mode="json") if run.brb else None,
        "compliance": run.compliance.model_dump(mode="json") if run.compliance else None,
    }


@app.post("/api/planning-v2/runs")
async def api_planning_v2_start(file: UploadFile = File(...)):
    """Stage 1-4: ingest the uploaded strategic plan, extract, enrich, and run gap
    analysis, returning the ranked question set for the chat column to render."""
    content = await file.read()
    try:
        run = await run_in_threadpool(planning_v2_pipeline.start_run, content, file.filename or "upload")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _planning_v2_run_payload(run)


@app.get("/api/planning-v2/runs/{run_id}")
def api_planning_v2_get(run_id: str):
    try:
        run = planning_v2_pipeline.PlanningRun.load(run_id)
    except FileNotFoundError:
        raise HTTPException(404, "run not found")
    return _planning_v2_run_payload(run)


@app.post("/api/planning-v2/runs/{run_id}/answer")
def api_planning_v2_answer(run_id: str, req: PlanningV2AnswerRequest):
    try:
        run = planning_v2_pipeline.PlanningRun.load(run_id)
    except FileNotFoundError:
        raise HTTPException(404, "run not found")
    run = planning_v2_pipeline.answer(run, req.field, req.value)
    return _planning_v2_run_payload(run)


@app.post("/api/planning-v2/runs/{run_id}/finish")
async def api_planning_v2_finish(run_id: str):
    """Stage 5-6: synthesize the Tactical Plan + BRB (falling back any un-answered
    question to its suggested_default) and run the compliance validator over it."""
    try:
        run = planning_v2_pipeline.PlanningRun.load(run_id)
    except FileNotFoundError:
        raise HTTPException(404, "run not found")
    try:
        run = await run_in_threadpool(planning_v2_pipeline.finish_run, run)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _planning_v2_run_payload(run)


@app.get("/api/planning-v2/runs/{run_id}/handoff")
def api_planning_v2_handoff(run_id: str):
    """Stage 7 -- emit the BRB as the orchestration input. 400s if compliance blockers
    are still open (see pipeline.handoff)."""
    try:
        run = planning_v2_pipeline.PlanningRun.load(run_id)
    except FileNotFoundError:
        raise HTTPException(404, "run not found")
    try:
        brb = planning_v2_pipeline.handoff(run)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"brb": brb}


class StudioAnswer(BaseModel):
    project_id: str
    ask_id: str
    value: str


@app.post("/api/studio/answer")
def api_studio_answer(body: StudioAnswer):
    proj = pstore.get_project(body.project_id)
    if not proj:
        raise HTTPException(404, "project not found")
    state = proj["state"]
    studio = state.get("studio") or {}
    pending = studio.get("await_ask")
    if not pending or pending.get("ask_id") != body.ask_id:
        raise HTTPException(409, "no matching ask is awaiting an answer")
    step = studio_run.SEQUENCE[studio["idx"]]
    # A step may pose several questions in turn (the journey series), so the ask names the
    # key its answer belongs under; the section id is the default for single-ask steps.
    studio["answers"][pending.get("answer_key") or step["id"]] = body.value.strip()
    messages = proj["messages"]
    # Persist the QUESTION, not just the answer. Only the user's reply used to be written
    # here, so reopening a finished plan showed a column of bare answers with nothing to say
    # what had been asked. The full ask payload is already on `await_ask`, and the chosen
    # value rides along in the same meta so rehydration can render the card locked without
    # having to pair it with the message that follows.
    messages.append(_msg("agent", pending.get("text") or "",
                         {"kind": "studio_ask", "ask": pending, "answer": body.value.strip()}))
    messages.append(_msg("user", body.value.strip()))
    pstore.save_project(body.project_id, state=state, messages=messages)
    return {"ok": True, "resume": True}


class StudioRevise(BaseModel):
    project_id: str
    section_id: str
    value: str
    # Panel narrowing for the segmentation decision, e.g. {"states": ["TX"]}. Persisted on
    # state so the next stream seeds ctx with it and every re-sized share is counted on the
    # narrowed population.
    filters: dict | None = None


@app.post("/api/studio/revise")
def api_studio_revise(body: StudioRevise):
    """Change a decision that already landed, and rebuild everything that depended on it.

    Implemented as a rewind rather than a new engine: the studio index moves back to the
    revised step and the existing /api/studio/stream replays forward from there, so
    apply_answer, compose_section and the decision records all run through their normal
    paths. Sections and records are overwritten in place by id (no version history) --
    the client reducer replaces on re-emit."""
    proj = pstore.get_project(body.project_id)
    if not proj:
        raise HTTPException(404, "project not found")
    idx = next((i for i, s in enumerate(studio_run.SEQUENCE) if s["id"] == body.section_id), None)
    if idx is None:
        raise HTTPException(404, f"unknown section '{body.section_id}'")
    value = body.value.strip()
    if not value:
        raise HTTPException(400, "value is required")

    state = proj["state"]
    studio = state.get("studio") or {}
    if not studio.get("answers"):
        raise HTTPException(409, "this plan has no landed decisions to revise")

    stage = decision_spine.stage_for(body.section_id)
    affected = decision_spine.dependents_of(stage["id"]) if stage else []

    studio["answers"][body.section_id] = value
    studio["idx"] = idx
    studio["await_ask"] = None
    # Drop everything from the revised step forward so the replay rebuilds it. Sections keep
    # their identity (the reducer replaces by id), but the persisted copies must go or a
    # section that no longer applies would survive the rebuild.
    keep_ids = {s["id"] for s in studio_run.SEQUENCE[:idx]}
    studio["sections"] = [s for s in (studio.get("sections") or []) if s.get("section_id") in keep_ids]
    state["studio_done"] = False
    # Drop the records this revision invalidates. studio_run replaces them on replay anyway,
    # but a run that is interrupted part-way would otherwise leave the brief quoting reasoning
    # derived from the OLD decision, which is worse than leaving it visibly incomplete.
    stale = {stage["id"], *affected} if stage else set()
    ctx_cached = state.get("_plan_ctx") or {}
    if stale and ctx_cached.get("decision_records"):
        ctx_cached["decision_records"] = [r for r in ctx_cached["decision_records"]
                                          if r.get("stage_id") not in stale]
    if body.filters is not None:
        ctx_cached["segment_filters"] = body.filters
    if body.filters is not None:
        state["segment_filters"] = body.filters
    pstore.save_project(body.project_id, state=state, messages=proj["messages"])
    return {"ok": True, "resume": True, "from_section": body.section_id,
            "affected_stages": affected, "affected_sections": len(studio_run.SEQUENCE) - idx - 1}


class StudioAutoAssume(BaseModel):
    project_id: str
    enabled: bool


@app.post("/api/studio/auto-assume")
def api_studio_auto_assume(body: StudioAutoAssume):
    """Toggle auto-assume for the planning run. Takes effect at the NEXT ask, including one
    posed by a stream that is still open. If an ask is already sitting on the gate, the
    caller is told what value would be assumed for it so it can be answered immediately
    (the stream is closed at that point, so the server can't resume itself)."""
    proj = pstore.get_project(body.project_id)
    if not proj:
        raise HTTPException(404, "project not found")
    _STUDIO_AUTO[body.project_id] = bool(body.enabled)
    pending = (proj["state"].get("studio") or {}).get("await_ask")
    return {
        "ok": True,
        "auto_assume": bool(body.enabled),
        "pending_ask_id": pending.get("ask_id") if pending else None,
        "pending_value": studio_run.auto_answer_value(pending) if (pending and body.enabled) else "",
    }


# ------------------------------------------------------------------ #
# Legacy single-shot endpoints (kept for scripting / backward compat)
# ------------------------------------------------------------------ #

class StrategyRequest(BaseModel):
    brand: str
    therapy_area: str = ""
    persona: str
    stage_key: str


class CompetitiveRequest(BaseModel):
    brand: str
    therapy_area: str = ""
    competitors: list[str] = []


class MarketLandscapeRequest(BaseModel):
    brand: str
    therapy_area: str = ""


class PositioningRequest(BaseModel):
    brand: str
    therapy_area: str = ""
    persona: str
    stage_key: str
    competitors: list[str] = []


class KpiRequest(BaseModel):
    stage_key: str
    channel_mix_pct: dict[str, float] = {}


class AutoRunRequest(BaseModel):
    brand: str
    therapy_area: str = ""
    lifecycle_key: str
    budget: float = 0


class CogneeProbeRequest(BaseModel):
    brand: str = ""
    therapy_area: str = ""
    topics: list[str] = []


class CogneeFeedbackRequest(BaseModel):
    topic: str
    brand: str = ""
    therapy_area: str = ""
    request: str = ""
    observed: str = ""
    feedback: str
    expected: str = ""
    rating: str = ""


@app.get("/api/options")
def get_options():
    return {"stages": list_stage_options(), "personas": list_persona_options(),
            "lifecycle_stages": list_lifecycle_options(), "llm_enabled": llm_enabled(),
            "llm_status": get_llm_status(),
            "studio_llm_status": studio_run.llm_decisioning.get_llm_status()}


@app.get("/api/llm/status")
def api_llm_status(probe: bool = False):
    try:
        from strategy import conversation_llm as studio_conversation_llm

        available = studio_conversation_llm.llm_available()
        status = studio_run.llm_decisioning.get_llm_status()
        diagnostics = dict(status.get("diagnostics") or {})
        diagnostics["llm_available"] = available
        if probe and available:
            start = time.time()
            try:
                client = studio_conversation_llm._get_client()
                resp = client.messages.create(
                    model=studio_conversation_llm.MODEL,
                    max_tokens=20,
                    system="Return strict JSON only.",
                    messages=[{"role": "user", "content": "{\"ping\": true}"}],
                )
                text = next((block.text for block in resp.content if block.type == "text"), "")
                diagnostics["probe_ok"] = True
                diagnostics["probe_latency_ms"] = int((time.time() - start) * 1000)
                diagnostics["probe_preview"] = text[:120]
            except Exception as exc:  # noqa: BLE001 - expose the reachable/unreachable reason
                short = str(exc).strip().splitlines()[0][:500]
                status = {
                    "engine": "azure-foundry",
                    "ok": False,
                    "detail": f"Studio LLM live probe failed ({type(exc).__name__}: {short})",
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                diagnostics["probe_ok"] = False
                diagnostics["probe_exception_type"] = type(exc).__name__
                diagnostics["probe_exception"] = short
        return {"available": available, "status": {**status, "diagnostics": diagnostics}}
    except Exception as exc:  # noqa: BLE001 - diagnostics endpoint must report, not fail closed
        short = str(exc).strip().splitlines()[0][:500]
        return {
            "available": False,
            "status": {
                "engine": "azure-foundry",
                "ok": False,
                "detail": f"Studio LLM status check failed ({type(exc).__name__}: {short})",
                "diagnostics": {"exception_type": type(exc).__name__, "exception": short},
            },
        }


@app.post("/api/auto-run")
def post_auto_run(req: AutoRunRequest):
    return run_full_analysis(req.brand, req.therapy_area, req.lifecycle_key, req.budget)


@app.post("/api/generate-strategy")
def post_generate_strategy(req: StrategyRequest):
    return generate_strategy(req.brand, req.therapy_area, req.persona, req.stage_key)


@app.post("/api/competitive-analysis")
def post_competitive_analysis(req: CompetitiveRequest):
    competitors = [c.strip() for c in req.competitors if c.strip()]
    return build_swot(req.brand, competitors, req.therapy_area)


@app.post("/api/market-landscape")
def post_market_landscape(req: MarketLandscapeRequest):
    return market_landscape(req.brand, req.therapy_area)


@app.post("/api/positioning-statement")
def post_positioning_statement(req: PositioningRequest):
    competitors = [c.strip() for c in req.competitors if c.strip()]
    return build_positioning_statement(req.brand, req.therapy_area, req.persona, req.stage_key, competitors)


@app.post("/api/kpi-framework")
def post_kpi_framework(req: KpiRequest):
    return build_kpi_framework(req.stage_key, req.channel_mix_pct)


# ------------------------------------------------------------------ #
# HCP 360: synthetic demographics/affinity/TRx/writer-status data,
# reviewable at /hcp360 (see also strategy/hcp_360.py)
# ------------------------------------------------------------------ #

@app.get("/api/hcp360")
def api_hcp360_stats():
    """Row counts per table -- confirms the store is loaded."""
    return hcp_360.stats()


@app.get("/api/hcp360/hcps")
def api_hcp360_list(specialty: str = "", state: str = "", brand_writer: str = "", limit: int = 100):
    """Filtered roster (demographic summary rows)."""
    return hcp_360.list_hcps(specialty=specialty or None, state=state or None,
                              brand_writer=brand_writer or None, limit=limit)


@app.get("/api/hcp360/hcps/{npi}")
def api_hcp360_detail(npi: int):
    """One HCP's full 360 view: demographics + channel/content affinity + day/time
    preference + writer status + TRx."""
    hcp = hcp_360.get_hcp(npi)
    if not hcp:
        raise HTTPException(404, f"no HCP with npi {npi}")
    return hcp


@app.get("/api/hcp360/segment/{group_by}")
def api_hcp360_segment(group_by: str):
    """Panel counts grouped by one allow-listed dimension (specialty/state/preferred_channel/
    segment/writing_persona/brand) -- powers the Reporting tab's demographic breakdowns."""
    try:
        return {"group_by": group_by, "rows": hcp_360.segment_summary(group_by)}
    except ValueError as e:
        raise HTTPException(400, str(e))


class HcpAskRequest(BaseModel):
    question: str


@app.post("/api/hcp360/ask")
def api_hcp360_ask(req: HcpAskRequest):
    """Free-text Q&A over the panel -- the LLM calls list_hcps/get_hcp/segment_summary
    (strategy/hcp_360.py's bounded tool-use loop) to answer, e.g. 'segment HCPs by
    preferred channel' or 'how many oncologists write Xalkori'."""
    return hcp_360.ask(req.question)


@app.get("/hcp360")
def root_hcp360():
    """Standalone review page for the HCP 360 data store (plain HTML/JS, no frontend
    build required)."""
    return FileResponse(APP_DIR / "static" / "hcp360.html")


@app.get("/")
def root():
    """New React + MUI front-end (built by frontend/ via Vite into static/v2) is now the
    default landing experience -- migration complete enough to promote it off /v2."""
    return FileResponse(APP_DIR / "static" / "v2" / "index.html")


@app.get("/v2")
def root_v2():
    """Kept as an alias to / so any existing /v2 links/bookmarks keep working."""
    return FileResponse(APP_DIR / "static" / "v2" / "index.html")


@app.get("/legacy")
def root_legacy():
    """Old static/JS front-end, kept reachable (not deleted) in case of rollback or reference
    during the migration."""
    return FileResponse(APP_DIR / "static" / "index.html")


app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
