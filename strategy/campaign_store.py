"""Data-access layer for the Campaign & Content data model (db/campaign_content_schema.sql).

Initialises the relational schema on SQLite (portable to Oracle PL/SQL / Postgres -- see
the DDL header), wires it to the content-addressed blob_store, and persists a generated
campaign plan into the normalized model: brand/indication, campaign + version (plan md +
result JSON go to the blob store), segment, messages, an atomic-claims library with
claim<->reference substantiation, DAM content assets, channels and KPIs.

This is what turns a one-off generated plan into queryable, reusable content assets --
the point of the data structure the home dashboard reports against.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import blob_store  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
# The package import, not a flat `import brand_kit`: a second module instance would keep its
# own stale kit cache and miss brands created since it first loaded (see brand_journey.py).
from strategy import brand_kit  # noqa: E402
import db  # noqa: E402  (dual-dialect SQLite/Postgres connection factory)
from paths import data_path  # noqa: E402

DB_PATH = data_path("campaigns.db")
SCHEMA_PATH = pathlib.Path(__file__).resolve().parent.parent / "db" / "campaign_content_schema.sql"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _conn():
    return db.connect("campaigns")


# Columns added after databases already existed. CREATE TABLE IF NOT EXISTS won't add them,
# so each is attempted with a plain ADD COLUMN whose "already exists" error is swallowed
# (the projects.py idiom; the rollback keeps Postgres' transaction usable).
_ADDED_COLUMNS = (
    ("brand", "kit_key", "TEXT"),
    ("campaign", "engagement_plan_id", "INTEGER REFERENCES engagement_plan(id)"),
    ("campaign", "closed_at", "TEXT"),
    ("campaign", "status_detail", "TEXT"),
    ("campaign", "snapshot_json", "TEXT"),
    ("campaign", "snapshot_at", "TEXT"),
    ("campaign_version", "snapshot_json", "TEXT"),
    # "rules": base + structured edits (the Journey model). "document": the Campaign Plan's
    # Operations diagram, a WorkflowDocument kept on the project and edited in its own
    # editor (hierarchy plan U6, user decision 2026-09-24). layout_json holds a frozen copy
    # only when the campaign was closed by a move to another brand.
    ("flow", "kind", "TEXT NOT NULL DEFAULT 'rules'"),
    ("flow", "layout_json", "TEXT"),
)
# Indexes on added columns, created only once the columns exist.
_ADDED_INDEXES = (
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_brand_kit_key ON brand(kit_key) WHERE kit_key IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS ix_campaign_plan ON campaign(engagement_plan_id)",
    "CREATE INDEX IF NOT EXISTS ix_campaign_project ON campaign(project_id)",
)


def init_db() -> None:
    """Create the schema if missing and add later columns (idempotent)."""
    conn = _conn()
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
        for table, col, decl in _ADDED_COLUMNS:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
                conn.commit()
            except Exception:  # noqa: BLE001  (SQLite: OperationalError; Postgres: DuplicateColumn)
                conn.rollback()
        for ddl in _ADDED_INDEXES:
            conn.execute(ddl)
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------ blob manifest ----

def _store_blob(conn: sqlite3.Connection, data: str | bytes, mime: str, name: str) -> str | None:
    if data is None:
        return None
    manifest = blob_store.put(data, mime_type=mime, original_name=name)
    conn.execute(
        "INSERT OR IGNORE INTO blob (blob_key, mime_type, byte_size, original_name, storage_uri, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (manifest["blob_key"], manifest["mime_type"], manifest["byte_size"],
         manifest["original_name"], manifest["storage_uri"], _now()),
    )
    return manifest["blob_key"]


# ------------------------------------------------------------------ upserts -----------

def brand_row_for_kit(conn, key: str) -> int:
    """The brand row for brand-kit key `key` (brand.kit_key), linking an existing row of the
    same case-insensitive name or creating one. The one place kit brands get their row."""
    row = conn.execute("SELECT id FROM brand WHERE kit_key=?", (key,)).fetchone()
    if row:
        return row["id"]
    row = conn.execute("SELECT id FROM brand WHERE lower(name)=lower(?) AND kit_key IS NULL "
                       "ORDER BY CASE WHEN name=? THEN 0 ELSE 1 END, id LIMIT 1", (key, key)).fetchone()
    if row:
        conn.execute("UPDATE brand SET kit_key=? WHERE id=?", (key, row["id"]))
        return row["id"]
    kit = brand_kit.kit_for(key) or {}
    cur = conn.execute(
        "INSERT INTO brand (name, generic_name, therapy_area, kit_key) VALUES (?,?,?,?)",
        (key, kit.get("generic") or None, kit.get("therapy_area") or None, key),
    )
    return cur.lastrowid


def _brand_id(conn, brand: str, therapy_area: str = "", generic: str = "", lifecycle: str = "",
              client: str = "") -> int | None:
    if not brand:
        return None
    key = brand_kit.canonical_key(brand)
    if key is not None:
        bid = brand_row_for_kit(conn, key)
        if client:
            conn.execute("INSERT OR IGNORE INTO client (name) VALUES (?)", (client,))
            cid = conn.execute("SELECT id FROM client WHERE name=?", (client,)).fetchone()["id"]
            conn.execute("UPDATE brand SET client_id=COALESCE(client_id, ?) WHERE id=?", (cid, bid))
        return bid
    client_id = None
    if client:
        conn.execute("INSERT OR IGNORE INTO client (name) VALUES (?)", (client,))
        client_id = conn.execute("SELECT id FROM client WHERE name=?", (client,)).fetchone()["id"]
    row = conn.execute("SELECT id FROM brand WHERE name=?", (brand,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO brand (client_id, name, generic_name, therapy_area, lifecycle_key) VALUES (?,?,?,?,?)",
        (client_id, brand, generic or None, therapy_area or None, lifecycle or None),
    )
    return cur.lastrowid


def _indication_id(conn, brand_id: int | None, label: str) -> int | None:
    if not brand_id or not label:
        return None
    row = conn.execute("SELECT id FROM indication WHERE brand_id=? AND label=?", (brand_id, label)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO indication (brand_id, label) VALUES (?,?)", (brand_id, label))
    return cur.lastrowid


def _ref_id(conn, source_type: str, citation: str, url: str = "", external_id: str = "") -> int:
    if external_id:
        row = conn.execute("SELECT id FROM ref_source WHERE source_type=? AND external_id=?",
                           (source_type, external_id)).fetchone()
        if row:
            return row["id"]
    cur = conn.execute(
        "INSERT INTO ref_source (source_type, citation, url, external_id, created_at) VALUES (?,?,?,?,?)",
        (source_type, citation[:500], url or None, external_id or None, _now()),
    )
    return cur.lastrowid


# ------------------------------------------------------------------ main persist ------

def persist_campaign_from_result(result: dict, slots: dict, plan_markdown: str = "",
                                 project_id: str = "") -> dict:
    """Fold a generated plan (orchestrator result + captured slots) into the normalized
    model. Returns a small summary of what was written. Best-effort: never raises into the
    request path -- a failure here must not break plan generation.

    A project already linked to an open campaign (the Campaign Plan of a campaign) gets a new
    version on that campaign; its derived rows (segment, messages, channels, KPIs) are
    replaced to match the latest run. Only an unlinked project inserts a campaign."""
    init_db()
    conn = _conn()
    try:
        brand = slots.get("brand") or result.get("brand", "")
        ta = slots.get("therapy_area") or result.get("therapy_area", "")
        indication = slots.get("indication") or result.get("indication", "")
        inferred = result.get("inferred_inputs", {})
        strat = result.get("stage_2_4_strategy", {})
        budget = (result.get("stage_5_budget") or {}).get("total_budget")

        linked = conn.execute(
            "SELECT id, brand_id FROM campaign WHERE project_id=? AND status<>'closed' ORDER BY id DESC LIMIT 1",
            (project_id,),
        ).fetchone() if project_id else None

        if linked:
            campaign_id, bid = linked["id"], linked["brand_id"]
            iid = _indication_id(conn, bid, indication)
            conn.execute(
                """UPDATE campaign SET indication_id=?, lifecycle_key=?, persona=?, journey_stage=?,
                   cx_maturity=?, objective=?, total_budget=?, updated_at=? WHERE id=?""",
                (iid, slots.get("lifecycle_key"), inferred.get("persona"), inferred.get("stage_label"),
                 (result.get("cx_maturity") or {}).get("level"),
                 (strat.get("stage_profile") or {}).get("engagement_goal"), budget, _now(), campaign_id),
            )
            for table in ("campaign_segment", "campaign_message", "campaign_channel", "campaign_kpi"):
                conn.execute(f"DELETE FROM {table} WHERE campaign_id=?", (campaign_id,))
        else:
            bid = _brand_id(conn, brand, ta, lifecycle=slots.get("lifecycle_key", ""))
            iid = _indication_id(conn, bid, indication)
            cur = conn.execute(
                """INSERT INTO campaign (project_id, brand_id, indication_id, name, lifecycle_key, persona,
                   journey_stage, cx_maturity, objective, total_budget, status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (project_id or None, bid, iid, f"{brand} · {indication or ta}".strip(" ·"),
                 slots.get("lifecycle_key"), inferred.get("persona"), inferred.get("stage_label"),
                 (result.get("cx_maturity") or {}).get("level"),
                 (strat.get("stage_profile") or {}).get("engagement_goal"),
                 budget, "draft", _now(), _now()),
            )
            campaign_id = cur.lastrowid

        # Versioned snapshot -> blob store (plan markdown + full result JSON).
        plan_key = _store_blob(conn, plan_markdown, "text/markdown", f"{brand}_plan.md") if plan_markdown else None
        result_key = _store_blob(conn, json.dumps(result), "application/json", f"{brand}_result.json")
        version_no = (conn.execute("SELECT COALESCE(MAX(version_no), 0) AS n FROM campaign_version "
                                   "WHERE campaign_id=?", (campaign_id,)).fetchone()["n"] or 0) + 1
        snapshot = conn.execute("SELECT snapshot_json FROM campaign WHERE id=?", (campaign_id,)).fetchone()
        conn.execute(
            "INSERT INTO campaign_version (campaign_id, version_no, plan_blob_key, result_blob_key, created_at, "
            "snapshot_json) VALUES (?,?,?,?,?,?)",
            (campaign_id, version_no, plan_key, result_key, _now(), snapshot["snapshot_json"] if snapshot else None),
        )

        # Segment profile.
        sp = result.get("stage_2_4_segment_profile") or {}
        if sp:
            conn.execute(
                "INSERT INTO campaign_segment (campaign_id, persona, abcd_json, ladder_json, digital_json) "
                "VALUES (?,?,?,?,?)",
                (campaign_id, inferred.get("persona"),
                 json.dumps(sp.get("abcd_segmentation_pct")), json.dumps(sp.get("adoption_ladder_pct")),
                 json.dumps(sp.get("digital_preference_pct"))),
            )

        # Messages + an atomic-claims library with claim<->reference substantiation.
        mf = result.get("stage_2_4_message_flow") or {}
        kb = strat.get("kb_grounding") or {}
        # Build a small reference pool from real KB documents (brand + therapy area).
        ref_ids: list[int] = []
        for scope in ("brand", "therapy_area"):
            for src, items in (kb.get(scope) or {}).items():
                for it in items[:2]:
                    ref_ids.append(_ref_id(conn, src, it.get("title", ""), it.get("url", "")))
        claims_written = 0
        for ord_i, km in enumerate(mf.get("key_messages", [])):
            cur = conn.execute(
                "INSERT INTO campaign_message (campaign_id, topic, ord) VALUES (?,?,?)",
                (campaign_id, km.get("topic", ""), ord_i),
            )
            msg_id = cur.lastrowid
            for supporting in km.get("supporting_messages", []):
                if not supporting or supporting.startswith("["):
                    continue  # skip the toolkit's placeholder brackets
                cur = conn.execute(
                    """INSERT INTO claim (brand_id, indication_id, text, claim_type, claim_status, created_at)
                       VALUES (?,?,?,?,?,?)""",
                    (bid, iid, supporting, _classify_claim(km.get("topic", ""), supporting), "draft", _now()),
                )
                claim_id = cur.lastrowid
                claims_written += 1
                if claim_id == cur.lastrowid and ord_i == 0:
                    conn.execute("UPDATE campaign_message SET claim_id=? WHERE id=?", (claim_id, msg_id))
                # Substantiate against the first available real reference (traceability).
                if ref_ids:
                    conn.execute("INSERT OR IGNORE INTO claim_reference (claim_id, ref_id, locator) VALUES (?,?,?)",
                                 (claim_id, ref_ids[claims_written % len(ref_ids)], None))

        # DAM content assets (the Sheet-8 audit seeds -> catalogue rows).
        persona = inferred.get("persona", "")
        assets_written = 0
        for km in mf.get("key_messages", []):
            conn.execute(
                """INSERT INTO content_asset (brand_id, indication_id, title, asset_format, branded,
                   target_group, description, created_at) VALUES (?,?,?,?,?,?,?,?)""",
                (bid, iid, km.get("topic", ""), "email", 1, persona,
                 (km.get("supporting_messages") or [""])[0], _now()),
            )
            assets_written += 1

        # Channels + KPIs.
        alloc = (result.get("stage_5_budget") or {}).get("allocation") or {}
        pp_npp = {r["channel"]: r["bucket"] for r in (result.get("stage_2_4_pp_npp") or [])}
        for ch, v in alloc.items():
            conn.execute(
                "INSERT INTO campaign_channel (campaign_id, channel, share_pct, budget_amount, pp_npp) VALUES (?,?,?,?,?)",
                (campaign_id, ch, v.get("pct"), v.get("amount"), pp_npp.get(ch)),
            )
        kpi = result.get("stage_7_kpi") or {}
        for kind, key in [("leading", "leading_indicators"), ("lagging", "lagging_indicators"),
                          ("operational", "operational_kpis")]:
            for metric in kpi.get(key, []):
                conn.execute("INSERT INTO campaign_kpi (campaign_id, kpi_type, metric) VALUES (?,?,?)",
                             (campaign_id, kind, metric))

        conn.commit()
        return {"campaign_id": campaign_id, "version_no": version_no, "claims": claims_written,
                "assets": assets_written, "references": len(ref_ids)}
    finally:
        conn.close()


def _classify_claim(topic: str, text: str) -> str:
    t = (topic + " " + text).lower()
    if "safety" in t or "adverse" in t or "tolerab" in t:
        return "safety"
    if "dosing" in t or "administration" in t:
        return "access"
    if "mechanism" in t or "moa" in t:
        return "moa"
    return "efficacy"


# ------------------------------------------------------------------ read helpers ------

def library_stats() -> dict:
    """Aggregate counts for the home dashboard's data-model panel."""
    init_db()
    conn = _conn()
    try:
        def one(q: str) -> int:
            return conn.execute(q).fetchone()[0]
        return {
            "campaigns": one("SELECT COUNT(*) FROM campaign"),
            "claims": one("SELECT COUNT(*) FROM claim"),
            "claims_approved": one("SELECT COUNT(*) FROM claim WHERE claim_status='approved'"),
            "references": one("SELECT COUNT(*) FROM ref_source"),
            "content_assets": one("SELECT COUNT(*) FROM content_asset"),
            "content_modules": one("SELECT COUNT(*) FROM content_module"),
            "blobs": one("SELECT COUNT(*) FROM blob"),
            "unsubstantiated_claims": one("SELECT COUNT(*) FROM v_unsubstantiated_claims"),
        }
    finally:
        conn.close()


def content_library_for(brand: str, indication: str = "") -> dict:
    """The reusable content library for a brand (optionally narrowed to an indication):
    claims (with substantiating references), reusable modules, and DAM assets. This is what
    the Brand Engagement Plan's Phase-2/3 sections render -- real claims/references/components
    extracted from the library, not placeholders. Brand-level claims (indication_id NULL) are
    always included; indication-specific claims are included when they match `indication`.
    Returns empty lists when the brand isn't in the library yet (plan then falls back to its
    template)."""
    init_db()
    conn = _conn()
    try:
        brow = conn.execute("SELECT id FROM brand WHERE name=?", (brand,)).fetchone()
        if not brow:
            return {"brand": brand, "indication": indication, "found": False,
                    "claims": [], "modules": [], "assets": [], "counts": {}}
        bid = brow["id"]
        iid = None
        if indication:
            irow = conn.execute("SELECT id FROM indication WHERE brand_id=? AND label=?", (bid, indication)).fetchone()
            iid = irow["id"] if irow else None

        # Claims: brand-level (NULL indication) + the selected indication's claims.
        if iid is not None:
            claim_rows = conn.execute(
                "SELECT * FROM claim WHERE brand_id=? AND (indication_id IS NULL OR indication_id=?) "
                "ORDER BY CASE claim_status WHEN 'approved' THEN 0 WHEN 'in_review' THEN 1 ELSE 2 END, id",
                (bid, iid)).fetchall()
        else:
            claim_rows = conn.execute(
                "SELECT * FROM claim WHERE brand_id=? "
                "ORDER BY CASE claim_status WHEN 'approved' THEN 0 WHEN 'in_review' THEN 1 ELSE 2 END, id",
                (bid,)).fetchall()
        claims = []
        for c in claim_rows:
            refs = conn.execute(
                "SELECT rs.source_type, rs.citation, rs.url, rs.external_id, cr.locator "
                "FROM claim_reference cr JOIN ref_source rs ON rs.id=cr.ref_id WHERE cr.claim_id=?",
                (c["id"],)).fetchall()
            claims.append({
                "id": c["id"], "text": c["text"], "claim_type": c["claim_type"],
                "status": c["claim_status"], "material_number": c["material_number"],
                "references": [dict(r) for r in refs],
            })

        # Modules (brand-level + indication) with their claim texts.
        if iid is not None:
            mod_rows = conn.execute(
                "SELECT * FROM content_module WHERE brand_id=? AND (indication_id IS NULL OR indication_id=?) ORDER BY id",
                (bid, iid)).fetchall()
        else:
            mod_rows = conn.execute("SELECT * FROM content_module WHERE brand_id=? ORDER BY id", (bid,)).fetchall()
        modules = []
        for m in mod_rows:
            mc = conn.execute(
                "SELECT c.text FROM module_claim mc JOIN claim c ON c.id=mc.claim_id WHERE mc.module_id=?",
                (m["id"],)).fetchall()
            modules.append({"id": m["id"], "name": m["name"], "module_type": m["module_type"],
                            "status": m["status"], "material_number": m["material_number"],
                            "business_rules": m["business_rules"], "claims": [r["text"] for r in mc]})

        # DAM assets (indication-scoped when an indication is given, else all for the brand).
        if iid is not None:
            asset_rows = conn.execute(
                "SELECT * FROM content_asset WHERE brand_id=? AND (indication_id IS NULL OR indication_id=?) ORDER BY id",
                (bid, iid)).fetchall()
        else:
            asset_rows = conn.execute("SELECT * FROM content_asset WHERE brand_id=? ORDER BY id", (bid,)).fetchall()
        assets = []
        for a in asset_rows:
            mods = conn.execute(
                "SELECT cm.name FROM asset_module am JOIN content_module cm ON cm.id=am.module_id WHERE am.asset_id=?",
                (a["id"],)).fetchall()
            assets.append({"id": a["id"], "title": a["title"], "file_name": a["file_name"],
                           "asset_format": a["asset_format"], "branded": bool(a["branded"]),
                           "target_group": a["target_group"], "description": a["description"],
                           "url": a["url"], "id_code": a["id_code"], "blob_key": a["blob_key"],
                           "modules": [r["name"] for r in mods]})

        return {
            "brand": brand, "indication": indication, "found": True,
            "claims": claims, "modules": modules, "assets": assets,
            "counts": {"claims": len(claims), "approved_claims": sum(1 for c in claims if c["status"] == "approved"),
                       "modules": len(modules), "assets": len(assets),
                       "references": len({r["external_id"] or r["citation"] for c in claims for r in c["references"]})},
        }
    finally:
        conn.close()


def blob_meta(blob_key: str) -> dict | None:
    """Mime type / size / original name for a stored blob, so the API can serve it with the
    right Content-Type. Returns None for an unknown key."""
    init_db()
    conn = _conn()
    try:
        r = conn.execute("SELECT blob_key, mime_type, byte_size, original_name FROM blob WHERE blob_key=?",
                         (blob_key,)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def library_brands() -> dict:
    """Index for the Claims Library view: one row per brand that has library content, with
    its claim / reference / module / asset / image counts, plus portfolio totals."""
    init_db()
    conn = _conn()
    try:
        rows = conn.execute("""
            SELECT b.id, b.name AS brand, b.generic_name, b.therapy_area, b.lifecycle_key,
                   COALESCE(c.name, '') AS client,
                   (SELECT COUNT(*) FROM claim x WHERE x.brand_id=b.id) AS claims,
                   (SELECT COUNT(*) FROM claim x WHERE x.brand_id=b.id AND x.claim_status='approved') AS approved,
                   (SELECT COUNT(*) FROM content_module m WHERE m.brand_id=b.id) AS modules,
                   (SELECT COUNT(*) FROM content_asset a WHERE a.brand_id=b.id) AS assets,
                   (SELECT COUNT(*) FROM content_asset a WHERE a.brand_id=b.id AND a.asset_format='image') AS images,
                   (SELECT COUNT(DISTINCT i.id) FROM indication i WHERE i.brand_id=b.id) AS indications
            FROM brand b LEFT JOIN client c ON c.id = b.client_id
            ORDER BY c.name, b.name""").fetchall()
        brands = [dict(r) for r in rows if r["claims"] or r["assets"]]
        for b in brands:
            b["references"] = conn.execute(
                "SELECT COUNT(DISTINCT cr.ref_id) FROM claim_reference cr JOIN claim c2 ON c2.id=cr.claim_id "
                "WHERE c2.brand_id=?", (b["id"],)).fetchone()[0]
            # Kit brands: the authored components (with real images) replace the DB's counts,
            # same "kit wins" rule as brand_library_detail().
            kit = brand_kit.kit_for(b["brand"])
            if kit and kit.get("components"):
                kit_lib = brand_kit.content_library_from_kit(kit)
                b["claims"] = len(kit_lib["claims"])
                b["approved"] = kit_lib["counts"]["approved_claims"]
                b["assets"] = len(kit_lib["assets"])
                b["images"] = sum(1 for a in kit_lib["assets"] if a.get("image_url"))
                b["references"] = kit_lib["counts"]["references"]
        stats = library_stats()
        return {"brands": brands, "totals": stats}
    finally:
        conn.close()


def brand_library_detail(brand: str) -> dict:
    """Everything the Claims Library shows for one brand: claims grouped by type (each with
    its substantiating references), reusable modules, and the DAM assets split into images
    (real bytes in the blob store) and other creative."""
    init_db()
    conn = _conn()
    try:
        brow = conn.execute("SELECT * FROM brand WHERE name=?", (brand,)).fetchone()
        if not brow:
            return {"found": False, "brand": brand}
        bid = brow["id"]
        client = conn.execute("SELECT name FROM client WHERE id=?", (brow["client_id"],)).fetchone()
        indications = [r["label"] for r in conn.execute(
            "SELECT label FROM indication WHERE brand_id=? ORDER BY id", (bid,)).fetchall()]

        claims = []
        for c in conn.execute(
                "SELECT * FROM claim WHERE brand_id=? ORDER BY "
                "CASE claim_status WHEN 'approved' THEN 0 WHEN 'in_review' THEN 1 ELSE 2 END, id", (bid,)).fetchall():
            refs = conn.execute(
                "SELECT rs.source_type, rs.citation, rs.url, rs.external_id, cr.locator "
                "FROM claim_reference cr JOIN ref_source rs ON rs.id=cr.ref_id WHERE cr.claim_id=?",
                (c["id"],)).fetchall()
            ind = conn.execute("SELECT label FROM indication WHERE id=?", (c["indication_id"],)).fetchone() \
                if c["indication_id"] else None
            claims.append({"id": c["id"], "text": c["text"], "claim_type": c["claim_type"],
                           "status": c["claim_status"], "material_number": c["material_number"],
                           "mlr_code": c["mlr_code"], "approved_at": c["approved_at"],
                           "expires_at": c["expires_at"], "indication": ind["label"] if ind else "",
                           "references": [dict(r) for r in refs]})

        modules = []
        for m in conn.execute("SELECT * FROM content_module WHERE brand_id=? ORDER BY id", (bid,)).fetchall():
            mc = conn.execute("SELECT c.id, c.text FROM module_claim mc JOIN claim c ON c.id=mc.claim_id "
                              "WHERE mc.module_id=?", (m["id"],)).fetchall()
            modules.append({"id": m["id"], "name": m["name"], "module_type": m["module_type"],
                            "status": m["status"], "material_number": m["material_number"],
                            "business_rules": m["business_rules"], "claims": [dict(x) for x in mc]})

        images, assets = [], []
        for a in conn.execute("SELECT * FROM content_asset WHERE brand_id=? ORDER BY asset_format, id", (bid,)).fetchall():
            item = {"id": a["id"], "title": a["title"], "file_name": a["file_name"],
                    "asset_format": a["asset_format"], "branded": bool(a["branded"]),
                    "target_group": a["target_group"], "description": a["description"],
                    "url": a["url"], "id_code": a["id_code"], "blob_key": a["blob_key"]}
            (images if a["asset_format"] == "image" else assets).append(item)

        # A brand-kit's authored claims + creative components (with real image URLs) are the
        # source of truth for a kit brand -- they win over whatever lossy echo a prior plan
        # run persisted here (same "kit wins" rule brand_kit_mod applies for the live plan;
        # see orchestrator.py). Non-kit brands are untouched.
        kit = brand_kit.kit_for(brand)
        if kit and kit.get("components"):
            kit_lib = brand_kit.content_library_from_kit(kit, indications[0] if indications else "")
            claims = kit_lib["claims"]
            assets = kit_lib["assets"]

        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for c in claims:
            by_type[c["claim_type"]] = by_type.get(c["claim_type"], 0) + 1
            by_status[c["status"]] = by_status.get(c["status"], 0) + 1

        image_count = len(images) + sum(1 for a in assets if a.get("image_url"))
        return {"found": True, "brand": brand, "generic": brow["generic_name"],
                "therapy_area": brow["therapy_area"], "lifecycle_key": brow["lifecycle_key"],
                "client": client["name"] if client else "", "indications": indications,
                "claims": claims, "modules": modules, "images": images, "assets": assets,
                "counts": {"claims": len(claims), "approved": by_status.get("approved", 0),
                           "modules": len(modules), "images": image_count, "assets": len(assets),
                           "by_type": by_type, "by_status": by_status}}
    finally:
        conn.close()


def campaign_counts_by_brand() -> dict[str, int]:
    init_db()
    conn = _conn()
    try:
        # Open campaigns, the same count the Cockpit's brand overview shows (hierarchy R-R6);
        # keyed by the brand row's name and its brand-kit key, in any case, so a roster name
        # and a kit key that differ only in case agree.
        rows = conn.execute(
            "SELECT b.name AS name, b.kit_key AS kit_key, COUNT(c.id) AS n FROM campaign c "
            "JOIN brand b ON b.id=c.brand_id WHERE c.status<>'closed' GROUP BY b.id, b.name, b.kit_key"
        ).fetchall()
        out: dict[str, int] = {}
        for r in rows:
            keys = {r["name"], r["kit_key"]} - {None}
            for k in keys | {k.lower() for k in keys}:
                out[k] = out.get(k, 0) + r["n"]
        return out
    finally:
        conn.close()
