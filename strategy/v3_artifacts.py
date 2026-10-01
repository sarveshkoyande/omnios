"""Redesign Phase 4: typed, versioned artifacts produced by agent workspaces (C9-C11, C15, C16).

An artifact is a schema-shaped object, not prose. The campaign brief is a direct projection of
the workspace's framework inputs: every field names the framework input it came from, and a
field nobody decided reads "Needs input" rather than being invented. Every Generate and every
edit writes a new version; nothing is overwritten.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import brand_kit  # noqa: E402
from paths import data_path  # noqa: E402

NEEDS_INPUT = "Needs input"

# The campaign brief's schema: sections -> fields, each projected from one framework input
# (config/frameworks/campaign_spine.json keys) or a brand-kit field.
BRIEF_SCHEMA: list[dict] = [
    {"id": "snapshot", "title": "Snapshot", "fields": [
        {"id": "brand", "label": "Brand", "from": "meta:brand"},
        {"id": "therapy_area", "label": "Therapy area", "from": "kit:therapy_area"},
        {"id": "objective", "label": "Objective", "from": "S1.2"},
        {"id": "audience", "label": "Target audience", "from": "S2.2"},
        {"id": "why_now", "label": "Why now", "from": "S0.2"},
    ]},
    {"id": "purpose", "title": "Purpose", "fields": [
        {"id": "campaign_type", "label": "Campaign type", "from": "S0.3"},
        {"id": "program_context", "label": "Program context", "from": "S0.1"},
        {"id": "lifecycle", "label": "Brand & lifecycle", "from": "S0.0"},
    ]},
    {"id": "objective", "title": "Objective & measures", "fields": [
        {"id": "pillars", "label": "Strategic pillars", "from": "S1.0"},
        {"id": "statement", "label": "Objective statement", "from": "S1.2"},
        {"id": "leading_indicators", "label": "Leading indicators", "from": "S8.0"},
        {"id": "targets", "label": "Targets", "from": "S8.1"},
    ]},
    {"id": "audience", "title": "Audience & eligibility", "fields": [
        {"id": "segment", "label": "Primary segment", "from": "S2.2"},
        {"id": "eligibility", "label": "Eligibility rules", "from": "S2.3"},
    ]},
    {"id": "comms", "title": "Communication strategy", "fields": [
        {"id": "core_claim", "label": "Core claim", "from": "S5.1"},
        {"id": "lead_message", "label": "Lead message", "from": "S5.2"},
        {"id": "claims_library", "label": "Approved claims", "from": "S5.0"},
        {"id": "competitive_context", "label": "Competitive context", "from": "S3.1"},
    ]},
    {"id": "channels", "title": "Channels", "fields": [
        {"id": "anchor_channel", "label": "Anchor channel", "from": "S6.2"},
    ]},
    {"id": "deliverables", "title": "Deliverables", "fields": [
        {"id": "variants", "label": "Testing variants", "from": "S7.1"},
        {"id": "content_inventory", "label": "Existing content", "from": "S7.0"},
    ]},
    {"id": "compliance", "title": "Compliance", "fields": [
        {"id": "audience_type", "label": "Audience & content type", "from": "S4.0"},
        {"id": "review_ladder", "label": "Review ladder", "from": "S4.1"},
    ]},
    {"id": "timeline", "title": "Timeline", "fields": [
        {"id": "launch", "label": "Launch", "from": "S9.1"},
    ]},
]

_DB = None


def _conn() -> sqlite3.Connection:
    global _DB
    if _DB is None:
        path = data_path("v3_artifacts.db")
        path.parent.mkdir(parents=True, exist_ok=True)
        _DB = sqlite3.connect(str(path), check_same_thread=False)
        _DB.row_factory = sqlite3.Row
        _DB.execute("""CREATE TABLE IF NOT EXISTS artifacts (
            id TEXT PRIMARY KEY, type TEXT, agent TEXT, brand TEXT, plan_id INTEGER, campaign_id INTEGER,
            title TEXT, created_at TEXT, updated_at TEXT)""")
        _DB.execute("""CREATE TABLE IF NOT EXISTS versions (
            artifact_id TEXT, version INTEGER, created_at TEXT, reason TEXT, body TEXT,
            PRIMARY KEY (artifact_id, version))""")
        _DB.commit()
    return _DB


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def compose_brief(brand: str, inputs: dict, extras: list[dict]) -> dict:
    """Projects the workspace inputs into the brief schema. `inputs` is {key: {label, value, ...}}."""
    kit = brand_kit.kit_for(brand) or {}
    sections = []
    for sec in BRIEF_SCHEMA:
        fields = []
        for f in sec["fields"]:
            src = f["from"]
            if src == "meta:brand":
                value, origin = brand, "Settings"
            elif src.startswith("kit:"):
                value, origin = kit.get(src[4:]), "Brand kit"
            else:
                inp = inputs.get(src) or {}
                value, origin = inp.get("value"), f"{src} · {inp.get('label', '')}".strip(" ·")
            fields.append({"id": f["id"], "label": f["label"], "value": value or NEEDS_INPUT,
                           "source": origin, "needs_input": not value})
        sections.append({"id": sec["id"], "title": sec["title"], "fields": fields})
    context = [x for x in extras if (x.get("value") or "").strip()]
    if context:
        sections.append({"id": "context", "title": "Additional context", "fields": [
            {"id": f"extra_{i}", "label": x.get("label", "Context"), "value": x["value"].strip(),
             "source": "You", "needs_input": False} for i, x in enumerate(context)]})
    return {"type": "campaign_brief", "schema_version": 1, "sections": sections}


# Which artifact type each agent produces (D4: Campaign plan -> Flow, Brief).
AGENT_ARTIFACT = {"brief-compiler": "campaign_brief", "briefing-agent": "campaign_brief", "campaign-planner": "campaign_plan", "flow-planner": "flow"}

_DERIVATION_SOURCE = {"derive": "Brand data", "confirm": "Confirmed", "ask": "You"}


def compose_campaign_plan(inputs: dict, extras: list[dict]) -> dict:
    """The campaign plan (D5): every framework decision, one section per spine stage."""
    import agent_forms  # local: agent_forms imports brand_kit too; avoid an import cycle at load
    fw = agent_forms.load_framework("campaign_spine")
    sections = []
    for st in fw["stages"]:
        fields = []
        for dp in st["data_points"]:
            inp = inputs.get(dp["key"]) or {}
            value = inp.get("value")
            label = dp["label"][:1].upper() + dp["label"][1:]
            fields.append({"id": dp["key"].replace(".", "_"), "label": label, "value": value or NEEDS_INPUT,
                           "source": f"{dp['key']} · {_DERIVATION_SOURCE.get(dp['derivation'], dp['derivation'])}",
                           "needs_input": not value})
        sections.append({"id": st["id"], "title": st["name"], "fields": fields})
    context = [x for x in extras if (x.get("value") or "").strip()]
    if context:
        sections.append({"id": "context", "title": "Additional context", "fields": [
            {"id": f"extra_{i}", "label": x.get("label", "Context"), "value": x["value"].strip(),
             "source": "You", "needs_input": False} for i, x in enumerate(context)]})
    return {"type": "campaign_plan", "schema_version": 1, "sections": sections}


FLOW_SCHEMA: list[dict] = [
    {"id": "audience", "title": "Audience", "fields": [
        {"id": "segment", "label": "Segments", "from": "S2.2"},
        {"id": "eligibility", "label": "Eligibility rules", "from": "S2.3"},
    ]},
    {"id": "messages", "title": "Messages", "fields": [
        {"id": "lead_message", "label": "Lead message", "from": "S5.2"},
        {"id": "core_claim", "label": "Core claim", "from": "S5.1"},
    ]},
    {"id": "channel", "title": "Channel & cadence", "fields": [
        {"id": "anchor_channel", "label": "Anchor channel", "from": "S6.2"},
    ]},
    {"id": "timing", "title": "Timing", "fields": [
        {"id": "launch", "label": "Launch", "from": "S9.1"},
    ]},
]


def compose_flow(inputs: dict) -> dict:
    """The flow (D3): renders the campaign's structure; it decides nothing new. The diagram
    itself is produced by strategy/flow_sop and shown in the viewer's Diagram tab."""
    sections = []
    for sec in FLOW_SCHEMA:
        fields = []
        for f in sec["fields"]:
            inp = inputs.get(f["from"]) or {}
            value = inp.get("value")
            fields.append({"id": f["id"], "label": f["label"], "value": value or NEEDS_INPUT,
                           "source": f"{f['from']} · {inp.get('label', '')}".strip(" ·"), "needs_input": not value})
        sections.append({"id": sec["id"], "title": sec["title"], "fields": fields})
    sections.append({"id": "diagram", "title": "Diagram", "fields": [{
        "id": "diagram_source", "label": "Diagram source",
        "value": ("Rendered by the SOP flow generator from its sample brief (Leqvio Fall Push). "
                  "Feeding this campaign's own plan into the generator is not wired yet."),
        "source": "strategy/flow_sop", "needs_input": False}]})
    return {"type": "flow", "schema_version": 1, "sections": sections}


def compose_for(agent: str, brand: str, inputs: dict, extras: list[dict]) -> dict:
    kind = AGENT_ARTIFACT.get(agent, "campaign_brief")
    if kind == "campaign_plan":
        return compose_campaign_plan(inputs, extras)
    if kind == "flow":
        return compose_flow(inputs)
    return compose_brief(brand, inputs, extras)


def _row(artifact_id: str) -> sqlite3.Row | None:
    return _conn().execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()


def _latest(artifact_id: str) -> sqlite3.Row | None:
    return _conn().execute("SELECT * FROM versions WHERE artifact_id = ? ORDER BY version DESC LIMIT 1",
                           (artifact_id,)).fetchone()


def _view(meta: sqlite3.Row, ver: sqlite3.Row) -> dict:
    return {**dict(meta), "version": ver["version"], "version_reason": ver["reason"],
            "version_created_at": ver["created_at"], **json.loads(ver["body"])}


def _add_version(artifact_id: str, body: dict, reason: str) -> dict:
    db = _conn()
    last = _latest(artifact_id)
    version = (last["version"] if last else 0) + 1
    now = _now()
    db.execute("INSERT INTO versions VALUES (?, ?, ?, ?, ?)", (artifact_id, version, now, reason, json.dumps(body)))
    db.execute("UPDATE artifacts SET updated_at = ? WHERE id = ?", (now, artifact_id))
    db.commit()
    return get(artifact_id)


def generate(agent: str, brand: str, plan_id: int | None, campaign_id: int | None, title: str,
             inputs: dict, extras: list[dict]) -> dict:
    """Generate (or regenerate) the artifact for this agent + campaign; a new version either way."""
    db = _conn()
    body = {"inputs": inputs, "extras": extras, "artifact": compose_for(agent, brand, inputs, extras)}
    existing = db.execute("SELECT id FROM artifacts WHERE agent = ? AND brand = ? AND IFNULL(campaign_id, -1) = IFNULL(?, -1)",
                          (agent, brand, campaign_id)).fetchone()
    if existing:
        db.execute("UPDATE artifacts SET title = ? WHERE id = ?", (title, existing["id"]))
        return _add_version(existing["id"], body, "Regenerated")
    artifact_id = uuid.uuid4().hex[:12]
    now = _now()
    db.execute("INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
               (artifact_id, AGENT_ARTIFACT.get(agent, "campaign_brief"), agent, brand, plan_id, campaign_id, title, now, now))
    return _add_version(artifact_id, body, "Generated")


def get(artifact_id: str, version: int | None = None) -> dict | None:
    meta = _row(artifact_id)
    if not meta:
        return None
    ver = (_conn().execute("SELECT * FROM versions WHERE artifact_id = ? AND version = ?", (artifact_id, version)).fetchone()
           if version else _latest(artifact_id))
    return _view(meta, ver) if ver else None


def find(agent: str, brand: str, campaign_id: int | None) -> dict | None:
    row = _conn().execute("SELECT id FROM artifacts WHERE agent = ? AND brand = ? AND IFNULL(campaign_id, -1) = IFNULL(?, -1)",
                          (agent, brand, campaign_id)).fetchone()
    return get(row["id"]) if row else None


def edit_fields(artifact_id: str, changes: dict[str, str], reason: str | None = None) -> dict:
    """Structured edit (C11): only existing field ids, string values. Writes a new version."""
    current = get(artifact_id)
    if not current:
        raise KeyError(artifact_id)
    art = json.loads(json.dumps(current["artifact"]))
    known = {f["id"]: f for s in art["sections"] for f in s["fields"]}
    unknown = [k for k in changes if k not in known]
    if unknown:
        raise ValueError(f"Unknown field(s): {', '.join(unknown)}")
    for k, v in changes.items():
        v = str(v).strip()
        known[k].update({"value": v or NEEDS_INPUT, "needs_input": not v, "source": "Refined" if reason else "Edited by you"})
    labels = ", ".join(known[k]["label"] for k in changes)
    return _add_version(artifact_id, {"inputs": current["inputs"], "extras": current["extras"], "artifact": art},
                        reason or f"Edited {labels}")


def restore(artifact_id: str, version: int) -> dict:
    old = get(artifact_id, version)
    if not old:
        raise KeyError(f"{artifact_id} v{version}")
    return _add_version(artifact_id, {"inputs": old["inputs"], "extras": old["extras"], "artifact": old["artifact"]},
                        f"Restored version {version}")


def versions(artifact_id: str) -> list[dict]:
    rows = _conn().execute("SELECT version, created_at, reason FROM versions WHERE artifact_id = ? ORDER BY version DESC",
                           (artifact_id,)).fetchall()
    return [dict(r) for r in rows]


def list_artifacts(brand: str | None = None) -> list[dict]:
    q = "SELECT a.*, (SELECT MAX(version) FROM versions v WHERE v.artifact_id = a.id) AS version FROM artifacts a"
    rows = _conn().execute(q + (" WHERE brand = ?" if brand else "") + " ORDER BY updated_at DESC",
                           (brand,) if brand else ()).fetchall()
    return [dict(r) for r in rows]
