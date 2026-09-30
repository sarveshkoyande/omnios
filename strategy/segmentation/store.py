"""Segmentation Planner sessions: one per brand + campaign (the scope the Cockpit workspace
picks), holding the conversation, the segment being defined and the segments created.

Stored in `segmentation_planner.db` through strategy/db.py like the app's other writable stores
(SQLite under DATA_DIR by default, Postgres when DATABASE_URL is set).
"""
from __future__ import annotations

import json
import time
import uuid

from strategy import db

SCHEMA = """
CREATE TABLE IF NOT EXISTS seg_session (
    id TEXT PRIMARY KEY,
    brand TEXT,
    plan_id INTEGER,
    campaign_id INTEGER,
    title TEXT NOT NULL DEFAULT '',
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_seg_session_scope ON seg_session (brand, campaign_id);
"""

_COLUMNS = "id, brand, plan_id, campaign_id, title, state_json, created_at, updated_at"


def _conn():
    conn = db.connect("segmentation_planner")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _row(r) -> dict | None:
    if r is None:
        return None
    return {"id": r["id"], "brand": r["brand"], "plan_id": r["plan_id"], "campaign_id": r["campaign_id"],
            "title": r["title"], "state": json.loads(r["state_json"]),
            "created_at": r["created_at"], "updated_at": r["updated_at"]}


def get(session_id: str) -> dict | None:
    conn = _conn()
    try:
        return _row(conn.execute(f"SELECT {_COLUMNS} FROM seg_session WHERE id = ?", (session_id,)).fetchone())
    finally:
        conn.close()


def find(brand: str | None, campaign_id: int | None) -> dict | None:
    """The newest session for this brand + campaign (a missing campaign is its own scope)."""
    same = "IS NOT DISTINCT FROM" if db.IS_PG else "IS"  # NULL-safe equality on each dialect
    conn = _conn()
    try:
        if campaign_id is None:
            r = conn.execute(f"SELECT {_COLUMNS} FROM seg_session WHERE brand {same} ? AND campaign_id IS NULL "
                             "ORDER BY updated_at DESC LIMIT 1", (brand,)).fetchone()
        else:
            r = conn.execute(f"SELECT {_COLUMNS} FROM seg_session WHERE brand {same} ? AND campaign_id = ? "
                             "ORDER BY updated_at DESC LIMIT 1", (brand, campaign_id)).fetchone()
        return _row(r)
    finally:
        conn.close()


def create(brand: str | None, plan_id: int | None, campaign_id: int | None, title: str, state: dict) -> dict:
    sid = uuid.uuid4().hex[:12]
    now = _now()
    conn = _conn()
    try:
        conn.execute(f"INSERT INTO seg_session ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (sid, brand, plan_id, campaign_id, title, json.dumps(state), now, now))
        conn.commit()
    finally:
        conn.close()
    return get(sid)


def save_state(session_id: str, state: dict) -> None:
    conn = _conn()
    try:
        conn.execute("UPDATE seg_session SET state_json = ?, updated_at = ? WHERE id = ?",
                     (json.dumps(state), _now(), session_id))
        conn.commit()
    finally:
        conn.close()


def set_fields(session_id: str, **fields) -> None:
    """Update title / plan_id."""
    allowed = {k: v for k, v in fields.items() if k in ("title", "plan_id")}
    if not allowed:
        return
    sets = ", ".join(f"{k} = ?" for k in allowed)
    conn = _conn()
    try:
        conn.execute(f"UPDATE seg_session SET {sets}, updated_at = ? WHERE id = ?", (*allowed.values(), _now(), session_id))
        conn.commit()
    finally:
        conn.close()
