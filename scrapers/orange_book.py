"""FDA Orange Book downloadable data-file scraper.

Downloads the public Orange Book ZIP, stores the raw archive and its three tilde-delimited
text files, and indexes each extracted file in the document lake. Structured loading lives
in `pharma_intel.py`.
"""
from __future__ import annotations

import hashlib
import html.parser
import io
import re
import time
import zipfile
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests

from storage import get_db, save_blob, upsert_document

PAGE_URL = "https://www.fda.gov/drugs/drug-approvals-and-databases/orange-book-data-files"
USER_AGENT = "OmniDataHubResearchBot/0.1 (+local research; FDA Orange Book public data)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
}
FALLBACK_ZIP_URLS = [
    "https://www.fda.gov/media/76860/download",
    "https://www.fda.gov/media/76860/download?attachment",
]


class _ZipLinkParser(html.parser.HTMLParser):
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
    rp.set_url("https://www.fda.gov/robots.txt")
    try:
        rp.read()
    except Exception:
        return False
    return rp.can_fetch(USER_AGENT, url)


def _discover_zip_url(page_html: str) -> str | None:
    parser = _ZipLinkParser()
    parser.feed(page_html)
    for href, text in parser.links:
        candidate = f"{href} {text}".lower()
        if "zip" in candidate or "compressed" in candidate:
            return urljoin(PAGE_URL, href)
    return None


def _download_zip() -> tuple[str, bytes]:
    page = requests.get(PAGE_URL, headers=HEADERS, timeout=30)
    page.raise_for_status()
    zip_urls = []
    discovered = _discover_zip_url(page.text)
    if discovered:
        zip_urls.append(discovered)
    zip_urls.extend(FALLBACK_ZIP_URLS)

    last_error = ""
    for url in dict.fromkeys(zip_urls):
        if not _can_fetch(url):
            last_error = f"blocked_by_robots:{url}"
            continue
        try:
            resp = requests.get(url, headers={**HEADERS, "Accept": "application/zip,*/*"}, timeout=60)
            if resp.status_code in {401, 402, 403, 404}:
                last_error = f"http_{resp.status_code}:{url}"
                continue
            resp.raise_for_status()
            if zipfile.is_zipfile(io.BytesIO(resp.content)):
                return url, resp.content
            last_error = f"not_zip:{url}"
        except Exception as exc:
            last_error = f"{type(exc).__name__}:{url}:{exc}"
    raise RuntimeError(f"could not download Orange Book ZIP ({last_error})")


def run() -> int:
    conn = get_db()
    try:
        url, payload = _download_zip()
        digest = hashlib.sha1(payload).hexdigest()[:16]
        zip_blob = save_blob("orange_book", f"orange_book_{digest}.zip", payload)
        upsert_document(
            conn,
            source="orange_book:zip",
            external_id=digest,
            search_term="FDA Orange Book",
            title="FDA Orange Book downloadable data ZIP",
            doc_type="orange_book_zip",
            url=url,
            blob_path=zip_blob,
            metadata={"bytes": len(payload), "source_page": PAGE_URL},
        )

        count = 1
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            for member in zf.namelist():
                if not re.search(r"(products|patent|exclusivity)\.txt$", member, re.IGNORECASE):
                    continue
                raw = zf.read(member)
                try:
                    text = raw.decode("latin-1")
                except UnicodeDecodeError:
                    text = raw.decode("utf-8", errors="replace")
                member_id = hashlib.sha1(f"{digest}:{member}".encode("utf-8")).hexdigest()[:16]
                blob = save_blob("orange_book", f"{digest}_{member}", text)
                upsert_document(
                    conn,
                    source=f"orange_book:{member.lower()}",
                    external_id=member_id,
                    search_term="FDA Orange Book",
                    title=f"FDA Orange Book {member}",
                    doc_type="orange_book_data_file",
                    url=url,
                    blob_path=blob,
                    metadata={"zip_sha1": digest, "member": member, "rows_hint": max(0, text.count("\n") - 1)},
                )
                count += 1
        print(f"[orange_book] saved {count} documents from {url}")
        time.sleep(0.5)
        return count
    finally:
        conn.close()


if __name__ == "__main__":
    run()
