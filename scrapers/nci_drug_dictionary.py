"""NCI Drug Dictionary scraper.

Fetches structured drug/agent definitions from the public NCI Drug Dictionary
API for oncology-priority brand/generic terms. Brand names are mapped through
label-derived generic names because the NCI endpoint is most reliable for
preferred/generic names such as pembrolizumab.
"""
from __future__ import annotations

import json
import pathlib
import re
import sqlite3
import time
from typing import Any
from urllib.parse import quote

import requests

from storage import DB_PATH, get_db, save_blob, upsert_document

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
SEEDS_PATH = BASE_DIR / "config" / "pharma_intel_seed_terms.json"
BASE_URL = "https://webapis.cancer.gov/drugdictionary/v1"
USER_AGENT = "OmniDataHubResearchBot/0.1 (+local research; NCI Drug Dictionary records)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "term"


def _seed_brands(max_brands: int | None) -> list[str]:
    seeds = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
    brands = [str(brand).strip() for brand in seeds.get("priority_oncology_brands", []) if str(brand).strip()]
    return brands[:max_brands] if max_brands else brands


def _generic_terms_for_brands(brands: list[str], max_generics_per_brand: int = 3) -> dict[str, list[str]]:
    if not DB_PATH.exists():
        return {}
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    out: dict[str, list[str]] = {}
    try:
        for brand in brands:
            rows = conn.execute(
                """
                SELECT generic_name
                FROM (
                    SELECT generic_name FROM regulatory_label_message WHERE lower(brand)=lower(?)
                    UNION
                    SELECT generic_name FROM dailymed_label WHERE lower(search_term)=lower(?) OR lower(brand)=lower(?)
                    UNION
                    SELECT generic_name FROM openfda_ndc_product WHERE lower(matched_brand)=lower(?)
                )
                WHERE generic_name IS NOT NULL AND trim(generic_name) <> ''
                LIMIT ?
                """,
                (brand, brand, brand, brand, max_generics_per_brand),
            ).fetchall()
            terms = []
            for row in rows:
                generic = str(row["generic_name"]).strip()
                if generic and generic.lower() != brand.lower():
                    terms.append(generic)
            if terms:
                out[brand] = terms
    except sqlite3.Error:
        return {}
    finally:
        conn.close()
    return out


def _get_drug(term: str) -> dict[str, Any]:
    resp = requests.get(f"{BASE_URL}/Drugs/{quote(term)}", headers=HEADERS, timeout=30)
    if resp.status_code == 404:
        return {}
    resp.raise_for_status()
    return resp.json()


def _term_candidates(term: str) -> list[str]:
    base = re.sub(r"\s+", " ", term.strip()).strip()
    variants = [
        base,
        base.lower(),
        re.sub(r"\([^)]*\)", "", base).strip().lower(),
        re.sub(r"\b(maleate|mesylate|succinate|hydrochloride|sodium|form\s+[a-z0-9]+|premix)\b", "", base, flags=re.I).strip().lower(),
    ]
    for sep in [" and ", ";", "/"]:
        if sep in base.lower():
            variants.extend(part.strip().lower() for part in re.split(sep, base, flags=re.I) if part.strip())
    out: list[str] = []
    seen: set[str] = set()
    for value in variants:
        value = re.sub(r"\s+", " ", value).strip(" ,-")
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def fetch_for_term(conn, brand: str, term: str, term_type: str) -> int:
    payload: dict[str, Any] = {}
    resolved_term = term
    for candidate in _term_candidates(term):
        payload = _get_drug(candidate)
        if payload and payload.get("termId"):
            resolved_term = candidate
            break
    if not payload or not payload.get("termId"):
        return 0
    term_id = str(payload.get("termId"))
    blob_path = save_blob(
        "nci_drug_dictionary",
        f"nci_drug_dictionary_{_slug(brand)}_{term_type}_{_slug(resolved_term)}_{term_id}.json",
        json.dumps(payload, indent=2),
    )
    upsert_document(
        conn,
        source="nci:drug_dictionary",
        external_id=f"{_slug(brand)}_{term_type}_{_slug(resolved_term)}_{term_id}",
        search_term=brand,
        title=f"NCI Drug Dictionary: {payload.get('nciConceptName') or payload.get('name') or term}",
        doc_type="nci_drug_dictionary_entry",
        url=f"{BASE_URL}/Drugs/{quote(resolved_term)}",
        blob_path=blob_path,
        metadata={
            "brand": brand,
            "query_term": term,
            "resolved_term": resolved_term,
            "term_type": term_type,
            "term_id": term_id,
            "nci_concept_id": payload.get("nciConceptId", ""),
            "nci_concept_name": payload.get("nciConceptName", ""),
            "alias_count": len(payload.get("aliases") or []),
        },
    )
    return 1


def run(brands: list[str] | None = None, max_brands: int | None = 18) -> int:
    if brands is None:
        brands = _seed_brands(max_brands)
    elif max_brands:
        brands = brands[:max_brands]
    generics = _generic_terms_for_brands(brands)

    conn = get_db()
    saved = 0
    try:
        for brand in brands:
            terms = [("brand", brand)]
            terms.extend(("generic", term) for term in generics.get(brand, []))
            seen: set[str] = set()
            for term_type, term in terms:
                key = term.lower()
                if key in seen:
                    continue
                seen.add(key)
                try:
                    n = fetch_for_term(conn, brand, term, term_type)
                    saved += n
                    if n:
                        print(f"[nci_drug_dictionary] {brand} / {term}: saved")
                except Exception as exc:
                    print(f"[nci_drug_dictionary] {brand} / {term}: FAILED ({exc})")
                time.sleep(0.2)
    finally:
        conn.close()
    return saved


if __name__ == "__main__":
    run()
