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
    # Lightweight migration: existing DB files predate campaign_plan_layout, and
    # CREATE TABLE IF NOT EXISTS won't add columns to an already-created table.
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN campaign_plan_layout TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN orchestration_tasks TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
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
        "campaign_plan_layout": json.loads(row["campaign_plan_layout"]) if row["campaign_plan_layout"] else None,
        "orchestration_tasks": json.loads(row["orchestration_tasks"]) if row["orchestration_tasks"] else None,
    }


def _plan_stage(has_layout: bool, has_tasks: bool, has_result: bool) -> str:
    """Which of the four workspace stages a plan currently sits in.

    Derived from the furthest downstream artifact the plan has produced:
    an orchestration task set (Engagement Orchestration) and a campaign
    flow layout (Campaign Operations) are the two persisted markers. Once
    both are built and the plan itself is complete, the live work has moved
    on to measurement, so the plan sits in Reporting. Everything else — a
    plan still in brief, building, or freshly plan-ready — sits in Planning.
    """
    if has_layout and has_tasks and has_result:
        return "reporting"
    if has_layout:
        return "operations"
    if has_tasks:
        return "orchestration"
    return "planning"


def list_projects() -> list[dict]:
    """Project list for the Home dashboard + workspace drawer.

    Enriched with a compact brief digest pulled from each project's `state.slots`
    (brand / therapy area / campaign name / lifecycle / objective) plus a
    `has_result` flag, so the Home page can render rich plan cards without a
    per-project fetch. Kept cheap: parses only the two JSON blobs it needs and
    never loads messages/plan HTML.
    """
    conn = _conn()
    # `IS NOT NULL` flags let us bucket each plan into its furthest workspace
    # stage without loading the (potentially large) layout/tasks blobs.
    rows = conn.execute(
        """SELECT id, name, created_at, updated_at, phase, state_json, result_json,
                  (campaign_plan_layout IS NOT NULL) AS has_layout,
                  (orchestration_tasks IS NOT NULL) AS has_tasks
           FROM projects ORDER BY updated_at DESC"""
    ).fetchall()
    conn.close()
    out: list[dict] = []
    for r in rows:
        slots: dict = {}
        try:
            slots = (json.loads(r["state_json"]) or {}).get("slots", {}) or {}
        except (ValueError, TypeError):
            slots = {}
        has_result = bool(r["result_json"])
        out.append(
            {
                "id": r["id"],
                "name": r["name"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "phase": r["phase"],
                "brand": slots.get("brand") or "",
                "therapy_area": slots.get("therapy_area") or "",
                "campaign_name": slots.get("campaign_name") or "",
                "lifecycle_key": slots.get("lifecycle_key") or "",
                "objective": slots.get("objective") or "",
                "has_result": has_result,
                "stage": _plan_stage(bool(r["has_layout"]), bool(r["has_tasks"]), has_result),
            }
        )
    return out


def save_project(
    pid: str,
    *,
    name: str | None = None,
    state: dict | None = None,
    messages: list[dict] | None = None,
    result: dict | None = None,
    plan_markdown: str | None = None,
    plan_html: str | None = None,
    campaign_plan_layout: dict | None = None,
    orchestration_tasks: list | None = None,
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
    campaign_plan_layout = campaign_plan_layout if campaign_plan_layout is not None else proj["campaign_plan_layout"]
    orchestration_tasks = orchestration_tasks if orchestration_tasks is not None else proj["orchestration_tasks"]

    conn = _conn()
    conn.execute(
        """UPDATE projects SET name=?, updated_at=?, phase=?, state_json=?, messages_json=?,
           result_json=?, plan_markdown=?, plan_html=?, campaign_plan_layout=?, orchestration_tasks=? WHERE id=?""",
        (
            name, _now(), state["phase"], json.dumps(state), json.dumps(messages),
            json.dumps(result) if result is not None else None,
            plan_markdown, plan_html,
            json.dumps(campaign_plan_layout) if campaign_plan_layout is not None else None,
            json.dumps(orchestration_tasks) if orchestration_tasks is not None else None,
            pid,
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
