"""
Award-winning campaign store: loads config/brand_campaign_awards.json into the
campaign_award table (db/campaign_content_schema.sql, SQLite via data/campaigns.db) and
provides matching queries so the Brand Engagement Plan's precedent section can surface
real award-winning creative relevant to the brand / therapy area / client.

Each award record captures WHY it won, its core message, and a description of the hero
creative -- the creative-inspiration payload requested. `load_awards()` is idempotent;
`awards_for(brand, therapy_area, client)` returns the most relevant matches (brand >
therapy_area > client > industry benchmark).
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import campaign_store  # noqa: E402  (reuses DB path + schema init)

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
AWARDS_JSON = BASE_DIR / "config" / "brand_campaign_awards.json"
CATALOG_JSON = BASE_DIR / "config" / "client_brands.json"


def _client_for_brand(brand: str) -> str:
    """Resolve a brand's client from the roster so client-level award matches work."""
    if not brand or not CATALOG_JSON.exists():
        return ""
    data = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    for client, brands in data.get("clients", {}).items():
        if any(b.get("brand", "").lower() == brand.lower() for b in brands):
            return client
    return ""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _conn() -> sqlite3.Connection:
    campaign_store.init_db()
    conn = sqlite3.connect(campaign_store.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def load_awards() -> dict:
    """Upsert every award campaign from the JSON. Idempotent. Returns a count."""
    if not AWARDS_JSON.exists():
        return {"loaded": 0, "error": "brand_campaign_awards.json not found"}
    data = json.loads(AWARDS_JSON.read_text(encoding="utf-8"))
    conn = _conn()
    loaded = 0
    try:
        for a in data.get("awards", []):
            conn.execute(
                """INSERT INTO campaign_award
                   (award_id, title, client, brand, therapy_area, roster_link, roster_link_note,
                    festival, award, tier, year, agency, why_awarded, key_message, creative_summary,
                    images_description, source_urls_json, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(award_id) DO UPDATE SET
                     title=excluded.title, client=excluded.client, brand=excluded.brand,
                     therapy_area=excluded.therapy_area, roster_link=excluded.roster_link,
                     roster_link_note=excluded.roster_link_note, festival=excluded.festival,
                     award=excluded.award, tier=excluded.tier, year=excluded.year, agency=excluded.agency,
                     why_awarded=excluded.why_awarded, key_message=excluded.key_message,
                     creative_summary=excluded.creative_summary, images_description=excluded.images_description,
                     source_urls_json=excluded.source_urls_json, updated_at=excluded.updated_at""",
                (a.get("id"), a.get("title", ""), a.get("client", ""), a.get("brand", ""),
                 a.get("therapy_area", ""), a.get("roster_link", ""), a.get("roster_link_note", ""),
                 a.get("festival", ""), a.get("award", ""), a.get("tier", ""), a.get("year"),
                 a.get("agency", ""), a.get("why_awarded", ""), a.get("key_message", ""),
                 a.get("creative_summary", ""), a.get("images_description", ""),
                 json.dumps(a.get("source_urls", [])), _now()),
            )
            loaded += 1
        conn.commit()
    finally:
        conn.close()
    return {"loaded": loaded}


def _row_to_dict(r: sqlite3.Row, match: str) -> dict:
    return {
        "award_id": r["award_id"], "title": r["title"], "client": r["client"], "brand": r["brand"],
        "therapy_area": r["therapy_area"], "roster_link": r["roster_link"],
        "roster_link_note": r["roster_link_note"], "festival": r["festival"], "award": r["award"],
        "tier": r["tier"], "year": r["year"], "agency": r["agency"], "why_awarded": r["why_awarded"],
        "key_message": r["key_message"], "creative_summary": r["creative_summary"],
        "images_description": r["images_description"], "source_urls": json.loads(r["source_urls_json"] or "[]"),
        "match": match,
    }


def awards_for(brand: str = "", therapy_area: str = "", client: str = "", limit: int = 4) -> list[dict]:
    """Most relevant award campaigns, ranked brand > therapy_area > client > industry
    benchmark, de-duplicated. Ensures the JSON is loaded first (idempotent)."""
    load_awards()
    if not client:
        client = _client_for_brand(brand)
    conn = _conn()
    try:
        seen: set[str] = set()
        out: list[dict] = []

        def _collect(rows, match):
            for r in rows:
                if r["award_id"] not in seen:
                    seen.add(r["award_id"])
                    out.append(_row_to_dict(r, match))

        if brand:
            _collect(conn.execute("SELECT * FROM campaign_award WHERE brand=? ORDER BY year DESC", (brand,)).fetchall(), "brand")
        if therapy_area:
            _collect(conn.execute("SELECT * FROM campaign_award WHERE therapy_area=? ORDER BY year DESC", (therapy_area,)).fetchall(), "therapy_area")
        if client:
            _collect(conn.execute("SELECT * FROM campaign_award WHERE client=? ORDER BY year DESC", (client,)).fetchall(), "client")
        # Fill remaining slots with industry benchmarks (roster_link='industry').
        _collect(conn.execute("SELECT * FROM campaign_award WHERE roster_link='industry' ORDER BY year DESC").fetchall(), "industry")
        return out[:limit]
    finally:
        conn.close()


def all_awards() -> list[dict]:
    load_awards()
    conn = _conn()
    try:
        return [_row_to_dict(r, "all") for r in conn.execute("SELECT * FROM campaign_award ORDER BY year DESC, title").fetchall()]
    finally:
        conn.close()


if __name__ == "__main__":
    print(load_awards())
    print("Novartis / prostate cancer matches:")
    for a in awards_for(brand="", therapy_area="prostate cancer", client="Novartis"):
        print(f"  [{a['match']}] {a['title']} — {a['award']} ({a['festival']} {a['year']})")
