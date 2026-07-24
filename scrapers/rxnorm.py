"""NLM RxNorm / RxNav scraper.

Resolves oncology-priority brand and generic terms to RxNorm identifiers and
captures related concept groups. This improves cross-source normalization across
labels, NDC packages, trials, recalls, shortages, and literature.
"""
from __future__ import annotations

import json
import pathlib
import re
import sqlite3
import time
from typing import Any

import requests

from storage import DB_PATH, get_db, save_blob, upsert_document

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
SEEDS_PATH = BASE_DIR / "config" / "pharma_intel_seed_terms.json"
BASE_URL = "https://rxnav.nlm.nih.gov/REST"
USER_AGENT = "OmniDataHubResearchBot/0.1 (+local research; RxNorm vocabulary records)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "term"


def _seed_brands(max_brands: int | None) -> list[str]:
    seeds = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
    brands = [str(brand).strip() for brand in seeds.get("priority_oncology_brands", []) if str(brand).strip()]
    return brands[:max_brands] if max_brands else brands


def _generic_terms_for_brands(brands: list[str], max_generics_per_brand: int = 2) -> dict[str, list[str]]:
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
                )
                WHERE generic_name IS NOT NULL AND trim(generic_name) <> ''
                LIMIT ?
                """,
                (brand, brand, brand, max_generics_per_brand),
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


def _get_json(path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    resp = requests.get(f"{BASE_URL}{path}", params=params or {}, headers=HEADERS, timeout=30)
    if resp.status_code == 404:
        return {}
    resp.raise_for_status()
    return resp.json()


def fetch_for_term(conn, brand: str, term: str, term_type: str) -> int:
    rxcui_payload = _get_json("/rxcui.json", {"name": term, "search": "1"})
    ids = (rxcui_payload.get("idGroup") or {}).get("rxnormId") or []
    if not ids:
        return 0
    rxcui = str(ids[0])
    properties = _get_json(f"/rxcui/{rxcui}/properties.json")
    related = _get_json(f"/rxcui/{rxcui}/allrelated.json")
    historical_ndcs = _get_json(f"/rxcui/{rxcui}/allhistoricalndcs.json")
    payload = {
        "brand": brand,
        "query_term": term,
        "term_type": term_type,
        "rxcui": rxcui,
        "rxcui_response": rxcui_payload,
        "properties": properties.get("properties") or {},
        "related": related,
        "historical_ndcs": historical_ndcs,
    }
    blob_path = save_blob(
        "rxnorm",
        f"rxnorm_{_slug(brand)}_{term_type}_{_slug(term)}.json",
        json.dumps(payload, indent=2),
    )
    source_name = (payload["properties"] or {}).get("name") or term
    upsert_document(
        conn,
        source="rxnav:rxnorm",
        external_id=f"{_slug(brand)}_{term_type}_{_slug(term)}_{rxcui}",
        search_term=brand,
        title=f"RxNorm concept {rxcui}: {source_name}",
        doc_type="rxnorm_concept_records",
        url=f"{BASE_URL}/rxcui.json?name={term}&search=1",
        blob_path=blob_path,
        metadata={
            "brand": brand,
            "query_term": term,
            "term_type": term_type,
            "rxcui": rxcui,
            "tty": (payload["properties"] or {}).get("tty", ""),
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
                key = f"{term_type}:{term.lower()}"
                if key in seen:
                    continue
                seen.add(key)
                try:
                    n = fetch_for_term(conn, brand, term, term_type)
                    saved += n
                    if n:
                        print(f"[rxnorm] {brand} / {term}: saved")
                except Exception as exc:
                    print(f"[rxnorm] {brand} / {term}: FAILED ({exc})")
                time.sleep(0.2)
    finally:
        conn.close()
    return saved


if __name__ == "__main__":
    run()
