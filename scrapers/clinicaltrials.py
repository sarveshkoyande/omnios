"""ClinicalTrials.gov v2 API scraper -- public, keyless."""
from __future__ import annotations

import json
import time
import requests

from storage import get_db, save_blob, upsert_document

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"


def fetch_for_term(conn, term: str, limit: int = 5) -> int:
    count = 0
    params = {"query.term": term, "pageSize": limit}
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    save_blob("clinicaltrials", f"search_{term.replace(' ', '_')}.json", resp.text)

    for study in data.get("studies", [])[:limit]:
        protocol = study.get("protocolSection", {})
        ident = protocol.get("identificationModule", {})
        status_mod = protocol.get("statusModule", {})
        design = protocol.get("designModule", {})
        conditions_mod = protocol.get("conditionsModule", {})

        nct_id = ident.get("nctId")
        if not nct_id:
            continue
        title = ident.get("briefTitle", nct_id)
        blob_path = save_blob("clinicaltrials", f"study_{nct_id}.json", json.dumps(study, indent=2))
        upsert_document(
            conn,
            source="clinicaltrials",
            external_id=nct_id,
            search_term=term,
            title=title,
            doc_type="trial_record",
            url=f"https://clinicaltrials.gov/study/{nct_id}",
            blob_path=blob_path,
            metadata={
                "status": status_mod.get("overallStatus"),
                "phase": design.get("phases"),
                "conditions": conditions_mod.get("conditions"),
            },
        )
        count += 1
        time.sleep(0.2)
    return count


def run(terms: list[str]) -> int:
    conn = get_db()
    total = 0
    for term in terms:
        try:
            n = fetch_for_term(conn, term)
            print(f"[clinicaltrials] {term}: {n} studies")
            total += n
        except Exception as e:
            print(f"[clinicaltrials] {term}: FAILED ({e})")
        time.sleep(0.3)
    conn.close()
    return total


if __name__ == "__main__":
    import pathlib

    seeds = json.loads((pathlib.Path(__file__).resolve().parent.parent / "config" / "seed_terms.json").read_text())
    run(seeds["drugs"] + seeds["therapy_areas"])
