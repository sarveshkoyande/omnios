"""Aggregates every 'needs alignment' item the toolkit templates could not answer from
state -- feasibility checklist (Sheet 5), CX Planning Questionnaire (Sheet 4), Target
Customer Group Template (Sheet 3), and the RACI seed (Sheet 14) -- into a small number
of themed groups the chat agent asks the user about after the plan is generated. This
is the deliberate middle path between the toolkit's 40+ blank cells and bam.py's
design note not to interrogate the user up front: the plan ships as a first draft
immediately, then the agent follows up on what only the brand team can know.
"""
from __future__ import annotations


def _feas_open(feasibility: dict, ids: set[str]) -> list[str]:
    return [q["text"] for q in feasibility["questions"] if not q["auto_answered"] and q["id"] in ids]


def build_open_questions(feasibility: dict, cx_questionnaire: dict, tcg: dict) -> list[dict]:
    """Returns ordered groups: [{id, title, source, questions: [str]}]. Groups with no
    open questions are dropped, so the list shrinks as the user volunteers more."""
    groups = [
        {"id": "objectives", "title": "Brand objectives, dependencies & key dates",
         "source": "CX Planning Questionnaire (Sheet 4)",
         "questions": [q["text"] for q in cx_questionnaire["open_questions"]]},
        {"id": "segment", "title": "Target customer group knowledge",
         "source": "Target Customer Group Template (Sheet 3)",
         "questions": [q["text"] for q in tcg["open_questions"]][:5]},
        {"id": "database", "title": "Customer database & opt-ins",
         "source": "CX feasibility checklist (Sheet 5)",
         "questions": _feas_open(feasibility, {"q1", "q2", "q3"})},
        {"id": "content", "title": "Content readiness",
         "source": "CX feasibility checklist (Sheet 5)",
         "questions": _feas_open(feasibility, {"q4", "q5"})},
        {"id": "campaign_ops", "title": "Campaign planning choices",
         "source": "CX feasibility checklist (Sheet 5)",
         "questions": _feas_open(feasibility, {"q6", "q7", "q8", "q9", "q10", "q11", "q13", "q14"})},
        {"id": "experience", "title": "Omnichannel experience & personalization ambition",
         "source": "CX feasibility checklist (Sheet 5)",
         "questions": _feas_open(feasibility, {"q15", "q16"})},
        {"id": "raci", "title": "RACI ownership",
         "source": "Campaign execution RACI (Sheet 14)",
         "questions": ["The RACI matrix in the plan is an illustrative seed — which stakeholders actually own "
                       "(Accountable) and execute (Responsible) each workstream on your side?"]},
    ]
    return [g for g in groups if g["questions"]]
