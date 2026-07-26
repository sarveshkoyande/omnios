"""Home-screen ticker feed: new launches, FDA approvals, FDA notices, indication changes.

Merges two sources:
  1. Curated regulatory events (config/regulatory_feed.json) -- editorial, dated, roster-
     specific (approvals / launches / indication changes / notices).
  2. Live KB-derived freshness -- the most recently fetched trials and labels from
     data/omni_kb.db, surfaced as "new evidence indexed" items so the ticker also reflects
     the tool's own live data intake.

Returns a flat, date-sorted list the front-end scrolls as a marquee. Every item is typed
and carries its provenance so the UI can badge curated vs live.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import db  # noqa: E402  (dual-dialect KB connection: SQLite file locally, Postgres on Render)
from paths import data_path  # noqa: E402

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
KB_DB = data_path("omni_kb.db")
CURATED = BASE_DIR / "config" / "regulatory_feed.json"
CATALOG = BASE_DIR / "config" / "client_brands.json"


def _roster_brands() -> list[str]:
    if not CATALOG.exists():
        return []
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    return [b["brand"] for brands in data.get("clients", {}).values() for b in brands]

_TYPE_ICON = {"approval": "verified", "launch": "rocket_launch", "indication_change": "swap_horiz",
              "notice": "gavel", "label_update": "description", "trial": "science", "literature": "menu_book"}


def _curated() -> list[dict]:
    if not CURATED.exists():
        return []
    data = json.loads(CURATED.read_text(encoding="utf-8"))
    out = []
    for e in data.get("events", []):
        out.append({
            "date": e.get("date", ""),
            "type": e.get("type", "notice"),
            "brand": e.get("brand", ""),
            "text": e.get("headline", ""),
            "detail": e.get("detail", ""),
            "url": e.get("source_url", ""),
            "provenance": "curated",
            "icon": _TYPE_ICON.get(e.get("type", "notice"), "campaign"),
        })
    return out


def _live_kb(limit: int = 6) -> list[dict]:
    conn = db.kb_connect()
    if conn is None:
        return []
    roster = _roster_brands()
    out = []
    try:
        # Only surface freshly-indexed evidence for the client roster brands (not the
        # legacy seed terms), so the ticker stays portfolio-relevant.
        if roster:
            placeholders = " OR ".join(["search_term LIKE ?"] * len(roster))
            params = [f"%{b}%" for b in roster] + [limit]
            rows = conn.execute(
                "SELECT source, search_term, title, url, fetched_at FROM documents "
                f"WHERE source IN ('clinicaltrials','dailymed','openfda') AND ({placeholders}) "
                "ORDER BY fetched_at DESC LIMIT ?", params).fetchall()
        else:
            rows = conn.execute(
                "SELECT source, search_term, title, url, fetched_at FROM documents "
                "WHERE source IN ('clinicaltrials','dailymed','openfda') "
                "ORDER BY fetched_at DESC LIMIT ?", (limit,)).fetchall()
        for r in rows:
            is_trial = r["source"] == "clinicaltrials"
            out.append({
                "date": (r["fetched_at"] or "")[:10],
                "type": "trial" if is_trial else "label_update",
                "brand": r["search_term"] or "",
                "text": ("New trial indexed: " if is_trial else "Label indexed: ") + (r["title"] or "")[:90],
                "detail": "",
                "url": r["url"] or "",
                "provenance": "live",
                "icon": _TYPE_ICON["trial"] if is_trial else _TYPE_ICON["label_update"],
            })
    finally:
        conn.close()
    return out


def build_feed(include_live: bool = True) -> list[dict]:
    items = _curated()
    if include_live:
        items += _live_kb()
    items.sort(key=lambda x: x.get("date", ""), reverse=True)
    return items
