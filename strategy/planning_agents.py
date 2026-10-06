"""Engagement Planning, Segmentation and Channel agents: one engine, three agents, steps that call each other.

The Brand Kit (Brand IQ) is the brand context; these agents choose, prioritise and sequence from it and never
rebuild it (docs/redesign/brand-kit-reorg.md, "Engagement Planning"). Each agent is a list of steps:

  engagement-planner-2 (Engagement Planning Agent)  objectives -> focus -> approach -> portfolio
  brand-persona-builder (Segmentation Planner Agent)         focus
  channel-planner (Channel Mix Agent)                    approach

`focus` IS the Segmentation Planner Agent and `approach` IS the Channel Mix Agent: the Engagement Planning Agent calls the
same step functions the standalone agents run, so a segment or channel decision is made in one place. The
latest result of each (from either entry point) is kept per brand, so a standalone run starts from the
engagement plan's objectives and the Channel Mix Agent from the latest segments.

Every agent has a chat box (`chat`): free text is read by the model only (rule R1) and routed to answer,
redo a step with guidance, jump ahead, or switch auto-run on/off. Guidance is kept on the record and passed
to every later step, including the called agents. Stages use the Brand Kit ladder (channel_playbook.json):
aware -> interested -> trial -> adopt -> advocate. No model -> LLMUnavailable, nothing written (R2).

Records: DATA_DIR/planning_agents/<agent>/<id>.json (with history); latest per brand:
DATA_DIR/planning_agents/latest/<brand>.json.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import brand_kit  # noqa: E402
from llm_json import LLMUnavailable, complete_json  # noqa: E402
from paths import data_path  # noqa: E402

STEPS = {
    "objectives": {"name": "Objectives", "full": "Objectives for the period"},
    "focus": {"name": "Where to focus", "full": "Where to focus (Segmentation Planner Agent)", "agent": "brand-persona-builder"},
    "approach": {"name": "Message & channels", "full": "Message & channel approach (Channel Mix Agent)", "agent": "channel-planner"},
    "portfolio": {"name": "Campaign portfolio", "full": "Campaign portfolio"},
}
AGENTS = {
    "engagement-planner-2": {"name": "Engagement Planning Agent", "steps": ["objectives", "focus", "approach", "portfolio"]},
    "brand-persona-builder": {"name": "Segmentation Planner Agent", "steps": ["focus"]},
    "channel-planner": {"name": "Channel Mix Agent", "steps": ["approach"]},
}
STAGES = ["aware", "interested", "trial", "adopt", "advocate"]


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _check_agent(agent: str) -> dict:
    if agent not in AGENTS:
        raise ValueError(f"unknown agent '{agent}'")
    return AGENTS[agent]


# ------------------------------------------------------------------ store

def _path(agent: str, pid: str) -> Path:
    return data_path("planning_agents", agent, f"{pid}.json")


def _raw(agent: str, pid: str) -> dict:
    p = _path(agent, pid)
    if not p.exists():
        raise KeyError(pid)
    return json.loads(p.read_text(encoding="utf-8"))


def _public(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if k != "history"}


def _save(rec: dict, reason: str) -> dict:
    rec["version"] = int(rec.get("version") or 0) + 1
    rec["updated_at"] = _now()
    rec.setdefault("history", []).append({"version": rec["version"], "at": rec["updated_at"], "reason": reason,
                                          "steps": json.loads(json.dumps(rec.get("steps")))})
    rec["history"] = rec["history"][-40:]
    p = _path(rec["agent"], rec["id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return _public(rec)


def get(agent: str, pid: str) -> dict:
    _check_agent(agent)
    return _public(_raw(agent, pid))


def list_records(agent: str, brand: str | None = None) -> list[dict]:
    _check_agent(agent)
    d = data_path("planning_agents", agent)
    out = []
    if d.exists():
        for p in d.glob("*.json"):
            try:
                r = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if brand and (r.get("brand") or "").lower() != brand.lower():
                continue
            out.append({k: r.get(k) for k in ("id", "brand", "title", "version", "updated_at")} |
                       {"approved": sum(1 for s in (r.get("steps") or {}).values() if s.get("status") == "approved"),
                        "of": len(AGENTS[agent]["steps"])})
    return sorted(out, key=lambda x: x.get("updated_at") or "", reverse=True)


def create(agent: str, brand: str, months: int = 6, title: str | None = None) -> dict:
    spec = _check_agent(agent)
    key = brand_kit.canonical_key(brand)
    if not key:
        raise KeyError(brand)
    today = dt.date.today()
    start = today.replace(day=1)
    end_m = start.month - 1 + max(1, int(months))
    end = dt.date(start.year + end_m // 12, end_m % 12 + 1, 1) - dt.timedelta(days=1)
    pid = uuid.uuid4().hex[:12]
    rec = {"id": pid, "agent": agent, "brand": key, "version": 0, "created_at": _now(),
           "title": title or (f"{key} engagement plan — {start:%b %Y} to {end:%b %Y}" if agent == "engagement-planner-2"
                              else f"{key} · {spec['name']} — {today:%d %b %Y}"),
           "period": {"start": start.isoformat(), "end": end.isoformat(), "months": int(months)},
           "ack": None, "steps": {}, "guidance": [], "chat": [], "auto": False, "published": None}
    return _save(rec, "Created")


# ------------------------------------------------------------------ latest per brand (the agents' shared memory)

def _latest_path(brand: str) -> Path:
    return data_path("planning_agents", "latest", f"{brand}.json")


def latest(brand: str) -> dict:
    p = _latest_path(brand)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _remember(brand: str, kind: str, output: dict, rec: dict) -> None:
    cur = latest(brand)
    cur[kind] = {"output": output, "from": {"agent": rec["agent"], "id": rec["id"], "title": rec["title"]}, "at": _now()}
    p = _latest_path(brand)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cur, ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------------------------ grounding: the Brand Kit, reused as is

def _kit_view(brand: str) -> dict:
    kit = dict(brand_kit.kit_for(brand) or {})
    plans = kit.get("plans") or []
    active = next((p for p in plans if p.get("id") == kit.get("active_plan")), plans[0] if plans else None)
    return {**kit, **(active or {})}


def _short(v, n: int = 260):
    if isinstance(v, str):
        return v[:n]
    if isinstance(v, list):
        return [_short(x, n) for x in v[:14]]
    if isinstance(v, dict):
        return {k: _short(x, n) for k, x in v.items() if k not in ("history", "errors", "states", "status")}
    return v


def _grounding(rec: dict) -> dict:
    """The Brand Kit sections these agents reuse, labelled by the tab they come from."""
    import agent_intake
    brand = rec["brand"]
    k = _kit_view(brand)
    pick = lambda d, ks: {x: d.get(x) for x in ks if d.get(x) not in (None, "", [], {})}  # noqa: E731
    personas = k.get("personas") or {}
    ch = k.get("channels") or {}
    g = {
        "brand": brand, "today": dt.date.today().isoformat(), "period": rec.get("period"),
        "brand_iq": _short(pick(k, ("generic", "company", "therapy_area", "indication", "lifecycle_stage", "positioning_statement",
                                    "core_claim", "tagline", "key_objective", "key_objectives", "unmet_need", "primary_audience",
                                    "strategic_imperatives", "kpis", "forecast", "growth_opportunities"))),
        "market": _short({"brand_situation": k.get("brand_situation"),
                          "patient_flow": [{"stages": [pick(s, ("stage", "value", "unit", "what")) for s in f.get("stages") or []]}
                                           for f in k.get("patient_flow") or []],
                          "competitors": [pick(c, ("name", "threat", "counter")) for c in k.get("competitors") or []][:8],
                          "market_access": k.get("market_access"), "proof_points": k.get("proof_points")}),
        "audiences": _short({"segments": k.get("audience_segments"),
                             "personas": {a: [pick(p, ("name", "specialties", "who", "tier", "behaviours", "barrier", "moment", "key_message"))
                                              for p in personas.get(a) or []] for a in ("hcp", "patient", "caregiver")},
                             "ladder_now": ch.get("ladder_focus")}),
        "message": _short({"messages": k.get("message_hierarchy"), "by_persona": k.get("messages_by_persona"),
                           "claim_check": [pick(c, ("where", "claim", "verdict", "why")) for c in (k.get("compliance_check") or {}).get("claim_checks") or []
                                           if c.get("verdict") in ("caution", "risk")]}),
        "channels": _short({"brand_mix": ch.get("mix"), "brand_cards": [pick(c, ("framework_id", "channel", "role", "audiences")) for c in ch.get("cards") or []],
                            "stage": ch.get("stage"), "moments": ch.get("moments"), "plan_activities": k.get("activities")}),
    }
    try:
        import kit_proposer
        pb = kit_proposer.channel_playbook()
        g["ladder"] = [{x: r[x] for x in ("id", "name", "goal", "hcp", "patient", "success")} for r in pb["ladder"]]
        g["channel_playbook"] = [{x: c[x] for x in ("id", "name", "audience", "lifecycle", "use_when")} for c in pb["channels"]]
    except Exception:  # noqa: BLE001
        g["ladder"] = STAGES
    try:
        import client_data
        cd = client_data.summary(brand)
        g["client_data"] = {"SYNTHETIC": bool(cd.get("synthetic")),
                            **{x: cd.get(x) for x in ("hcps_by_segment", "channel_reach_pct", "field_force")}}
    except Exception:  # noqa: BLE001
        pass
    try:
        import compliance
        cp = compliance.for_brand(brand) or {}
        g["compliance_channel_rules"] = _short(cp.get("channel_rules"))
    except Exception:  # noqa: BLE001
        pass
    intake = agent_intake.load(rec["agent"], rec["id"])
    if (intake.get("text") or "").strip():
        g["your_documents"] = {"files": [f["name"] for f in intake.get("files") or []], "text": intake["text"][:20000]}
    if (intake.get("notes") or "").strip():
        g["your_notes"] = intake["notes"]
    return g


# ------------------------------------------------------------------ the steps

_ROLE = ("You are a senior US pharma brand and omnichannel strategist. The Brand Kit (Brand IQ) is the brand's context: "
         "REUSE it as given -- personas, ladder stages, messages, channel roles -- and never re-segment the audience "
         "or invent a new message. Your job is to choose, prioritise and sequence. Where the brand plan and other sources "
         "disagree, the brand plan wins and you say so. Never invent figures or dates; anything missing goes in "
         "`questions`. Client data marked SYNTHETIC may be used for illustrative sizing and you must say so. If you "
         "disagree with the Brand Kit (e.g. a persona looks to be on a different ladder stage), keep the kit's value and "
         "add a `kit_notes` entry. Ladder stages are exactly: aware, interested, trial, adopt, advocate. Follow the "
         "person's guidance. Short plain sentences. Reply with ONE JSON object matching the shape, with a `reasoning` "
         "array of 3-6 short sentences on what you used and why.")

_SHAPES = {
    "objectives": {
        "objectives": [{"id": "O1", "objective": "", "imperative": "the strategic imperative it serves", "measure": "",
                        "baseline": "", "target": "", "by": "YYYY-MM", "gap": "the unmet need / patient-flow leak it closes",
                        "source": "Brand Kit section or brand plan"}],
        "questions": [{"question": "", "why": ""}], "kit_notes": [{"what": "", "note": ""}], "reasoning": [""]},
    "focus": {
        "segments": [{"id": "S1", "persona": "a Brand Kit persona or segment name, exactly", "audience": "HCP|Patient|Caregiver",
                      "from_stage": "aware|interested|trial|adopt|advocate", "to_stage": "aware|interested|trial|adopt|advocate",
                      "priority": "High|Standard|Low", "objective_ids": ["O1"], "why": "", "barrier": "", "moment": "",
                      "size": "number or null", "size_source": "client data (SYNTHETIC) / brand plan / null"}],
        "deprioritised": [{"persona": "", "why": ""}],
        "questions": [{"question": "", "why": ""}], "kit_notes": [{"what": "", "note": ""}], "reasoning": [""]},
    "approach": {
        "by_segment": [{"segment_id": "S1", "persona": "", "move": "trial -> adopt",
                        "lead_message": {"pillar": "a Brand Kit message pillar, exactly", "message": "", "source": ""},
                        "channels": [{"channel": "", "framework_id": "channel playbook id or ''", "job": "",
                                      "weight": "lead|support", "why": ""}],
                        "avoid": [{"what": "", "why": "e.g. claim flagged in the claim check"}]}],
        "mix": [{"channel": "", "framework_id": "", "weight": "lead|support|light", "segment_ids": ["S1"]}],
        "rules": [{"rule": "", "why": ""}],
        "questions": [{"question": "", "why": ""}], "kit_notes": [{"what": "", "note": ""}], "reasoning": [""]},
    "portfolio": {
        "campaigns": [{"id": "C1", "name": "", "objective_ids": ["O1"], "segment_ids": ["S1"], "move": "",
                       "message": "", "lead_channels": [""], "start": "YYYY-MM", "end": "YYYY-MM",
                       "moment": "a Brand Kit key moment it rides, or ''", "kpi": "", "why": ""}],
        "sequencing": [""], "questions": [{"question": "", "why": ""}], "kit_notes": [{"what": "", "note": ""}], "reasoning": [""]},
}

_TASKS = {
    "objectives": "Set the plan's objectives for the period: 2-4 objectives, each tied to a strategic imperative, a "
                  "measure with baseline -> target (from the brand plan's KPIs where they exist), a date inside the "
                  "period, and the unmet need or patient-flow leak it closes.",
    "focus": "You are the Segmentation Planner Agent. Using the Brand Kit's personas and segments AS GIVEN, decide who gets "
             "focus in this period: 3-6 segments, each with the ladder move this period must achieve (from_stage -> "
             "to_stage, using the kit's current stage where known), priority, the objective(s) it serves, the barrier "
             "and the moment that matters (from the persona card). Say who is deprioritised and why.",
    "approach": "You are the Channel Mix Agent. For each focus segment, pick the lead message pillar from the Brand Kit's "
                "message matrix / messages by persona, and 2-4 channels with their job for that ladder move, using the "
                "channel playbook's ladder jobs, the brand's channel mix and lifecycle stage, reach (client data) and "
                "compliance channel rules. Name claims to avoid from the claim check. Then the overall mix and 3-5 "
                "orchestration rules.",
    "portfolio": "Turn the approach into the campaigns that deliver the plan within the period: 3-6 campaigns, each with "
                 "objective(s), segment(s), ladder move, message, lead channels, start and end month inside the period "
                 "(riding the Brand Kit's key moments where they fit), and a KPI. Then the sequencing logic.",
}


def _inputs_for(rec: dict, step: str) -> dict:
    """Earlier steps of this record, else the brand's latest from the other agents (standalone runs)."""
    steps = rec.get("steps") or {}
    have = {s: (steps.get(s) or {}).get("output") for s in ("objectives", "focus", "approach") if (steps.get(s) or {}).get("output")}
    lat = latest(rec["brand"])
    if step in ("focus", "approach", "portfolio") and "objectives" not in have and lat.get("objectives"):
        have["objectives"] = lat["objectives"]["output"]
    if step in ("approach", "portfolio") and "focus" not in have:
        if not lat.get("focus"):
            raise ValueError("No focus segments yet: run the Segmentation Planner Agent (or the Engagement Planning Agent) first.")
        have["focus"] = lat["focus"]["output"]
    if step == "portfolio" and "approach" not in have and lat.get("approach"):
        have["approach"] = lat["approach"]["output"]
    order = list(STEPS)
    return {s: v for s, v in have.items() if order.index(s) < order.index(step)}


def run_step(agent: str, pid: str, step: str, feedback: str | None = None, force: bool = False) -> dict:
    spec = _check_agent(agent)
    if step not in spec["steps"]:
        raise ValueError(f"'{step}' is not a step of the {spec['name']}")
    rec = _raw(agent, pid)
    seq = spec["steps"]
    n = seq.index(step)
    if not force and not rec.get("auto"):
        for prev in seq[:n]:
            if (rec["steps"].get(prev) or {}).get("status") != "approved":
                raise ValueError(f"Approve “{STEPS[prev]['name']}” first, or tell the agent in the chat to skip ahead.")
    current = (rec["steps"].get(step) or {}).get("output")
    payload = {"task": _TASKS[step], "shape": _SHAPES[step], "earlier_steps": _inputs_for(rec, step),
               "grounding": _grounding(rec),
               "guidance_from_the_person": [g["text"] for g in rec.get("guidance") or [] if g.get("step") in (None, step)]}
    if feedback:
        payload["change_request"] = {"previous_draft": current, "feedback": feedback}
    out = complete_json(_ROLE + (" Revise the previous draft to address the change request; keep what it doesn't touch."
                                 if feedback else ""), payload, max_tokens=7000)
    reasoning = out.pop("reasoning", None) or []
    if isinstance(reasoning, str):
        reasoning = [reasoning]
    rec["steps"][step] = {"status": "approved" if rec.get("auto") else "draft", "output": out, "reasoning": reasoning,
                          "feedback": feedback, "run_at": _now(), "by": STEPS[step].get("agent") or agent}
    for later in seq[n + 1:]:
        if later in rec["steps"]:
            rec["steps"][later]["status"] = "stale"
    _remember(rec["brand"], step, out, rec)
    return _save(rec, f"{STEPS[step]['name']} {'revised' if feedback else 'drafted'}")


def approve(agent: str, pid: str, step: str) -> dict:
    rec = _raw(agent, pid)
    s = rec["steps"].get(step)
    if not s or not s.get("output"):
        raise ValueError("Run this step first.")
    s["status"] = "approved"
    s["approved_at"] = _now()
    return _save(rec, f"{STEPS[step]['name']} approved")


# ------------------------------------------------------------------ acknowledgement

def acknowledge(agent: str, pid: str) -> dict:
    import agent_intake
    spec = _check_agent(agent)
    rec = _raw(agent, pid)
    g = _grounding(rec)
    lat = latest(rec["brand"])
    context = {"brand": rec["brand"], "period": rec["period"], "steps": [STEPS[s]["full"] for s in spec["steps"]],
               "brand_kit_has": {"strategic_imperatives": bool(g["brand_iq"].get("strategic_imperatives")),
                                 "kpis": bool(g["brand_iq"].get("kpis")),
                                 "personas": any(g["audiences"]["personas"].values()),
                                 "ladder_stages": bool(g["audiences"].get("ladder_now")),
                                 "message_matrix": bool(g["message"].get("messages")),
                                 "channel_mix": bool(g["channels"].get("brand_mix")),
                                 "key_moments": bool(g["channels"].get("moments")),
                                 "claim_check": bool(g["message"].get("claim_check"))},
               "latest_from_other_agents": {k: v.get("from") for k, v in lat.items()},
               "client_data_synthetic": (g.get("client_data") or {}).get("SYNTHETIC")}
    rec["ack"] = agent_intake.acknowledge(
        f"You are the {spec['name']} for a US pharma brand. You reuse the Brand Kit (personas, ladder stages, messages, "
        "channel roles) and decide priorities; you never rebuild it.", context, agent_intake.load(agent, pid),
        "Say which Brand Kit sections you will reuse and which are missing (name the Brand Kit tab where they can be "
        "drafted). If a Segmentation or Channel result already exists from another agent, say you'll start from it. "
        "Say client data is synthetic.")
    return _save(rec, "Acknowledged the input")


# ------------------------------------------------------------------ chat: steer the agent in your own words

def chat(agent: str, pid: str, message: str) -> dict:
    """Read the person's message (model only) and decide what to do. Returns {record, reply, action}; the client
    then runs any step the action names, so progress shows step by step."""
    spec = _check_agent(agent)
    rec = _raw(agent, pid)
    seq = spec["steps"]
    state = {s: {"name": STEPS[s]["name"], "status": (rec["steps"].get(s) or {}).get("status") or "not run",
                 "summary": _short((rec["steps"].get(s) or {}).get("output"), 160),
                 "reasoning": (rec["steps"].get(s) or {}).get("reasoning")} for s in seq}
    out = complete_json(
        f"You are the {spec['name']}'s conversation layer. The person typed a message while the agent runs its steps "
        f"({', '.join(seq)}). Decide what they want: 'answer' (a question about the work: answer it from the steps' "
        "content and reasoning, change nothing), 'redo' (change a step: set `step` to the step it affects and "
        "`guidance` to their instruction, rewritten as a clear instruction), 'jump' (run a later step without "
        "approving the ones before: set `step`), 'auto_on' (run everything without stopping for approval), 'auto_off' "
        "(go back to approving each step), 'note' (general guidance for all later steps: set `guidance`). If a redo "
        "touches an earlier step, say in the reply which later steps will need refreshing. Reply in one or two short "
        "sentences. Reply with one JSON object.\n"
        'Shape: {"intent":"answer|redo|jump|auto_on|auto_off|note","step":"' + "|".join(seq) + '|null","guidance":"","reply":""}',
        {"message": message, "steps": state, "auto": rec.get("auto"), "recent_chat": (rec.get("chat") or [])[-8:]},
        max_tokens=1200)
    intent = out.get("intent") or "answer"
    step = out.get("step") if out.get("step") in seq else None
    guidance = (out.get("guidance") or "").strip()
    reply = out.get("reply") or ""
    action = None
    if intent in ("redo", "note") and guidance:
        rec.setdefault("guidance", []).append({"text": guidance, "step": step if intent == "redo" else None, "at": _now()})
    if intent == "redo" and step:
        action = {"type": "run", "step": step, "feedback": guidance or message}
    elif intent == "jump" and step:
        action = {"type": "run", "step": step, "force": True}
    elif intent == "auto_on":
        rec["auto"] = True
        for s in seq:
            if (rec["steps"].get(s) or {}).get("status") == "draft":
                rec["steps"][s]["status"] = "approved"
        action = {"type": "run_all"}
    elif intent == "auto_off":
        rec["auto"] = False
    rec.setdefault("chat", []).extend([{"role": "you", "text": message, "at": _now()},
                                       {"role": "agent", "text": reply, "intent": intent, "step": step, "at": _now()}])
    rec["chat"] = rec["chat"][-60:]
    return {"record": _save(rec, f"Chat: {intent}"), "reply": reply, "action": action}


# ------------------------------------------------------------------ save to Campaigns & Journeys

def publish(agent: str, pid: str) -> dict:
    import hierarchy
    from engagement_agent import _month_bounds
    if agent != "engagement-planner-2":
        raise ValueError("Only an engagement plan is saved to Campaigns & Journeys.")
    rec = _raw(agent, pid)
    port = rec["steps"].get("portfolio") or {}
    if port.get("status") != "approved":
        raise ValueError("Approve the campaign portfolio before saving.")
    per = rec["period"]
    link = dict(rec.get("published") or {})
    try:
        if not link.get("plan_id"):
            raise hierarchy.NotFound("new")
        hierarchy.update_plan(link["plan_id"], name=rec["title"], period_start=per["start"], period_end=per["end"])
    except hierarchy.NotFound:
        link["plan_id"] = hierarchy.create_plan(rec["brand"], rec["title"], per["start"], per["end"])["id"]
    camps = dict(link.get("campaigns") or {})
    for c in port["output"].get("campaigns") or []:
        cid = camps.get(str(c.get("id")))
        name = c.get("name") or "Untitled campaign"
        start, end = _month_bounds(c.get("start"), False), _month_bounds(c.get("end"), True)
        try:
            if not cid:
                raise hierarchy.NotFound("new")
            hierarchy.rename_campaign(cid, name)
            hierarchy.schedule_campaign(cid, start, end)
        except hierarchy.NotFound:
            camps[str(c.get("id"))] = hierarchy.create_campaign(link["plan_id"], name, start, end)["id"]
    link.update({"campaigns": camps, "at": _now()})
    rec["published"] = link
    return _save(rec, f"Saved to Campaigns & Journeys ({len(camps)} campaign(s))")


__all__ = ["AGENTS", "STEPS", "STAGES", "create", "get", "list_records", "latest", "acknowledge", "run_step", "approve",
           "chat", "publish", "LLMUnavailable"]
