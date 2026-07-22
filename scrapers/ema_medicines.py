"""EMA centrally authorised medicines JSON downloader.

EMA publishes machine-readable JSON exports for its medicine website data. This
scraper stores the current medicine-pages JSON feed as a raw document; structured
normalisation happens in pharma_intel.py.
"""
from __future__ import annotations

import hashlib
import json
import time

import requests

from storage import get_db, save_blob, upsert_document

MEDICINES_URL = "https://www.ema.europa.eu/en/documents/report/medicines-output-medicines_json-report_en.json"
DOCUMENTS_URL = "https://www.ema.europa.eu/en/documents/report/documents-output-epar_documents_json-report_en.json"
PAGE_URL = "https://www.ema.europa.eu/en/about-us/about-website/download-website-data-json-data-format"
USER_AGENT = "OmniDataHubResearchBot/0.1 (+local research; EMA public JSON)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json,text/plain;q=0.8,*/*;q=0.5",
}


def _fetch_feed(
    conn,
    *,
    url: str,
    source: str,
    external_id: str,
    title: str,
    doc_type: str,
    filename_prefix: str,
) -> int:
    resp = requests.get(url, headers=HEADERS, timeout=120)
    resp.raise_for_status()
    text = resp.text
    timestamp = ""
    total_records = 0
    try:
        data = resp.json()
        timestamp = data.get("meta", {}).get("timestamp", "")
        total_records = data.get("meta", {}).get("total_records", len(data.get("data", [])))
        payload = json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        payload = text
        for line in text.splitlines()[:8]:
            stripped = line.strip().strip(",")
            if stripped.startswith('"total_records"'):
                total_records = int(stripped.split(":", 1)[1].strip())
            elif stripped.startswith('"timestamp"'):
                timestamp = stripped.split(":", 1)[1].strip().strip('"')
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    blob_path = save_blob("ema_medicines", f"{filename_prefix}_{digest}.json", payload)
    upsert_document(
        conn,
        source=source,
        external_id=external_id,
        search_term="EMA medicines",
        title=title,
        doc_type=doc_type,
        url=url,
        blob_path=blob_path,
        metadata={
            "source_page": PAGE_URL,
            "timestamp": timestamp,
            "total_records": total_records,
        },
    )
    print(f"[ema_medicines] {external_id}: saved {total_records} records")
    return 1


def run() -> int:
    conn = get_db()
    try:
        total = 0
        total += _fetch_feed(
            conn,
            url=MEDICINES_URL,
            source="ema_medicines:medicine_pages_json",
            external_id="medicine_pages_json",
            title="EMA medicine pages JSON data file",
            doc_type="ema_medicines_json",
            filename_prefix="ema_medicines",
        )
        total += _fetch_feed(
            conn,
            url=DOCUMENTS_URL,
            source="ema_medicines:epar_documents_json",
            external_id="epar_documents_json",
            title="EMA documents related to centrally authorised medicines JSON data file",
            doc_type="ema_epar_documents_json",
            filename_prefix="ema_epar_documents",
        )
        return total
    finally:
        conn.close()
        time.sleep(0.2)


if __name__ == "__main__":
    run()
