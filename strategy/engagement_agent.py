"""The Engagement Planner agent (docs/redesign/engagement-plan.md, "How the agent builds it").

Works the way the Briefing Agent and Segmentation Planner do: read everything first, ask only
what's genuinely missing (max 3 questions), surface up to 3 impactful assumptions, then draft.

    1 Frame        -- engagement_plans.create() (brand, period, industry)
    2 Read         -- read(): Brand IQ only, structured fields, no model. Every item gets an id
                      ("kpi:2", "persona:hcp:1") that later drafts must cite.
    3 Clarify      -- clarify(): model proposes <=3 questions from real gaps
    4 Assumptions  -- answer(): model lists <=3 impactful assumptions (or skips with auto_assume)
    5 Draft        -- draft(): model writes the plan body, citing grounding ids

Rules R1/R2: free text is only read by the model; with no model (or a failed call) the step
raises LLMUnavailable and the API returns a plain message -- nothing is guessed.
Agent state (step, questions, answers, assumptions) lives in the plan body under "agent", so it
is versioned with the plan.
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
MAX_ASSUMPTIONS = 3


def _txt(v) -> str:
    return "" if v is None else str(v)


def _item(gid: str, page: str, label: str, value) -> dict:
    return {"id": gid, "page": page, "label": label, "value": value}


def read(plan_id: str) -> dict:
    """Step 2: gather Brand IQ into a cited grounding list (structured reads only)."""
    plan = ep.get(plan_id)
    if not plan:
        raise KeyError(plan_id)
    brand = plan["brand"]
    kit = brand_kit.kit_for(brand) or {}
    plans = kit.get("plans") or []
    active = next((p for p in plans if p.get("id") == plan["brand_iq_plan"]), plans[0] if plans else {})
    g: list[dict] = []

    for i, o in enumerate(kit.get("key_objectives") or []):
        g.append(_item(f"objective:{i}", "Brand Kit", "Key objective", {k: o.get(k) for k in ("objective", "measure", "target_date", "priority")}))
    for i, si in enumerate(active.get("strategic_imperatives") or []):
        g.append(_item(f"imperative:{i}", "Brand Kit · plan", f"Strategic imperative {si.get('id')}",
                       {k: si.get(k) for k in ("imperative", "segment", "insight", "driver", "barrier", "activation_objective")}))
    for i, k_ in enumerate(active.get("kpis") or []):
        g.append(_item(f"kpi:{i}", "Market Intelligence · plan", f"KPI ({k_.get('si')})", {k: k_.get(k) for k in ("kpi", "baseline", "data_source")}))
    for i, a in enumerate(active.get("activities") or []):
        g.append(_item(f"activity:{i}", "Brand plan activities", f"Planned activity ({a.get('si')})",
                       {k: a.get(k) for k in ("activity", "audience", "channel", "timing", "lead")}))
    if active.get("forecast"):
        g.append(_item("forecast", "Market Intelligence · plan", "Sales / patient forecast", active["forecast"]))
    for i, x in enumerate(active.get("growth_opportunities") or []):
        g.append(_item(f"growth:{i}", "Market Intelligence · plan", "Growth opportunity", {k: x.get(k) for k in ("id", "name", "share")}))

    personas = kit.get("personas") or {}
    for grp in ("hcp", "patient", "caregiver"):
        for i, p in enumerate(personas.get(grp) or []):
            g.append(_item(f"persona:{grp}:{i}", "Personas", f"{grp.upper()} persona",
                           {k: p.get(k) for k in ("name", "specialties", "who", "si", "behaviours", "barrier", "moment", "key_message", "tone")}))
    for i, s in enumerate((kit.get("care_continuum") or {}).get("stages") or []):
        g.append(_item(f"journey:{i}", "Personas", "Patient journey stage", {k: s.get(k) for k in ("stage", "patient")}))

    for i, m in enumerate(kit.get("message_hierarchy") or []):
        g.append(_item(f"pillar:{i}", "Brand Kit", "Message pillar", {k: m.get(k) for k in ("pillar", "claim", "evidence")}))
    for f in ("positioning_statement", "core_claim", "tagline"):
        if kit.get(f):
            g.append(_item(f"brand:{f}", "Brand Kit", f.replace("_", " ").capitalize(), kit[f]))
    un = kit.get("unmet_need") or {}
    for i, f in enumerate(un.get("facts") or []):
        g.append(_item(f"fact:{i}", "Brand Kit", "Unmet-need fact", {"label": f.get("label"), "value": f.get("value")}))
    for i, c in enumerate(kit.get("competitors") or []):
        g.append(_item(f"competitor:{i}", "Brand Kit", "Competitor", {k: c.get(k) for k in ("name", "type", "threat", "counter", "differentiation")}))
    for i, pp in enumerate(active.get("proof_points") or kit.get("proof_points") or []):
        g.append(_item(f"proof:{i}", "Market Intelligence", "What has worked", {k: pp.get(k) for k in ("name", "result")}))

    cp = compliance.for_brand(brand)
    if cp:
        steps = (cp.get("approval_workflow") or {}).get("steps") or []
        g.append(_item("compliance:approval", "Compliance", "Approval workflow (lead time)",
                       [f"{s.get('step')} ({s.get('sla')})" for s in steps]))
        for i, r in enumerate(cp.get("channel_rules") or []):
            g.append(_item(f"compliance:channel:{i}", "Compliance", "Channel rule", {k: r.get(k) for k in ("channel", "rule")}))

    gaps = []
    if not kit.get("approved_indication") or _txt(kit.get("approved_indication")).startswith("Needs input"):
        gaps.append({"what": "Approved indication", "page": "Compliance Guardrails"})
    if not active:
        gaps.append({"what": "No active brand plan in Brand IQ", "page": "Brand Kit"})
    if not (kit.get("audience_intel") or {}).get("trial_footprint"):
        gaps.append({"what": "Audience sizes", "page": "Personas"})

    body = plan["body"]
    body["sources"] = g
    body["agent"] = {**(body.get("agent") or {}), "step": "read", "gaps": gaps,
                     "brand_iq_plan": active.get("name") or active.get("id")}
    return ep.save(plan_id, body, f"Read Brand IQ ({len(g)} items)")


def _frame(plan: dict) -> dict:
    fw = ep.framework(plan["industry"])
    return {"brand": plan["brand"], "industry": plan["industry"], "period": f"{plan['period_start']} to {plan['period_end']}",
            "months": plan["months"], "lifecycle_lens": fw["lifecycle_lens"], "funnel_stages": fw["funnel_stages"],
            "campaign_types": fw["campaign_types"], "channels": fw["channels"], "fixed_moment_types": fw["fixed_moment_types"],
            "frequency_caps": fw["frequency_caps"], "gatekeeper": fw["vocabulary"]["gatekeeper"]}


_ROLE = ("You are a senior omnichannel engagement strategist for a {industry} brand. You plan the next "
         "{months} months for ONE brand: which audiences, what must change (belief/behaviour shifts), "
         "through which campaigns, when, and how success is measured. You only use the grounding "
         "provided (Brand IQ); never invent facts, numbers or claims.")


def clarify(plan_id: str) -> dict:
    """Step 3: up to 3 questions about genuine gaps (model)."""
    plan = ep.get(plan_id)
    if not plan["body"].get("sources"):
        plan = read(plan_id)
    fw = ep.framework(plan["industry"])
    system = (_ROLE.format(industry=plan["industry"].replace("_", " "), months=plan["months"]) + "\n\n"
              f"Read the grounding. Ask AT MOST {MAX_QUESTIONS} questions, and only about information that is "
              "genuinely missing AND would change the plan (priorities, committed work, relative budget, scope, "
              "dates). Never ask what the grounding already answers. Consolidate related gaps. Offer 2-4 short "
              "options where sensible. If nothing critical is missing, return an empty list.\n"
              'Reply with JSON only: {"questions":[{"id":"q1","question":"...","why":"...","options":["..."]}]}')
    out = complete_json(system, {"frame": _frame(plan), "topics_worth_asking": fw["clarify_topics"],
                                 "grounding": plan["body"]["sources"], "known_gaps": plan["body"]["agent"].get("gaps")},
                        max_tokens=1500)
    qs = [q for q in (out.get("questions") or []) if isinstance(q, dict) and q.get("question")][:MAX_QUESTIONS]
    body = plan["body"]
    body["agent"] = {**body["agent"], "step": "clarify", "questions": qs}
    return ep.save(plan_id, body, f"Asked {len(qs)} question(s)" if qs else "No questions needed")


def answer(plan_id: str, answers: dict, auto_assume: bool = False) -> dict:
    """Step 4: record answers, then list up to 3 impactful assumptions (model).
    With auto_assume the assumptions are proposed and accepted in one go."""
    plan = ep.get(plan_id)
    body = plan["body"]
    agent = body.get("agent") or {}
    agent["answers"] = answers or {}
    system = (_ROLE.format(industry=plan["industry"].replace("_", " "), months=plan["months"]) + "\n\n"
              f"Given the grounding and the user's answers, list AT MOST {MAX_ASSUMPTIONS} assumptions you still "
              "have to make that would materially change the plan (which audiences lead, campaign sequencing, "
              "channel emphasis, budget split). Each must be specific enough that overriding it changes the plan. "
              "If everything is clear, return an empty list.\n"
              'Reply with JSON only: {"assumptions":[{"id":"a1","text":"...","impact":"..."}]}')
    out = complete_json(system, {"frame": _frame(plan), "grounding": body.get("sources"),
                                 "questions": agent.get("questions"), "answers": agent["answers"]}, max_tokens=1200)
    assumptions = [{**a, "status": "accepted" if auto_assume else "proposed"}
                   for a in (out.get("assumptions") or []) if isinstance(a, dict) and a.get("text")][:MAX_ASSUMPTIONS]
    body["assumptions"] = assumptions
    agent["step"] = "assumptions"
    body["agent"] = agent
    return ep.save(plan_id, body, f"Listed {len(assumptions)} assumption(s)")


_DRAFT_SHAPE = {
    "situation": {"narrative": "2-4 sentences: where we are now, citing baselines", "baselines": [{"metric": "", "today": "", "source": "grounding id"}],
                  "changes": [""], "lessons": [""]},
    "objectives": [{"id": "o1", "objective": "", "kpi": "", "baseline": "", "target": "", "by": "", "serves": "imperative/goal",
                    "priority": "Primary|Secondary", "source": "grounding id(s)"}],
    "audiences": [{"id": "a1", "name": "", "lifecycle": "lens id", "why_now": "", "funnel_type": "key of funnel_stages",
                   "funnel": {"<stage>": {"today": "number/% or null", "target": "number/% or null"}}, "source": ""}],
    "shifts": [{"audience_id": "a1", "objective_id": "o1", "from": "", "to": "", "barrier": "", "message": "", "proof": "",
                "moment": "", "source": ""}],
    "campaigns": [{"id": "c1", "name": "", "type": "one of campaign_types", "audience_ids": ["a1"], "shift_refs": ["a1:o1"],
                   "message": "", "channels": [""], "start": "YYYY-MM", "end": "YYYY-MM", "weight": "relative % of budget",
                   "kpi": "", "status": "proposed", "source": ""}],
    "channels": [{"audience_id": "a1", "mix": [{"channel": "", "role": "lead|support"}], "frequency_cap": ""}],
    "fixed_moments": [{"date": "YYYY-MM", "label": "", "type": "one of fixed_moment_types", "source": ""}],
    "budget": {"by_objective": {"o1": 40}, "by_audience": {"a1": 50}, "by_channel": {"Email": 20}},
    "measurement": {"kpi_tree": [{"objective_id": "o1", "kpi": "", "leading_indicators": [""]}], "review_cadence": ""},
    "risks": [{"risk": "", "likelihood": "Low|Medium|High", "impact": "Low|Medium|High", "owner": "", "mitigation": ""}],
}


def draft(plan_id: str, assumption_decisions: dict | None = None) -> dict:
    """Step 5: write the plan body (model), every item citing grounding ids."""
    plan = ep.get(plan_id)
    body = plan["body"]
    for a in body.get("assumptions") or []:
        d = (assumption_decisions or {}).get(a.get("id"))
        if isinstance(d, dict):
            a["status"] = d.get("status", a.get("status"))
            if d.get("note"):
                a["note"] = d["note"]
        elif a.get("status") == "proposed":
            a["status"] = "accepted"
    system = (_ROLE.format(industry=plan["industry"].replace("_", " "), months=plan["months"]) + "\n\n"
              "Write the engagement plan as JSON matching `shape` exactly (same keys; lists may hold several items).\n"
              "Rules:\n"
              "- 2-4 objectives, outcomes not activities, taken from the grounding's objectives/KPIs.\n"
              "- Audiences come from the grounding's personas; 2-5 priority audiences.\n"
              "- Shift map: one row per audience x objective that matters (skip irrelevant pairs).\n"
              "- Every shift must be owned by at least one campaign; prefer the brand plan's planned activities.\n"
              "- Campaign dates must fall inside the period. Respect the gatekeeper lead time before launches.\n"
              "- Budget is RELATIVE (percentages summing to ~100 per breakdown), never money.\n"
              "- Funnel numbers only where the grounding gives them; otherwise null. Never invent figures.\n"
              "- Every item's `source` names the grounding id(s) it came from; use \"answer\" or \"assumption\" "
              "for items based on the user's answers or accepted assumptions.\n"
              "- Honour the user's answers and accepted assumptions; ignore rejected ones.\n"
              "Reply with the JSON object only.")
    payload = {"shape": _DRAFT_SHAPE, "frame": _frame(plan), "grounding": body.get("sources"),
               "answers": (body.get("agent") or {}).get("answers"), "assumptions": body.get("assumptions")}
    out = complete_json(system, payload, max_tokens=8000)
    for key in ("situation", "objectives", "audiences", "shifts", "campaigns", "channels", "fixed_moments",
                "budget", "measurement", "risks"):
        if key in out:
            body[key] = out[key]
    body["agent"] = {**(body.get("agent") or {}), "step": "draft"}
    return ep.save(plan_id, body, "Drafted by the Engagement Planner")


__all__ = ["read", "clarify", "answer", "draft", "LLMUnavailable"]
