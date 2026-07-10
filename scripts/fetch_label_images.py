"""
Fetch REAL product images into the content-addressed blob store.

Source: DailyMed's SPL media API. Every brand in the roster already has its FDA Structured
Product Label indexed (data/omni_kb.db, source='dailymed', external_id = the SPL setid), and
DailyMed publishes that label's figures -- product photographs, structural formulae, dosing
and Kaplan-Meier charts -- as real JPG/PNG files:

    https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/<setid>/media.json
    https://dailymed.nlm.nih.gov/dailymed/image.cfm?setid=<setid>&name=<file>

These are the brand's own regulatory-approved label figures, so they are the most defensible
imagery a claims library can hold: public-domain US government-hosted content, traceable to
the exact SPL that substantiates the brand's claims. Each image is stored as real bytes in
the blob store, registered in the `blob` manifest, and catalogued as a `content_asset`
(asset_format='image') carrying the source URL for provenance.

Idempotent: assets are tagged with GEN_TAG in `id_code`; a rerun clears and rebuilds them.
The blob store is content-addressed, so re-downloading identical bytes is a no-op.

Usage:  python scripts/fetch_label_images.py [--per-brand N] [--brand NAME]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "strategy"))
import blob_store  # noqa: E402
import campaign_store  # noqa: E402

KB_DB = ROOT / "data" / "omni_kb.db"
CATALOG = ROOT / "config" / "client_brands.json"

GEN_TAG = "OMNIGEN"
IMG_TAG = f"{GEN_TAG}-IMG"
MEDIA_API = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{setid}/media.json"
UA = "OmniOS-DataHub/1.0 (research prototype; contact: brand team)"
DEFAULT_PER_BRAND = 6          # polite cap: enough variety without hammering DailyMed
SLEEP_BETWEEN = 0.4            # seconds between image downloads

_MIME = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif"}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _is_image(data: bytes) -> str | None:
    """Sniff the magic bytes so we never store an HTML error page as a 'JPEG'."""
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return None


def _setid_for(conn_kb: sqlite3.Connection, brand: str) -> tuple[str, str] | None:
    row = conn_kb.execute(
        "SELECT external_id, title FROM documents WHERE source='dailymed' AND search_term LIKE ? "
        "AND external_id IS NOT NULL LIMIT 1", (f"%{brand}%",)).fetchone()
    return (row[0], row[1]) if row else None


def _media_list(setid: str) -> list[dict]:
    try:
        payload = json.loads(_get(MEDIA_API.format(setid=setid)))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        print(f"    media API failed: {e}")
        return []
    return (payload.get("data") or {}).get("media") or []


def _clear_generated(conn) -> None:
    conn.execute("DELETE FROM content_asset WHERE id_code LIKE ?", (f"{IMG_TAG}-%",))
    conn.commit()


def build(per_brand: int = DEFAULT_PER_BRAND, only_brand: str = "") -> dict:
    campaign_store.init_db()
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    conn = sqlite3.connect(campaign_store.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn_kb = sqlite3.connect(KB_DB)

    _clear_generated(conn)
    stats = {"brands_with_images": 0, "brands_no_setid": 0, "images": 0, "bytes": 0,
             "skipped_non_image": 0, "failed": 0}
    try:
        for client, brands in catalog.get("clients", {}).items():
            for b in brands:
                brand = b["brand"]
                if only_brand and brand.lower() != only_brand.lower():
                    continue
                found = _setid_for(conn_kb, brand)
                if not found:
                    print(f"[{brand}] no DailyMed setid indexed — skipping")
                    stats["brands_no_setid"] += 1
                    continue
                setid, label_title = found
                media = _media_list(setid)
                if not media:
                    print(f"[{brand}] no media on SPL {setid[:8]}…")
                    continue

                bid = campaign_store._brand_id(conn, brand, b.get("therapy_area", ""),
                                               b.get("generic", ""), b.get("lifecycle_key", ""), client)
                n = 0
                for i, m in enumerate(media[:per_brand], start=1):
                    name, url = m.get("name", ""), m.get("url", "")
                    if not url:
                        continue
                    try:
                        data = _get(url)
                    except Exception as e:  # noqa: BLE001
                        print(f"    {name}: download failed ({e})")
                        stats["failed"] += 1
                        continue
                    mime = _is_image(data)
                    if not mime:
                        print(f"    {name}: not an image (got {len(data)}b) — skipped")
                        stats["skipped_non_image"] += 1
                        continue

                    manifest = blob_store.put(data, mime_type=mime, original_name=name)
                    conn.execute(
                        "INSERT OR IGNORE INTO blob (blob_key, mime_type, byte_size, original_name, storage_uri, created_at) "
                        "VALUES (?,?,?,?,?,?)",
                        (manifest["blob_key"], mime, manifest["byte_size"], name, manifest["storage_uri"], _now()))
                    conn.execute(
                        """INSERT INTO content_asset (brand_id, indication_id, file_name, title, asset_format,
                           branded, target_group, description, url, id_code, blob_key, created_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (bid, None, name, f"{brand} label figure {i}", "image", 1, "HCP — specialist",
                         f"Figure from the FDA Structured Product Label for {brand} "
                         f"(SPL setid {setid}). Public-domain label artwork; use per MLR guidance.",
                         url, f"{IMG_TAG}-{brand[:4].upper()}-{i}", manifest["blob_key"], _now()))
                    n += 1
                    stats["images"] += 1
                    stats["bytes"] += manifest["byte_size"]
                    time.sleep(SLEEP_BETWEEN)
                if n:
                    stats["brands_with_images"] += 1
                    print(f"[{brand}] {n} label image(s) from SPL {setid[:8]}…")
                conn.commit()
    finally:
        conn.commit()
        conn.close()
        conn_kb.close()
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-brand", type=int, default=DEFAULT_PER_BRAND)
    ap.add_argument("--brand", default="")
    a = ap.parse_args()
    print("Fetching real FDA label images from DailyMed into the blob store…")
    s = build(a.per_brand, a.brand)
    s["megabytes"] = round(s["bytes"] / 1_048_576, 2)
    print(json.dumps(s, indent=2))
