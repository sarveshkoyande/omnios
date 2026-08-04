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
import db  # noqa: E402  (dual-dialect SQLite/Postgres connection factory)

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


def _conn():
    conn = db.connect("projects")
    conn.executescript(SCHEMA)
    # Lightweight migration: existing DB files predate these columns, and
    # CREATE TABLE IF NOT EXISTS won't add columns to an already-created table. SQLite has no
    # `ADD COLUMN IF NOT EXISTS`, so we attempt a plain ADD COLUMN and swallow the "column
    # exists" error on both dialects. The rollback() matters on Postgres: without it the
    # failed ALTER leaves the transaction aborted and every later statement fails (on SQLite
    # it's a harmless no-op).
    for col in ("campaign_plan_layout", "orchestration_tasks"):
        try:
            conn.execute(f"ALTER TABLE projects ADD COLUMN {col} TEXT")
            conn.commit()
        except Exception:  # noqa: BLE001  (SQLite: OperationalError; Postgres: DuplicateColumn)
            conn.rollback()
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


def _planning_progress(state: dict) -> dict | None:
    """How far the Stage 1 studio run has got: sections completed out of the sequence.

    This measures the PLANNING stage only, and callers must label it that way. It is not
    a proxy for overall campaign completion -- the other three stages are marked by the
    artifacts they produce (`_plan_stage` above), not by a percentage, and presenting this
    number as "progress" full stop is how the Home cards ended up implying a plan was 90%
    finished when only its brief existed.

    Returns None when the plan has no studio state yet, so the caller can render nothing
    rather than a fabricated zero.
    """
    studio = (state or {}).get("studio") or {}
    if not studio:
        return None
    try:
        # Imported lazily: studio_run pulls in the whole planning stack, and projects.py is
        # imported early enough that a module-level import risks a cycle.
        from strategy import studio_run

        total = len(studio_run.SEQUENCE)
    except Exception:
        return None
    if not total:
        return None
    done = max(0, min(int(studio.get("idx") or 0), total))
    return {"done": done, "total": total, "pct": round(done * 100 / total)}


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
        state: dict = {}
        try:
            state = json.loads(r["state_json"]) or {}
        except (ValueError, TypeError):
            state = {}
        slots: dict = state.get("slots", {}) or {}
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
                "planning_progress": _planning_progress(state),
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
    """Atomically persist only the fields supplied by the caller.

    Project artifacts are saved independently: an activity-board edit, a diagram
    autosave, and a planning/brief update can all arrive at once.  The previous
    read-modify-write implementation copied every untouched field from an earlier
    snapshot, so the last request could silently restore stale activities, layout,
    or brief state.  Each save is now a column-level patch in one SQL update.
    """
    updates = ["updated_at=?"]
    values: list[object] = [_now()]

    if name is not None:
        updates.append("name=?")
        values.append(name)
    if state is not None:
        updates.append("state_json=?")
        values.append(json.dumps(state))
        if "phase" in state:
            updates.append("phase=?")
            values.append(state["phase"])
    if messages is not None:
        updates.append("messages_json=?")
        values.append(json.dumps(messages))
    if result is not None:
        updates.append("result_json=?")
        values.append(json.dumps(result))
    if plan_markdown is not None:
        updates.append("plan_markdown=?")
        values.append(plan_markdown)
    if plan_html is not None:
        updates.append("plan_html=?")
        values.append(plan_html)
    if campaign_plan_layout is not None:
        updates.append("campaign_plan_layout=?")
        values.append(json.dumps(campaign_plan_layout))
    if orchestration_tasks is not None:
        updates.append("orchestration_tasks=?")
        values.append(json.dumps(orchestration_tasks))

    conn = _conn()
    conn.execute(f"UPDATE projects SET {', '.join(updates)} WHERE id=?", (*values, pid))
    conn.commit()
    conn.close()
    return get_project(pid)


def delete_project(pid: str) -> None:
    conn = _conn()
    conn.execute("DELETE FROM projects WHERE id = ?", (pid,))
    conn.commit()
    conn.close()
