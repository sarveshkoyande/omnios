"""Journey store for the Agentic Brand Journey (KTD2).

Per brand: journey-only answers, pending drafts per step, step status, step chat turns and
the flow document, in its own SQLite file (<DATA_DIR>/brand_journey.db) -- same
"own flat store" pattern as the other strategy/ stores.

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
# a flat `import brand_kit` would be a separate module instance with its own stale cache.
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
    key = brand_kit.canonical_key(brand)
    if key is None:
        raise KeyError(f"no brand kit for '{brand}'")
    return key


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


def _recent_turns(brand: str, step: str, limit: int = 6) -> str:
    """The step's last few chat turns as plain text, so a short follow-up ("all recipients,
    3 days after") is read against the question the agent just asked."""
    conn = _conn()
    try:
        rows = list(conn.execute("SELECT role, text FROM journey_turns WHERE brand=? AND step=? "
                                 "ORDER BY seq DESC LIMIT ?", (_key(brand), step, limit)))
    finally:
        conn.close()
    return "\n".join(f"{r['role']}: {r['text']}" for r in reversed(rows)) or "(none)"


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
from strategy import kit_chat  # noqa: E402  (reuses FIELD_SHAPES and the envelope parser)

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
    hints = [f'- "{k}" must be shaped exactly like: {kit_chat.FIELD_SHAPES[k]}'
             for k in keys if k in kit_chat.FIELD_SHAPES]
    return ("\n\nRequired JSON shape for structured fields:\n" + "\n".join(hints)) if hints else ""


def _call_llm_json(system: str, payload: str) -> dict:
    """One call, one retry on invalid JSON, strict=False parse (kit_chat.parse_envelope) --
    the kit_chat._call_llm idiom. Raises on provider failure; callers fall back."""
    client = conversation_llm._get_client()

    def _call(extra: str = "") -> dict:
        resp = client.messages.create(model=conversation_llm.MODEL, max_tokens=6000, system=system,
                                      messages=[{"role": "user", "content": payload + extra}])
        text = next((b.text for b in resp.content if b.type == "text"), "")
        return kit_chat.parse_envelope(text)

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
    if key in kit_chat.FIELD_SHAPES or jf.FIELDS_BY_KEY[key]["target"] == "brand":
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
                       f"Next open question: {nxt}\n\n"
                       f"Conversation so far:\n{_recent_turns(b, step)}")
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
    Kit) moves back to drafted. Returns the changed steps in step order.

    Compared against kept + pending values, so re-uploading the same document does not stack
    duplicate drafts; a new value supersedes the field's pending set-mode draft."""
    b = _key(brand)
    with ThreadPoolExecutor(max_workers=len(CONTENT_STEPS)) as pool:
        results = dict(zip(CONTENT_STEPS, pool.map(lambda s: extract_step(s, text), CONTENT_STEPS)))
    answers = _effective_answers(b)
    pending = list_drafts(b)
    changed = []
    for step in CONTENT_STEPS:
        allowed = set(_step_fields(step))
        updates = {k: v for k, v in (results.get(step) or {}).items()
                   if k in allowed and jf.has_value(v) and v != answers.get(k)}
        for d in pending:
            if d["mode"] == "set" and d["field"] in updates:
                undo(b, d["id"])
        proposed = [propose(b, step, k, v) for k, v in updates.items()]
        if proposed:
            changed.append(step)
            if step_status(b, step) == "confirmed":
                reopen(b, step)
    return changed


_NAME_RE = re.compile(r"\b(?:called|named)\s+([A-Z][\w\-]*)")
# "Zeltrova is a ..." / "Zeltrova, a ..." -- a leading capitalised word used as the subject.
_LEAD_NAME_RE = re.compile(r"^([A-Z][\w\-]+)(?:\s+is\b|\s+will\b|,)")


def name_from_description(description: str) -> str:
    """Best-effort brand name from a one-line description without the LLM: "... called X"
    or "... named X", else the whole description when it is one to three words."""
    d = (description or "").strip()
    m = _NAME_RE.search(d)
    if m:
        return m.group(1)
    m = _LEAD_NAME_RE.match(d)
    if m:
        return m.group(1)
    return d if d and len(d.split()) <= 3 else ""


def start_journey(name: str, description: str, text: str) -> dict:
    """Create a brand and start its journey (F1, F2). An explicit `name` wins; else it comes
    from the document (brand_kit.infer_brand_name) or the description. ValueError when no
    name can be found, KeyError when the brand already exists."""
    name = ((name or "").strip() or (brand_kit.infer_brand_name(text) if text else "")
            or name_from_description(description)
            or (brand_kit.infer_brand_name(description) if description else ""))
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


# ---- U6: brand-derived ctx, rules-built flow, stable block codes, structured edits (KTD6, KTD8)

import copy  # noqa: E402

import campaign_ops  # noqa: E402

FLOW_OPS = ("add", "remove", "connect", "change")
FLOW_NODE_TYPES = ("send", "wait", "decision", "branch", "exit", "followup", "closure")
_CHANGEABLE = ("label", "channel", "detail", "day")
_AUDIENCE_GROUP = {"hcps": "hcp", "patients": "patient", "caregivers": "patient", "payers": "payer"}

_FLOW_TURN_SYSTEM = """You turn a pharma marketer's request into structured edits of a campaign
flow. Blocks are identified ONLY by their block code (B1, B2, ...). Allowed operations:
{"op": "add", "type": "send|wait|decision|branch|exit|followup|closure", "label": "...", "after": "<code, optional>", "channel": "<optional>", "detail": "<optional>", "ref": "<optional temp name, e.g. N1>"}
A later op in the same list may use an earlier add's "ref" in place of a block code.
{"op": "remove", "code": "<code>"}
{"op": "connect", "from": "<code>", "to": "<code>", "label": "<optional>"}
{"op": "change", "code": "<code>", "set": {"label|channel|detail|day": <value>}}
Use only codes that exist in the flow given. The last "user:" line is the current request;
read it together with the earlier turns (it may answer your previous question). Prefer
acting: when the combined request names what to add or change and roughly where, return the
ops with sensible defaults (e.g. an email reminder is a "send" with channel "email"; "N days
after" means a "wait" of N days followed by the send). Ask one short question only when you
truly cannot choose the block or the operation. The change lands as a draft the user keeps
or undoes, so a reasonable guess is better than another question. Reply with ONLY one raw
JSON object, no markdown fences:
{"reply": "<at most two sentences>", "ops": [ ... ]}"""

_FLOW_HELP = ("I can edit the flow with structured changes: add a block, remove one, connect "
              "two, or change one's label, channel, detail or day. Name blocks by their code, "
              "for example: change B3's channel to SMS.")


def _conn_flow():
    conn = _conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS journey_flow_draft (
        brand TEXT PRIMARY KEY, ops_json TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    return conn


def _primary_persona(kit: dict, primary_audience) -> str:
    personas = kit.get("personas") or {}
    if not isinstance(personas, dict):
        return ""
    group = _AUDIENCE_GROUP.get(str(primary_audience or "").strip().lower(), "hcp")
    for g in [group] + [g for g in personas if g != group]:
        items = [p for p in (personas.get(g) or []) if isinstance(p, dict)]
        if items:
            primary = next((p for p in items if str(p.get("tier", "")).lower() == "primary"), items[0])
            return str(primary.get("name") or "")
    return ""


def brand_ctx(brand: str) -> dict:
    """KTD6: the minimal ctx build_campaign_plan reads, from the kept kit and journey answers.
    Project-only keys (bam, kpi, journey_spec, micro_journeys, studio_answers, strategy,
    segment_profile) get empty defaults; the kept Message pillars become the message ladder."""
    b = _key(brand)
    kit = brand_kit.kit_for(b) or {}
    answers = answers_for(b)
    persona = _primary_persona(kit, answers.get("primary_audience"))
    audience = [str(answers.get("primary_audience") or "").strip(), persona]
    pillars = [str(p["pillar"]).strip() for p in (kit.get("message_hierarchy") or [])
               if isinstance(p, dict) and p.get("pillar")]
    indication = str(kit.get("indication") or "")
    return {
        "brand": b,
        "therapy_area": str(kit.get("therapy_area") or indication),
        "brief": {"audience": " - ".join(x for x in audience if x),
                  "objective": str(answers.get("key_objective") or "")},
        "inferred": {"persona": persona or "the target persona"},
        "content_library": brand_kit.content_library_from_kit(kit, indication),
        "message_flow": {"ladder_sequence": pillars} if pillars else {},
        "bam": {}, "kpi": {}, "journey_spec": {}, "micro_journeys": {}, "studio_answers": {},
        "strategy": {}, "segment_profile": {},
    }


def _next_code(codes: dict) -> str:
    nums = [int(c[1:]) for c in codes.values() if str(c)[1:].isdigit()]
    return f"B{max(nums, default=0) + 1}"


def _assign_codes(flow: dict, codes: dict) -> None:
    """Stable key = node type + semantic source (the rules builder's node id). Matching keys
    reuse their code; new keys take the next free code. Mutates flow and codes."""
    for n in flow["nodes"]:
        key = f"{n['type']}:{n['id']}"
        if key not in codes:
            codes[key] = _next_code(codes)
        n["data"]["block_code"] = codes[key]


def _by_code(flow: dict, code) -> dict:
    n = next((n for n in flow["nodes"] if n["data"].get("block_code") == code), None)
    if n is None:
        raise ValueError(f"no block {code} in this flow")
    return n


def _normalize_op(op) -> dict:
    if not isinstance(op, dict) or op.get("op") not in FLOW_OPS:
        raise ValueError(f"unknown flow operation {op!r}: use one of {', '.join(FLOW_OPS)}")
    op = dict(op)
    if op["op"] == "add":
        if op.get("type") not in FLOW_NODE_TYPES:
            raise ValueError(f"add needs a node type from {', '.join(FLOW_NODE_TYPES)}")
        if not str(op.get("label") or "").strip():
            raise ValueError("add needs a label")
        op.setdefault("uid", uuid.uuid4().hex[:12])
    if op["op"] == "change":
        s = op.get("set")
        if not isinstance(s, dict) or not s or any(k not in _CHANGEABLE for k in s):
            raise ValueError(f"change needs 'set' with only {', '.join(_CHANGEABLE)}")
    return op


def _apply_op(flow: dict, codes: dict, op: dict) -> None:
    """Apply one op in place; ValueError (nothing applied) when a target block is missing."""
    kind = op["op"]
    if kind == "add":
        anchor = _by_code(flow, op["after"]) if op.get("after") else None
        key = f"added:{op['uid']}"
        if key not in codes:
            codes[key] = _next_code(codes)
        nid = f"added_{op['uid']}"
        pos = anchor["position"] if anchor else {"x": 0, "y": 0}
        data = {"label": str(op["label"]), "block_code": codes[key]}
        for k in ("channel", "detail", "day"):
            if op.get(k) not in (None, ""):
                data[k] = op[k]
        flow["nodes"].append({"id": nid, "type": op["type"],
                              "position": {"x": pos["x"] + 300, "y": pos["y"]}, "data": data})
        if anchor:
            flow["edges"].append({"id": f"e_{anchor['id']}_{nid}", "source": anchor["id"],
                                  "target": nid})
    elif kind == "remove":
        nid = _by_code(flow, op.get("code"))["id"]
        flow["nodes"] = [n for n in flow["nodes"] if n["id"] != nid]
        flow["edges"] = [e for e in flow["edges"] if nid not in (e["source"], e["target"])]
    elif kind == "connect":
        src, dst = _by_code(flow, op.get("from")), _by_code(flow, op.get("to"))
        eid = f"e_{src['id']}_{dst['id']}"
        if not any(e["id"] == eid for e in flow["edges"]):
            edge = {"id": eid, "source": src["id"], "target": dst["id"]}
            if op.get("label"):
                edge["label"] = str(op["label"])
            flow["edges"].append(edge)
    else:
        _by_code(flow, op.get("code"))["data"].update(op["set"])


def _apply_ops(flow: dict, codes: dict, ops: list, strict: bool) -> tuple[list, list]:
    """(applied, dropped). strict: the first failing op raises instead of being dropped."""
    applied, dropped = [], []
    refs: dict = {}  # an add op's optional "ref" -> the block code it received, for later ops in the batch
    for op in ops:
        try:
            resolved = {k: (refs.get(v, v) if k in ("after", "from", "to", "code") else v)
                        for k, v in op.items()}
            _apply_op(flow, codes, resolved)
            if op.get("op") == "add" and op.get("ref"):
                refs[op["ref"]] = codes[f"added:{op['uid']}"]
            applied.append(op)
        except ValueError as e:
            if strict:
                raise
            dropped.append({"op": op, "reason": str(e)})
    return applied, dropped


def _load_flow_row(conn, b: str) -> dict | None:
    row = conn.execute("SELECT doc_json FROM journey_flow WHERE brand=?", (b,)).fetchone()
    return json.loads(row["doc_json"]) if row else None


def _save_flow_row(conn, b: str, stored: dict) -> None:
    conn.execute("DELETE FROM journey_flow WHERE brand=?", (b,))
    conn.execute("INSERT INTO journey_flow (brand, doc_json, updated_at) VALUES (?,?,?)",
                 (b, json.dumps(stored), _now()))


def _draft_ops(conn, b: str) -> list | None:
    row = conn.execute("SELECT ops_json FROM journey_flow_draft WHERE brand=?", (b,)).fetchone()
    return json.loads(row["ops_json"]) if row else None


def _set_draft_ops(conn, b: str, ops: list | None) -> None:
    conn.execute("DELETE FROM journey_flow_draft WHERE brand=?", (b,))
    if ops:
        conn.execute("INSERT INTO journey_flow_draft (brand, ops_json, updated_at) VALUES (?,?,?)",
                     (b, json.dumps(ops), _now()))


def _flow_waiting(b: str) -> list[str]:
    return next(s["waiting"] for s in journey_state(b)["steps"] if s["step"] == "flow")


def _current(stored: dict) -> tuple[dict, dict]:
    """Kept flow = rules skeleton + kept ops (validated when they were kept or rebuilt)."""
    flow, codes = copy.deepcopy(stored["base"]["flow"]), dict(stored["codes"])
    _apply_ops(flow, codes, stored["ops"], strict=False)
    return flow, codes


def _flow_doc(b: str, stored: dict | None, draft_ops: list | None) -> dict:
    if stored is None:
        waiting = _flow_waiting(b)
        return {"brand": b, "status": "waiting" if waiting else "not_built", "waiting": waiting,
                "flow": None, "plan": None, "ops": [], "dropped": [], "draft": None}
    flow, codes = _current(stored)
    draft = None
    if draft_ops:
        dflow = copy.deepcopy(flow)
        _apply_ops(dflow, codes, draft_ops, strict=False)
        draft = {"ops": draft_ops, "flow": dflow}
    plan = {k: v for k, v in stored["base"].items() if k != "flow"}
    return {"brand": b, "status": "built", "waiting": [], "flow": flow, "plan": plan,
            "ops": stored["ops"], "dropped": stored.get("dropped", []), "draft": draft}


def get_flow(brand: str) -> dict:
    b = _key(brand)
    conn = _conn_flow()
    try:
        return _flow_doc(b, _load_flow_row(conn, b), _draft_ops(conn, b))
    finally:
        conn.close()


def build_flow(brand: str) -> dict:
    """Build or rebuild (R16, R17): rules skeleton from the brand ctx with the LLM step off,
    stable codes, then kept ops reapplied by code; ops whose target is gone are dropped and
    reported. Returns the waiting prerequisites instead when Brief, Audience and Message are
    not all confirmed."""
    b = _key(brand)
    if _flow_waiting(b):
        return _flow_doc(b, None, None)
    base = campaign_ops.build_campaign_plan(brand_ctx(b), use_llm=False)
    conn = _conn_flow()
    try:
        prev = _load_flow_row(conn, b) or {"codes": {}, "ops": []}
        codes = dict(prev["codes"])
        _assign_codes(base["flow"], codes)
        flow = copy.deepcopy(base["flow"])
        kept, dropped = _apply_ops(flow, codes, prev["ops"], strict=False)
        stored = {"base": base, "codes": codes, "ops": kept, "dropped": dropped}
        pending = _draft_ops(conn, b)
        if pending:
            ok, _ = _apply_ops(flow, dict(codes), pending, strict=False)
            _set_draft_ops(conn, b, ok)
        _save_flow_row(conn, b, stored)
        _ensure_seeded(conn, b)
        if _stored_statuses(conn, b).get("flow") == "not_started":
            _set_status(conn, b, "flow", "drafted")
        conn.commit()
        return _flow_doc(b, stored, _draft_ops(conn, b))
    finally:
        conn.close()


def propose_flow_ops(brand: str, ops) -> dict:
    """Validate `ops` against the current flow (kept + pending draft) and append them to the
    draft. ValueError, with no draft change, if any op is malformed or targets a missing code."""
    b = _key(brand)
    if not isinstance(ops, list) or not ops:
        raise ValueError('send an operations envelope: {"ops": [{"op": ...}]}')
    ops = [_normalize_op(op) for op in ops]
    conn = _conn_flow()
    try:
        stored = _load_flow_row(conn, b)
        if stored is None:
            raise ValueError("build the flow before editing it")
        flow, codes = _current(stored)
        pending = _draft_ops(conn, b) or []
        _apply_ops(flow, codes, pending, strict=False)
        _apply_ops(flow, codes, ops, strict=True)
        _set_draft_ops(conn, b, pending + ops)
        conn.commit()
        return _flow_doc(b, stored, pending + ops)
    finally:
        conn.close()


def keep_flow_draft(brand: str) -> dict:
    """Append the draft ops to the kept list; codes of added blocks become permanent."""
    b = _key(brand)
    conn = _conn_flow()
    try:
        stored, pending = _load_flow_row(conn, b), _draft_ops(conn, b)
        if stored and pending:
            flow, codes = _current(stored)
            ok, _ = _apply_ops(flow, codes, pending, strict=False)
            stored["ops"], stored["codes"] = stored["ops"] + ok, codes
            _save_flow_row(conn, b, stored)
            _set_draft_ops(conn, b, None)
            conn.commit()
        return _flow_doc(b, stored, None)
    finally:
        conn.close()


def undo_flow_draft(brand: str) -> dict:
    b = _key(brand)
    conn = _conn_flow()
    try:
        _set_draft_ops(conn, b, None)
        conn.commit()
        return _flow_doc(b, _load_flow_row(conn, b), None)
    finally:
        conn.close()


def _call_flow_llm(system: str, payload: str) -> dict:
    return _call_llm_json(system, payload)


def flow_turn(brand: str, message: str = "", ops=None) -> dict:
    """The Flow step's turn (KTD8). An explicit ops envelope lands as a draft (ValueError on
    an invalid op, no draft). Free text becomes ops through the LLM when it is on; an LLM
    failure or an invalid LLM op degrades to a help reply with no draft -- never raises."""
    b = _key(brand)
    message = (message or "").strip()
    if ops:
        doc = propose_flow_ops(b, ops)
        if message:
            add_turn(b, "flow", "user", message)
        reply = f"Drafted {len(ops)} change{'s' if len(ops) != 1 else ''}. Keep or undo."
        add_turn(b, "flow", "agent", reply)
        return {"reply": reply, "mode": "ops", "flow": doc}
    add_turn(b, "flow", "user", message)
    current = get_flow(b)
    mode, reply = "fallback", ""
    if current["status"] != "built":
        reply = "Build the flow first: it needs Brief, Audience and Message confirmed."
    elif message and _llm_on():
        try:
            shown = (current["draft"] or current)["flow"]
            blocks = [{"code": n["data"]["block_code"], "type": n["type"],
                       "label": n["data"].get("label")} for n in shown["nodes"]]
            env = _call_flow_llm(_FLOW_TURN_SYSTEM, f"Blocks:\n{json.dumps(blocks)}\n\n"
                                 f"Conversation so far:\n{_recent_turns(b, 'flow')}")
            if env.get("ops"):
                current = propose_flow_ops(b, env["ops"])
            reply, mode = str(env.get("reply") or "").strip(), "llm"
        except Exception as e:  # noqa: BLE001 -- degrade, never fail
            print(f"[brand_journey] flow turn LLM failed for {b}: {e!r}")
            current, mode, reply = get_flow(b), "fallback", ""
    reply = reply or _FLOW_HELP
    add_turn(b, "flow", "agent", reply)
    return {"reply": reply, "mode": mode, "flow": current}
