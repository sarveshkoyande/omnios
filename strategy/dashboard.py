"""Home-dashboard data: per-brand performance signals for the client roster.

Reads the fixed brand catalog (config/client_brands.json), the scraped knowledge base
(data/omni_kb.db) and the discovered-competitor checkpoint (data/client_brand_intel.json),
and folds in campaign counts from the campaign data model. Every number is real, derived
from indexed public data -- a "how are these brands performing" read for the landing
page, not a claim of market share.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import campaign_store  # noqa: E402

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
KB_DB = BASE_DIR / "data" / "omni_kb.db"
CATALOG = BASE_DIR / "config" / "client_brands.json"
COMPETITORS = BASE_DIR / "data" / "client_brand_intel.json"

_LIFECYCLE_LABEL = {"launch": "Launch", "growth": "Growth", "mature": "Mature", "loe": "LOE / defend"}


def _kb_counts(conn: sqlite3.Connection, brand: str) -> dict:
    like = f"%{brand}%"
    def n(where: str, *params) -> int:
        return conn.execute(f"SELECT COUNT(*) FROM documents WHERE {where}", params).fetchone()[0]
    trials_total = n("source='clinicaltrials' AND (search_term LIKE ? OR title LIKE ?)", like, like)
    trials_recruiting = n(
        "source='clinicaltrials' AND (search_term LIKE ? OR title LIKE ?) "
        "AND (metadata_json LIKE '%Recruiting%' OR metadata_json LIKE '%RECRUITING%')", like, like)
    pubmed = n("source='pubmed' AND (search_term LIKE ? OR title LIKE ?)", like, like)
    labels = n("source IN ('dailymed','openfda') AND (search_term LIKE ? OR title LIKE ?)", like, like)
    return {"trials_total": trials_total, "trials_recruiting": trials_recruiting,
            "pubmed": pubmed, "labels": labels}


def _momentum(counts: dict, competitors: int) -> int:
    """A rough 0-100 'visible activity' score from indexed evidence -- recruiting trials
    and recent literature push it up; a crowded competitor field tempers it. Illustrative,
    not a market metric."""
    score = (min(counts["trials_recruiting"], 10) * 6
             + min(counts["trials_total"], 20) * 1.5
             + min(counts["pubmed"], 10) * 2.5
             + min(counts["labels"], 4) * 3)
    score = min(100, score)
    if competitors >= 5:
        score = max(0, score - 6)
    return int(round(score))


def brand_performance() -> dict:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["clients"]
    competitors = {}
    if COMPETITORS.exists():
        competitors = json.loads(COMPETITORS.read_text(encoding="utf-8"))
    campaigns = campaign_store.campaign_counts_by_brand()

    conn = sqlite3.connect(KB_DB) if KB_DB.exists() else None
    clients_out = []
    totals = {"brands": 0, "clients": 0, "recruiting_trials": 0, "campaigns": 0}
    for client, brands in catalog.items():
        totals["clients"] += 1
        brand_cards = []
        for b in brands:
            counts = _kb_counts(conn, b["brand"]) if conn else {"trials_total": 0, "trials_recruiting": 0, "pubmed": 0, "labels": 0}
            comp = competitors.get(b["brand"], [])
            card = {
                "brand": b["brand"],
                "generic": b.get("generic", ""),
                "therapy_area": b.get("therapy_area", ""),
                "indications": b.get("indications", []),
                "lifecycle_key": b.get("lifecycle_key", ""),
                "lifecycle_label": _LIFECYCLE_LABEL.get(b.get("lifecycle_key", ""), b.get("lifecycle_key", "")),
                "competitors": comp,
                "competitor_count": len(comp),
                "campaigns": campaigns.get(b["brand"], 0),
                "momentum": _momentum(counts, len(comp)),
                **counts,
            }
            brand_cards.append(card)
            totals["brands"] += 1
            totals["recruiting_trials"] += counts["trials_recruiting"]
            totals["campaigns"] += card["campaigns"]
        clients_out.append({"client": client, "brands": brand_cards})
    if conn:
        conn.close()

    return {"clients": clients_out, "totals": totals, "library": campaign_store.library_stats()}
