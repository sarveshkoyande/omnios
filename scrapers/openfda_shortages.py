"""openFDA drug-shortages scraper.

Pulls FDA's current/resolved shortage records for the Oncology therapeutic
category. This supports access-risk and patient-support planning; it is not
brand demand or utilization evidence.
"""
from __future__ import annotations

import json
import time
from typing import Any

import requests

from storage import get_db, save_blob, upsert_document

BASE_URL = "https://api.fda.gov/drug/shortages.json"
USER_AGENT = "OmniDataHubResearchBot/0.1 (+local research; openFDA shortage records)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}


def _fetch_page(search: str, limit: int, skip: int) -> dict[str, Any]:
    resp = requests.get(BASE_URL, params={"search": search, "limit": limit, "skip": skip}, headers=HEADERS, timeout=30)
    if resp.status_code == 404:
        return {"meta": {"results": {"total": 0}}, "results": []}
    resp.raise_for_status()
    return resp.json()


def run(search: str = 'therapeutic_category:"Oncology"', page_size: int = 100, max_records: int = 300) -> int:
    conn = get_db()
    saved = 0
    try:
        skip = 0
        while skip < max_records:
            payload = _fetch_page(search, min(page_size, max_records - skip), skip)
            rows = payload.get("results", [])
            if not rows:
                break
            meta = payload.get("meta", {})
            blob_path = save_blob("openfda_shortages", f"oncology_shortages_skip_{skip}.json", json.dumps(payload, indent=2))
            total = (meta.get("results") or {}).get("total", "")
            upsert_document(
                conn,
                source="openfda:drug_shortages",
                external_id=f"oncology_{skip}",
                search_term="oncology",
                title=f"openFDA oncology drug shortages rows {skip + 1}-{skip + len(rows)}",
                doc_type="drug_shortage_records",
                url=f"{BASE_URL}?search={search}",
                blob_path=blob_path,
                metadata={
                    "search": search,
                    "skip": skip,
                    "row_count": len(rows),
                    "total_available": total,
                    "last_updated": meta.get("last_updated", ""),
                    "source_disclaimer": meta.get("disclaimer", ""),
                },
            )
            saved += 1
            skip += len(rows)
            if skip >= int(total or skip) or len(rows) < page_size:
                break
            time.sleep(0.4)
    finally:
        conn.close()
    return saved


if __name__ == "__main__":
    run()
