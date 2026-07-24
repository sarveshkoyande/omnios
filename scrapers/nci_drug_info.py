"""NCI cancer drug information summary scraper.

Uses drug information links resolved from the NCI Drug Dictionary captures and
stores the public NCI patient-facing cancer drug summaries. These summaries add
approved-use context, update dates, related resources, and clinical-trial links
that complement FDA label sections and technical dictionary definitions.
"""
from __future__ import annotations

from html.parser import HTMLParser
import json
import pathlib
import re
import sqlite3
import time
from typing import Any

import requests

from storage import DB_PATH, get_db, save_blob, upsert_document

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
USER_AGENT = "OmniDataHubResearchBot/0.1 (+local research; NCI drug information summaries)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "term"


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self._skip_depth = 0
        self._href = ""
        self._link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if tag == "a" and not self._skip_depth:
            attrs_dict = {k.lower(): v or "" for k, v in attrs}
            self._href = attrs_dict.get("href", "")
            self._link_text = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "a" and self._href:
            label = " ".join(" ".join(self._link_text).split())
            if label:
                self.links.append({"text": label, "href": self._href})
            self._href = ""
            self._link_text = []
        if tag in {"p", "li", "h1", "h2", "h3", "div", "section"} and not self._skip_depth:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if not text:
            return
        self.parts.append(text)
        if self._href:
            self._link_text.append(text)


def _clean_text(markup: str) -> tuple[str, list[dict[str, str]]]:
    parser = _TextParser()
    parser.feed(markup)
    text = "\n".join(line.strip() for line in " ".join(parser.parts).split("\n") if line.strip())
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text, parser.links


def _section(text: str, start: str, end_markers: list[str]) -> str:
    start_idx = text.find(start)
    if start_idx < 0:
        return ""
    section_start = start_idx + len(start)
    end_idx = len(text)
    for marker in end_markers:
        idx = text.find(marker, section_start)
        if idx >= 0:
            end_idx = min(end_idx, idx)
    return text[section_start:end_idx].strip()


def _meta_from_text(text: str) -> dict[str, Any]:
    title_match = re.search(r"#?\s*([A-Z][A-Za-z0-9 \-]+)\s+Placeholder slot", text)
    title = title_match.group(1).strip() if title_match else ""
    brand_section = _section(text, "US Brand Name(s)", ["FDA Approved", "Use in Cancer"])
    fda_section = _section(text, "FDA Approved", ["FDA label information", "Use in Cancer"])
    use_section = _section(text, "Use in Cancer", ["More About", "Research Results", "Clinical Trials Accepting Patients", "Important:"])
    posted = ""
    updated = ""
    posted_match = re.search(r"Posted:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", text)
    updated_match = re.search(r"Updated:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", text)
    if posted_match:
        posted = posted_match.group(1)
    if updated_match:
        updated = updated_match.group(1)
    return {
        "title": title,
        "us_brand_names": brand_section,
        "fda_approved": fda_section.split()[0] if fda_section else "",
        "use_in_cancer": use_section,
        "posted_date": posted,
        "updated_date": updated,
    }


def _source_rows(max_rows: int | None) -> list[sqlite3.Row]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT matched_brand, query_term, nci_concept_name, drug_info_summary_url
            FROM nci_drug_dictionary_entry
            WHERE drug_info_summary_url IS NOT NULL
              AND trim(drug_info_summary_url) <> ''
            ORDER BY matched_brand, nci_concept_name
            """
        ).fetchall()
        if max_rows:
            rows = rows[:max_rows]
        return rows
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def fetch_row(conn, row: sqlite3.Row) -> int:
    url = str(row["drug_info_summary_url"] or "").strip()
    if not url:
        return 0
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 404:
        return 0
    resp.raise_for_status()
    text, links = _clean_text(resp.text)
    meta = _meta_from_text(text)
    brand = str(row["matched_brand"] or "").strip()
    concept = str(row["nci_concept_name"] or row["query_term"] or brand).strip()
    blob_path = save_blob("nci_drug_info", f"nci_drug_info_{_slug(brand)}_{_slug(concept)}.html", resp.text)
    upsert_document(
        conn,
        source="nci:drug_information_summary",
        external_id=f"{_slug(brand)}_{_slug(concept)}",
        search_term=brand,
        title=f"NCI Drug Information Summary: {meta.get('title') or concept}",
        doc_type="nci_drug_information_summary",
        url=url,
        blob_path=blob_path,
        metadata={
            "brand": brand,
            "query_term": row["query_term"],
            "nci_concept_name": concept,
            "title": meta.get("title", ""),
            "us_brand_names": meta.get("us_brand_names", ""),
            "fda_approved": meta.get("fda_approved", ""),
            "posted_date": meta.get("posted_date", ""),
            "updated_date": meta.get("updated_date", ""),
            "use_in_cancer_excerpt": str(meta.get("use_in_cancer", ""))[:2000],
            "link_count": len(links),
            "links": links[:40],
            "text_excerpt": text[:2500],
        },
    )
    return 1


def run(max_rows: int | None = None) -> int:
    rows = _source_rows(max_rows)
    conn = get_db()
    saved = 0
    try:
        for row in rows:
            try:
                n = fetch_row(conn, row)
                saved += n
                if n:
                    print(f"[nci_drug_info] {row['matched_brand']} / {row['nci_concept_name']}: saved")
            except Exception as exc:
                print(f"[nci_drug_info] {row['matched_brand']} / {row['nci_concept_name']}: FAILED ({exc})")
            time.sleep(0.2)
    finally:
        conn.close()
    return saved


if __name__ == "__main__":
    run()

