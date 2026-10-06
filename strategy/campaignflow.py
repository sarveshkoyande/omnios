"""Engagement Planner 2: the CampaignFlow 30-minute planning framework as an agent
(config/frameworks/campaignflow.json).

Six steps, each reading the APPROVED output of the step before:
  1 Campaign objective card   2 Target audience segmentation   3 Channel planning
  4 Journey design            5 Omnichannel planning           6 Campaign brief
Every step is one model call grounded in Brand IQ (brand plan fields, kit, personas, compliance, client
data -- SYNTHETIC until real feeds exist -- and the person's documents and notes), the framework's own
rules for that step, and the approved earlier steps. A step's output is a draft until the person approves
it; a step can be redone with feedback. Gaps become questions, never inventions (rule R2: no model ->
LLMUnavailable, nothing written).

Plans are kept per id under DATA_DIR/campaignflow/<id>.json, with every save kept as a version.
Save publishes the plan into the brand hierarchy: an engagement plan, the campaign, and one journey (flow)
per named journey, so they appear in Campaigns & Journeys, Live simulation and the Flow Agent.
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

AGENT = "engagement-planner-2"
FRAMEWORK_FILE = Path(__file__).resolve().parent.parent / "config" / "frameworks" / "campaignflow.json"
STEP_IDS = ["objective", "audience", "channels", "journeys", "omnichannel", "brief"]


def framework() -> dict:
    return json.loads(FRAMEWORK_FILE.read_text(encoding="utf-8"))


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _path(pid: str) -> Path:
    return data_path("campaignflow", f"{pid}.json")


def get(pid: str) -> dict | None:
    p = _path(pid)
    if not p.exists():
        return None
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec.pop("history", None)
    return rec


def _raw(pid: str) -> dict:
    p = _path(pid)
    if not p.exists():
        raise KeyError(pid)
    return json.loads(p.read_text(encoding="utf-8"))


def _save(rec: dict, reason: str) -> dict:
    rec["version"] = int(rec.get("version") or 0) + 1
    rec["updated_at"] = _now()
    snap = {k: v for k, v in rec.items() if k != "history"}
    rec.setdefault("history", []).append({"version": rec["version"], "at": rec["updated_at"], "reason": reason,
                                          "steps": json.loads(json.dumps(snap.get("steps")))})
    rec["history"] = rec["history"][-40:]
    p = _path(rec["id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return {k: v for k, v in rec.items() if k != "history"}


def list_plans(brand: str | None = None) -> list[dict]:
    d = data_path("campaignflow")
    out = []
    if d.exists():
        for p in d.glob("*.json"):
            try:
                r = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if brand and (r.get("brand") or "").lower() != brand.lower():
                continue
            out.append({k: r.get(k) for k in ("id", "brand", "title", "version", "created_at", "updated_at")} |
                       {"approved": sum(1 for s in (r.get("steps") or {}).values() if s.get("status") == "approved")})
    return sorted(out, key=lambda x: x.get("updated_at") or "", reverse=True)


def create(brand: str, title: str | None = None) -> dict:
    key = brand_kit.canonical_key(brand)
    if not key:
        raise KeyError(brand)
    pid = uuid.uuid4().hex[:12]
    now = _now()
    rec = {"id": pid, "brand": key, "title": title or f"{key} campaign plan — {dt.date.today():%b %Y}",
           "created_at": now, "updated_at": now, "version": 0, "ack": None, "steps": {}, "published": None}
    return _save(rec, "Created")


# ------------------------------------------------------------------ grounding

def _kit_view(brand: str) -> dict:
    """The kit as the pages read it: the active brand plan's fields laid over the kit's own."""
    kit = dict(brand_kit.kit_for(brand) or {})
    plans = kit.get("plans") or []
    active = next((p for p in plans if p.get("id") == kit.get("active_plan")), plans[0] if plans else None)
    if active:
        kit = {**kit, **active}
    return kit


def _grounding(rec: dict) -> dict:
    import agent_intake
    brand = rec["brand"]
    kit = _kit_view(brand)
    pick = lambda d, ks: {k: d.get(k) for k in ks if d.get(k) not in (None, "", [], {})}  # noqa: E731
    g = {"brand": brand, "today": dt.date.today().isoformat(),
         "brand_kit": pick(kit, ("generic", "company", "therapy_area", "indication", "lifecycle_stage", "positioning_statement",
                                 "core_claim", "key_objective", "key_objectives", "unmet_need", "primary_audience",
                                 "brand_situation", "strategic_imperatives", "kpis", "activities", "audience_segments",
                                 "message_hierarchy", "messages_by_persona", "guardrails", "voice_do", "voice_dont",
                                 "care_continuum", "calendar", "proof_points")),
         "indications": [pick(i, ("name", "condition", "population", "line", "criteria")) for i in kit.get("indications") or []],
         "hcp_personas": [pick(p, ("name", "specialties", "who", "behaviours", "barrier", "moment", "key_message", "tone"))
                          for p in ((kit.get("personas") or {}).get("hcp") or [])][:6],
         "competitors": [pick(c, ("name", "type", "threat", "counter")) for c in kit.get("competitors") or []][:8],
         "us_approval": ((kit.get("product_profile") or {}).get("us_approval") or {}).get("value")}
    try:
        import compliance
        cp = compliance.for_brand(brand) or {}
        g["compliance"] = {"approval_workflow": cp.get("approval_workflow"), "channel_rules": cp.get("channel_rules"),
                           "suppressions": cp.get("suppressions")}
    except Exception:  # noqa: BLE001
        pass
    try:
        import client_data
        cd = client_data.summary(brand)
        g["client_data"] = {"SYNTHETIC": bool(cd.get("synthetic")), **{k: cd.get(k) for k in (
            "hcps_by_segment", "channel_reach_pct", "field_force", "lowest_access_states", "top_states_by_high_decile_hcps")}}
    except Exception:  # noqa: BLE001
        pass
    intake = agent_intake.load(AGENT, rec["id"])
    if (intake.get("text") or "").strip():
        g["your_documents"] = {"files": [f["name"] for f in intake.get("files") or []], "text": intake["text"][:30000]}
    if (intake.get("notes") or "").strip():
        g["your_notes"] = intake["notes"]
    return g


# ------------------------------------------------------------------ acknowledgement

def acknowledge(pid: str) -> dict:
    import agent_intake
    rec = _raw(pid)
    g = _grounding(rec)
    fw = framework()
    context = {"brand": rec["brand"], "brand_iq_present": {k: bool(v) for k, v in g["brand_kit"].items()},
               "has_indications": bool(g.get("indications")), "has_hcp_personas": bool(g.get("hcp_personas")),
               "has_compliance_profile": bool(g.get("compliance")), "client_data_synthetic": (g.get("client_data") or {}).get("SYNTHETIC"),
               "framework_from_brand_plan": fw["from_brand_plan"], "framework_not_from_brand_plan": fw["not_from_brand_plan"]}
    rec["ack"] = agent_intake.acknowledge(
        "You are Engagement Planner 2, running the CampaignFlow six-step framework (objective card -> audience "
        "segmentation -> channel plan -> journey design -> omnichannel rules -> campaign brief) for one US pharma "
        "campaign.", context, agent_intake.load(AGENT, pid),
        "Name which brand-plan inputs the framework needs are present (audience and roles, objective, strategic "
        "imperatives, KPIs, guardrails, therapy area) and which are missing (they will become questions on the "
        "objective card). Say plainly that dates, segment sizes, consent coverage, content approval status, "
        "cadence and channel budget never come from a brand plan, and that client data here is synthetic. Say "
        "whether this looks like an existing brand (Rx lifecycle) or a launch brand (IQVIA eligibility).")
    return _save(rec, "Acknowledged the input")


# ------------------------------------------------------------------ the six steps

_SHAPES = {
    "objective": {
        "campaign_name": "", "brand_mode": "existing|launch", "mode_reason": "",
        "card": {k: {"value": "", "source": "brand plan section / your notes / 'question raised'"} for k in (
            "campaign_objective", "target_audience", "current_behaviour", "desired_behaviour",
            "strategic_imperative", "messaging_guardrails", "channel_priorities")},
        "audience_roles": {"primary_prescribers": [""], "adjacent_pathway": [""]},
        "kpis": [{"kpi": "", "target": "", "source": ""}],
        "timing": {"earliest_start": "", "why": ""},
        "questions": [{"question": "", "why": "", "owner": ""}], "reasoning": [""]},
    "audience": {
        "mode": "existing|launch",
        "universe": {"primary": {"specialties": [""], "inclusion": ""}, "adjacent": {"roles": [""], "inclusion": ""}},
        "gates": [{"gate": "", "rule": ""}],
        "segments": [{"segment": "Awareness|Trialist|Adopter|Advocate|Stopper or Primary|Secondary|Tertiary",
                      "definition": "", "strategic_priority": "Activate|Grow|Retain|Support|Reactivate|Enable (existing only)",
                      "est_hcps": "number or null (null when no count can be grounded)", "count_source": "where the count comes from, or why it is missing", "brand_opportunity": "High|Medium|Low", "hcp_reachability": "High|Medium|Low",
                      "investment_priority": "High|Standard|Low", "desired_progression": ""}],
        "adjacent_segments": [{"role": "", "strategic_priority": "Enable", "est_hcps": 0, "pathway_kpi": ""}],
        "focus": "which segments get greater campaign focus and why",
        "gaps": [{"gap": "", "owner": ""}], "reasoning": [""]},
    "channels": {
        "engagement_needs": [{"progression": "", "need": ""}],
        "candidates": [{"channel": "", "message_fit": "", "hcp_engagement": "", "consent_access": "", "feasibility": "",
                        "result": "live|removed", "reason": ""}],
        "mix": [{"segment": "", "progression": "", "investment_priority": "", "digital_affinity": "High|Medium|Low",
                 "channels": [{"channel": "", "job": "", "modules": [""]}]}],
        "constraints": [{"type": "frequency|coordination|suppression", "rule": ""}],
        "gap_register": [{"gap": "", "blocks": "", "owner": ""}], "reasoning": [""]},
    "journeys": {
        "journeys": [{"id": "J1", "name": "", "type": "Welcome|Nurture|Story Follow-up|Awareness|Other", "segments": [""],
                      "entry": "", "objective": "", "cadence": "",
                      "steps": [{"id": "T1", "play": "Initiate|Reinforce|Escalate", "tactic": "", "channel": "", "module": "",
                                 "cta": "", "wait": "e.g. 7 days (CONFIGURABLE)", "signal": "",
                                 "on_signal": "next step id or action", "on_no_signal": "wait / retry / alternate (never exit)"}],
                      "exit": [""], "opt_out": "", "next_journey": "", "build_order": 1}],
        "branch_catalog": [{"branch": "", "trigger": "", "action": ""}],
        "movability": [{"segment": "", "score": "High|Medium|Low", "effect": ""}],
        "measures": [{"measure": "", "why": ""}],
        "gap_register": [{"gap": "", "blocks": "", "owner": ""}], "reasoning": [""]},
    "omnichannel": {
        "signals": [{"signal": "", "meaning": "meaningful|weak|noise|non-response|access need|progression", "evidence_window": ""}],
        "rules": [{"id": "OC-001", "journey": "J1", "type": "entry|sequence|branch|wait|reclassification|suppression|collision|exit|safe",
                   "if": "", "then": "", "else": "", "hard_gate": False}],
        "channel_sequence": [{"journey": "J1", "starts": "", "follows_signal": "", "covers_no_response": ""}],
        "safe_outcomes": [{"when": "", "outcome": "WAIT|NO_ACTION|suppress|human review"}],
        "approvals": [{"who": "", "approves": ""}],
        "upstream_gaps": [{"gap": "", "returns_to_step": 0}], "reasoning": [""]},
    "brief": {
        "sections": [{"n": 1, "title": "", "content": "", "owner": ""}],
        "build_mapping": [{"journey": "J1", "entry": "", "initial_tactic": "", "rule_ids": [""], "content": "", "channel": "",
                           "exit": "", "next_journey": "", "safe_outcome": ""}],
        "qa": [{"scenario": "", "expected": "", "rule_ids": [""]}],
        "definition_of_done": [{"item": "", "status": "met|open", "why": ""}],
        "open_items": [{"item": "", "owner": ""}], "reasoning": [""]},
}

_ROLE = ("You are Engagement Planner 2, a senior US pharma omnichannel planner running the CampaignFlow 30-minute "
         "planning framework. It plans HCP engagement (prescribers and adjacent pathway roles), not patient "
         "programmes. Follow the framework step and its rules exactly. Use ONLY the grounding (Brand IQ, "
         "the person's documents and notes) and the APPROVED earlier steps; cite sources. If the brand plan and public data disagree, use the brand plan and say so; AI drafts in Brand IQ rank last. Never invent figures, "
         "dates, thresholds, consent coverage or content approval status: when something is missing, put it in the "
         "questions or gap register with an owner. Client data marked SYNTHETIC may be used for illustrative counts, "
         "and you must say so where it is used. Use the brand's own words. Reply with ONE JSON object matching the "
         "shape, including a `reasoning` array of 3-6 short sentences on what you used and why.")


def run_step(pid: str, step: str, feedback: str | None = None) -> dict:
    if step not in STEP_IDS:
        raise ValueError(f"unknown step '{step}'")
    rec = _raw(pid)
    n = STEP_IDS.index(step)
    for prev in STEP_IDS[:n]:
        if (rec["steps"].get(prev) or {}).get("status") != "approved":
            raise ValueError(f"Approve step {STEP_IDS.index(prev) + 1} before running step {n + 1}.")
    fw = framework()
    spec = fw["steps"][n]
    approved = {s: rec["steps"][s]["output"] for s in STEP_IDS[:n]}
    current = (rec["steps"].get(step) or {}).get("output")
    payload = {"framework_principle": fw["principle"], "this_step": spec, "vocabulary": fw["vocabulary"],
               "approved_earlier_steps": approved, "grounding": _grounding(rec), "shape": _SHAPES[step]}
    if feedback:
        payload["change_request"] = {"previous_draft": current, "feedback": feedback}
    out = complete_json(_ROLE + (" Revise the previous draft to address the change request; keep what it doesn't touch."
                                 if feedback else ""), payload, max_tokens=9000)
    reasoning = out.pop("reasoning", None) or []
    if isinstance(reasoning, str):
        reasoning = [reasoning]
    rec["steps"][step] = {"status": "draft", "output": out, "reasoning": reasoning, "feedback": feedback,
                          "run_at": _now()}
    # a redone step invalidates the approvals after it
    for later in STEP_IDS[n + 1:]:
        if later in rec["steps"]:
            rec["steps"][later]["status"] = "stale"
    return _save(rec, f"Step {n + 1} {'revised' if feedback else 'drafted'}: {spec['name']}")


def approve(pid: str, step: str) -> dict:
    rec = _raw(pid)
    s = rec["steps"].get(step)
    if not s or not s.get("output"):
        raise ValueError("run this step first")
    s["status"] = "approved"
    s["approved_at"] = _now()
    return _save(rec, f"Step {STEP_IDS.index(step) + 1} approved")


# ------------------------------------------------------------------ save to Campaigns & Journeys

def publish(pid: str) -> dict:
    import hierarchy
    rec = _raw(pid)
    if (rec["steps"].get("journeys") or {}).get("status") != "approved":
        raise ValueError("Approve the journey design (step 4) before saving.")
    card = rec["steps"]["objective"]["output"]
    journeys = rec["steps"]["journeys"]["output"].get("journeys") or []
    link = dict(rec.get("published") or {})
    try:
        if not link.get("plan_id"):
            raise hierarchy.NotFound("new")
        hierarchy.update_plan(link["plan_id"], name=rec["title"])
    except hierarchy.NotFound:
        link["plan_id"] = hierarchy.create_plan(rec["brand"], rec["title"])["id"]
    name = card.get("campaign_name") or rec["title"]
    try:
        if not link.get("campaign_id"):
            raise hierarchy.NotFound("new")
        hierarchy.rename_campaign(link["campaign_id"], name)
    except hierarchy.NotFound:
        link["campaign_id"] = hierarchy.create_campaign(link["plan_id"], name)["id"]
    flows = dict(link.get("flows") or {})
    existing = {f["id"] for f in hierarchy.list_flows(link["campaign_id"])}
    for j in journeys:
        jid = str(j.get("id"))
        if flows.get(jid) in existing:
            continue
        f = hierarchy.create_flow(link["campaign_id"], f"{j.get('name') or jid} ({j.get('type') or 'Journey'})", "manual")
        flows[jid] = f["id"]
    link.update({"flows": flows, "at": _now()})
    rec["published"] = link
    return _save(rec, f"Saved to Campaigns & Journeys ({len(flows)} journey(s))")


__all__ = ["framework", "create", "get", "list_plans", "acknowledge", "run_step", "approve", "publish",
           "STEP_IDS", "AGENT", "LLMUnavailable"]
