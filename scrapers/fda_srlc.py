"""FDA Drug Safety-related Labeling Changes scraper.

Captures bounded SrLC search result rows and their public detail pages for
oncology-priority brands. SrLC pages are FDA-hosted HTML rather than JSON APIs,
so this scraper stores raw search/detail HTML and normalizes the result table.
"""
from __future__ import annotations

import html
from html.parser import HTMLParser
import json
import pathlib
import re
import shutil
import time
from typing import Any
from urllib.parse import urljoin

import requests

from storage import get_db, save_blob, upsert_document

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
SEEDS_PATH = BASE_DIR / "config" / "pharma_intel_seed_terms.json"
SEARCH_URL = "https://www.accessdata.fda.gov/scripts/cder/safetylabelingchanges/index.cfm?event=searchResult.page"
DETAIL_BASE_URL = "https://www.accessdata.fda.gov/scripts/cder/safetylabelingchanges/index.cfm"
USER_AGENT = "OmniDataHubResearchBot/0.1 (+local research; FDA SrLC public pages)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "term"


def _seed_brands(max_brands: int | None) -> list[str]:
    seeds = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
    brands = [str(brand).strip() for brand in seeds.get("priority_oncology_brands", []) if str(brand).strip()]
    return brands[:max_brands] if max_brands else brands


class _ResultTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[dict[str, str]]] = []
        self._in_row = False
        self._in_cell = False
        self._current_row: list[dict[str, str]] = []
        self._current_text: list[str] = []
        self._current_href = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "tr":
            self._in_row = True
            self._current_row = []
        elif self._in_row and tag in {"td", "th"}:
            self._in_cell = True
            self._current_text = []
            self._current_href = ""
        elif self._in_cell and tag == "a":
            attrs_dict = {k.lower(): v or "" for k, v in attrs}
            self._current_href = attrs_dict.get("href", "")

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_text.append(data)

    def handle_entityref(self, name: str) -> None:
        if self._in_cell:
            self._current_text.append(html.unescape(f"&{name};"))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._in_cell and tag in {"td", "th"}:
            text = " ".join(" ".join(self._current_text).split())
            self._current_row.append({"text": text, "href": self._current_href})
            self._in_cell = False
        elif self._in_row and tag == "tr":
            if self._current_row:
                self.rows.append(self._current_row)
            self._in_row = False


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            text = " ".join(data.split())
            if text:
                self.parts.append(text)


def _clean_text(markup: str, max_chars: int = 6000) -> str:
    parser = _TextParser()
    parser.feed(markup)
    text = " ".join(parser.parts)
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text[:max_chars]


def _parse_rows(markup: str) -> list[dict[str, str]]:
    parser = _ResultTableParser()
    parser.feed(markup)
    parsed: list[dict[str, str]] = []
    headers: list[str] = []
    for row in parser.rows:
        cells = [cell["text"] for cell in row]
        if not cells:
            continue
        lowered = [cell.lower() for cell in cells]
        if "drug name" in lowered and "active ingredient" in lowered:
            headers = lowered
            continue
        if len(cells) < 6 or not headers:
            continue
        detail_href = row[0].get("href", "") or row[-1].get("href", "") or cells[-1]
        parsed.append(
            {
                "drug_name": cells[0],
                "active_ingredient": cells[1],
                "application_number": cells[2],
                "application_type": cells[3],
                "supplement_date": cells[4],
                "database_updated": cells[5],
                "detail_url": urljoin(DETAIL_BASE_URL, detail_href) if detail_href else "",
            }
        )
    return parsed


def _fetch_search(term: str) -> str:
    resp = requests.post(SEARCH_URL, data={"drug_name": term, "TextSearch": "Search"}, headers=HEADERS, timeout=40)
    resp.raise_for_status()
    return resp.text


def _fetch_detail(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=40)
    resp.raise_for_status()
    return resp.text


def fetch_for_brand(conn, brand: str) -> int:
    search_html = _fetch_search(brand)
    rows = _parse_rows(search_html)
    search_blob_path = save_blob("fda_srlc", f"srlc_search_{_slug(brand)}.html", search_html)
    upsert_document(
        conn,
        source="fda:safety_labeling_changes",
        external_id=f"search_{_slug(brand)}",
        search_term=brand,
        title=f"FDA SrLC search results for {brand}",
        doc_type="srlc_search_results",
        url=SEARCH_URL,
        blob_path=search_blob_path,
        metadata={"brand": brand, "row_count": len(rows), "query_term": brand},
    )
    saved = 1
    for idx, row in enumerate(rows, start=1):
        detail_url = row.get("detail_url") or ""
        drug_id_match = re.search(r"DrugNameID=(\d+)", detail_url, re.IGNORECASE)
        drug_id = drug_id_match.group(1) if drug_id_match else f"{_slug(row.get('drug_name', brand))}_{idx}"
        detail_html = _fetch_detail(detail_url) if detail_url else ""
        detail_text = _clean_text(detail_html)
        detail_blob_path = save_blob("fda_srlc", f"srlc_detail_{_slug(brand)}_{drug_id}.html", detail_html)
        upsert_document(
            conn,
            source="fda:safety_labeling_changes",
            external_id=f"detail_{_slug(brand)}_{drug_id}",
            search_term=brand,
            title=f"FDA SrLC detail: {row.get('drug_name') or brand}",
            doc_type="srlc_detail_page",
            url=detail_url,
            blob_path=detail_blob_path,
            metadata={**row, "brand": brand, "detail_text_excerpt": detail_text[:1200]},
        )
        saved += 1
        time.sleep(0.2)
    return saved


def run(brands: list[str] | None = None, max_brands: int | None = 18) -> int:
    if brands is None:
        brands = _seed_brands(max_brands)
    elif max_brands:
        brands = brands[:max_brands]
    conn = get_db()
    saved = 0
    try:
        conn.execute("DELETE FROM documents WHERE source='fda:safety_labeling_changes'")
        conn.commit()
        raw_dir = BASE_DIR / "data" / "raw" / "fda_srlc"
        if raw_dir.exists():
            shutil.rmtree(raw_dir)
        for brand in brands:
            try:
                n = fetch_for_brand(conn, brand)
                saved += n
                print(f"[fda_srlc] {brand}: saved {n}")
            except Exception as exc:
                print(f"[fda_srlc] {brand}: FAILED ({exc})")
            time.sleep(0.35)
    finally:
        conn.close()
    return saved


if __name__ == "__main__":
    run()
