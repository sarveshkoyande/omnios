"""Per-(project, brand, section) draft store for the brand-plan update flow.

Holds an agent's proposed diff for one of the five kit-update sections
(kit-brand-details / kit-brand-persona / kit-guardrails / kit-hcp-persona /
kit-hcp-segmentation) while the user reviews it. Nothing here ever writes to
config/brand_kits.json directly -- that only happens in publish_draft(), and
only for the fields the caller names as accepted. Own store
(data/kit_drafts.db), same "own flat SQLite file" pattern as every other
store in strategy/ (see strategy/paths.py).
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from paths import data_path  # noqa: E402
import db  # noqa: E402  (dual-dialect SQLite/Postgres connection factory)
# Package-qualified, not a flat `import brand_kit` -- see strategy/kit_chat.py's import
# comment for why: publish_draft()'s apply_diff() call needs to invalidate the SAME
# `_load()` cache app/server.py reads from, or a publish looks like it silently didn't
# take until the process restarts.
from strategy import brand_kit  # noqa: E402

DB_PATH = data_path("kit_drafts.db")

STATUSES = ("not_started", "drafting", "awaiting_review", "published")


def _conn():
    conn = db.connect("kit_drafts")
    conn.execute("""CREATE TABLE IF NOT EXISTS drafts (
        project_id TEXT NOT NULL,
        brand      TEXT NOT NULL,
        section    TEXT NOT NULL,
        status     TEXT NOT NULL DEFAULT 'not_started',
        diff_json  TEXT,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (project_id, brand, section)
    )""")
    return conn


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def get_draft(project_id: str, brand: str, section: str) -> dict:
    """This section's draft row, or a synthetic not_started row if none exists yet."""
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT status, diff_json, updated_at FROM drafts "
            "WHERE project_id=? AND brand=? AND section=?", (project_id, brand, section)
        ).fetchone()
        if not row:
            return {"section": section, "status": "not_started", "diff": {}, "updated_at": None}
        item = dict(row)
        return {
            "section": section,
            "status": item["status"],
            "diff": json.loads(item["diff_json"]) if item["diff_json"] else {},
            "updated_at": item["updated_at"],
        }
    finally:
        conn.close()


def list_drafts(project_id: str, brand: str) -> list[dict]:
    """One entry per known kit-update section (see kit_chat.KIT_SECTIONS), in a fixed
    order, for the progress rail -- callers get a complete 5-row list even before any
    agent has run, rather than having to fill in the gaps themselves."""
    import kit_chat  # local import: kit_chat imports this module, so import here avoids a cycle
    return [get_draft(project_id, brand, section) for section in kit_chat.KIT_SECTIONS]


def upsert_draft(project_id: str, brand: str, section: str, status: str, diff: dict) -> dict:
    if status not in STATUSES:
        raise ValueError(f"unknown draft status '{status}'")
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO drafts (project_id, brand, section, status, diff_json, updated_at) "
            "VALUES (?,?,?,?,?,?) "
            "ON CONFLICT (project_id, brand, section) DO UPDATE SET "
            "status=excluded.status, diff_json=excluded.diff_json, updated_at=excluded.updated_at",
            (project_id, brand, section, status, json.dumps(diff), _now()))
        conn.commit()
    finally:
        conn.close()
    return get_draft(project_id, brand, section)


def publish_draft(project_id: str, brand: str, section: str, accepted_fields: list[str]) -> dict:
    """Apply only the accepted fields from this section's current diff to the brand's
    live kit, then clear the draft (status -> published, diff_json -> empty).

    A no-op (not an error) when the section has no pending diff, or when
    accepted_fields is empty -- covers the double-click case: the second publish
    click finds nothing left to apply and simply confirms the already-published state."""
    draft = get_draft(project_id, brand, section)
    diff = draft["diff"] or {}
    unknown = [f for f in accepted_fields if f not in diff]
    if unknown:
        raise ValueError(f"accepted field(s) not in this section's current diff: {unknown}")

    fields_to_apply = {f: diff[f]["proposed"] for f in accepted_fields if f in diff}
    if fields_to_apply:
        brand_kit.apply_diff(brand, fields_to_apply)

    return upsert_draft(project_id, brand, section, "published", {})
