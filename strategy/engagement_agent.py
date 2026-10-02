"""The Engagement Planner agent, v2 (docs/redesign/engagement-plan-v2.md section 2).

    1 Frame       engagement_plans.create()
    2 Read        read()        Brand IQ only, structured reads, every item gets a citable id
    3 Classify    classify()    lifecycle x archetype x access (from Brand IQ, else proposed)
    4 Diagnose    diagnose()    the patient-flow bucket: stages, conversions, top leaks, gaps,
                                and questions that come FROM the diagnosis (<= 3)
    5 Options     options()     root causes of the top leaks + 2-3 strategic options with trade-offs
    6 Decide      choose()      the user picks (or mixes) options
    7 Draft       draft()       objectives tied to the leaks, shift map on the adoption ladder,
                                portfolio, timeline, relative budget, KPI tree, risks
    8 Check       check()       feasibility (deterministic) + red team (model)

Nothing here is brand-specific: everything comes from Brand IQ and the archetype framework.
Rules R1/R2: free text is read only by the model; no model -> LLMUnavailable (the API returns a
plain 503) and nothing is guessed. Each step is saved as a plan version.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import brand_kit  # noqa: E402
import compliance  # noqa: E402
import engagement_plans as ep  # noqa: E402
from llm_json import LLMUnavailable, complete_json  # noqa: E402

MAX_QUESTIONS = 3


def _item(gid: str, page: str, label: str, value) -> dict:
    return {"id": gid, "page": page, "label": label, "value": value}


def _pick(d: dict, keys) -> dict:
    return {k: d.get(k) for k in keys if d.get(k) not in (None, "", [], {})}


def _kit(plan: dict) -> dict:
    return brand_kit.kit_for(plan["brand"]) or {}


def _active_plan(plan: dict, kit: dict) -> dict:
    plans = kit.get("plans") or []
    return next((p for p in plans if p.get("id") == plan.get("brand_iq_plan")), plans[0] if plans else {})


# --------------------------------------------------------------------------- 2 Read

def read(plan_id: str) -> dict:
    """Gather Brand IQ into a cited grounding list. Works for any brand: sections a kit doesn't
    have are simply absent (and listed as gaps), never filled in."""
    plan = ep.get(plan_id)
    if not plan:
        raise KeyError(plan_id)
    kit = _kit(plan)
    bp = _active_plan(plan, kit)
    g: list[dict] = []

    for f in ("company", "generic", "lifecycle_stage", "positioning_statement", "core_claim", "tagline"):
        if kit.get(f):
            g.append(_item(f"brand:{f}", "Brand Kit", f.replace("_", " ").capitalize(), kit[f]))
    approval = ((kit.get("product_profile") or {}).get("us_approval") or {}).get("value")
    if approval:
        g.append(_item("brand:us_approval", "Brand Kit", "US approval", approval))
    for i, ind in enumerate(kit.get("indications") or []):
        g.append(_item(f"indication:{i}", "Brand Kit", "Indication", _pick(ind, ("name", "condition", "population", "line", "criteria"))))
    for fi, flow in enumerate(kit.get("patient_flow") or []):
        for si, st in enumerate(flow.get("stages") or []):
            g.append(_item(f"flow:{fi}:{si}", "Brand Kit · patient flow", f"{flow.get('indication_id')} · {st.get('stage')}",
                           _pick(st, ("stage", "value", "unit", "what", "verdict", "caveat", "source"))))
        for li, lk in enumerate(flow.get("leaks") or []):
            g.append(_item(f"leak:{fi}:{li}", "Brand Kit · patient flow", f"{flow.get('indication_id')} · evidence of a leak", lk))
    for i, s in enumerate(kit.get("audience_segments") or []):
        g.append(_item(f"segment:{i}", "Personas", "Audience segment", _pick(s, ("name", "who", "why", "ladder_rung", "ladder_reason", "tier", "status"))))
    personas = kit.get("personas") or {}
    for grp in ("hcp", "patient", "caregiver"):
        for i, p in enumerate(personas.get(grp) or []):
            g.append(_item(f"persona:{grp}:{i}", "Personas", f"{grp.upper()} persona",
                           _pick(p, ("name", "specialties", "who", "behaviours", "barrier", "moment", "key_message", "tone"))))
    for i, c in enumerate(kit.get("competitors") or []):
        g.append(_item(f"competitor:{i}", "Brand Kit", "Competitor / alternative", _pick(c, ("name", "type", "status", "threat", "counter", "indication", "source"))))
    for i, m in enumerate(kit.get("message_hierarchy") or []):
        g.append(_item(f"pillar:{i}", "Brand Kit", "Message pillar", _pick(m, ("pillar", "claim", "evidence"))))
    for i, o in enumerate(kit.get("key_objectives") or []):
        g.append(_item(f"objective:{i}", "Brand Kit", "Key objective (brand plan)", _pick(o, ("objective", "measure", "target_date", "priority"))))
    for i, si in enumerate(bp.get("strategic_imperatives") or []):
        g.append(_item(f"imperative:{i}", "Brand plan", f"Strategic imperative {si.get('id')}", _pick(si, ("imperative", "segment", "insight", "barrier", "activation_objective"))))
    for i, k_ in enumerate(bp.get("kpis") or []):
        g.append(_item(f"kpi:{i}", "Brand plan", "KPI", _pick(k_, ("kpi", "baseline", "data_source"))))
    for i, a in enumerate(bp.get("activities") or []):
        g.append(_item(f"activity:{i}", "Brand plan", "Planned activity", _pick(a, ("activity", "audience", "channel", "timing"))))
    for i, pp in enumerate(bp.get("proof_points") or []):
        g.append(_item(f"proof:{i}", "Market Intelligence", "What has worked", _pick(pp, ("name", "result"))))
    cp = compliance.for_brand(plan["brand"])
    if cp:
        steps = (cp.get("approval_workflow") or {}).get("steps") or []
        g.append(_item("compliance:approval", "Compliance", "Approval workflow", [f"{s.get('step')} ({s.get('sla')})" for s in steps]))
        for i, r in enumerate(cp.get("channel_rules") or []):
            g.append(_item(f"compliance:channel:{i}", "Compliance", "Channel rule", _pick(r, ("channel", "rule"))))

    gaps = []
    if not kit.get("patient_flow"):
        gaps.append({"what": "Patient flow (where patients are lost)", "page": "Brand Kit"})
    if not bp:
        gaps.append({"what": "No uploaded brand plan — objectives will be proposed from the diagnosis", "page": "Brand Kit"})
    if not cp:
        gaps.append({"what": "No company SOPs / approval workflow", "page": "Compliance Guardrails"})
    if not (kit.get("audience_segments") or personas.get("hcp")):
        gaps.append({"what": "Audience segments", "page": "Personas"})

    body = plan["body"]
    body["sources"] = g
    body["agent"] = {"step": "read", "gaps": gaps, "brand_iq_plan": bp.get("name") if bp else None}
    return ep.save(plan_id, body, f"Read Brand IQ ({len(g)} items)")


def _frame(plan: dict, fw: dict) -> dict:
    out = {"brand": plan["brand"], "period": f"{plan['period_start']} to {plan['period_end']}", "months": plan["months"],
           "adoption_ladder": fw["adoption_ladder"], "campaign_types": fw["campaign_types"], "channels": fw["channels"],
           "fixed_moment_types": fw["fixed_moment_types"], "frequency_caps": fw["frequency_caps"],
           "mlr_lead_time_weeks": fw["mlr_lead_time_weeks"]}
    if fw.get("archetype"):
        out["archetype"] = fw["archetype"]
    return out


def _role(plan: dict) -> str:
    return ("You are a senior pharmaceutical brand and omnichannel engagement strategist. You plan the next "
            f"{plan['months']} months for ONE brand. You reason like a brand team: find where patients are lost, "
            "why, which audience's belief or behaviour causes it, and what would move them. Use ONLY the grounding "
            "(Brand IQ) and the user's answers; never invent facts, figures or claims. Cite grounding ids. "
            "ALWAYS reply with a single JSON object matching the requested shape -- no prose, no markdown.")


# --------------------------------------------------------------------------- 3 Classify

def classify(plan_id: str, override: dict | None = None) -> dict:
    """Use the brand's situation from Brand IQ (or propose one); the user may override."""
    plan = ep.get(plan_id)
    if not plan["body"].get("sources"):
        plan = read(plan_id)
    kit = _kit(plan)
    situation = dict(kit.get("brand_situation") or {})
    if not situation.get("archetype"):
        import brand_builder
        situation = brand_builder.propose_situation(plan["brand"], {
            "today": ep._now()[:10], "indications": kit.get("indications"), "lifecycle_stage": kit.get("lifecycle_stage"),
            "us_approval": ((kit.get("product_profile") or {}).get("us_approval") or {}).get("value")})
    if override:
        situation.update({k: v for k, v in override.items() if k in ("lifecycle", "archetype", "access")})
        situation["status"] = "confirmed"
    fw = ep.framework()
    labels = {**{x["id"]: x["label"] for x in fw["lifecycle"]}, **{x["id"]: x["label"] for x in fw["archetypes"]},
              **{x["id"]: x["label"] for x in fw["access"]}}
    situation["labels"] = {k: labels.get(situation.get(k)) for k in ("lifecycle", "archetype", "access")}
    body = plan["body"]
    body["classification"] = situation
    body["agent"] = {**body.get("agent", {}), "step": "classify"}
    return ep.save(plan_id, body, "Situation confirmed" if override else "Situation classified")


# --------------------------------------------------------------------------- 4 Diagnose

def diagnose(plan_id: str) -> dict:
    plan = ep.get(plan_id)
    body = plan["body"]
    cls = body.get("classification") or {}
    fw = ep.framework(cls.get("archetype") or "chronic_primary")
    system = (_role(plan) + "\n\nDiagnose the patient-flow 'leaky bucket'. Choose the indication that matters most for "
              "this period (say why). Lay out the archetype's patient-flow stages with the best figure the grounding "
              "gives for each (cite the grounding id; keep match/proxy verdicts and caveats), the conversion between "
              "consecutive stages where both are known, and the TOP 2-3 LEAKS -- where the most patients are lost or "
              "the evidence of loss is strongest -- each with its evidence. Use the archetype's typical leaks as "
              "hypotheses, but only claim a leak the grounding supports. Only AVOIDABLE loss counts as a leak -- "
              "patients lost to missed suspicion, no testing, inertia, access, side-effect management or early "
              "stopping. Natural attrition (disease progression, death, ineligibility by label) is not a leak; "
              "note it separately in `natural_attrition`. List data gaps. Then write up to "
              f"{MAX_QUESTIONS} questions for the brand team that come from THIS diagnosis (missing numbers that would "
              "change which leak is biggest, contradictions, priorities between indications) -- never generic.\n"
              'Shape: {"indication":"","why_this_indication":"","stages":[{"stage":"","value":null,"unit":"","what":"",'
              '"verdict":"match|proxy|none","caveat":"","source":""}],"conversions":[{"from":"","to":"","rate":""}],'
              '"leaks":[{"id":"L1","stage":"","finding":"","size":"large|medium|unknown","evidence":[""]}],'
              '"natural_attrition":[""],"gaps":[""],"questions":[{"id":"q1","question":"","why":"","options":[""]}]}')
    out = complete_json(system, {"frame": _frame(plan, fw), "classification": cls, "grounding": body.get("sources"),
                                 "known_gaps": body["agent"].get("gaps")}, max_tokens=5000)
    out["questions"] = [q for q in out.get("questions") or [] if isinstance(q, dict) and q.get("question")][:MAX_QUESTIONS]
    body["bucket"] = out
    body["agent"] = {**body["agent"], "step": "diagnose", "questions": out["questions"]}
    return ep.save(plan_id, body, f"Diagnosed: {len(out.get('leaks') or [])} leak(s)")


# --------------------------------------------------------------------------- 5 Options

def options(plan_id: str, answers: dict | None = None) -> dict:
    plan = ep.get(plan_id)
    body = plan["body"]
    agent = body["agent"]
    agent["answers"] = answers or agent.get("answers") or {}
    cls = body.get("classification") or {}
    fw = ep.framework(cls.get("archetype") or "chronic_primary")
    system = (_role(plan) + "\n\nFor each top leak in the diagnosis, give its root cause: which audience segment's "
              "belief or behaviour causes it, where they sit on the adoption ladder, and the evidence (grounding ids). "
              "Then propose 2-3 DISTINCT strategic options for the period -- real choices a brand team would debate "
              "(e.g. fix initiation in primary care vs deepen specialist use vs fix persistence). For each: the "
              "thesis, which leaks it addresses, expected impact on the bucket (direction and rough size, only from "
              "the grounding), relative cost (low/medium/high), risk, time to effect, and what you give up. Then say "
              "which you'd recommend and why. Respect the lifecycle stage's focus.\n"
              'Shape: {"root_causes":[{"leak":"L1","audience":"","ladder_rung":"","belief":"","behaviour":"","evidence":[""]}],'
              '"options":[{"id":"A","name":"","thesis":"","leaks_addressed":["L1"],"impact":"","relative_cost":"","risk":"",'
              '"time_to_effect":"","trade_off":""}],"recommendation":{"id":"A","why":""}}')
    out = complete_json(system, {"frame": _frame(plan, fw), "classification": cls,
                                 "lifecycle_focus": next((x["focus"] for x in fw["lifecycle"] if x["id"] == cls.get("lifecycle")), None),
                                 "diagnosis": body.get("bucket"), "answers": agent["answers"],
                                 "grounding": body.get("sources")}, max_tokens=5000)
    body["root_causes"] = out.get("root_causes") or []
    body["options"] = out.get("options") or []
    body["recommendation"] = out.get("recommendation")
    agent["step"] = "options"
    body["agent"] = agent
    return ep.save(plan_id, body, f"{len(body['options'])} strategic option(s)")


def choose(plan_id: str, ids: list[str], note: str | None = None) -> dict:
    plan = ep.get(plan_id)
    body = plan["body"]
    valid = {o.get("id") for o in body.get("options") or []}
    ids = [i for i in ids if i in valid]
    if not ids:
        raise ValueError("choose at least one of the proposed options")
    body["chosen_option"] = {"ids": ids, "note": note}
    body["agent"] = {**body["agent"], "step": "decide"}
    return ep.save(plan_id, body, f"Chose option(s) {', '.join(ids)}")


# --------------------------------------------------------------------------- 7 Draft

_SHAPE = {
    "situation": {"narrative": "3-5 sentences: where the brand loses patients and what this plan bets on", "baselines": [{"metric": "", "today": "", "source": ""}]},
    "objectives": [{"id": "o1", "objective": "", "leak": "L1", "kpi": "", "baseline": "", "target": "", "by": "", "priority": "Primary|Secondary", "source": ""}],
    "audiences": [{"id": "a1", "name": "", "why_now": "", "ladder_today": "", "ladder_target": "", "source": ""}],
    "shifts": [{"audience_id": "a1", "objective_id": "o1", "from": "belief/behaviour today", "to": "target", "ladder_move": "Aware -> Trialled",
                "barrier": "", "message": "", "proof": "", "moment": "", "source": ""}],
    "campaigns": [{"id": "c1", "name": "", "type": "", "audience_ids": ["a1"], "shift_refs": ["a1:o1"], "message": "",
                   "channels": [""], "start": "YYYY-MM", "end": "YYYY-MM", "weight": 25, "content": "exists|adapt|new", "kpi": "", "source": ""}],
    "fixed_moments": [{"date": "YYYY-MM", "label": "", "type": "", "source": ""}],
    "budget": {"by_objective": {"o1": 40}, "by_audience": {"a1": 50}, "by_channel": {"Email": 20}},
    "measurement": {"kpi_tree": [{"objective_id": "o1", "kpi": "", "leading_indicators": [""]}], "review_cadence": ""},
    "risks": [{"risk": "", "likelihood": "", "impact": "", "mitigation": ""}],
}


def draft(plan_id: str) -> dict:
    plan = ep.get(plan_id)
    body = plan["body"]
    chosen = body.get("chosen_option") or {}
    if not chosen.get("ids"):
        raise ValueError("choose a strategic option first")
    cls = body.get("classification") or {}
    fw = ep.framework(cls.get("archetype") or "chronic_primary")
    picked = [o for o in body.get("options") or [] if o.get("id") in chosen["ids"]]
    system = (_role(plan) + "\n\nWrite the engagement plan for the CHOSEN option(s), as JSON matching `shape`.\n"
              "- 2-4 objectives, each tied to a diagnosed leak (L-id), outcomes not activities; use the grounding's "
              "brand-plan objectives/KPIs where they exist, otherwise propose and mark source 'proposed from diagnosis'.\n"
              "- Audiences come from the root causes; give each its adoption-ladder rung today and target.\n"
              "- Shift map: one row per audience x objective that matters, with the ladder move.\n"
              "- Every shift owned by at least one campaign; reuse brand-plan activities when they fit. Campaign "
              f"dates inside the period; first launches no earlier than {fw['mlr_lead_time_weeks']} weeks after the "
              "start (MLR review) unless the content already exists.\n"
              "- Budget is RELATIVE (% per breakdown, ~100), never money. Campaign `weight` is a number.\n"
              "- Every item names its source (grounding id, 'answer', 'option A', or 'proposed from diagnosis').\n"
              "Reply with the JSON object only.")
    out = complete_json(system, {"shape": _SHAPE, "frame": _frame(plan, fw), "classification": cls,
                                 "diagnosis": body.get("bucket"), "root_causes": body.get("root_causes"),
                                 "chosen_options": picked, "user_note": chosen.get("note"),
                                 "answers": body["agent"].get("answers"), "grounding": body.get("sources")}, max_tokens=9000)
    for key in ("situation", "objectives", "audiences", "shifts", "campaigns", "fixed_moments", "budget", "measurement", "risks"):
        if key in out:
            body[key] = out[key]
    body["checks"] = None
    body["agent"] = {**body["agent"], "step": "draft"}
    return ep.save(plan_id, body, "Drafted by the Engagement Planner")


# --------------------------------------------------------------------------- 8 Check

def _month_index(ym: str, start: str) -> int | None:
    try:
        y, m = int(str(ym)[:4]), int(str(ym)[5:7])
        return (y - int(start[:4])) * 12 + (m - int(start[5:7]))
    except (TypeError, ValueError):
        return None


def _feasibility(plan: dict, fw: dict) -> list[dict]:
    """Deterministic checks on the draft's own structure (no text interpretation)."""
    b = plan["body"]
    issues: list[dict] = []
    camps = b.get("campaigns") or []
    owned = {r for c in camps for r in (c.get("shift_refs") or [])}
    for s in b.get("shifts") or []:
        ref = f"{s.get('audience_id')}:{s.get('objective_id')}"
        if ref not in owned:
            issues.append({"check": "Coverage", "severity": "high", "issue": f"Shift {ref} has no campaign", "fix": "Add or extend a campaign to own it"})
    for k, label in (("by_objective", "objective"), ("by_audience", "audience"), ("by_channel", "channel")):
        vals = [float(v) for v in ((b.get("budget") or {}).get(k) or {}).values() if str(v).replace(".", "", 1).isdigit()]
        if vals and abs(sum(vals) - 100) > 5:
            issues.append({"check": "Budget", "severity": "low", "issue": f"Budget by {label} sums to {sum(vals):.0f}%, not 100%", "fix": "Rebalance"})
    lead = fw["mlr_lead_time_weeks"]
    for c in camps:
        i0, i1 = _month_index(c.get("start"), plan["period_start"]), _month_index(c.get("end"), plan["period_start"])
        if i0 is None or i1 is None:
            issues.append({"check": "Timeline", "severity": "medium", "issue": f"'{c.get('name')}' has no valid dates", "fix": "Set start/end"})
            continue
        if i0 < 0 or i1 >= plan["months"]:
            issues.append({"check": "Timeline", "severity": "medium", "issue": f"'{c.get('name')}' runs outside the plan period", "fix": "Move inside the period"})
        if i0 * 4.3 < lead and c.get("content") not in ("exists",):
            issues.append({"check": "MLR lead time", "severity": "medium",
                           "issue": f"'{c.get('name')}' starts in month {i0 + 1} with {c.get('content') or 'unknown'} content; MLR needs ~{lead} weeks",
                           "fix": "Start later, or use existing approved content first"})
    cap = fw["frequency_caps"].get("hcp_campaigns_in_parallel", 2)
    for a in b.get("audiences") or []:
        for m in range(plan["months"]):
            live = [c.get("name") for c in camps if a.get("id") in (c.get("audience_ids") or [])
                    and (_month_index(c.get("start"), plan["period_start"]) or 0) <= m <= (_month_index(c.get("end"), plan["period_start"]) or -1)]
            if len(live) > cap:
                issues.append({"check": "Audience fatigue", "severity": "medium",
                               "issue": f"{a.get('name')}: {len(live)} campaigns at once in month {m + 1} ({', '.join(live)})",
                               "fix": f"Sequence them; cap is {cap} in parallel"})
                break
    return issues


def check(plan_id: str) -> dict:
    plan = ep.get(plan_id)
    body = plan["body"]
    cls = body.get("classification") or {}
    fw = ep.framework(cls.get("archetype") or "chronic_primary")
    feas = _feasibility(plan, fw)
    system = (_role(plan) + "\n\nRed-team this engagement plan. Be specific and critical: the most likely competitor "
              "response, the weakest assumption, what would make the plan fail, a leak the plan ignores, and the "
              "leading indicator that would show failure early. For each, propose a concrete fix.\n"
              'Shape: {"red_team":[{"issue":"","why_it_matters":"","fix":"","severity":"high|medium|low"}]}')
    out = complete_json(system, {"plan": {k: body.get(k) for k in ("objectives", "audiences", "shifts", "campaigns", "budget", "risks")},
                                 "diagnosis": body.get("bucket"), "root_causes": body.get("root_causes"),
                                 "grounding_competitors": [s for s in body.get("sources") or [] if str(s.get("id", "")).startswith("competitor")]},
                        max_tokens=2500)
    body["checks"] = {"feasibility": feas, "red_team": out.get("red_team") or []}
    body["agent"] = {**body["agent"], "step": "check"}
    return ep.save(plan_id, body, f"Checked: {len(feas)} feasibility issue(s), {len(body['checks']['red_team'])} red-team point(s)")


__all__ = ["read", "classify", "diagnose", "options", "choose", "draft", "check", "LLMUnavailable"]
