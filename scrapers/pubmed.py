"""PubMed (NCBI E-utilities) scraper -- public, keyless (rate-limited to 3 req/sec)."""
from __future__ import annotations

import json
import time
import requests
import xml.etree.ElementTree as ET

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

from storage import get_db, save_blob, upsert_document


def fetch_for_term(conn, term: str, limit: int = 5) -> int:
    search_resp = requests.get(
        ESEARCH,
        params={"db": "pubmed", "term": term, "retmax": limit, "retmode": "json"},
        timeout=30,
    )
    search_resp.raise_for_status()
    ids = search_resp.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return 0

    time.sleep(0.4)
    fetch_resp = requests.get(
        EFETCH,
        params={"db": "pubmed", "id": ",".join(ids), "retmode": "xml"},
        timeout=30,
    )
    fetch_resp.raise_for_status()
    save_blob("pubmed", f"search_{term.replace(' ', '_')}.xml", fetch_resp.text)

    root = ET.fromstring(fetch_resp.content)
    count = 0
    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//PMID")
        pmid = pmid_el.text if pmid_el is not None else None
        title_el = article.find(".//ArticleTitle")
        title = "".join(title_el.itertext()) if title_el is not None else pmid
        journal_el = article.find(".//Journal/Title")
        journal = journal_el.text if journal_el is not None else None
        year_el = article.find(".//PubDate/Year")
        year = year_el.text if year_el is not None else None
        abstract_parts = [t for t in article.itertext()] if article is not None else []
        if not pmid:
            continue

        blob_path = save_blob("pubmed", f"article_{pmid}.json", json.dumps({
            "pmid": pmid, "title": title, "journal": journal, "year": year,
        }, indent=2))
        upsert_document(
            conn,
            source="pubmed",
            external_id=pmid,
            search_term=term,
            title=title or pmid,
            doc_type="journal_article",
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            blob_path=blob_path,
            metadata={"journal": journal, "year": year},
        )
        count += 1
    return count


def run(terms: list[str]) -> int:
    conn = get_db()
    total = 0
    for term in terms:
        try:
            n = fetch_for_term(conn, term)
            print(f"[pubmed] {term}: {n} articles")
            total += n
        except Exception as e:
            print(f"[pubmed] {term}: FAILED ({e})")
        time.sleep(0.4)
    conn.close()
    return total


if __name__ == "__main__":
    import pathlib

    seeds = json.loads((pathlib.Path(__file__).resolve().parent.parent / "config" / "seed_terms.json").read_text())
    run(seeds["drugs"] + seeds["therapy_areas"])
