"""Precedent Campaign Agent -- surfaces real, individual award-winning pharma campaigns
as creative inspiration.

Queries the 'awards' documents scraped by scrapers/awards.py (public PR Newswire press
releases announcing PM360 Pharma Choice / Trailblazer Awards winners -- see that module's
docstring for why this source and not a paywalled/blocked one).

Earlier versions of this agent matched at the whole-press-release level ("here's a link to
an announcement"). This version parses the individual per-campaign winner entries out of
each release -- category, award tier, agency/sponsor, and campaign title -- e.g. "GOLD:
Fingerpaint Marketing and Neurelis, Inc. for 'Give Seizures the Sprayer' (Multichannel)".
That's genuinely reusable creative inspiration (a real campaign name, agency, and category),
not just a pointer to go read something. What it is NOT: actual creative assets (images,
color palettes, page layouts). Those live on agency portfolio sites and the richer
PM360/MM+M article pages, which return HTTP 403 (Cloudflare bot protection) to any
automated fetch, including this app's -- there is no honest way to pull them from a public,
keyless source. The plan document says so explicitly rather than inventing colors or
describing images that were never retrieved.

Matching is keyword overlap (therapy-area/brand words vs. each entry's category + title +
agency/sponsor text); if nothing matches, the most recent entries are returned instead of
nothing, clearly flagged as unmatched -- same "never fabricate, be honest when nothing
matched" rule the rest of this tool follows.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scrapers"))
from storage import get_db, BASE_DIR  # noqa: E402

_WORD_RE = re.compile(r"[a-zA-Z]{4,}")
_STOPWORDS = {"with", "from", "that", "this", "have", "were", "into", "than", "then",
              "their", "them", "such", "also", "will", "which", "these", "those"}

# Matches "<CATEGORY>\n\n<TIER>: <agency/sponsor text> for \"<title>\"" blocks in the
# scraped press-release text -- see scrapers/awards.py for the plain-text format these
# releases come in. DOTALL because a wrapped title can span a line break before the
# closing quote (e.g. a multi-line campaign name).
_ENTRY_RE = re.compile(
    r'([A-Z][A-Z/&\s]{2,40}?)\s*\n\s*\n\s*(GOLD|SILVER|BRONZE):\s*(.+?)\s+for\s+"(.+?)"',
    re.DOTALL,
)


def _keywords(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text)} - _STOPWORDS


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _parse_entries(text: str) -> list[dict]:
    entries = []
    for m in _ENTRY_RE.finditer(text):
        entries.append({
            "category": _clean(m.group(1)),
            "tier": m.group(2).title(),
            "agency_sponsor": _clean(m.group(3)),
            "title": _clean(m.group(4)),
        })
    return entries


def find_precedent_campaigns(therapy_area: str, brand: str = "", limit: int = 3) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT title, url, blob_path, metadata_json, fetched_at FROM documents WHERE source='awards' "
        "ORDER BY fetched_at DESC"
    ).fetchall()
    conn.close()
    if not rows:
        return []

    query_kw = _keywords(therapy_area) | _keywords(brand)
    scored = []
    for doc_title, url, blob_path, metadata_json, fetched_at in rows:
        meta = json.loads(metadata_json or "{}")
        program, year = meta.get("program"), meta.get("year")
        blob_full = BASE_DIR / blob_path
        if not blob_full.exists():
            continue
        text = blob_full.read_text(encoding="utf-8", errors="ignore")
        for entry in _parse_entries(text):
            entry_kw = _keywords(entry["category"]) | _keywords(entry["title"]) | _keywords(entry["agency_sponsor"])
            scored.append({
                "title": entry["title"], "category": entry["category"], "tier": entry["tier"],
                "agency_sponsor": entry["agency_sponsor"], "program": program, "year": year, "url": url,
                "match_score": len(query_kw & entry_kw),
            })

    if not scored:
        return []

    scored.sort(key=lambda r: (-r["match_score"], -(r["year"] or 0)))
    matched = [r for r in scored if r["match_score"] > 0][:limit]
    if matched:
        for r in matched:
            r["matched"] = True
        return matched

    # Honest fallback: no therapy-area/brand overlap found in any parsed entry -- return
    # the most recent entries instead of nothing, clearly flagged as not matched.
    fallback = scored[:limit]
    for r in fallback:
        r["matched"] = False
    return fallback
