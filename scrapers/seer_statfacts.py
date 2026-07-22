"""NCI SEER Cancer Stat Facts scraper -- public, keyless HTML pages."""
from __future__ import annotations

import hashlib
import html as html_lib
import re
import time

import requests

from html_extract import html_to_text as _html_to_text
from storage import get_db, save_blob, upsert_document

SOURCES = [
    {"site": "Breast Cancer", "therapy_area": "breast cancer", "url": "https://seer.cancer.gov/statfacts/html/breast.html"},
    {"site": "Lung and Bronchus Cancer", "therapy_area": "lung cancer", "url": "https://seer.cancer.gov/statfacts/html/lungb.html"},
    {"site": "Prostate Cancer", "therapy_area": "prostate cancer", "url": "https://seer.cancer.gov/statfacts/html/prost.html"},
    {"site": "Colorectal Cancer", "therapy_area": "colorectal cancer", "url": "https://seer.cancer.gov/statfacts/html/colorect.html"},
    {"site": "Melanoma of the Skin", "therapy_area": "melanoma", "url": "https://seer.cancer.gov/statfacts/html/melan.html"},
    {"site": "Bladder Cancer", "therapy_area": "bladder cancer", "url": "https://seer.cancer.gov/statfacts/html/urinb.html"},
    {"site": "Kidney and Renal Pelvis Cancer", "therapy_area": "renal cell carcinoma", "url": "https://seer.cancer.gov/statfacts/html/kidrp.html"},
    {"site": "Non-Hodgkin Lymphoma", "therapy_area": "lymphoma", "url": "https://seer.cancer.gov/statfacts/html/nhl.html"},
    {"site": "Leukemia", "therapy_area": "leukemia", "url": "https://seer.cancer.gov/statfacts/html/leuks.html"},
    {"site": "Myeloma", "therapy_area": "multiple myeloma", "url": "https://seer.cancer.gov/statfacts/html/mulmy.html"},
]

HEADERS = {
    "User-Agent": "OmniDataHubResearchBot/0.1 (+local research; NCI SEER public Stat Facts)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
}

_ANY_TAG_RE = re.compile(r"<[^>]+>")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _plain(raw_html: str) -> str:
    return " ".join(_html_to_text(raw_html).split())


def _title(raw_html: str, fallback: str) -> str:
    match = _TITLE_RE.search(raw_html or "")
    if not match:
        return fallback
    title = html_lib.unescape(_ANY_TAG_RE.sub("", match.group(1))).strip()
    return title.split(" | ")[0].strip() or fallback


def _extract_stats(raw_html: str) -> dict[str, str | int | float | None]:
    text = _plain(raw_html)

    def number_after(label: str) -> int | None:
        match = re.search(rf"{re.escape(label)}\s+([0-9,]+)", text)
        return int(match.group(1).replace(",", "")) if match else None

    def percent_after(label: str) -> float | None:
        match = re.search(rf"{re.escape(label)}\s+([0-9.]+)%", text)
        return float(match.group(1)) if match else None

    return {
        "estimated_new_cases_2026": number_after("Estimated New Cases in 2026"),
        "percent_all_new_cases": percent_after("% of All New Cancer Cases"),
        "estimated_deaths_2026": number_after("Estimated Deaths in 2026"),
        "percent_all_cancer_deaths": percent_after("% of All Cancer Deaths"),
        "five_year_relative_survival_percent": percent_after("5-Year Relative Survival"),
    }


def run() -> int:
    conn = get_db()
    written = 0
    try:
        for entry in SOURCES:
            try:
                resp = requests.get(entry["url"], headers=HEADERS, timeout=45)
                if resp.status_code in {401, 402, 403, 404}:
                    print(f"[seer_statfacts] {entry['site']}: http_{resp.status_code}")
                    continue
                resp.raise_for_status()
                resp.encoding = "utf-8"  # requests' auto-detected encoding mangles (R)/em-dashes on some sites
                external_id = hashlib.sha1(entry["url"].encode("utf-8")).hexdigest()[:16]
                text = _html_to_text(resp.text)
                blob_path = save_blob("seer_statfacts", f"{external_id}.txt", text)
                metadata = {
                    "agency": "NCI",
                    "program": "SEER",
                    "site": entry["site"],
                    "therapy_area": entry["therapy_area"],
                    **_extract_stats(resp.text),
                    "content_length": len(text),
                }
                upsert_document(
                    conn,
                    source="seer:statfacts",
                    external_id=external_id,
                    search_term=entry["therapy_area"],
                    title=_title(resp.text, f"SEER Cancer Stat Facts: {entry['site']}"),
                    doc_type="epidemiology_statfacts",
                    url=entry["url"],
                    blob_path=blob_path,
                    metadata=metadata,
                )
                written += 1
                print(f"[seer_statfacts] {entry['site']}: saved")
            except Exception as exc:
                print(f"[seer_statfacts] {entry['site']}: FAILED ({exc})")
            time.sleep(0.2)
        return written
    finally:
        conn.close()


if __name__ == "__main__":
    run()
