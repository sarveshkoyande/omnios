"""SEC EDGAR company-submissions scraper for top pharma companies.

Fetches public `data.sec.gov/submissions/CIK##########.json` records for a curated
top-pharma CIK/ticker seed list. Structured filing metadata is loaded by
`pharma_intel.py`.
"""
from __future__ import annotations

import json
import pathlib
import time

import requests

from storage import get_db, save_blob, upsert_document

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "sec_top_pharma_companies.json"
USER_AGENT = "OmniDataHubResearchBot/0.1 research-contact@example.com"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json",
}


def _submissions_url(cik: str) -> str:
    return f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"


def run(companies: list[dict] | None = None) -> int:
    if companies is None:
        companies = json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("companies", [])

    conn = get_db()
    saved = 0
    try:
        for company in companies:
            cik = company["cik"].zfill(10)
            url = _submissions_url(cik)
            try:
                resp = requests.get(url, headers=HEADERS, timeout=30)
                if resp.status_code in {401, 403, 404}:
                    print(f"[sec_edgar] {company['ticker']}: http_{resp.status_code}")
                    continue
                resp.raise_for_status()
                data = resp.json()
                blob_path = save_blob("sec_edgar", f"{cik}_{company['ticker']}_submissions.json", json.dumps(data, indent=2))
                upsert_document(
                    conn,
                    source="sec_edgar:submissions",
                    external_id=cik,
                    search_term=company["company"],
                    title=f"SEC submissions for {company['company']} ({company['ticker']})",
                    doc_type="sec_company_submissions",
                    url=url,
                    blob_path=blob_path,
                    metadata={
                        "company": company["company"],
                        "ticker": company["ticker"],
                        "cik": cik,
                        "forms": company.get("forms", []),
                        "sec_name": data.get("name", ""),
                    },
                )
                saved += 1
                print(f"[sec_edgar] {company['ticker']}: saved")
            except Exception as exc:
                print(f"[sec_edgar] {company.get('ticker', company.get('company'))}: FAILED ({exc})")
            time.sleep(0.2)
    finally:
        conn.close()
    return saved


if __name__ == "__main__":
    run()
