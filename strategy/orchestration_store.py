"""Engagement Orchestration -- persistence for downstream integration (M2/M3).

Two SQLite tables under DATA_DIR (same flat-file pattern as projects.py):

  external_binding -- the internal Activity <-> downstream record link. One row per
    (project, activity, system): the external id/url, a hash of the last-synced field snapshot
    (for idempotent skip-if-unchanged), and the sync state. This is the loop-prevention +
    external-ID-map layer from PRD 6.6.

  stub_item -- the mock downstream system's OWN store. The StubConnector writes items here so a
    two-way sync (M3) has a real, independently-mutable "other side" to read back and reconcile,
    exactly as a real Monday/Smartsheet/Jira board would hold the item. `origin` tags who last
    wrote ('orchestrator' vs 'external') so echo loops can be detected.

Real connectors (Monday GraphQL / Smartsheet / Jira) don't use stub_item -- they hold their
items in the vendor system; only external_binding is shared across all connectors.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from paths import data_path  # noqa: E402

DB_PATH = data_path("orchestration.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS external_binding (
    project_id TEXT NOT NULL,
    activity_id TEXT NOT NULL,
    system TEXT NOT NULL,
    external_id TEXT,
    external_url TEXT,
    last_synced_hash TEXT,
    sync_state TEXT,
    snapshot_json TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (project_id, activity_id, system)
);
CREATE TABLE IF NOT EXISTS stub_item (
    item_id TEXT PRIMARY KEY,
    system TEXT NOT NULL,
    project_id TEXT NOT NULL,
    activity_id TEXT NOT NULL,
    title TEXT,
    status TEXT,
    assignee TEXT,
    due TEXT,
    origin TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sync_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    activity_id TEXT,
    system TEXT,
    direction TEXT,
    field TEXT,
    old_value TEXT,
    new_value TEXT,
    result TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notification (
    project_id TEXT NOT NULL,
    dedupe_key TEXT NOT NULL,
    activity_id TEXT,
    trigger TEXT,
    severity TEXT,
    channel TEXT,
    recipient TEXT,
    title TEXT,
    body TEXT,
    gate TEXT,
    fire_count INTEGER NOT NULL DEFAULT 1,
    escalated INTEGER NOT NULL DEFAULT 0,
    acked INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (project_id, dedupe_key)
);
"""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# --- external bindings -------------------------------------------------------------------------

def get_binding(project_id: str, activity_id: str, system: str) -> dict | None:
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM external_binding WHERE project_id=? AND activity_id=? AND system=?",
        (project_id, activity_id, system)).fetchone()
    conn.close()
    return _binding_row(row) if row else None


def list_bindings(project_id: str) -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM external_binding WHERE project_id=? ORDER BY updated_at DESC",
        (project_id,)).fetchall()
    conn.close()
    return [_binding_row(r) for r in rows]


def _binding_row(row: sqlite3.Row) -> dict:
    return {
        "project_id": row["project_id"], "activity_id": row["activity_id"], "system": row["system"],
        "external_id": row["external_id"], "external_url": row["external_url"],
        "last_synced_hash": row["last_synced_hash"], "sync_state": row["sync_state"],
        "snapshot": json.loads(row["snapshot_json"]) if row["snapshot_json"] else None,
        "updated_at": row["updated_at"],
    }


def upsert_binding(project_id: str, activity_id: str, system: str, *, external_id: str | None,
                   external_url: str | None, last_synced_hash: str | None, sync_state: str,
                   snapshot: dict | None) -> dict:
    conn = _conn()
    conn.execute(
        """INSERT INTO external_binding
           (project_id, activity_id, system, external_id, external_url, last_synced_hash,
            sync_state, snapshot_json, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(project_id, activity_id, system) DO UPDATE SET
             external_id=excluded.external_id, external_url=excluded.external_url,
             last_synced_hash=excluded.last_synced_hash, sync_state=excluded.sync_state,
             snapshot_json=excluded.snapshot_json, updated_at=excluded.updated_at""",
        (project_id, activity_id, system, external_id, external_url, last_synced_hash,
         sync_state, json.dumps(snapshot) if snapshot is not None else None, _now()))
    conn.commit()
    conn.close()
    return get_binding(project_id, activity_id, system)


# --- stub downstream items (mock connector's own store) ---------------------------------------

def upsert_stub_item(item_id: str, *, system: str, project_id: str, activity_id: str,
                     title: str | None, status: str | None, assignee: str | None,
                     due: str | None, origin: str) -> None:
    conn = _conn()
    conn.execute(
        """INSERT INTO stub_item
           (item_id, system, project_id, activity_id, title, status, assignee, due, origin, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(item_id) DO UPDATE SET
             title=excluded.title, status=excluded.status, assignee=excluded.assignee,
             due=excluded.due, origin=excluded.origin, updated_at=excluded.updated_at""",
        (item_id, system, project_id, activity_id, title, status, assignee, due, origin, _now()))
    conn.commit()
    conn.close()


def get_stub_item(item_id: str) -> dict | None:
    conn = _conn()
    row = conn.execute("SELECT * FROM stub_item WHERE item_id=?", (item_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_stub_items(project_id: str) -> list[dict]:
    conn = _conn()
    rows = conn.execute("SELECT * FROM stub_item WHERE project_id=?", (project_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- sync event log ----------------------------------------------------------------------------

def record_sync_event(project_id: str, *, activity_id: str | None, system: str | None,
                      direction: str, field: str | None, old_value, new_value, result: str) -> None:
    conn = _conn()
    conn.execute(
        """INSERT INTO sync_event
           (project_id, activity_id, system, direction, field, old_value, new_value, result, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (project_id, activity_id, system, direction, field,
         None if old_value is None else str(old_value),
         None if new_value is None else str(new_value), result, _now()))
    conn.commit()
    conn.close()


def list_sync_events(project_id: str, limit: int = 50) -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM sync_event WHERE project_id=? ORDER BY id DESC LIMIT ?",
        (project_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- notifications (Nudge agent) --------------------------------------------------------------

def get_notification(project_id: str, dedupe_key: str) -> dict | None:
    conn = _conn()
    row = conn.execute("SELECT * FROM notification WHERE project_id=? AND dedupe_key=?",
                       (project_id, dedupe_key)).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_notification(project_id: str, dedupe_key: str, *, activity_id: str | None, trigger: str,
                        severity: str, channel: str, recipient: str, title: str, body: str,
                        gate: str | None, fire_count: int, escalated: bool) -> None:
    conn = _conn()
    conn.execute(
        """INSERT INTO notification
           (project_id, dedupe_key, activity_id, trigger, severity, channel, recipient, title,
            body, gate, fire_count, escalated, acked, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,?,?)
           ON CONFLICT(project_id, dedupe_key) DO UPDATE SET
             severity=excluded.severity, channel=excluded.channel, recipient=excluded.recipient,
             title=excluded.title, body=excluded.body, gate=excluded.gate,
             fire_count=excluded.fire_count, escalated=excluded.escalated,
             updated_at=excluded.updated_at""",
        (project_id, dedupe_key, activity_id, trigger, severity, channel, recipient, title, body,
         gate, fire_count, 1 if escalated else 0, _now(), _now()))
    conn.commit()
    conn.close()


def list_notifications(project_id: str, include_acked: bool = True) -> list[dict]:
    conn = _conn()
    q = "SELECT * FROM notification WHERE project_id=?"
    if not include_acked:
        q += " AND acked=0"
    q += " ORDER BY updated_at DESC"
    rows = conn.execute(q, (project_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def ack_notification(project_id: str, dedupe_key: str) -> bool:
    conn = _conn()
    cur = conn.execute("UPDATE notification SET acked=1, updated_at=? WHERE project_id=? AND dedupe_key=?",
                       (_now(), project_id, dedupe_key))
    conn.commit()
    n = cur.rowcount
    conn.close()
    return n > 0
