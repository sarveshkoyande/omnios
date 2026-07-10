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
from paths import data_path  # noqa: E402

KB_DB = data_path("omni_kb.db")
CATALOG = ROOT / "config" / "client_brands.json"

# Committed seed of the fetched label images. data/ is gitignored (it holds regenerable DBs
# and scraped caches), so the images live here instead: version-controlled, human-browsable,
# and used in preference to the network so a fresh clone rebuilds the library offline
# without re-hitting DailyMed. Delete a file here to force a re-download of just that image.
SEED_DIR = ROOT / "assets" / "label_images"
SEED_MANIFEST = SEED_DIR / "manifest.json"

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


IMAGE_URL = "https://dailymed.nlm.nih.gov/dailymed/image.cfm?setid={setid}&name={name}"


def _media_from_seed(brand: str, setid: str) -> list[dict]:
    """Reconstruct the media list from the committed seed directory, so a rebuild works with
    no network at all (the media API is the only other place filenames come from)."""
    d = SEED_DIR / _safe(brand)
    if not d.is_dir():
        return []
    return [{"name": p.name, "url": IMAGE_URL.format(setid=setid, name=p.name)}
            for p in sorted(d.iterdir()) if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif")]


def _media_list(setid: str, brand: str = "") -> list[dict]:
    try:
        payload = json.loads(_get(MEDIA_API.format(setid=setid)))
        media = (payload.get("data") or {}).get("media") or []
        if media:
            return media
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as e:
        print(f"    media API unavailable ({e}) — falling back to the committed seed")
    return _media_from_seed(brand, setid)


def _safe(name: str) -> str:
    return "".join(ch if (ch.isalnum() or ch in "-_.") else "_" for ch in name)


def _seed_path(brand: str, name: str) -> pathlib.Path:
    return SEED_DIR / _safe(brand) / _safe(name)


def _read_seed(brand: str, name: str) -> bytes | None:
    p = _seed_path(brand, name)
    return p.read_bytes() if p.exists() else None


def _write_seed(brand: str, name: str, data: bytes) -> None:
    p = _seed_path(brand, name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def export_seeds() -> dict:
    """Dump every image already in the blob store out to the committed seed directory,
    using the content_asset catalogue for the brand/filename/source-url mapping. Run once
    after a network fetch so the images can be version-controlled."""
    campaign_store.init_db()
    conn = sqlite3.connect(campaign_store.DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT b.name AS brand, a.file_name, a.blob_key, a.url, a.description "
        "FROM content_asset a JOIN brand b ON b.id=a.brand_id "
        "WHERE a.asset_format='image' AND a.blob_key IS NOT NULL ORDER BY b.name, a.id").fetchall()
    manifest, n, total = {}, 0, 0
    for r in rows:
        data = blob_store.get(r["blob_key"])
        if data is None:
            continue
        _write_seed(r["brand"], r["file_name"], data)
        manifest.setdefault(r["brand"], []).append(
            {"file": _safe(r["file_name"]), "blob_key": r["blob_key"], "bytes": len(data),
             "source_url": r["url"], "note": r["description"]})
        n += 1
        total += len(data)
    conn.close()
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    SEED_MANIFEST.write_text(json.dumps({
        "note": "Real figures from each brand's FDA Structured Product Label (DailyMed). "
                "Public-domain US-government content, traceable to the SPL that substantiates the "
                "brand's claims. Used as an offline seed by scripts/fetch_label_images.py.",
        "generated_by": "scripts/fetch_label_images.py --export-seeds",
        "images": n, "brands": len(manifest), "brand_images": manifest,
    }, indent=2), encoding="utf-8")
    return {"exported": n, "brands": len(manifest), "megabytes": round(total / 1_048_576, 2)}


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
             "from_seed": 0, "downloaded": 0, "skipped_non_image": 0, "failed": 0}
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
                media = _media_list(setid, brand)
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
                    # Prefer the committed seed: a fresh clone rebuilds offline and we don't
                    # re-hit DailyMed for bytes we already have under version control.
                    data = _read_seed(brand, name)
                    from_seed = data is not None
                    if not from_seed:
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
                    if not from_seed:
                        _write_seed(brand, name, data)   # keep the seed current
                    stats["from_seed" if from_seed else "downloaded"] += 1

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
                    if not from_seed:
                        time.sleep(SLEEP_BETWEEN)   # only rate-limit real network calls
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
    ap = argparse.ArgumentParser(description="Fetch real FDA label images into the blob store.")
    ap.add_argument("--per-brand", type=int, default=DEFAULT_PER_BRAND)
    ap.add_argument("--brand", default="")
    ap.add_argument("--export-seeds", action="store_true",
                    help="dump images already in the blob store to the committed assets/label_images seed")
    a = ap.parse_args()
    if a.export_seeds:
        print("Exporting blob-store images to the committed seed…")
        print(json.dumps(export_seeds(), indent=2))
    else:
        print("Fetching FDA label images (committed seed preferred, DailyMed as fallback)…")
        s = build(a.per_brand, a.brand)
        s["megabytes"] = round(s["bytes"] / 1_048_576, 2)
        print(json.dumps(s, indent=2))
