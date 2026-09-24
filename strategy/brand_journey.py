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


def step_status(brand: str, step: str) -> str:
    return next(s["status"] for s in journey_state(brand)["steps"] if s["step"] == step)


# ---- U3: step-scoped agent turn (KTD3) and document pre-fill (KTD5) ------------------------

import re  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

import conversation_llm  # noqa: E402
from strategy import kit_chat  # noqa: E402  (reuses _FIELD_SHAPES and the envelope parser)

CONTENT_STEPS = ("brief", "audience", "message", "kit")
_FALLBACK_MAX_CHARS = 200
_STRING_LIST_FIELDS = frozenset({"territories", "tone_pillars", "voice_do", "voice_dont"})

_TURN_SYSTEM = """You are the journey agent for a pharma brand's "{step_label}" step.

The system has already chosen which fields are open. You may ONLY propose values for these
open fields of this step: {fields}. Never propose any other field.

Propose a value only when the user's message clearly supports it -- this is pharma content,
and a fabricated value is worse than none. Keep "reply" to at most two short sentences and
at most one question; if you ask one, phrase the NEXT open field's question (given below)
rather than inventing your own.

Reply with ONLY one raw JSON object, no markdown fences, no prose outside it:
{{"reply": "<at most two sentences>", "proposals": {{"<field>": <value>, ...}}}}"""

_EXTRACT_SYSTEM = """You extract a pharma brand's "{step_label}" content from a brand-plan
document. You may ONLY fill these fields: {fields}. Include a field only when the document
text clearly states it -- leave it out otherwise; never guess or invent.

Reply with ONLY one raw JSON object, no markdown fences, no prose outside it:
{{"proposals": {{"<field>": <value>, ...}}}}"""


def _llm_on() -> bool:
    return conversation_llm.llm_available()


def _shape_hints(keys) -> str:
    hints = [f'- "{k}" must be shaped exactly like: {kit_chat._FIELD_SHAPES[k]}'
             for k in keys if k in kit_chat._FIELD_SHAPES]
    return ("\n\nRequired JSON shape for structured fields:\n" + "\n".join(hints)) if hints else ""


def _call_llm_json(system: str, payload: str) -> dict:
    """One call, one retry on invalid JSON, strict=False parse (kit_chat._parse_envelope) --
    the kit_chat._call_llm idiom. Raises on provider failure; callers fall back."""
    client = conversation_llm._get_client()

    def _call(extra: str = "") -> dict:
        resp = client.messages.create(model=conversation_llm.MODEL, max_tokens=6000, system=system,
                                      messages=[{"role": "user", "content": payload + extra}])
        text = next((b.text for b in resp.content if b.type == "text"), "")
        return kit_chat._parse_envelope(text)

    try:
        return _call()
    except (ValueError, json.JSONDecodeError):
        return _call("\n\nYour previous response was not valid JSON. Return only one raw JSON "
                     "object -- no markdown fences, no prose outside it, strings escaped.")


def _call_turn_llm(system: str, payload: str) -> dict:
    return _call_llm_json(system, payload)


def _effective_answers(b: str) -> dict:
    """Kept answers overlaid with pending set-mode drafts, so a drafted field is not asked
    again while it waits for keep or undo."""
    answers = answers_for(b)
    for d in list_drafts(b):
        if d["mode"] == "set":
            answers[d["field"]] = d["value"]
    return answers


def _is_scalar(b: str, key: str) -> bool:
    if key in kit_chat._FIELD_SHAPES or jf.FIELDS_BY_KEY[key]["target"] == "brand":
        return False
    current = (brand_kit.kit_for(b) or {}).get(key)
    if isinstance(current, dict):
        return False
    return not isinstance(current, list) or key in _STRING_LIST_FIELDS


def _step_fields(step: str) -> list[str]:
    return [f["key"] for f in jf.fields_for(step) if f["target"] != "brand"]


def agent_turn(brand: str, step: str, message: str) -> dict:
    """One short agent turn scoped to `step` (KTD3). Proposals outside the step's open
    fields are dropped; the rest become drafts. Never raises on LLM failure: falls back to
    the registry (question + chips; a short answer drafts the current question's field)."""
    b = _key(brand)
    jf.step_prerequisites(step)  # ValueError on unknown step
    if step == "flow":
        raise ValueError("flow edits use structured operations, not field turns")
    message = (message or "").strip()
    answers = _effective_answers(b)
    open_before = [f for f in jf.open_fields(step, answers) if f["target"] != "brand"]
    add_turn(b, step, "user", message)

    drafts, dropped, mode, reply = [], [], "fallback", ""
    if message and _llm_on():
        try:
            keys = [f["key"] for f in open_before]
            system = _TURN_SYSTEM.format(step_label=jf.STEP_LABELS[step],
                                         fields=", ".join(keys) or "(none)") + _shape_hints(keys)
            current = {k: answers.get(k) for k in _step_fields(step)}
            nxt = open_before[0]["question"] if open_before else "(nothing open)"
            payload = (f"Current values:\n{json.dumps(current, indent=2)}\n\n"
                       f"Next open question: {nxt}\n\nUser: {message}")
            env = _call_turn_llm(system, payload)
            proposals = env.get("proposals") or {}
            dropped = [k for k in proposals if k not in keys]
            drafts = [propose(b, step, k, v) for k, v in proposals.items()
                      if k in keys and jf.has_value(v)]
            reply, mode = str(env.get("reply") or "").strip(), "llm"
        except Exception as e:  # noqa: BLE001 -- degrade to the registry, never fail
            print(f"[brand_journey] turn LLM failed for {b}/{step}: {e!r}")
            for d in drafts:
                undo(b, d["id"])
            drafts, dropped, mode = [], [], "fallback"
    if mode == "fallback" and message and open_before:
        f = open_before[0]
        if len(message) <= _FALLBACK_MAX_CHARS and _is_scalar(b, f["key"]):
            value = [message] if f["key"] in _STRING_LIST_FIELDS else message
            drafts.append(propose(b, step, f["key"], value))

    nxt = jf.next_questions(step, _effective_answers(b), 1)
    question = nxt[0] if nxt else None
    if mode == "fallback" or not reply:
        reply = question["question"] if question else "That covers this step. Keep what looks right."
    add_turn(b, step, "agent", reply)
    return {"reply": reply, "question": question, "drafts": drafts, "dropped": dropped,
            "mode": mode, "state": journey_state(b)}


def extract_step(step: str, text: str) -> dict:
    """KTD5: one extraction call constrained to `step`'s registry fields. {} when the LLM
    is off or fails (never raises)."""
    if not (text or "").strip() or not _llm_on():
        return {}
    keys = _step_fields(step)
    system = _EXTRACT_SYSTEM.format(step_label=jf.STEP_LABELS[step],
                                    fields=", ".join(keys)) + _shape_hints(keys)
    try:
        env = _call_llm_json(system, f"Brand-plan document text:\n{text}")
        return {k: v for k, v in (env.get("proposals") or {}).items() if k in keys}
    except Exception as e:  # noqa: BLE001
        print(f"[brand_journey] extraction failed for {step}: {e!r}")
        return {}


def apply_document(brand: str, text: str) -> list[str]:
    """Run extraction for every content step concurrently, and propose drafts only where a
    value differs from the kept one (R10, R20). A changed confirmed step (including a locked
    Kit) moves back to drafted. Returns the changed steps in step order."""
    b = _key(brand)
    with ThreadPoolExecutor(max_workers=len(CONTENT_STEPS)) as pool:
        results = dict(zip(CONTENT_STEPS, pool.map(lambda s: extract_step(s, text), CONTENT_STEPS)))
    answers = answers_for(b)
    changed = []
    for step in CONTENT_STEPS:
        allowed = set(_step_fields(step))
        proposed = [propose(b, step, k, v) for k, v in (results.get(step) or {}).items()
                    if k in allowed and jf.has_value(v) and v != answers.get(k)]
        if proposed:
            changed.append(step)
            if step_status(b, step) == "confirmed":
                reopen(b, step)
    return changed


_NAME_RE = re.compile(r"\b(?:called|named)\s+([A-Z][\w\-]*)")


def name_from_description(description: str) -> str:
    """Best-effort brand name from a one-line description without the LLM: "... called X"
    or "... named X", else the whole description when it is one to three words."""
    d = (description or "").strip()
    m = _NAME_RE.search(d)
    if m:
        return m.group(1)
    return d if d and len(d.split()) <= 3 else ""


def start_journey(name: str, description: str, text: str) -> dict:
    """Create a brand and start its journey (F1, F2). An explicit `name` wins; else it comes
    from the document (brand_kit.infer_brand_name) or the description. ValueError when no
    name can be found, KeyError when the brand already exists."""
    name = ((name or "").strip() or (brand_kit.infer_brand_name(text) if text else "")
            or name_from_description(description))
    if not name:
        raise ValueError("couldn't tell the brand's name -- pass it as 'name'")
    brand_kit.create_brand(name)
    b = _key(name)
    changed = apply_document(b, text) if text else []
    if description and not text:
        if _llm_on():
            agent_turn(b, "brief", description)
        else:
            add_turn(b, "brief", "user", description)
    state = journey_state(b)
    brief = next(s for s in state["steps"] if s["step"] == "brief")
    return {"brand": b, "changed_steps": changed, "question": brief["question"], "state": state}
