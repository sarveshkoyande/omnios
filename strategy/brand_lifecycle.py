"""
Brand market-intelligence store: per-brand lifecycle-stage assessment and market
analysis, loaded from config/brand_market_intel.json into the brand_market_intel table
(db/campaign_content_schema.sql, SQLite via data/campaigns.db).

This is the second of the two data stores requested: a market-analysis store that says,
for every flagship brand, what lifecycle stage it is in and why -- grounded in public
market evidence -- so the dashboard and the planning agent can reason about stage rather
than trusting a hardcoded roster default.

`load_market_intel()` (idempotent) upserts every brand's analysis; `get_market_intel()`
and `all_market_intel()` read it back; `stage_distribution()` powers a dashboard rollup.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import campaign_store  # noqa: E402  (reuses its DB path, schema init, and brand upsert)

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
INTEL_JSON = BASE_DIR / "config" / "brand_market_intel.json"
CATALOG_JSON = BASE_DIR / "config" / "client_brands.json"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _conn() -> sqlite3.Connection:
    campaign_store.init_db()
    conn = sqlite3.connect(campaign_store.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _brand_client_map() -> dict[str, dict]:
    """brand_name -> {client, therapy_area, generic, lifecycle_key} from the roster."""
    if not CATALOG_JSON.exists():
        return {}
    data = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    out = {}
    for client, brands in data.get("clients", {}).items():
        for b in brands:
            out[b["brand"]] = {"client": client, "therapy_area": b.get("therapy_area", ""),
                               "generic": b.get("generic", ""), "lifecycle_key": b.get("lifecycle_key", "")}
    return out


def load_market_intel() -> dict:
    """Upsert every brand's market analysis into brand_market_intel. Idempotent.
    Also ensures a brand row (with client) exists so the intel links to it. Returns
    a summary count."""
    if not INTEL_JSON.exists():
        return {"loaded": 0, "error": "brand_market_intel.json not found"}
    intel = json.loads(INTEL_JSON.read_text(encoding="utf-8"))
    as_of = intel.get("as_of", "")
    roster = _brand_client_map()
    conn = _conn()
    loaded = 0
    try:
        for brand, m in intel.get("brands", {}).items():
            meta = roster.get(brand, {})
            bid = campaign_store._brand_id(
                conn, brand, therapy_area=meta.get("therapy_area", ""),
                generic=meta.get("generic", ""), lifecycle=meta.get("lifecycle_key", ""),
                client=meta.get("client", ""))
            conn.execute(
                """INSERT INTO brand_market_intel
                   (brand_id, brand_name, lifecycle_stage, stage_confidence, momentum,
                    evidence_json, catalysts_json, competitors_json, loe_horizon, whitespace,
                    campaign_posture, as_of, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(brand_name) DO UPDATE SET
                     brand_id=excluded.brand_id, lifecycle_stage=excluded.lifecycle_stage,
                     stage_confidence=excluded.stage_confidence, momentum=excluded.momentum,
                     evidence_json=excluded.evidence_json, catalysts_json=excluded.catalysts_json,
                     competitors_json=excluded.competitors_json, loe_horizon=excluded.loe_horizon,
                     whitespace=excluded.whitespace, campaign_posture=excluded.campaign_posture,
                     as_of=excluded.as_of, updated_at=excluded.updated_at""",
                (bid, brand, m.get("lifecycle_stage", ""), m.get("stage_confidence", ""),
                 m.get("momentum", ""), json.dumps(m.get("evidence", [])),
                 json.dumps(m.get("key_catalysts", [])), json.dumps(m.get("main_competitors", [])),
                 m.get("loe_horizon", ""), m.get("whitespace", ""), m.get("campaign_posture", ""),
                 as_of, _now()),
            )
            loaded += 1
        conn.commit()
    finally:
        conn.close()
    return {"loaded": loaded, "as_of": as_of}


def _row_to_dict(r: sqlite3.Row) -> dict:
    return {
        "brand": r["brand_name"],
        "lifecycle_stage": r["lifecycle_stage"],
        "stage_confidence": r["stage_confidence"],
        "momentum": r["momentum"],
        "evidence": json.loads(r["evidence_json"] or "[]"),
        "catalysts": json.loads(r["catalysts_json"] or "[]"),
        "competitors": json.loads(r["competitors_json"] or "[]"),
        "loe_horizon": r["loe_horizon"],
        "whitespace": r["whitespace"],
        "campaign_posture": r["campaign_posture"],
        "as_of": r["as_of"],
    }


def get_market_intel(brand: str) -> dict | None:
    conn = _conn()
    try:
        r = conn.execute("SELECT * FROM brand_market_intel WHERE brand_name=?", (brand,)).fetchone()
        return _row_to_dict(r) if r else None
    finally:
        conn.close()


def all_market_intel() -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM brand_market_intel ORDER BY brand_name").fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def stage_distribution() -> dict[str, int]:
    """Count of brands per lifecycle stage -- a dashboard rollup."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT lifecycle_stage, COUNT(*) n FROM brand_market_intel GROUP BY lifecycle_stage"
        ).fetchall()
        return {r["lifecycle_stage"]: r["n"] for r in rows}
    finally:
        conn.close()


if __name__ == "__main__":
    print(load_market_intel())
    print("stage distribution:", stage_distribution())
