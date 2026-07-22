"""FDA Purple Book monthly CSV downloader.

Downloads the latest public Purple Book CSV report from the FDA Purple Book downloads
page, stores the raw CSV, and indexes it in the document lake. Structured loading is in
`pharma_intel.py`.
"""
from __future__ import annotations

import hashlib
import html.parser
import re
import time
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests

from storage import get_db, save_blob, upsert_document

PAGE_URL = "https://purplebooksearch.fda.gov/downloads"
USER_AGENT = "OmniDataHubResearchBot/0.1 (+local research; FDA Purple Book public CSV)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,text/csv,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.5",
}
FALLBACK_CSV_URLS = [
    "https://www.accessdata.fda.gov/drugsatfda_docs/PurpleBook/2026/purplebook-search-June-data-download.csv",
]


class _CsvLinkParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href = ""
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            return
        attr_map = dict(attrs)
        self._href = attr_map.get("href", "")
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            self.links.append((self._href, " ".join(self._text)))
            self._href = ""
            self._text = []


def _can_fetch(url: str) -> bool:
    rp = RobotFileParser()
    parsed_root = "https://purplebooksearch.fda.gov/robots.txt" if "purplebooksearch.fda.gov" in url else "https://www.accessdata.fda.gov/robots.txt"
    rp.set_url(parsed_root)
    try:
        rp.read()
    except Exception:
        return False
    return rp.can_fetch(USER_AGENT, url)


def _discover_latest_csv(page_html: str) -> str | None:
    parser = _CsvLinkParser()
    parser.feed(page_html)
    csv_links: list[str] = []
    for href, text in parser.links:
        candidate = f"{href} {text}".lower()
        if "csv" in candidate:
            csv_links.append(urljoin(PAGE_URL, href))
    return csv_links[0] if csv_links else None


def run() -> int:
    conn = get_db()
    try:
        csv_urls: list[str] = []
        try:
            page = requests.get(PAGE_URL, headers=HEADERS, timeout=30)
            page.raise_for_status()
            discovered = _discover_latest_csv(page.text)
            if discovered:
                csv_urls.append(discovered)
        except Exception as exc:
            print(f"[purple_book] downloads page discovery failed ({exc})")
        csv_urls.extend(FALLBACK_CSV_URLS)

        resp = None
        csv_url = ""
        last_status = "no_csv_link"
        for candidate in dict.fromkeys(csv_urls):
            if not _can_fetch(candidate):
                last_status = "blocked_by_robots"
                continue
            try:
                attempt = requests.get(candidate, headers=HEADERS, timeout=60)
                if attempt.status_code in {401, 402, 403, 404}:
                    last_status = f"http_{attempt.status_code}"
                    continue
                attempt.raise_for_status()
                resp = attempt
                csv_url = candidate
                break
            except Exception as exc:
                last_status = f"failed:{exc}"
        if resp is None:
            print(f"[purple_book] latest_csv: {last_status}")
            return 0
        resp.encoding = resp.encoding or "utf-8"
        text = resp.text
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
        month_match = re.search(r"([A-Za-z]+[_ -]\d{4}|\d{4}[_ -]\d{2})", csv_url)
        release = month_match.group(1).replace(" ", "_") if month_match else "latest"
        blob_path = save_blob("purple_book", f"purple_book_{release}_{digest}.csv", text)
        upsert_document(
            conn,
            source="purple_book:latest_csv",
            external_id=digest,
            search_term="FDA Purple Book",
            title=f"FDA Purple Book CSV report ({release})",
            doc_type="purple_book_csv",
            url=csv_url,
            blob_path=blob_path,
            metadata={"source_page": PAGE_URL, "rows_hint": max(0, text.count("\n") - 1), "release": release},
        )
        print(f"[purple_book] latest_csv: saved {release}")
        time.sleep(0.5)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    run()
