"""Award-winning pharma campaign scraper -- public, keyless press releases.

There's no public API for "award-winning pharma campaigns" the way there is for FDA
labels or clinical trials -- award programs (PM360 Pharma Choice, PM360 Trailblazer,
Manny Awards, MM+M Awards) publish winners as ordinary web pages, not structured data.
The one genuinely public, non-paywalled, crawl-permitted source found for this is
PR Newswire press releases announcing the winners each year (prnewswire.com's
robots.txt has no AI/general crawler block and does not disallow /news-releases/).
MM+M's own site was ruled out: its robots.txt explicitly disallows ClaudeBot, and its
award pages are paywalled (HTTP 402) regardless.

Seed URLs live in config/award_sources.json -- add more there (any PR Newswire /
similarly public press release announcing pharma marketing award winners) to broaden
coverage, same pattern as config/seed_terms.json for the other scrapers.
"""
from __future__ import annotations

import hashlib
import html as html_lib
import re
import time
import requests

from storage import get_db, save_blob, upsert_document

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_ANY_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")
_BLANKLINES_RE = re.compile(r"\n{3,}")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _html_to_text(raw_html: str) -> str:
    """Minimal, dependency-free HTML-to-text: strip script/style, then all tags, unescape entities."""
    no_script = _TAG_RE.sub(" ", raw_html)
    no_tags = _ANY_TAG_RE.sub("\n", no_script)
    text = html_lib.unescape(no_tags)
    text = _WS_RE.sub(" ", text)
    text = _BLANKLINES_RE.sub("\n\n", text)
    return text.strip()


def _extract_title(raw_html: str, fallback: str) -> str:
    m = _TITLE_RE.search(raw_html)
    if not m:
        return fallback
    title = html_lib.unescape(_ANY_TAG_RE.sub("", m.group(1))).strip()
    return title.split(" | ")[0].strip() or fallback


def fetch_source(conn, entry: dict) -> int:
    url = entry["url"]
    program, year = entry["program"], entry["year"]
    resp = requests.get(url, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    resp.encoding = "utf-8"  # requests' auto-detected encoding mangled em-dashes/(R) on this site

    external_id = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    title = _extract_title(resp.text, f"{program} {year} winners")
    text = _html_to_text(resp.text)

    blob_path = save_blob("awards", f"{external_id}.txt", text)
    upsert_document(
        conn,
        source="awards",
        external_id=external_id,
        search_term=program,
        title=title,
        doc_type="award_announcement",
        url=url,
        blob_path=blob_path,
        metadata={"program": program, "year": year},
    )
    return 1


def run(sources: list[dict]) -> int:
    conn = get_db()
    total = 0
    for entry in sources:
        try:
            n = fetch_source(conn, entry)
            print(f"[awards] {entry['program']} {entry['year']}: saved")
            total += n
        except Exception as e:
            print(f"[awards] {entry['program']} {entry['year']}: FAILED ({e})")
        time.sleep(0.5)
    conn.close()
    return total


if __name__ == "__main__":
    import json
    import pathlib

    sources = json.loads((pathlib.Path(__file__).resolve().parent.parent / "config" / "award_sources.json").read_text())
    run(sources)
