"""CX Planning Questionnaire (Sheet 4 of the Customer Engagement Planning Toolkit
workbook) -- the 9-question brand-objectives / success / dependencies / key-dates
questionnaire, transcribed verbatim. Auto-answers what is derivable from state the
same way feasibility.py does (never guessing brand-team facts): questions about the
journey/message/measures come from the BAM chart, stage profile and KPI framework;
dependencies, risk-mitigation actions and key dates stay explicitly open and are
surfaced as "needs alignment" questions for the brand team.
"""
from __future__ import annotations

NEEDS_ALIGNMENT = "Needs alignment: the agent will ask you this in chat"

_SECTIONS = ["Brands Objectives", "Campaign Success", "Dependancies", "Key Dates"]

_QUESTIONS = [
    {"id": "cq1", "section": "Brands Objectives",
     "text": "Why are we planning a CX? What do you want we customers to know / do as a result of the omnichannel journey?"},
    {"id": "cq2", "section": "Brands Objectives",
     "text": "What are the customer engagement opportunities (leverage point, leakage point, inflection point)?"},
    {"id": "cq3", "section": "Brands Objectives",
     "text": "Why do we want our customers to change behavior? What impact do we want to the brand?"},
    {"id": "cq4", "section": "Brands Objectives",
     "text": "By designing and deploying an omnichannel journey at this leverage point, what behavior change do we want to see from the customer?"},
    {"id": "cq5", "section": "Brands Objectives",
     "text": "What is one idea do we want to get across in the journey? (I want… / To know or act… / So that they can… / and Overcome…)"},
    {"id": "cq6", "section": "Campaign Success",
     "text": "Which preliminary hypothesis can we set regarding success? Which measure should we track? (Start with standard, omnichannel KPIs. Include specific metrics required for this Customer Experience journey)"},
    {"id": "cq7", "section": "Dependancies",
     "text": "Are there any dependencies on external groups, capabilities, or inputs?"},
    {"id": "cq8", "section": "Dependancies",
     "text": "Are there any actions, coordination, or other activities that could mitigate risk?"},
    {"id": "cq9", "section": "Key Dates",
     "text": "What are upcoming dates that need to be integrated into the campaign planning process? E.g. Brand assessments, campaign launches, product innovations, capabilities coming online…"},
]


def build_cx_questionnaire(brand: str, persona: str, strategy: dict, bam: dict, kpi: dict) -> dict:
    sp = strategy["stage_profile"]
    m = strategy["messaging_architecture"]
    stage_label = strategy["inputs"]["stage"]

    one_idea = {
        "i_want": f"I want {persona} HCPs treating in this indication",
        "to_know_or_act": f"to move from “{m['current_belief']}” to “{m['desired_belief']}”",
        "so_that_they_can": f"so that they can {sp['engagement_goal'].rstrip('.').lower()}",
        "and_overcome": f"and overcome the barrier: {sp['core_barrier'].rstrip('.').lower()}",
    }

    auto_answers = {
        "cq1": (f"To move {persona} HCPs at the {stage_label} stage toward: {sp['engagement_goal']} "
                f"The journey should leave them believing “{m['desired_belief']}”."),
        "cq2": (f"Leverage point: the {stage_label} journey stage, where the core barrier is "
                f"“{sp['core_barrier']}”, the single highest-value point to intervene for {brand}."),
        "cq3": (f"Because the current prescriber belief (“{m['current_belief']}”) caps adoption; shifting it "
                f"unlocks the brand impact signalled by this stage: {sp['promotion_signal']}"),
        "cq4": f"The BAM A→B shift: {bam['a_to_b_shift']}",
        "cq5": ", ".join(one_idea.values()),
        "cq6": ("Track the standard omnichannel KPI set drafted in the measurement section; leading hypothesis "
                "metrics: " + "; ".join(kpi["leading_indicators"][:3]) + "."),
    }

    rows = []
    for q in _QUESTIONS:
        ans = auto_answers.get(q["id"])
        rows.append({**q, "answer": ans or NEEDS_ALIGNMENT, "auto_answered": ans is not None})

    return {
        "toolkit_reference": "CX Planning Questionnaire (Sheet 4)",
        "sections": _SECTIONS,
        "rows": rows,
        "one_idea": one_idea,
        "open_questions": [q for q in rows if not q["auto_answered"]],
        "auto_answered_count": sum(1 for r in rows if r["auto_answered"]),
        "total_questions": len(rows),
        "caveat": ("Auto-filled responses derive from the BAM chart, stage profile and KPI framework; dependencies "
                   "and key dates are genuinely brand-team facts and are left open for alignment rather than guessed."),
    }
