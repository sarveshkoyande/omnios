"""openFDA FAERS adverse-event count scraper.

This stores aggregate safety-signal counts by brand rather than individual case
reports. FAERS/openFDA data is unvalidated spontaneous reporting, so downstream
views must treat it as signal context, not incidence or comparative safety proof.
"""
from __future__ import annotations

import json
import pathlib
import time
from typing import Any

import requests

from storage import get_db, save_blob, upsert_document

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
SEEDS_PATH = BASE_DIR / "config" / "pharma_intel_seed_terms.json"
BASE_URL = "https://api.fda.gov/drug/event.json"
USER_AGENT = "OmniDataHubResearchBot/0.1 (+local research; aggregate openFDA FAERS counts)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}


def _count_query(brand: str, count_field: str, limit: int) -> dict[str, Any]:
    params = {
        "search": f'patient.drug.openfda.brand_name:"{brand}"',
        "count": count_field,
        "limit": limit,
    }
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
    if resp.status_code == 404:
        return {"meta": {}, "results": []}
    resp.raise_for_status()
    return resp.json()


def fetch_for_brand(conn, brand: str, reaction_limit: int = 25) -> int:
    reactions = _count_query(brand, "patient.reaction.reactionmeddrapt.exact", reaction_limit)
    seriousness = _count_query(brand, "serious", 5)
    payload = {
        "brand": brand,
        "reaction_counts": reactions.get("results", []),
        "serious_counts": seriousness.get("results", []),
        "meta": reactions.get("meta") or seriousness.get("meta") or {},
    }
    blob_path = save_blob(
        "openfda_events",
        f"faers_counts_{brand.lower().replace(' ', '_')}.json",
        json.dumps(payload, indent=2),
    )
    upsert_document(
        conn,
        source="openfda:drug_event",
        external_id=brand.lower(),
        search_term=brand,
        title=f"openFDA FAERS adverse-event counts for {brand}",
        doc_type="faers_adverse_event_counts",
        url=f"https://api.fda.gov/drug/event.json?search=patient.drug.openfda.brand_name:{brand}",
        blob_path=blob_path,
        metadata={
            "brand": brand,
            "reaction_count_rows": len(payload["reaction_counts"]),
            "serious_count_rows": len(payload["serious_counts"]),
            "last_updated": payload["meta"].get("last_updated", ""),
            "source_disclaimer": payload["meta"].get("disclaimer", ""),
        },
    )
    time.sleep(0.2)
    return 1


def run(brands: list[str] | None = None, max_brands: int | None = None, reaction_limit: int = 25) -> int:
    if brands is None:
        seeds = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
        brands = seeds.get("priority_oncology_brands", [])
    if max_brands:
        brands = brands[:max_brands]

    conn = get_db()
    total = 0
    try:
        for brand in brands:
            try:
                total += fetch_for_brand(conn, brand, reaction_limit=reaction_limit)
                print(f"[openfda_events] {brand}: saved")
            except Exception as exc:
                print(f"[openfda_events] {brand}: FAILED ({exc})")
            time.sleep(0.3)
    finally:
        conn.close()
    return total


if __name__ == "__main__":
    run(max_brands=12)
