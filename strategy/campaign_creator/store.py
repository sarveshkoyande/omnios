"""Campaign Planner sessions: one per brand + campaign (the scope the Cockpit workspace picks),
holding the whole create-campaign state, plus every version of its Campaign Briefing Document.

Stored in `campaign_creator.db` through strategy/db.py like the app's other writable stores
(SQLite under DATA_DIR by default, Postgres when DATABASE_URL is set).
"""
from __future__ import annotations

import json
import time
import uuid

from strategy import db

SCHEMA = """
CREATE TABLE IF NOT EXISTS cc_session (
    id TEXT PRIMARY KEY,
    brand TEXT,
    plan_id INTEGER,
    campaign_id INTEGER,
    title TEXT NOT NULL DEFAULT '',
    artifact_id TEXT,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_cc_session_scope ON cc_session (brand, campaign_id);
CREATE TABLE IF NOT EXISTS cc_briefing_version (
    session_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    briefing_json TEXT NOT NULL,
    PRIMARY KEY (session_id, version)
);
"""

_COLUMNS = "id, brand, plan_id, campaign_id, title, artifact_id, state_json, created_at, updated_at"


def _conn():
    conn = db.connect("campaign_creator")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _row(r) -> dict | None:
    if r is None:
        return None
    return {"id": r["id"], "brand": r["brand"], "plan_id": r["plan_id"], "campaign_id": r["campaign_id"],
            "title": r["title"], "artifact_id": r["artifact_id"], "state": json.loads(r["state_json"]),
            "created_at": r["created_at"], "updated_at": r["updated_at"]}


def get(session_id: str) -> dict | None:
    conn = _conn()
    try:
        return _row(conn.execute(f"SELECT {_COLUMNS} FROM cc_session WHERE id = ?", (session_id,)).fetchone())
    finally:
        conn.close()


def find(brand: str | None, campaign_id: int | None) -> dict | None:
    """The newest session for this brand + campaign (a missing campaign is its own scope)."""
    same = "IS NOT DISTINCT FROM" if db.IS_PG else "IS"  # NULL-safe equality on each dialect
    conn = _conn()
    try:
        if campaign_id is None:
            r = conn.execute(f"SELECT {_COLUMNS} FROM cc_session WHERE brand {same} ? AND campaign_id IS NULL "
                             "ORDER BY updated_at DESC LIMIT 1", (brand,)).fetchone()
        else:
            r = conn.execute(f"SELECT {_COLUMNS} FROM cc_session WHERE brand {same} ? AND campaign_id = ? "
                             "ORDER BY updated_at DESC LIMIT 1", (brand, campaign_id)).fetchone()
        return _row(r)
    finally:
        conn.close()


def find_by_artifact(artifact_id: str) -> dict | None:
    conn = _conn()
    try:
        return _row(conn.execute(f"SELECT {_COLUMNS} FROM cc_session WHERE artifact_id = ? ORDER BY updated_at DESC LIMIT 1",
                                 (artifact_id,)).fetchone())
    finally:
        conn.close()


def create(brand: str | None, plan_id: int | None, campaign_id: int | None, title: str, state: dict) -> dict:
    sid = uuid.uuid4().hex[:12]
    now = _now()
    conn = _conn()
    try:
        conn.execute(f"INSERT INTO cc_session ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (sid, brand, plan_id, campaign_id, title, None, json.dumps(state), now, now))
        conn.commit()
    finally:
        conn.close()
    return get(sid)


def save_state(session_id: str, state: dict) -> None:
    conn = _conn()
    try:
        conn.execute("UPDATE cc_session SET state_json = ?, updated_at = ? WHERE id = ?",
                     (json.dumps(state), _now(), session_id))
        conn.commit()
    finally:
        conn.close()


def set_fields(session_id: str, **fields) -> None:
    """Update title / plan_id / artifact_id."""
    allowed = {k: v for k, v in fields.items() if k in ("title", "plan_id", "artifact_id")}
    if not allowed:
        return
    sets = ", ".join(f"{k} = ?" for k in allowed)
    conn = _conn()
    try:
        conn.execute(f"UPDATE cc_session SET {sets}, updated_at = ? WHERE id = ?", (*allowed.values(), _now(), session_id))
        conn.commit()
    finally:
        conn.close()


def add_briefing_version(session_id: str, briefing: dict, reason: str) -> int:
    conn = _conn()
    try:
        r = conn.execute("SELECT MAX(version) AS v FROM cc_briefing_version WHERE session_id = ?", (session_id,)).fetchone()
        version = int((r["v"] if r else 0) or 0) + 1
        conn.execute("INSERT INTO cc_briefing_version (session_id, version, created_at, reason, briefing_json) VALUES (?, ?, ?, ?, ?)",
                     (session_id, version, _now(), reason, json.dumps(briefing)))
        conn.commit()
        return version
    finally:
        conn.close()


def briefing_versions(session_id: str) -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute("SELECT version, created_at, reason FROM cc_briefing_version WHERE session_id = ? "
                            "ORDER BY version DESC", (session_id,)).fetchall()
        return [{"version": r["version"], "created_at": r["created_at"], "reason": r["reason"]} for r in rows]
    finally:
        conn.close()


def briefing_version(session_id: str, version: int) -> dict | None:
    conn = _conn()
    try:
        r = conn.execute("SELECT briefing_json FROM cc_briefing_version WHERE session_id = ? AND version = ?",
                         (session_id, version)).fetchone()
        return json.loads(r["briefing_json"]) if r else None
    finally:
        conn.close()


def clear_briefing_versions(session_id: str) -> None:
    conn = _conn()
    try:
        conn.execute("DELETE FROM cc_briefing_version WHERE session_id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()
