"""Stage 5 — Pointed questions.

Turns the true gaps (`Gap.inferable == False`) that stage 4 identified into a
short, ranked question set. This stage does no new judgment about what's
missing — that already happened in gap analysis — it only selects, ranks, and
caps, which is what keeps the hard rule enforceable in one place: a gap that
stage 4 marked inferable structurally cannot carry a question (`Gap`'s own
validator forbids it), so there is no path for an already-resolved field to
leak into the question set here.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from strategy.planning_v2.models import Gap

MIN_QUESTIONS = 5
MAX_QUESTIONS = 8


class QuestionSet(BaseModel):
    questions: list[Gap] = Field(default_factory=list)  # this round — always inferable=False
    deferred: list[Gap] = Field(default_factory=list)  # true gaps beyond the cap, for a later round
    assumptions: list[Gap] = Field(default_factory=list)  # inferable=True gaps — logged, never asked


def build_question_set(gaps: list[Gap], *, max_questions: int = MAX_QUESTIONS) -> QuestionSet:
    true_gaps = sorted((g for g in gaps if not g.inferable), key=lambda g: g.impact_rank)
    assumptions = sorted((g for g in gaps if g.inferable), key=lambda g: g.impact_rank)
    return QuestionSet(
        questions=true_gaps[:max_questions],
        deferred=true_gaps[max_questions:],
        assumptions=assumptions,
    )


def apply_answer(gaps: list[Gap], field: str, answer: str) -> list[Gap]:
    """Resolve one true gap with the user's answer, turning it into a resolved
    assumption record (inferable=True, no question) so downstream synthesis
    treats it exactly like anything else that's now known — the distinction
    between "we inferred it" and "the user told us" doesn't need to survive
    past this point, only the value does."""
    out: list[Gap] = []
    for g in gaps:
        if g.field == field and not g.inferable:
            out.append(Gap(
                field=g.field, tactical_section_blocked=g.tactical_section_blocked,
                why_needed=g.why_needed, inferable=True, sources_attempted=g.sources_attempted,
                question=None, suggested_default=answer, impact_rank=g.impact_rank,
            ))
        else:
            out.append(g)
    return out
