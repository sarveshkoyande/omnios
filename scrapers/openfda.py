"""openFDA drug label scraper -- public, keyless API (rate-limited to 240 req/min)."""
from __future__ import annotations

import json
import time
import requests

from storage import get_db, save_blob, upsert_document

BASE_URL = "https://api.fda.gov/drug/label.json"


def fetch_for_term(conn, term: str, limit: int = 3) -> int:
    count = 0
    params = {"search": f'openfda.brand_name:"{term}"', "limit": limit}
    resp = requests.get(BASE_URL, params=params, timeout=30)
    if resp.status_code == 404:
        return 0
    resp.raise_for_status()
    data = resp.json()
    save_blob("openfda", f"search_{term.replace(' ', '_')}.json", resp.text)

    for entry in data.get("results", [])[:limit]:
        openfda = entry.get("openfda", {})
        set_id = entry.get("set_id") or (openfda.get("spl_id") or [None])[0] or term
        title = (openfda.get("brand_name") or [term])[0]
        blob_path = save_blob("openfda", f"label_{set_id}.json", json.dumps(entry, indent=2))
        upsert_document(
            conn,
            source="openfda",
            external_id=str(set_id),
            search_term=term,
            title=title,
            doc_type="drug_label",
            url=f"https://api.fda.gov/drug/label.json?search=openfda.brand_name:{title}",
            blob_path=blob_path,
            metadata={
                "manufacturer": openfda.get("manufacturer_name"),
                "route": openfda.get("route"),
                "indications_and_usage": entry.get("indications_and_usage"),
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
            print(f"[openfda] {term}: {n} labels")
            total += n
        except Exception as e:
            print(f"[openfda] {term}: FAILED ({e})")
        time.sleep(0.3)
    conn.close()
    return total


if __name__ == "__main__":
    import pathlib

    seeds = json.loads((pathlib.Path(__file__).resolve().parent.parent / "config" / "seed_terms.json").read_text())
    run(seeds["drugs"])
