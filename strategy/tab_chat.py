"""Per-tab chat: one persisted conversation thread per (project, workspace tab), each
routed to that tab's named agent (frontend/src/workspace/types.ts STAGE_AGENTS). Own
store (data/tab_chat.db) -- deliberately NOT a key inside strategy/projects.py's project
state, which stays exactly as-is for the automated run's streamed narration.

Two agent behaviors, dispatched by stage_id in ask():
  - "operations": the Campaign Operations agent can edit the project's campaign_plan_layout
    WorkflowDocument. It sees the live document, replies, and (when the request calls for a
    structural change) returns a full replacement document -- validated against a Python
    port of a subset of the flow-builder's "strict-flowchart" rules
    (frontend/.../flowbuilder/validation/engine.ts rules 1-4) before being persisted via the
    same full-overwrite path the UI itself already uses (projects.save_project).
  - "orchestration": the Engagement Orchestration agent manages the activity board —
    status answers grounded in the live board/schedule/notifications/sync state, plus
    add/edit/remove activity and manual nudge/follow-up actions (JSON envelope
    {reply, actions}, applied deterministically; hard gates never agent-closable).
  - "planning" / "reporting": grounded Q&A against the project's own plan content, no
    document mutation.

ask() never raises -- any failure (LLM unavailable, bad JSON, validation failure after
retry) returns a plain-text reply instead, same resilience contract as hcp_360.ask().
"""
from __future__ import annotations

import json
import re
import pathlib
import sqlite3
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from paths import data_path  # noqa: E402
import db  # noqa: E402  (dual-dialect SQLite/Postgres connection factory)
import projects as pstore  # noqa: E402
import conversation_llm  # noqa: E402
import hcp_360  # noqa: E402  (Reporting agent tools: list_hcps / segment_summary / get_hcp)
import data_blocks  # noqa: E402  (tool results -> renderable table/chart/drill-down blocks)
import reporting_insights  # noqa: E402  (Reporting agent grounding: KPIs / funnel / demographics)

DB_PATH = data_path("tab_chat.db")

STAGE_AGENTS = {
    "planning": "Campaign Planning & Strategy Agent",
    "orchestration": "Engagement Orchestration Agent",
    "operations": "Campaign Operations Agent",
    "reporting": "Reporting & Insights Agent",
}

_OPS_CONTEXT_STAGES = ("planning", "orchestration", "operations", "reporting")


def _conn():
    conn = db.connect("tab_chat")
    conn.execute("""CREATE TABLE IF NOT EXISTS messages (
        project_id TEXT NOT NULL,
        stage_id   TEXT NOT NULL,
        seq        INTEGER NOT NULL,
        role       TEXT NOT NULL,
        agent_id   TEXT,
        text       TEXT NOT NULL,
        kind       TEXT NOT NULL DEFAULT 'chat',
        ts         TEXT NOT NULL,
        PRIMARY KEY (project_id, stage_id, seq)
    )""")
    # Lightweight migration for the renderable data blocks attached to an answer (see
    # data_blocks.py): existing tab_chat.db files predate this column, and CREATE TABLE IF
    # NOT EXISTS won't add one. Same attempt-and-swallow idiom as projects.py -- SQLite has
    # no ADD COLUMN IF NOT EXISTS, and the rollback() is what keeps a Postgres transaction
    # from staying aborted after the duplicate-column error.
    try:
        conn.execute("ALTER TABLE messages ADD COLUMN data_json TEXT")
        conn.commit()
    except Exception:  # noqa: BLE001  (SQLite: OperationalError; Postgres: DuplicateColumn)
        conn.rollback()
    return conn


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def get_history(project_id: str, stage_id: str) -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT role, agent_id, text, kind, ts, data_json FROM messages "
            "WHERE project_id=? AND stage_id=? ORDER BY seq", (project_id, stage_id)
        ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            raw = item.pop("data_json", None)
            # Reloading the tab has to give back the same tables/charts the live answer
            # showed, so the blocks travel with the message rather than being recomputed.
            try:
                item["data_blocks"] = json.loads(raw) if raw else None
            except Exception:  # noqa: BLE001 -- a corrupt payload degrades to a text-only turn
                item["data_blocks"] = None
            out.append(item)
        return out
    finally:
        conn.close()


def append(project_id: str, stage_id: str, role: str, agent_id: str | None, text: str,
           kind: str = "chat", blocks: list[dict] | None = None) -> None:
    conn = _conn()
    try:
        nxt = conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 n FROM messages WHERE project_id=? AND stage_id=?",
            (project_id, stage_id)).fetchone()["n"]
        conn.execute(
            "INSERT INTO messages (project_id, stage_id, seq, role, agent_id, text, kind, ts, data_json) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (project_id, stage_id, nxt, role, agent_id, text, kind, _now(),
             json.dumps(blocks) if blocks else None))
        conn.commit()
    finally:
        conn.close()


def _limit_text(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _recent_lines(items: list[dict], max_items: int, max_chars: int) -> str:
    trimmed = items[-max_items:]
    lines = [f"{item.get('role', 'unknown')}: {_limit_text(item.get('text', ''), 240)}" for item in trimmed if item.get("text")]
    return _limit_text("\n".join(lines), max_chars) or "(none)"


def _brief_snapshot(proj: dict) -> str:
    slots = ((proj.get("state") or {}).get("slots") or {})
    lines = []
    for key, value in slots.items():
        if value in (None, "", 0, False):
            continue
        lines.append(f"{key}: {value}")
    return "\n".join(lines) or "(no brief fields captured yet)"


def _cross_stage_context(project_id: str) -> str:
    blocks = []
    for stage_id in _OPS_CONTEXT_STAGES:
        history = get_history(project_id, stage_id)
        if not history:
            continue
        # Regeneration needs the user's accumulated instructions, not just the last
        # sentence. Keep this bounded for the model, but give operations materially more
        # context than the ordinary chat-edit path used to receive.
        max_items = 24 if stage_id == "operations" else 12
        blocks.append(f"[{stage_id}]\n{_recent_lines(history, max_items, 3600 if stage_id == 'operations' else 1800)}")
    return "\n\n".join(blocks) or "(no tab-chat history yet)"


# ------------------------------------------------------ WorkflowDocument validation ---
# Python port of a subset of frontend/.../flowbuilder/validation/engine.ts's
# "strict-flowchart" profile (rules 1-4 only -- start/end reachability, start-has-no-
# inbound/end-has-no-outbound, decision branch labelling, orphan/dead-end nodes). Not
# full parity with the TS engine (rules 5-12 are warnings/advanced layout checks, out of
# scope here) -- good enough to reject a structurally broken LLM edit before it's saved.

def _is_start(t: str) -> bool:
    return t == "start" or t.startswith("event.start.")


def _is_end(t: str) -> bool:
    return t in ("end", "terminal") or t.startswith("event.end.")


def _is_annotation(t: str) -> bool:
    return t in ("comment", "text")


def _forward_reachable(start_ids: list[str], out: dict[str, list[dict]]) -> set[str]:
    seen = set(start_ids)
    stack = list(start_ids)
    while stack:
        nid = stack.pop()
        for e in out.get(nid, []):
            tgt = e["target"]["nodeId"]
            if tgt not in seen:
                seen.add(tgt)
                stack.append(tgt)
    return seen


def validate_document(doc: dict) -> list[str]:
    errors: list[str] = []
    for page in doc.get("pages", []):
        nodes = page.get("nodes", [])
        edges = page.get("edges", [])
        out: dict[str, list[dict]] = {n["id"]: [] for n in nodes}
        inn: dict[str, list[dict]] = {n["id"]: [] for n in nodes}
        for e in edges:
            out.setdefault(e["source"]["nodeId"], []).append(e)
            inn.setdefault(e["target"]["nodeId"], []).append(e)

        starts = [n for n in nodes if _is_start(n["type"])]
        ends = {n["id"] for n in nodes if _is_end(n["type"])}
        if not starts:
            errors.append(f"page '{page.get('id')}': no start node.")
        for n in nodes:
            if _is_annotation(n["type"]) or _is_end(n["type"]):
                continue
            reachable = _forward_reachable([n["id"]], out)
            if not (reachable & ends):
                errors.append(f"node '{n['label']}' ({n['id']}) has no path to an end/terminal node.")

        for n in nodes:
            if _is_start(n["type"]) and inn.get(n["id"]):
                errors.append(f"start node '{n['label']}' ({n['id']}) has inbound edges.")
            if _is_end(n["type"]) and out.get(n["id"]):
                errors.append(f"end node '{n['label']}' ({n['id']}) has outbound edges.")

        for n in nodes:
            if n["type"] != "decision" and not n["type"].startswith("gateway."):
                continue
            outgoing = out.get(n["id"], [])
            if len(outgoing) < 2:
                errors.append(f"decision '{n['label']}' ({n['id']}) needs >=2 outbound branches, has {len(outgoing)}.")
            for e in outgoing:
                label = e.get("label") or ((e.get("labels") or [{}])[0].get("text"))
                if not label:
                    errors.append(f"branch from decision '{n['label']}' ({n['id']}) is missing a label.")

        for n in nodes:
            if _is_annotation(n["type"]) or _is_start(n["type"]) or _is_end(n["type"]):
                continue
            if not inn.get(n["id"]):
                errors.append(f"node '{n['label']}' ({n['id']}) has no inbound edge (orphan).")
            if not out.get(n["id"]):
                errors.append(f"node '{n['label']}' ({n['id']}) has no outbound edge (dead end).")
    return errors


# ----------------------------------------------------------------- operations agent ---

_WORKFLOWDOC_SCHEMA_SUMMARY = """WorkflowDocument JSON shape (fields you may set; anything
you omit keeps its previous value if you're returning a partial-looking object -- but you
must always return the FULL document, not a diff):
{
  "schemaVersion": "1.0", "id": str, "name": str, "description": str,
  "direction": "TB"|"BT"|"LR"|"RL",
  "pages": [{
    "id": str, "name": str,
    "nodes": [{
      "id": str (unique), "type": one of the node types below, "label": str,
      "position": {"x": number, "y": number}, "size": {"w": number, "h": number},
      "ports": [], "data": {<field name>: {"type": "string"|"number"|"boolean"|"fixedList",
        "value": ..., "label": str, "options"?: [str]}},
      "style": {"stroke": "#hex", "fill": "#hex"}, "layerIds": [], "groupId": null
    }],
    "edges": [{
      "id": str (unique), "source": {"nodeId": str, "portId"?: "yes"|"no", "glue": "static"|"dynamic"},
      "target": {"nodeId": str, "glue": "static"|"dynamic"},
      "type": "sequence", "label"?: str,
      "line": {"style": "solid", "weight": 2, "color": "#333333", "arrowStart": "none",
        "arrowEnd": "arrow", "routing": "orthogonal", "curve": "step", "lineJumps": "none", "waypoints": []},
      "data": {}, "layerIds": []
    }],
    "groups": [], "layers": []
  }],
  "stencils": [...], "dataSets": [...], "theme": {...}, "validationProfile": "strict-flowchart",
  "meta": {...}, "customMasters": [...]
}

Node types you'll realistically use for a campaign journey: start, end, terminal, process,
decision, delay, prepare, event, manual-operation, priority-action, summary.
Campaign-specific node.data fields (all optional, use fixedList/string/number/boolean shape
above): campaignStepKind (fixedList, options ["send","wait","decision","exit","followup",
"closure"]), day (number), channel (string), detail (string), segment_key (string).

Decision nodes: each outgoing edge needs a distinct "label" (e.g. "Yes"/"No") and, when it's
a binary branch, source.portId "yes"/"no" with source.glue "static" (non-decision edges use
glue "dynamic" and no portId).

Structural rules that WILL be validated after you respond (violating these gets your edit
rejected and you'll be asked to fix it): every page needs >=1 start node; every non-end node
must have a forward path to an end/terminal node; start nodes have no inbound edges; end
nodes have no outbound edges; every decision node has >=2 outbound edges, each labeled;
every non-start/non-end node has >=1 inbound AND >=1 outbound edge (no orphans, no dead ends)."""

_OPS_SYSTEM = f"""You are the Campaign Operations Agent for a pharma omnichannel campaign
planning tool. You help the user edit an engagement-journey flow diagram by describing
changes in plain English. You see the diagram's current JSON (a WorkflowDocument) and the
conversation so far.

{_WORKFLOWDOC_SCHEMA_SUMMARY}

Respond with ONLY a single raw JSON object, no markdown fences, no prose outside it:
{{"reply": "<your natural-language reply to the user>",
  "document": <the FULL updated WorkflowDocument if the user asked for a structural change,
              or null if you're just answering a question / no change is needed>}}
Keep "reply" conversational and short. Never invent nodes/edges the user didn't ask for
beyond what's needed to keep the diagram structurally valid (e.g. adding a label to a new
branch). If the user explicitly requests FULL REGENERATION, this rule is superseded: use
the brief and conversation to replace the entire graph, including its node set, edge set,
labels, and positions, while preserving only supported campaign logic."""


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[: -3]
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


def _parse_ops_response(text: str) -> tuple[str, dict | None]:
    """Parse the operations agent response defensively.

    The model is instructed to return a single raw JSON object, but in practice it can
    sometimes emit code fences, a little prose, or an empty response. Rather than letting
    `json.loads()` leak a raw parser error into the UI, try a few recovery paths and then
    fail with a clean, human-readable exception.
    """
    cleaned = _strip_json_fence(text)
    if not cleaned:
        raise ValueError("empty response from the workflow editor")

    candidates = [cleaned]
    if not cleaned.startswith("{") or not cleaned.endswith("}"):
        # The model sometimes adds a sentence before or after the JSON object. Grab the
        # outermost braces as a best-effort recovery path.
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidates.append(cleaned[start : end + 1])

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if not isinstance(parsed, dict):
                raise ValueError("workflow editor response must be a JSON object")
            return parsed.get("reply", ""), parsed.get("document")
        except Exception as exc:  # noqa: BLE001 -- recovery path only
            last_error = exc

    raise ValueError(f"invalid JSON from the workflow editor ({last_error})")


def _ask_operations(project_id: str, message: str, document: dict | None = None) -> dict:
    proj = pstore.get_project(project_id)
    if not proj:
        return {"reply": "I can't find this project.", "document": None}
    doc = document or proj.get("campaign_plan_layout")
    if not doc:
        return {"reply": "There's no campaign diagram loaded yet for this project -- open "
                          "the Campaign Operations tab first so one gets generated, then "
                          "ask me to edit it.", "document": None}
    if not conversation_llm.llm_available():
        return {"reply": "The LLM isn't configured, so I can't make edits right now -- use "
                          "the manual editor instead.", "document": None}

    history = get_history(project_id, "operations")[-24:]
    convo = "\n".join(f"{m['role']}: {m['text']}" for m in history)
    brief_snapshot = _brief_snapshot(proj)
    plan_snapshot = _limit_text(proj.get("plan_markdown") or "", 5000) or "(no plan markdown saved yet)"
    stage1_convo = _recent_lines(proj.get("messages") or [], 14, 2500)
    cross_stage = _cross_stage_context(project_id)

    def _call(extra: str = "") -> tuple[str, dict | None]:
        client = conversation_llm._get_client()
        user_payload = (
            f"Campaign brief snapshot:\n{brief_snapshot}\n\n"
            f"Stage 1 planning conversation:\n{stage1_convo}\n\n"
            f"Saved plan snapshot:\n{plan_snapshot}\n\n"
            f"Relevant tab-chat history:\n{cross_stage}\n\n"
            f"Current diagram JSON:\n{json.dumps(doc)}\n\n"
            f"Operations conversation so far:\n{convo}\n\n"
            f"User: {message}{extra}"
        )
        resp = client.messages.create(model=conversation_llm.MODEL, max_tokens=16000,
                                       system=_OPS_SYSTEM,
                                       messages=[{"role": "user", "content": user_payload}])
        text = next((b.text for b in resp.content if b.type == "text"), "")
        if resp.stop_reason == "max_tokens":
            raise ValueError("the diagram is too large for the model to return in one "
                              "response -- try a smaller edit")
        return _parse_ops_response(text)

    try:
        try:
            reply, new_doc = _call()
        except ValueError as first_error:
            msg = str(first_error).lower()
            if "empty response" in msg or "invalid json" in msg:
                retry_note = (
                    "\n\nYour previous response was not valid JSON. "
                    "Return only one raw JSON object with exactly two keys: "
                    '"reply" and "document". Do not use markdown fences or prose.'
                )
                reply, new_doc = _call(retry_note)
            else:
                raise
        if new_doc:
            errors = validate_document(new_doc)
            if errors:
                err_note = ("\n\nYour previous proposed document failed validation:\n- "
                             + "\n- ".join(errors[:8]) + "\nPlease fix and return the full "
                             "corrected document (or return document=null and explain if you "
                             "can't).")
                reply2, new_doc2 = _call(err_note)
                if new_doc2 and not validate_document(new_doc2):
                    reply, new_doc = reply2, new_doc2
                else:
                    reply = reply2 or (reply + " (I couldn't produce a structurally valid "
                                                "edit for that -- no change was made.)")
                    new_doc = None
        if new_doc:
            pstore.save_project(project_id, campaign_plan_layout=new_doc)
        return {"reply": reply or "Done.", "document": new_doc}
    except Exception as e:  # noqa: BLE001 -- never break the page on an LLM/parse failure
        return {"reply": f"Couldn't process that edit ({e}).", "document": None}


def regenerate_operations(project_id: str, document: dict | None = None) -> dict:
    """Full redraw request for the Campaign Operations diagram.

    Uses the operations agent when available, but always keeps a deterministic full-flow
    fallback. The old implementation returned ``document: null`` whenever the model was
    unavailable or produced an invalid response, which made the button appear to do
    nothing. The fallback is built from the same saved plan context as the initial Stage 3
    generation and is returned as a CampaignFlow for the frontend's document adapter.
    """
    proj = pstore.get_project(project_id)
    if not proj:
        return {"reply": "I can't find this project.", "document": None, "flow": None}

    fallback_flow = None
    ctx = (proj.get("state") or {}).get("_plan_ctx")
    if ctx:
        try:
            import campaign_ops
            # Keep this path deterministic. The optional wording enrichment belongs to the
            # AI redraw below; the fallback must still work when that service is down.
            fallback_flow = campaign_ops.build_campaign_plan(ctx, use_llm=False).get("flow")
        except Exception:  # noqa: BLE001 -- regeneration must retain a usable fallback
            fallback_flow = None

    instruction = (
        "FULL REGENERATION, not an incremental edit: redraw the campaign operations diagram "
        "completely from scratch. Ground the new journey in the campaign brief, the full "
        "Stage 1 planning conversation, the saved plan, and every relevant tab-chat "
        "instruction so far. Return a full replacement WorkflowDocument with a newly "
        "considered node and edge structure. Do not copy the current graph just because it "
        "is present in the context. Preserve only decisions that are still supported by "
        "the brief and conversation. Keep it concise, structurally valid, and fully wired "
        "from start to end."
    )
    append(project_id, "operations", "user", None, "[Regenerate diagram from brief and conversation context]", kind="action")
    result = _ask_operations(project_id, instruction, document=document)
    append(project_id, "operations", "assistant", "operations", result.get("reply", ""), kind="action")

    if result.get("document"):
        result["regenerated"] = True
        result["source"] = "ai"
        return result

    if fallback_flow:
        result["flow"] = fallback_flow
        result["regenerated"] = True
        result["source"] = "deterministic-fallback"
        result["reply"] = (
            (result.get("reply") or "The AI redraw was unavailable.")
            + " I rebuilt the complete diagram from the saved campaign brief and plan."
        )
    return result


# ------------------------------------------------------------- orchestration agent ---
# The Engagement Orchestration agent manages the activity board through chat: status
# ("where do we stand on X, why is it stuck") answered from the live board + schedule +
# notifications + downstream sync state, and write actions (add/edit/remove activity,
# manual nudge / follow-up to an owner on the user's behalf). Same JSON-envelope +
# deterministic-apply pattern as the operations agent; hard gates are never agent-closable.

_ORCH_SYSTEM = """You are the Engagement Orchestration Agent for a pharma omnichannel
campaign tool. You manage the project's activity board: setup activities routed to teams,
each with an owner role, SLA, planned dates, hard compliance gates and downstream
(Monday/Smartsheet/Jira-style) sync state.

You can BOTH answer and act. Respond with ONE raw JSON object only — no markdown fences,
no prose outside it: {"reply": "<your message to the user>", "actions": [...]}
"actions" is optional/empty for pure answers.

Action shapes (use EXACT activity ids from the board data):
 {"op":"add","title":"...","team":"<team>","category":"<category>","channel":"<channel or null>","assigned_to":"<role/person or null>"}
 {"op":"edit","id":"...","fields":{"title":?,"team":?,"assigned_to":?,"done":?,"channel":?,"category":?}}
 {"op":"remove","id":"..."}
 {"op":"nudge","id":"...","note":"<optional message sent to the owner>"}
 {"op":"followup","id":"...","note":"<optional follow-up message>"}

Teams: @TEAMS@
Categories: @CATEGORIES@

Rules:
- Status questions ("where do we stand / why is it stuck"): answer from the board data
  only, citing concrete fields — open vs done, planned window, slack, critical-path,
  unmet gating input, hard gate, overdue notifications, downstream sync state. No actions.
- An activity is typically stuck because its gating input isn't ready, a hard compliance
  gate is unmet, it's overdue vs SLA, it sits on the critical path with no slack, or its
  downstream item hasn't moved. Say which applies — don't invent reasons.
- NEVER set done=true on an activity that has a hard gate — explain who must clear it.
- If the user's reference is ambiguous between activities, ask which one — no actions.
- nudge/followup are sent on the user's behalf to the activity's owner/team; confirm in
  your reply who you nudged and about what.
- Keep replies short and concrete.

ACTIVITY BOARD:
@BOARD@

OPEN NOTIFICATIONS:
@NOTIFS@

DOWNSTREAM SYNC:
@BINDINGS@"""

_EDITABLE_FIELDS = {"title", "team", "assigned_to", "done", "channel", "category"}


def _orch_board_lines(pid: str, tasks: list[dict]) -> str:
    import orchestration_schedule
    sched: dict[str, dict] = {}
    try:
        res = orchestration_schedule.build_schedule(tasks)
        sched = {a.get("id"): a for a in res.get("activities", [])}
    except Exception:  # noqa: BLE001 — board grounding must survive a schedule failure
        pass
    lines = []
    for t in tasks:
        s = sched.get(t.get("id")) or {}
        bits = [f"id={t.get('id')}", f"title={t.get('title', '')}",
                f"status={'done' if t.get('done') else 'open'}",
                f"team={t.get('team', '')}", f"owner={t.get('assigned_to', '')}",
                f"category={t.get('category', '')}", f"sla={t.get('sla', '')}"]
        if t.get("channel"):
            bits.append(f"channel={t['channel']}")
        if s.get("planned_start"):
            bits.append(f"planned={s['planned_start']}→{s.get('planned_due', '?')}")
        if s.get("is_critical"):
            bits.append("critical-path")
        if s.get("slack_days") is not None:
            bits.append(f"slack={s['slack_days']}d")
        if t.get("gate"):
            bits.append(f"hard-gate={t['gate']}")
        if t.get("gating_input"):
            bits.append(f"gating-input={t['gating_input']}")
        lines.append(" | ".join(str(b) for b in bits))
    return "\n".join(lines) or "(no activities on the board yet)"


def _orch_apply_actions(pid: str, tasks: list[dict], actions: list) -> tuple[list[dict], list[str], bool]:
    """Deterministically apply the agent's actions. Returns (tasks, notes, changed_board)."""
    import orchestration_store as store
    import orchestration_tasks as ot
    notes: list[str] = []
    changed = False
    by_id = {t.get("id"): t for t in tasks}
    for act in actions if isinstance(actions, list) else []:
        if not isinstance(act, dict):
            continue
        op = act.get("op")
        if op == "add":
            title = (act.get("title") or "").strip()
            if not title:
                continue
            task = ot.manual_task(title, category=act.get("category") or "Custom",
                                  channel=act.get("channel"), team=act.get("team"),
                                  assigned_to=act.get("assigned_to"))
            tasks.append(task)
            by_id[task["id"]] = task
            notes.append(f"added “{title}” → {task['team']} ({task['sla']})")
            changed = True
        elif op in ("edit", "remove", "nudge", "followup"):
            task = by_id.get(act.get("id"))
            if not task:
                notes.append(f"couldn't find activity {act.get('id')!r} — no change")
                continue
            if op == "edit":
                fields = act.get("fields") or {}
                applied = []
                for k, v in fields.items():
                    if k not in _EDITABLE_FIELDS:
                        continue
                    if k == "done" and v and task.get("gate"):
                        notes.append(f"“{task.get('title')}” has a hard gate ({task['gate']}) — "
                                     "not closable by the agent")
                        continue
                    task[k] = v
                    applied.append(k)
                if "category" in applied:
                    ot.reenrich(task)
                if applied:
                    notes.append(f"updated “{task.get('title')}” ({', '.join(applied)})")
                    changed = True
            elif op == "remove":
                tasks.remove(task)
                by_id.pop(task.get("id"), None)
                notes.append(f"removed “{task.get('title')}”")
                changed = True
            else:  # nudge / followup — a manual notification to the owner, on the user's behalf
                dedupe = f"{task.get('id')}:manual-{op}"
                prev = store.get_notification(pid, dedupe)
                recipient = f"{task.get('assigned_to') or 'owner'} ({task.get('team', '')})"
                verb = "Nudge" if op == "nudge" else "Follow-up"
                store.upsert_notification(
                    pid, dedupe, activity_id=task.get("id"), trigger=f"manual-{op}",
                    severity="warning" if op == "nudge" else "info", channel="in-app",
                    recipient=recipient,
                    title=f"{verb} from the campaign owner: {task.get('title', '')}",
                    body=act.get("note") or f"{verb} on “{task.get('title', '')}” — please update status.",
                    gate=None, fire_count=(prev or {}).get("fire_count", 0) + 1, escalated=False)
                notes.append(f"{verb.lower()} sent to {recipient} re “{task.get('title')}”")
    return tasks, notes, changed


def _ask_orchestration(project_id: str, message: str) -> dict:
    import orchestration_store as store
    import orchestration_tasks as ot
    proj = pstore.get_project(project_id)
    if not proj:
        return {"reply": "I can't find this project."}
    if not conversation_llm.llm_available():
        return {"reply": "The LLM isn't configured, so I can't manage the board right now — "
                          "use the Activities board directly."}
    tasks = ot.ensure_enriched(proj.get("orchestration_tasks") or [])

    notifs = store.list_notifications(project_id, include_acked=False)[:12]
    notif_lines = "\n".join(
        f"activity={n.get('activity_id')} | {n.get('trigger')} | {n.get('severity')} | {n.get('title')}"
        for n in notifs) or "(none)"
    binds = store.list_bindings(project_id)
    bind_lines = "\n".join(
        f"activity={b.get('activity_id')} | system={b.get('system')} | state={b.get('sync_state')}"
        for b in binds[:25]) or "(nothing pushed downstream yet)"

    # .replace, not .format — the prompt's JSON examples are full of literal braces.
    system = (_ORCH_SYSTEM
              .replace("@TEAMS@", " | ".join(ot.TEAMS))
              .replace("@CATEGORIES@", " | ".join(ot.CATEGORIES))
              .replace("@BOARD@", _orch_board_lines(project_id, tasks))
              .replace("@NOTIFS@", notif_lines)
              .replace("@BINDINGS@", bind_lines))

    history = get_history(project_id, "orchestration")[-10:]
    convo = "\n".join(f"{m['role']}: {m['text']}" for m in history)

    def _call(extra: str = "") -> dict:
        client = conversation_llm._get_client()
        resp = client.messages.create(
            model=conversation_llm.MODEL, max_tokens=1500, system=system,
            messages=[{"role": "user", "content": f"Conversation so far:\n{convo}\n\nUser: {message}{extra}"}])
        text = next((b.text for b in resp.content if b.type == "text"), "")
        cleaned = _strip_json_fence(text)
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            cleaned = cleaned[start:end + 1]
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("expected a JSON object")
        return parsed

    try:
        try:
            parsed = _call()
        except Exception:  # noqa: BLE001 — one retry with a format reminder
            parsed = _call("\n\nYour previous response was not the required raw JSON object. "
                           'Return only {"reply": "...", "actions": [...]} with no fences.')
        reply = parsed.get("reply") or ""
        actions = parsed.get("actions") or []
        tasks, notes, changed = _orch_apply_actions(project_id, tasks, actions)
        if changed:
            pstore.save_project(project_id, orchestration_tasks=tasks)
        if notes:
            reply = (reply + "\n\n" if reply else "") + "✔ " + "\n✔ ".join(notes)
        # notifications count as a change for the frontend's refetch even if the board didn't move
        acted = changed or any(n.startswith(("nudge", "follow-up")) for n in notes)
        return {"reply": reply or "Done.", "changed": acted}
    except Exception as e:  # noqa: BLE001 — same never-raise contract as the other agents
        return {"reply": f"Couldn't process that ({e})."}


# ------------------------------------------------------------------- generic agents ---

_GENERIC_SYSTEM = """You are the {agent_name} for a pharma omnichannel campaign planning
tool. Answer the user's question about their campaign plan concisely and in character,
grounded ONLY in the plan content provided below -- don't invent facts not present in it.
If the plan content doesn't cover what they're asking, say so plainly.

Plan content:
{plan_content}"""


def _ask_generic(project_id: str, stage_id: str, message: str) -> dict:
    proj = pstore.get_project(project_id)
    if not proj:
        return {"reply": "I can't find this project."}
    if not conversation_llm.llm_available():
        return {"reply": "The LLM isn't configured, so I can't answer right now."}
    plan_content = (proj.get("plan_markdown") or "")[:8000] or "(no plan generated yet)"
    history = get_history(project_id, stage_id)[-10:]
    convo = "\n".join(f"{m['role']}: {m['text']}" for m in history)
    system = _GENERIC_SYSTEM.format(agent_name=STAGE_AGENTS[stage_id], plan_content=plan_content)
    try:
        client = conversation_llm._get_client()
        resp = client.messages.create(
            model=conversation_llm.MODEL, max_tokens=700, system=system,
            messages=[{"role": "user", "content": f"Conversation so far:\n{convo}\n\nUser: {message}"}])
        text = next((b.text for b in resp.content if b.type == "text"), "").strip()
        return {"reply": text or "No answer produced."}
    except Exception as e:  # noqa: BLE001
        return {"reply": f"Couldn't reach the LLM ({e})."}


_REPORTING_SYSTEM = (
    "You are the Reporting & Insights agent for a pharma omnichannel campaign. Answer questions "
    "about measurement — KPIs, the stage-promotion funnel, delivery/engagement targets, the UTM "
    "link/tagging matrix and the A/B test design — and about the HCP 360 audience panel. Ground "
    "measurement answers in the REPORTING INSIGHTS below; use the tools (list_hcps, "
    "segment_summary, get_hcp) for anything about specific HCPs or panel breakdowns. Be concise. "
    "The KPI numbers are TARGETS/benchmarks (industry baselines scaled by the lifecycle index), "
    "not observed results — say so when you cite a rate. Never invent panel numbers; only report "
    "what the tools return.\n\n"
    "Every breakdown you pull back from a tool is rendered for the user as a live, sortable "
    "table with its own chart and drill-down, directly under your reply — so do NOT paste a "
    "markdown table of those same rows. Answer in prose: the headline number, what it means "
    "for the plan, and any caveat. If you point at it, call it 'the table below' — it is "
    "rendered after your text, never above it.\n\n"
    "REPORTING INSIGHTS:\n{insights}\n\nPLAN (excerpt):\n{plan}"
)


def _ask_reporting(project_id: str, message: str) -> dict:
    """Reporting agent: a bounded tool-use loop over the HCP 360 panel, grounded in the
    reporting-insights payload + the plan. Never raises -- degrades to a plain reply."""
    proj = pstore.get_project(project_id)
    if not proj:
        return {"reply": "I can't find this project."}
    if not conversation_llm.llm_available():
        return {"reply": "The LLM isn't configured, so I can't answer free-text questions right "
                         "now — the KPI, demographic and tagging cards on the right are still live."}
    try:
        insights = reporting_insights.summary_text(project_id)
    except Exception:  # noqa: BLE001
        insights = "(reporting insights unavailable)"
    plan_content = (proj.get("plan_markdown") or "")[:5000] or "(no plan generated yet)"
    system = _REPORTING_SYSTEM.format(insights=insights[:4000], plan=plan_content)
    history = get_history(project_id, "reporting")[-8:]
    convo = "\n".join(f"{m['role']}: {m['text']}" for m in history)
    # Every tool result the loop sees is also shaped into a renderable block, so the answer
    # carries the actual rows the model reasoned over rather than a markdown table it typed
    # out from them. Deduped by (tool, arguments): the model re-running an identical query in
    # a later turn of the loop shouldn't stack a duplicate table under the reply.
    blocks: list[dict] = []
    seen_calls: set[str] = set()

    def _collect(tool_name: str, tool_input, result) -> None:
        key = f"{tool_name}:{json.dumps(tool_input, sort_keys=True, default=str)}"
        if key in seen_calls:
            return
        seen_calls.add(key)
        try:
            block = data_blocks.from_tool_call(tool_name, tool_input, result, f"blk{len(blocks) + 1}")
        except Exception:  # noqa: BLE001 -- a block is a bonus; never let shaping break the answer
            block = None
        if block:
            blocks.append(block)

    try:
        client = conversation_llm._get_client()
        messages: list[dict] = [{"role": "user", "content": f"Conversation so far:\n{convo}\n\nUser: {message}"}]
        for _ in range(3):  # bounded tool-use budget
            resp = client.messages.create(model=conversation_llm.MODEL, max_tokens=800,
                                           system=system, tools=hcp_360._TOOLS, messages=messages)
            messages.append({"role": "assistant", "content": resp.content})
            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            if not tool_uses:
                text = next((b.text for b in resp.content if b.type == "text"), "").strip()
                return {"reply": text or "No answer produced.", "data_blocks": blocks}
            tool_results = []
            for tu in tool_uses:
                try:
                    fn = hcp_360._TOOL_FUNCS.get(tu.name)
                    out = fn(**tu.input) if fn else {"error": f"unknown tool {tu.name}"}
                except Exception as e:  # noqa: BLE001
                    out = {"error": str(e)}
                else:
                    _collect(tu.name, tu.input, out)
                tool_results.append({"type": "tool_result", "tool_use_id": tu.id,
                                      "content": json.dumps(out, default=str)[:4000]})
            messages.append({"role": "user", "content": tool_results})
        return {"reply": "Couldn't settle on an answer within the tool-call budget — try a narrower question.",
                "data_blocks": blocks}
    except Exception as e:  # noqa: BLE001
        return {"reply": f"Couldn't reach the LLM ({e})."}


# ------------------------------------------------------------------------- dispatch ---

def ask(project_id: str, stage_id: str, message: str, document: dict | None = None) -> dict:
    """Route to the right agent behavior for this tab, append both turns to this tab's
    history, and return the reply (plus a "document" key when the operations agent
    changed the diagram). Never raises."""
    if stage_id not in STAGE_AGENTS:
        return {"reply": f"Unknown tab '{stage_id}'."}
    append(project_id, stage_id, "user", None, message)
    if stage_id == "operations":
        result = _ask_operations(project_id, message, document=document)
    elif stage_id == "orchestration":
        result = _ask_orchestration(project_id, message)
    elif stage_id == "reporting":
        result = _ask_reporting(project_id, message)
    else:
        result = _ask_generic(project_id, stage_id, message)
    append(project_id, stage_id, "assistant", stage_id, result.get("reply", ""),
           blocks=result.get("data_blocks"))
    return result
