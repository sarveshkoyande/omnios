"""FDA oncology/hematology approval-notification scraper.

Captures FDA's public oncology and hematologic malignancy approval-notification page.
Structured extraction into approval timeline records is handled by `pharma_intel.py`.
"""
from __future__ import annotations

import hashlib
import time
from urllib.robotparser import RobotFileParser

import requests

from html_extract import extract_title as _extract_title_raw, html_to_text as _html_to_text
from storage import get_db, save_blob, upsert_document

URL = "https://www.fda.gov/drugs/resources-information-approved-drugs/oncology-cancerhematologic-malignancies-approval-notifications"
USER_AGENT = "OmniDataHubResearchBot/0.1 (+local research; FDA oncology approvals public page)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
}


def _can_fetch() -> bool:
    rp = RobotFileParser()
    rp.set_url("https://www.fda.gov/robots.txt")
    try:
        rp.read()
    except Exception:
        return False
    return rp.can_fetch(USER_AGENT, URL)


def _extract_title(raw_html: str) -> str:
    return _extract_title_raw(raw_html, "FDA Oncology/Hematologic Malignancies Approval Notifications")


def run() -> int:
    conn = get_db()
    try:
        if not _can_fetch():
            print("[fda_oncology_approvals] notifications: blocked_by_robots")
            return 0
        resp = requests.get(URL, headers=HEADERS, timeout=30)
        if resp.status_code in {401, 402, 403, 404}:
            print(f"[fda_oncology_approvals] notifications: http_{resp.status_code}")
            return 0
        resp.raise_for_status()
        resp.encoding = "utf-8"  # requests' auto-detected encoding mangles (R)/em-dashes on some sites

        text = _html_to_text(resp.text)
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
        blob_path = save_blob("fda_oncology_approvals", f"notifications_{digest}.txt", text)
        upsert_document(
            conn,
            source="fda_oncology_approvals:notifications",
            external_id=digest,
            search_term="FDA oncology hematology approvals",
            title=_extract_title(resp.text),
            doc_type="oncology_approval_notifications",
            url=URL,
            blob_path=blob_path,
            metadata={
                "agency": "FDA",
                "category": "oncology_hematology_approval_notifications",
                "content_length": len(text),
            },
        )
        print("[fda_oncology_approvals] notifications: saved")
        time.sleep(0.5)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    run()
