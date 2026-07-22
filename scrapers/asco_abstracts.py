"""ASCO Annual Meeting public abstract-list scraper."""
from __future__ import annotations

import hashlib
import time

import requests

from html_extract import extract_title as _title_raw, html_to_text as _html_to_text
from storage import get_db, save_blob, upsert_document

PAGE_URL = "https://www.asco.org/annual-meeting/program/abstracts-posters"
ABSTRACT_CSV_URL = "https://d32wbias3z7pxg.cloudfront.net/abstract-exports/335/meeting_335_abstracts.csv"
USER_AGENT = "OmniDataHubResearchBot/0.1 (+local research; ASCO public abstract list)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/csv,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.5",
}


def _title(raw_html: str, fallback: str) -> str:
    return _title_raw(raw_html or "", fallback)


def run() -> int:
    conn = get_db()
    written = 0
    try:
        page = requests.get(PAGE_URL, headers=HEADERS, timeout=45)
        if page.status_code == 200:
            page.encoding = "utf-8"  # requests' auto-detected encoding mangles (R)/em-dashes on some sites
            page_id = hashlib.sha1(PAGE_URL.encode("utf-8")).hexdigest()[:16]
            page_text = _html_to_text(page.text)
            page_blob = save_blob("asco_abstracts", f"abstracts_posters_{page_id}.txt", page_text)
            upsert_document(
                conn,
                source="asco:abstracts_posters_page",
                external_id=page_id,
                search_term="ASCO 2026 abstracts posters",
                title=_title(page.text, "ASCO Abstracts & Posters"),
                doc_type="conference_abstract_index",
                url=PAGE_URL,
                blob_path=page_blob,
                metadata={"conference": "ASCO Annual Meeting", "year": 2026, "content_length": len(page_text)},
            )
            written += 1
            print("[asco_abstracts] abstracts_posters_page: saved")
        else:
            print(f"[asco_abstracts] abstracts_posters_page: http_{page.status_code}")

        csv_resp = requests.get(ABSTRACT_CSV_URL, headers=HEADERS, timeout=120)
        csv_resp.raise_for_status()
        csv_resp.encoding = csv_resp.encoding or "utf-8-sig"
        csv_id = "asco_2026_annual_meeting_abstracts_csv"
        csv_blob = save_blob("asco_abstracts", "meeting_335_abstracts.csv", csv_resp.text)
        upsert_document(
            conn,
            source="asco:abstract_list_csv",
            external_id=csv_id,
            search_term="ASCO 2026 annual meeting abstracts",
            title="2026 ASCO Annual Meeting Full Abstract List",
            doc_type="conference_abstract_csv",
            url=ABSTRACT_CSV_URL,
            blob_path=csv_blob,
            metadata={
                "conference": "ASCO Annual Meeting",
                "year": 2026,
                "content_type": csv_resp.headers.get("content-type", ""),
                "content_length": len(csv_resp.content),
            },
        )
        written += 1
        print("[asco_abstracts] abstract_list_csv: saved")
        time.sleep(0.5)
        return written
    finally:
        conn.close()


if __name__ == "__main__":
    run()
