"""SQLite-backed store for planning projects (the left-hand project list).

A project bundles: the conversation transcript, the captured slots, the dialog
state, and -- once the agents have run -- the full result plus the composed
campaign-plan document. Kept in its own DB file so it never collides with the
scraped-knowledge schema in scrapers/storage.py.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
import time
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from paths import data_path  # noqa: E402

DB_PATH = data_path("projects.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    phase TEXT NOT NULL,
    state_json TEXT NOT NULL,
    messages_json TEXT NOT NULL,
    result_json TEXT,
    plan_markdown TEXT,
    plan_html TEXT
);
"""


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def create_project(name: str, state: dict, messages: list[dict]) -> dict:
    pid = uuid.uuid4().hex[:12]
    now = _now()
    conn = _conn()
    conn.execute(
        "INSERT INTO projects (id, name, created_at, updated_at, phase, state_json, messages_json) VALUES (?,?,?,?,?,?,?)",
        (pid, name, now, now, state["phase"], json.dumps(state), json.dumps(messages)),
    )
    conn.commit()
    conn.close()
    return get_project(pid)


def get_project(pid: str) -> dict | None:
    conn = _conn()
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "phase": row["phase"],
        "state": json.loads(row["state_json"]),
        "messages": json.loads(row["messages_json"]),
        "result": json.loads(row["result_json"]) if row["result_json"] else None,
        "plan_markdown": row["plan_markdown"],
        "plan_html": row["plan_html"],
    }


def list_projects() -> list[dict]:
    conn = _conn()
    rows = conn.execute("SELECT id, name, created_at, updated_at, phase FROM projects ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_project(
    pid: str,
    *,
    name: str | None = None,
    state: dict | None = None,
    messages: list[dict] | None = None,
    result: dict | None = None,
    plan_markdown: str | None = None,
    plan_html: str | None = None,
) -> dict | None:
    proj = get_project(pid)
    if not proj:
        return None
    name = name if name is not None else proj["name"]
    state = state if state is not None else proj["state"]
    messages = messages if messages is not None else proj["messages"]
    result = result if result is not None else proj["result"]
    plan_markdown = plan_markdown if plan_markdown is not None else proj["plan_markdown"]
    plan_html = plan_html if plan_html is not None else proj["plan_html"]

    conn = _conn()
    conn.execute(
        """UPDATE projects SET name=?, updated_at=?, phase=?, state_json=?, messages_json=?,
           result_json=?, plan_markdown=?, plan_html=? WHERE id=?""",
        (
            name, _now(), state["phase"], json.dumps(state), json.dumps(messages),
            json.dumps(result) if result is not None else None,
            plan_markdown, plan_html, pid,
        ),
    )
    conn.commit()
    conn.close()
    return get_project(pid)


def delete_project(pid: str) -> None:
    conn = _conn()
    conn.execute("DELETE FROM projects WHERE id = ?", (pid,))
    conn.commit()
    conn.close()
