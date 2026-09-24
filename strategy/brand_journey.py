"""Journey store for the Agentic Brand Journey (KTD2).

Per brand: journey-only answers, pending drafts per step, step status, step chat turns and
the flow document, in its own SQLite file (<DATA_DIR>/brand_journey.db) -- same
"own flat store" pattern as strategy/kit_drafts.py.

Drafts are the only way agent content reaches a brand (R6, R7): `propose` stores one,
`keep` writes it -- kit-targeted values through `brand_kit.apply_diff`, so
config/brand_kits.json stays the kit's source of truth -- and `undo` deletes it without
touching the kit.

Status is checked against the kit on read: a confirmed step whose required fields are
missing from the kit reads as drafted. A brand with no status rows derives each step's
status from its kit (all required present -> confirmed, some content -> drafted, nothing
-> not_started); the first write to a brand persists that derivation as its seed.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import db  # noqa: E402
import journey_fields as jf  # noqa: E402
# Package-qualified so apply_diff clears the same _load() cache app/server.py reads --
# see the import comment in strategy/kit_chat.py.
from strategy import brand_kit  # noqa: E402

STATUSES = ("not_started", "drafted", "confirmed")
DRAFT_MODES = ("set", "append")


def _conn():
    conn = db.connect("brand_journey")
    conn.execute("""CREATE TABLE IF NOT EXISTS journey_answers (
        brand TEXT NOT NULL, key TEXT NOT NULL, value_json TEXT NOT NULL,
        updated_at TEXT NOT NULL, PRIMARY KEY (brand, key))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS journey_drafts (
        id TEXT PRIMARY KEY, brand TEXT NOT NULL, step TEXT NOT NULL, field TEXT NOT NULL,
        mode TEXT NOT NULL, path TEXT, value_json TEXT NOT NULL, created_at TEXT NOT NULL,
        seq INTEGER NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS journey_steps (
        brand TEXT NOT NULL, step TEXT NOT NULL, status TEXT NOT NULL,
        updated_at TEXT NOT NULL, PRIMARY KEY (brand, step))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS journey_turns (
        id TEXT PRIMARY KEY, brand TEXT NOT NULL, step TEXT NOT NULL, role TEXT NOT NULL,
        text TEXT NOT NULL, created_at TEXT NOT NULL, seq INTEGER NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS journey_flow (
        brand TEXT PRIMARY KEY, doc_json TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    return conn


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _key(brand: str) -> str:
    """Canonical kit key for `brand` (case-insensitive), or KeyError."""
    name = (brand or "").strip().lower()
    for k in brand_kit._load():
        if k.lower() == name:
            return k
    raise KeyError(f"no brand kit for '{brand}'")


def answers_for(brand: str) -> dict:
    """Current answers: kit values for kit-targeted fields, the brand name, and journey-only
    answers."""
    b = _key(brand)
    kit = brand_kit.kit_for(b) or {}
    answers = {f["key"]: kit.get(f["key"]) for f in jf.FIELDS if f["target"] == "kit"}
    answers["brand_name"] = b
    conn = _conn()
    try:
        for row in conn.execute("SELECT key, value_json FROM journey_answers WHERE brand=?", (b,)):
            answers[row["key"]] = json.loads(row["value_json"])
    finally:
        conn.close()
    return answers


def _derive(step: str, answers: dict, pending: bool) -> str:
    if step == "flow":
        return "drafted" if pending else "not_started"
    req = jf.required_fields(step, answers)
    if req and all(jf.has_value(answers.get(f["key"])) for f in req):
        return "confirmed"
    any_content = any(jf.has_value(answers.get(f["key"])) for f in jf.fields_for(step)
                      if f["key"] != "brand_name")
    return "drafted" if any_content or pending else "not_started"


def _stored_statuses(conn, b: str) -> dict:
    return {r["step"]: r["status"] for r in
            conn.execute("SELECT step, status FROM journey_steps WHERE brand=?", (b,))}


def _ensure_seeded(conn, b: str) -> None:
    if _stored_statuses(conn, b):
        return
    answers = answers_for(b)
    for step in jf.STEPS:
        conn.execute("INSERT INTO journey_steps (brand, step, status, updated_at) VALUES (?,?,?,?)",
                     (b, step, _derive(step, answers, False), _now()))


def _set_status(conn, b: str, step: str, status: str) -> None:
    conn.execute("DELETE FROM journey_steps WHERE brand=? AND step=?", (b, step))
    conn.execute("INSERT INTO journey_steps (brand, step, status, updated_at) VALUES (?,?,?,?)",
                 (b, step, status, _now()))


def _draft_row(row) -> dict:
    return {"id": row["id"], "step": row["step"], "field": row["field"], "mode": row["mode"],
            "path": row["path"], "value": json.loads(row["value_json"]),
            "created_at": row["created_at"]}


def propose(brand: str, step: str, field: str, value, mode: str = "set",
            path: str | None = None) -> dict:
    """Store a draft for `field` of `step`. mode="append" adds `value` as one item to the
    field's list (or to the sub-list `path`, e.g. personas.hcp) on keep."""
    b = _key(brand)
    f = jf.FIELDS_BY_KEY.get(field)
    if step not in jf.STEPS:
        raise ValueError(f"unknown journey step '{step}'")
    if f is None or f["step"] != step:
        raise ValueError(f"field '{field}' does not belong to step '{step}'")
    if mode not in DRAFT_MODES:
        raise ValueError(f"unknown draft mode '{mode}'")
    draft = {"id": uuid.uuid4().hex, "step": step, "field": field, "mode": mode,
             "path": path, "value": value, "created_at": _now()}
    conn = _conn()
    try:
        _ensure_seeded(conn, b)
        conn.execute("INSERT INTO journey_drafts (id, brand, step, field, mode, path, value_json, "
                     "created_at, seq) VALUES (?,?,?,?,?,?,?,?,?)",
                     (draft["id"], b, step, field, mode, path, json.dumps(value), draft["created_at"],
                      time.time_ns()))
        if _stored_statuses(conn, b).get(step) == "not_started":
            _set_status(conn, b, step, "drafted")
        conn.commit()
    finally:
        conn.close()
    return draft


def list_drafts(brand: str, step: str | None = None) -> list[dict]:
    b = _key(brand)
    conn = _conn()
    try:
        sql, args = "SELECT * FROM journey_drafts WHERE brand=?", [b]
        if step:
            sql, args = sql + " AND step=?", args + [step]
        return [_draft_row(r) for r in conn.execute(sql + " ORDER BY seq", args)]
    finally:
        conn.close()


def _merged_value(current, draft: dict):
    if draft["mode"] == "set":
        return draft["value"]
    if draft["path"]:
        base = dict(current) if isinstance(current, dict) else {}
        base[draft["path"]] = list(base.get(draft["path"]) or []) + [draft["value"]]
        return base
    return list(current or []) + [draft["value"]]


def keep(brand: str, draft_id: str) -> dict:
    """Commit one draft: kit fields via brand_kit.apply_diff, the rest to journey answers.
    KeyError if the draft does not exist."""
    b = _key(brand)
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM journey_drafts WHERE id=? AND brand=?",
                           (draft_id, b)).fetchone()
        if row is None:
            raise KeyError(f"no draft '{draft_id}' for '{b}'")
        draft = _draft_row(row)
        target = jf.FIELDS_BY_KEY[draft["field"]]["target"]
        if target == "kit":
            current = (brand_kit.kit_for(b) or {}).get(draft["field"])
            brand_kit.apply_diff(b, {draft["field"]: _merged_value(current, draft)})
        elif target == "journey":
            prev = conn.execute("SELECT value_json FROM journey_answers WHERE brand=? AND key=?",
                                (b, draft["field"])).fetchone()
            value = _merged_value(json.loads(prev["value_json"]) if prev else None, draft)
            conn.execute("DELETE FROM journey_answers WHERE brand=? AND key=?", (b, draft["field"]))
            conn.execute("INSERT INTO journey_answers (brand, key, value_json, updated_at) "
                         "VALUES (?,?,?,?)", (b, draft["field"], json.dumps(value), _now()))
        # target == "brand": the name is the kit key; renaming is out of scope, keep is a no-op.
        conn.execute("DELETE FROM journey_drafts WHERE id=?", (draft_id,))
        _ensure_seeded(conn, b)
        if _stored_statuses(conn, b).get(draft["step"]) == "not_started":
            _set_status(conn, b, draft["step"], "drafted")
        conn.commit()
    finally:
        conn.close()
    return draft


def keep_all(brand: str, step: str) -> list[dict]:
    return [keep(brand, d["id"]) for d in list_drafts(brand, step)]


def undo(brand: str, draft_id: str) -> bool:
    """Delete a draft; never touches the kit. Idempotent: False if it was already gone."""
    b = _key(brand)
    conn = _conn()
    try:
        cur = conn.execute("DELETE FROM journey_drafts WHERE id=? AND brand=?", (draft_id, b))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def confirm(brand: str, step: str) -> None:
    """Mark `step` confirmed. ValueError if a required field is still missing."""
    b = _key(brand)
    answers = answers_for(b)
    missing = [f["key"] for f in jf.required_fields(step, answers)
               if not jf.has_value(answers.get(f["key"]))]
    if missing:
        raise ValueError(f"cannot confirm '{step}': missing {', '.join(missing)}")
    conn = _conn()
    try:
        _ensure_seeded(conn, b)
        _set_status(conn, b, step, "confirmed")
        conn.commit()
    finally:
        conn.close()


def reopen(brand: str, step: str) -> None:
    """Unlock a confirmed step for editing (R15, R20)."""
    b = _key(brand)
    jf.step_prerequisites(step)
    conn = _conn()
    try:
        _ensure_seeded(conn, b)
        _set_status(conn, b, step, "drafted")
        conn.commit()
    finally:
        conn.close()


def add_turn(brand: str, step: str, role: str, text: str) -> None:
    b = _key(brand)
    jf.step_prerequisites(step)
    conn = _conn()
    try:
        conn.execute("INSERT INTO journey_turns (id, brand, step, role, text, created_at, seq) "
                     "VALUES (?,?,?,?,?,?,?)",
                     (uuid.uuid4().hex, b, step, role, text, _now(), time.time_ns()))
        conn.commit()
    finally:
        conn.close()


def journey_state(brand: str, history_step: str | None = None) -> dict:
    """Per-step status, waiting prerequisites, pending drafts, the current open question as
    a fresh prompt, and the count of earlier chat turns (R4). Turns themselves are only
    included for `history_step`."""
    b = _key(brand)
    answers = answers_for(b)
    drafts = list_drafts(b)
    conn = _conn()
    try:
        stored = _stored_statuses(conn, b)
        counts = {r["step"]: r["n"] for r in conn.execute(
            "SELECT step, COUNT(*) AS n FROM journey_turns WHERE brand=? GROUP BY step", (b,))}
        history = None
        if history_step:
            history = [{"role": r["role"], "text": r["text"], "created_at": r["created_at"]}
                       for r in conn.execute("SELECT role, text, created_at FROM journey_turns "
                                             "WHERE brand=? AND step=? ORDER BY seq",
                                             (b, history_step))]
    finally:
        conn.close()

    statuses: dict[str, str] = {}
    for step in jf.STEPS:
        pending = any(d["step"] == step for d in drafts)
        status = stored.get(step) or _derive(step, answers, pending)
        if status == "confirmed" and step != "flow":
            req = jf.required_fields(step, answers)
            if not all(jf.has_value(answers.get(f["key"])) for f in req):
                status = "drafted"
        statuses[step] = status

    steps = []
    for step in jf.STEPS:
        nxt = jf.next_questions(step, answers, 1) if step != "flow" else []
        entry = {
            "step": step,
            "label": jf.STEP_LABELS[step],
            "status": statuses[step],
            "waiting": [p for p in jf.step_prerequisites(step) if statuses[p] != "confirmed"],
            "drafts": [d for d in drafts if d["step"] == step],
            "question": nxt[0] if nxt else None,
            "earlier_count": counts.get(step, 0),
        }
        if history is not None and step == history_step:
            entry["history"] = history
        steps.append(entry)
    return {"brand": b, "steps": steps}
