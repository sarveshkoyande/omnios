"""openFDA NDC Directory scraper.

Pulls bounded marketed-product/package records for oncology-priority brand and
generic terms. The NDC Directory is useful for package, labeler, route, dosage
form, and marketing-category context; openFDA cautions that listing does not mean
FDA has verified submitted product information.
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
BASE_URL = "https://api.fda.gov/drug/ndc.json"
USER_AGENT = "OmniDataHubResearchBot/0.1 (+local research; openFDA NDC Directory records)"
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


def _fetch(search: str, limit: int) -> dict[str, Any]:
    resp = requests.get(BASE_URL, params={"search": search, "limit": limit}, headers=HEADERS, timeout=30)
    if resp.status_code == 404:
        return {"meta": {"results": {"total": 0}}, "results": []}
    resp.raise_for_status()
    return resp.json()


def fetch_for_term(conn, brand: str, term: str, field: str, limit: int) -> int:
    search = f'{field}:"{term}"'
    payload = _fetch(search, limit)
    rows = payload.get("results") or []
    if not rows:
        return 0
    meta = payload.get("meta") or {}
    blob_path = save_blob(
        "openfda_ndc",
        f"ndc_{_slug(brand)}_{field}_{_slug(term)}.json",
        json.dumps(payload, indent=2),
    )
    total = (meta.get("results") or {}).get("total", "")
    upsert_document(
        conn,
        source="openfda:drug_ndc",
        external_id=f"{_slug(brand)}_{field}_{_slug(term)}",
        search_term=brand,
        title=f"openFDA NDC Directory records for {brand} via {term}",
        doc_type="ndc_directory_records",
        url=f"{BASE_URL}?search={search}",
        blob_path=blob_path,
        metadata={
            "brand": brand,
            "query_term": term,
            "query_field": field,
            "row_count": len(rows),
            "total_available": total,
            "last_updated": meta.get("last_updated", ""),
            "source_disclaimer": meta.get("disclaimer", ""),
        },
    )
    return 1


def run(brands: list[str] | None = None, max_brands: int | None = 18, per_term_limit: int = 50) -> int:
    if brands is None:
        brands = _seed_brands(max_brands)
    elif max_brands:
        brands = brands[:max_brands]
    generics = _generic_terms_for_brands(brands)

    conn = get_db()
    saved = 0
    try:
        for brand in brands:
            terms = [("brand_name", brand)]
            terms.extend(("generic_name", term) for term in generics.get(brand, []))
            seen_terms: set[str] = set()
            for field, term in terms:
                key = f"{field}:{term.lower()}"
                if key in seen_terms:
                    continue
                seen_terms.add(key)
                try:
                    n = fetch_for_term(conn, brand, term, field, per_term_limit)
                    saved += n
                    if n:
                        print(f"[openfda_ndc] {brand} / {field}:{term}: saved")
                except Exception as exc:
                    print(f"[openfda_ndc] {brand} / {field}:{term}: FAILED ({exc})")
                time.sleep(0.25)
    finally:
        conn.close()
    return saved


if __name__ == "__main__":
    run()
