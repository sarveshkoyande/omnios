"""Official oncology brand-site scraper.

Fetches a curated list of public HCP/patient brand websites, stores text-only page
captures, and indexes them in `documents` for structured message extraction.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import time
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from html_extract import extract_title as _extract_title, html_to_text as _html_to_text
from storage import get_db, save_blob, upsert_document

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "official_oncology_brand_sites.json"
USER_AGENT = "OmniDataHubResearchBot/0.1 (+local research; public brand pages only)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
}

_ROBOTS_CACHE: dict[str, RobotFileParser] = {}


def _robots_for(url: str) -> RobotFileParser:
    parsed = urlparse(url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    if root not in _ROBOTS_CACHE:
        rp = RobotFileParser()
        rp.set_url(f"{root}/robots.txt")
        try:
            rp.read()
        except Exception:
            rp.parse(["User-agent: *", "Disallow: /"])
        _ROBOTS_CACHE[root] = rp
    return _ROBOTS_CACHE[root]


def _can_fetch(url: str) -> bool:
    return _robots_for(url).can_fetch(USER_AGENT, url)


def fetch_site(conn, site: dict[str, Any]) -> str:
    url = site["url"]
    if not _can_fetch(url):
        return "blocked_by_robots"

    response = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
    if response.status_code in {401, 402, 403, 404}:
        return f"http_{response.status_code}"
    response.raise_for_status()
    response.encoding = "utf-8"  # requests' auto-detected encoding mangles (R)/em-dashes on some brand sites

    external_id = hashlib.sha1(f"{site['brand']}|{site['audience']}|{url}".encode("utf-8")).hexdigest()[:16]
    title = _extract_title(response.text, f"{site['brand']} {site['audience']} official site")
    text = _html_to_text(response.text)
    blob_path = save_blob(
        "brand_sites",
        f"{site['brand'].lower()}_{site['audience']}_{external_id}.txt",
        text,
    )
    upsert_document(
        conn,
        source=f"brand_site:{site['brand'].lower()}:{site['audience']}",
        external_id=external_id,
        search_term=site["brand"],
        title=title,
        doc_type="official_brand_site",
        url=url,
        blob_path=blob_path,
        metadata={
            "brand": site["brand"],
            "generic": site.get("generic", ""),
            "company": site.get("company", ""),
            "therapy_area": site.get("therapy_area", ""),
            "audience": site.get("audience", ""),
            "content_length": len(text),
        },
    )
    return "saved"


def run(sites: list[dict[str, Any]] | None = None) -> int:
    if sites is None:
        sites = json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("sites", [])

    conn = get_db()
    saved = 0
    try:
        for site in sites:
            try:
                status = fetch_site(conn, site)
                print(f"[brand_sites] {site['brand']} {site['audience']}: {status}")
                if status == "saved":
                    saved += 1
            except Exception as exc:
                print(f"[brand_sites] {site['brand']} {site['audience']}: FAILED ({exc})")
            time.sleep(0.8)
    finally:
        conn.close()
    return saved


if __name__ == "__main__":
    run()
