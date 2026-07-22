"""Public web-page ingestion for pharma intelligence sources.

This is intentionally conservative: it only fetches URLs explicitly marked
`ingest_enabled` in config/public_pharma_intel_sources.json, checks robots.txt, stores
text-only page captures, and records extraction hints in metadata. APIs remain handled by
their purpose-built scrapers.
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
SOURCE_CONFIG = BASE_DIR / "config" / "public_pharma_intel_sources.json"
USER_AGENT = "OmniDataHubResearchBot/0.1 (+local research; public pages only)"
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
            # If robots cannot be read, keep this as a manual-review source.
            rp.parse(["User-agent: *", "Disallow: /"])
        _ROBOTS_CACHE[root] = rp
    return _ROBOTS_CACHE[root]


def _can_fetch(url: str) -> bool:
    return _robots_for(url).can_fetch(USER_AGENT, url)


def fetch_source(conn, entry: dict[str, Any]) -> str:
    url = entry["url"]
    if not _can_fetch(url):
        return "blocked_by_robots"

    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code in {401, 402, 403, 404}:
        return f"http_{resp.status_code}"
    resp.raise_for_status()
    resp.encoding = "utf-8"  # requests' auto-detected encoding mangles (R)/em-dashes on some sites

    external_id = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    title = _extract_title(resp.text, entry["name"])
    text = _html_to_text(resp.text)
    key = f"{entry['category']}/{entry['id']}_{external_id}.txt"
    blob_path = save_blob("public_web", key, text)

    upsert_document(
        conn,
        source=f"public_web:{entry['id']}",
        external_id=external_id,
        search_term=entry.get("category", ""),
        title=title,
        doc_type=entry.get("category", "public_web"),
        url=url,
        blob_path=blob_path,
        metadata={
            "source_id": entry["id"],
            "name": entry["name"],
            "category": entry.get("category", ""),
            "fields": entry.get("fields", []),
            "content_length": len(text),
        },
    )
    return "saved"


def run(sources: list[dict[str, Any]] | None = None) -> int:
    if sources is None:
        sources = json.loads(SOURCE_CONFIG.read_text(encoding="utf-8")).get("sources", [])

    conn = get_db()
    saved = 0
    try:
        for entry in sources:
            if entry.get("access") == "public_api" or not entry.get("ingest_enabled"):
                continue
            try:
                status = fetch_source(conn, entry)
                print(f"[public_web] {entry['id']}: {status}")
                if status == "saved":
                    saved += 1
            except Exception as exc:
                print(f"[public_web] {entry['id']}: FAILED ({exc})")
            time.sleep(0.8)
    finally:
        conn.close()
    return saved


if __name__ == "__main__":
    run()
