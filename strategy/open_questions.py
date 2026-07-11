"""Aggregates every 'needs alignment' item the toolkit templates could not answer from
state -- feasibility checklist (Sheet 5), CX Planning Questionnaire (Sheet 4), Target
Customer Group Template (Sheet 3), and the RACI seed (Sheet 14) -- into a small number
of themed groups the chat agent asks the user about.

The groups are ordered and tagged by toolkit PHASE (align -> select -> create -> deploy)
so the interactive build can gate the plan phase by phase: the run reveals only the
Align sections and asks the Align questions; answering a phase's questions unlocks the
next phase's sections and its questions. Every phase carries at least one always-present
checkpoint question, so no phase is ever skipped even when the feasibility rows all
auto-answer.
"""
from __future__ import annotations

# Toolkit phase running order, used to compute how far the plan is revealed.
PHASE_ORDER = ["align", "select", "create", "deploy"]


def _feas_open(feasibility: dict, ids: set[str]) -> list[str]:
    return [q["text"] for q in feasibility["questions"] if not q["auto_answered"] and q["id"] in ids]


def build_open_questions(feasibility: dict, cx_questionnaire: dict, tcg: dict) -> list[dict]:
    """Returns ordered groups: [{id, phase, title, source, questions: [str]}], sequenced by
    toolkit phase. Groups with no open questions are dropped (the two checkpoint groups and
    the RACI group always carry a question, so each phase keeps at least one)."""
    groups = [
        # ---- Phase 1 · Align on customer understanding & CX objectives ----
        {"id": "objectives", "phase": "align", "title": "Brand objectives, dependencies & key dates",
         "source": "CX Planning Questionnaire (Sheet 4)",
         "questions": [q["text"] for q in cx_questionnaire["open_questions"]]},
        {"id": "segment", "phase": "align", "title": "Target customer group knowledge",
         "source": "Target Customer Group Template (Sheet 3)",
         "questions": [q["text"] for q in tcg["open_questions"]][:5]},
        {"id": "database", "phase": "align", "title": "Customer database & opt-ins",
         "source": "CX feasibility checklist (Sheet 5)",
         "questions": _feas_open(feasibility, {"q1", "q2", "q3"})},
        # ---- Phase 2 · Select relevant messages & channels ----
        {"id": "select_checkpoint", "phase": "select", "title": "Message & channel guardrails",
         "source": "Message Flow + Channel Selection (Sheets 6-7)",
         "questions": ["Before I lock the message flow and channel plan: is there any channel you must "
                       "include or exclude, and any key message you must lead with — or cannot use yet?"]},
        # ---- Phase 3 · Create omnichannel CX ----
        {"id": "create_checkpoint", "phase": "create", "title": "Omnichannel CX build priorities",
         "source": "Map content + Design flows (Sheets 8-9)",
         "questions": ["For the omnichannel CX build: which existing assets should we prioritise reusing, "
                       "and are there content/MLR constraints or must-have journeys I should design around?"]},
        {"id": "content", "phase": "create", "title": "Content readiness",
         "source": "CX feasibility checklist (Sheet 5)",
         "questions": _feas_open(feasibility, {"q4", "q5"})},
        {"id": "campaign_ops", "phase": "create", "title": "Campaign planning choices",
         "source": "CX feasibility checklist (Sheet 5)",
         "questions": _feas_open(feasibility, {"q6", "q7", "q8", "q9", "q10", "q11", "q13", "q14"})},
        {"id": "experience", "phase": "create", "title": "Omnichannel experience & personalization ambition",
         "source": "CX feasibility checklist (Sheet 5)",
         "questions": _feas_open(feasibility, {"q15", "q16"})},
        # ---- Phase 4 · Deploy campaign ----
        {"id": "raci", "phase": "deploy", "title": "RACI ownership",
         "source": "Campaign execution RACI (Sheet 14)",
         "questions": ["The RACI matrix in the plan is an illustrative seed — which stakeholders actually own "
                       "(Accountable) and execute (Responsible) each workstream on your side?"]},
    ]
    return [g for g in groups if g["questions"]]


def revealed_phases_for(groups: list[dict], next_idx: int) -> set[str]:
    """The set of toolkit phases the plan should reveal given the clarify cursor. `next_idx`
    is the index of the group about to be asked (== len(groups) once every group is answered).
    Reveals every phase from Align up to and including the phase of the group being asked;
    once clarification is complete, all phases are revealed."""
    if not groups or next_idx >= len(groups):
        return set(PHASE_ORDER)
    current_phase = groups[next_idx].get("phase", "align")
    try:
        cutoff = PHASE_ORDER.index(current_phase)
    except ValueError:
        cutoff = 0
    return set(PHASE_ORDER[: cutoff + 1])
