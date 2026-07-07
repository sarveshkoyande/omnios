"""DailyMed (NIH/NLM) SPL scraper -- public, keyless API."""
from __future__ import annotations

import json
import time
import requests

from storage import get_db, save_blob, upsert_document

BASE_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2"


def fetch_for_term(conn, term: str, limit: int = 5) -> int:
    count = 0
    resp = requests.get(f"{BASE_URL}/spls.json", params={"drug_name": term, "pagesize": limit}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    save_blob("dailymed", f"search_{term.replace(' ', '_')}.json", resp.text)

    for entry in data.get("data", [])[:limit]:
        setid = entry.get("setid")
        title = entry.get("title") or entry.get("spl_version") or setid
        if not setid:
            continue
        blob_path = save_blob("dailymed", f"spl_{setid}.json", json.dumps(entry, indent=2))
        upsert_document(
            conn,
            source="dailymed",
            external_id=setid,
            search_term=term,
            title=title,
            doc_type="spl_label",
            url=f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}",
            blob_path=blob_path,
            metadata=entry,
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
            print(f"[dailymed] {term}: {n} SPLs")
            total += n
        except Exception as e:
            print(f"[dailymed] {term}: FAILED ({e})")
        time.sleep(0.3)
    conn.close()
    return total


if __name__ == "__main__":
    import json
    import pathlib

    seeds = json.loads((pathlib.Path(__file__).resolve().parent.parent / "config" / "seed_terms.json").read_text())
    run(seeds["drugs"])
