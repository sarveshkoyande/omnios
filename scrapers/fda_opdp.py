"""FDA OPDP untitled-letter index scraper.

Captures the public FDA page that lists Office of Prescription Drug Promotion
untitled letters and corresponding promotional communications. The structured builder
extracts company/product/date records from the saved text.
"""
from __future__ import annotations

import hashlib
import html as html_lib
import re
import time
from io import BytesIO
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests
from pypdf import PdfReader

from html_extract import extract_title as _extract_title, html_to_text as _html_to_text
from storage import get_db, save_blob, upsert_document

URL = "https://www.fda.gov/drugs/warning-letters-and-notice-violation-letters-pharmaceutical-companies/untitled-letters"
USER_AGENT = "OmniDataHubResearchBot/0.1 (+local research; FDA public OPDP page)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
}

_ANY_TAG_RE = re.compile(r"<[^>]+>")
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)
_LINK_RE = re.compile(r'<a\s+[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<label>.*?)</a>', re.IGNORECASE | re.DOTALL)
_P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)


def _can_fetch() -> bool:
    rp = RobotFileParser()
    rp.set_url("https://www.fda.gov/robots.txt")
    try:
        rp.read()
    except Exception:
        return False
    return rp.can_fetch(USER_AGENT, URL)


def _cell_text(raw_html: str) -> str:
    return " ".join(_html_to_text(raw_html).split())


def _first_paragraph_or_text(raw_html: str) -> str:
    match = _P_RE.search(raw_html)
    return _cell_text(match.group(1) if match else raw_html)


def _media_id(url: str) -> str:
    match = re.search(r"/media/(\d+)/download", url)
    if match:
        return match.group(1)
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _extract_letter_links(raw_html: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row_html in _ROW_RE.findall(raw_html):
        cells = _CELL_RE.findall(row_html)
        if len(cells) < 3:
            continue
        issued_date = _cell_text(cells[0])
        company = _first_paragraph_or_text(cells[1])
        product_issue = _cell_text(cells[2])
        for link in _LINK_RE.finditer(row_html):
            label = _cell_text(link.group("label"))
            if label.lower() != "untitled letter":
                continue
            href = urljoin("https://www.fda.gov", html_lib.unescape(link.group("href")))
            title_match = re.search(r'title="([^"]+)"', link.group(0), re.IGNORECASE)
            title = html_lib.unescape(title_match.group(1)).strip() if title_match else label
            rows.append(
                {
                    "issued_date": issued_date,
                    "company": company,
                    "product_issue": product_issue,
                    "url": href,
                    "title": title,
                    "media_id": _media_id(href),
                }
            )
    return rows


def _pdf_text(raw_pdf: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(raw_pdf))
        pages = [(page.extract_text() or "") for page in reader.pages]
        return "\n\n".join(page.strip() for page in pages if page.strip()).strip()
    except Exception as exc:
        return f"[PDF text extraction failed: {exc}]"


def _fetch_letter_documents(conn, raw_html: str) -> int:
    written = 0
    for link in _extract_letter_links(raw_html):
        try:
            resp = requests.get(link["url"], headers=HEADERS, timeout=45)
            if resp.status_code in {401, 402, 403, 404}:
                print(f"[fda_opdp] letter {link['media_id']}: http_{resp.status_code}")
                continue
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            pdf_blob_path = None
            if "pdf" in content_type.lower() or link["url"].lower().endswith(".pdf"):
                raw_pdf = resp.content
                pdf_blob_path = save_blob("fda_opdp", f"letters/{link['media_id']}.pdf", raw_pdf)
                text = _pdf_text(raw_pdf)
                content_length = len(raw_pdf)
            else:
                # Some older letter links resolve to an HTML landing page instead of a
                # /media/<id>/download PDF -- capture the real page text instead of
                # feeding non-PDF bytes to the PDF parser and storing its failure message.
                text = _html_to_text(resp.text)
                content_length = len(resp.text)
            if text.startswith("[PDF text extraction failed"):
                print(f"[fda_opdp] letter {link['media_id']}: pdf_parse_failed, skipped")
                continue
            text_path = save_blob("fda_opdp", f"letters/{link['media_id']}.txt", text)
            upsert_document(
                conn,
                source="fda_opdp:untitled_letter_document",
                external_id=link["media_id"],
                search_term="OPDP untitled letter document",
                title=link["title"],
                doc_type="opdp_untitled_letter",
                url=link["url"],
                blob_path=text_path,
                metadata={
                    "agency": "FDA",
                    "office": "Office of Prescription Drug Promotion",
                    "issued_date": link["issued_date"],
                    "company": link["company"],
                    "product_issue": link["product_issue"],
                    "pdf_blob_path": pdf_blob_path,
                    "content_type": content_type,
                    "content_length": content_length,
                    "text_length": len(text),
                },
            )
            written += 1
            print(f"[fda_opdp] letter {link['media_id']}: saved")
        except Exception as exc:
            print(f"[fda_opdp] letter {link['media_id']}: FAILED ({exc})")
        time.sleep(0.1)
    return written


def run() -> int:
    conn = get_db()
    try:
        if not _can_fetch():
            print("[fda_opdp] untitled_letters: blocked_by_robots")
            return 0
        resp = requests.get(URL, headers=HEADERS, timeout=30)
        if resp.status_code in {401, 402, 403, 404}:
            print(f"[fda_opdp] untitled_letters: http_{resp.status_code}")
            return 0
        resp.raise_for_status()
        resp.encoding = "utf-8"

        external_id = hashlib.sha1(URL.encode("utf-8")).hexdigest()[:16]
        text = _html_to_text(resp.text)
        blob_path = save_blob("fda_opdp", f"untitled_letters_{external_id}.txt", text)
        upsert_document(
            conn,
            source="fda_opdp:untitled_letters",
            external_id=external_id,
            search_term="OPDP untitled letters",
            title=_extract_title(resp.text, "FDA OPDP Untitled Letters"),
            doc_type="promotional_compliance_index",
            url=URL,
            blob_path=blob_path,
            metadata={
                "agency": "FDA",
                "office": "Office of Prescription Drug Promotion",
                "content_length": len(text),
            },
        )
        print("[fda_opdp] untitled_letters: saved")
        written = 1 + _fetch_letter_documents(conn, resp.text)
        time.sleep(0.5)
        return written
    finally:
        conn.close()


if __name__ == "__main__":
    run()
