"""Staged field registry and next-question engine for the Agentic Brand Journey (KTD1).

Every journey field is declared once here: its step, stage order, target (a brand-kit
field, or the brand's own name), question text, chip options, whether it is required for
the step to count as complete, and an optional condition over earlier answers. The LLM
never chooses the question -- `next_questions()` is a pure function over this registry and
the current answers; the agent only phrases what it returns.

Conditions return True (relevant), False (not relevant), or None (waiting on an earlier
answer that has not been given yet). A field is open only when its condition is True and
it is unanswered.
"""
from __future__ import annotations

from typing import Any, Callable

STEPS: tuple[str, ...] = ("brief", "audience", "message", "kit", "flow")
STEP_LABELS = {"brief": "Brief", "audience": "Audience", "message": "Message",
               "kit": "Kit", "flow": "Flow"}
_PREREQS: dict[str, tuple[str, ...]] = {
    "brief": (),
    "audience": ("brief",),
    "message": ("brief",),
    "kit": ("brief", "message"),
    "flow": ("brief", "audience", "message"),
}

# Product-claim fields: only relevant when the brand is marketed as branded (R9, AE1).
CLAIM_FIELDS = frozenset({"core_claim", "message_hierarchy", "approved_indication",
                          "safety_reference"})


def _branded_only(answers: dict) -> bool | None:
    val = answers.get("branded")
    if not has_value(val):
        return None
    return str(val).strip().lower() != "unbranded"


def _f(step: str, key: str, question: str, *, chips: list[str] | None = None,
       target: str = "kit", required: bool = False,
       condition: Callable[[dict], bool | None] | None = None) -> dict:
    return {"step": step, "key": key, "target": target, "question": question,
            "chips": chips or [], "required": required, "condition": condition}


# List order within a step IS the stage order.
FIELDS: list[dict[str, Any]] = [
    # Brief (R12)
    _f("brief", "brand_name", "What's the brand called?", target="brand", required=True),
    _f("brief", "indication", "What is the brand indicated for?", required=True),
    _f("brief", "territories", "Which territory are you launching in first?",
       chips=["US", "EU", "UK", "Japan", "Canada", "Other"], required=True),
    _f("brief", "lifecycle_stage", "Where is the brand in its lifecycle?",
       chips=["Pre-launch", "Launch", "Growth", "Mature"]),
    _f("brief", "key_objective", "What is the main objective for this brand right now?",
       required=True),
    _f("brief", "success_measure", "How will you measure success?",
       chips=["New patient starts", "Market share", "HCP reach", "Adherence"]),
    _f("brief", "branded", "Is this a branded or unbranded programme?",
       chips=["branded", "unbranded"]),
    # Audience (R14)
    _f("audience", "primary_audience", "Who is the primary audience?",
       chips=["HCPs", "Patients", "Caregivers", "Payers"]),
    _f("audience", "personas", "Describe the key personas you want to reach.", required=True),
    _f("audience", "competitors", "Which competitors matter most?"),
    # Message (R13)
    _f("message", "core_claim", "What is the core claim?", required=True,
       condition=_branded_only),
    _f("message", "positioning_statement", "How would you position the brand in one sentence?",
       required=True),
    _f("message", "tagline", "Do you have a tagline?"),
    _f("message", "message_hierarchy", "What are the message pillars and their proof points?",
       required=True, condition=_branded_only),
    _f("message", "tone_pillars", "Which tone words describe the brand voice?",
       chips=["Confident", "Evidence-led", "Empathetic", "Reassuring"], required=True),
    _f("message", "voice_do", "Which words or phrases should the voice use?"),
    _f("message", "voice_dont", "Which words or phrases must the voice avoid?"),
    _f("message", "brand_personification", "If the brand were a person, who would it be?"),
    # Kit (R15)
    _f("kit", "guardrails", "What are the compliance dos and don'ts?", required=True),
    _f("kit", "approved_indication", "What is the approved indication wording?",
       required=True, condition=_branded_only),
    _f("kit", "safety_reference", "What is the safety reference?", required=True,
       condition=_branded_only),
]
FIELDS_BY_KEY = {f["key"]: f for f in FIELDS}


def has_value(val: Any) -> bool:
    """Non-empty: strings with text, non-empty lists, dicts with any non-empty value."""
    if val is None:
        return False
    if isinstance(val, str):
        return bool(val.strip())
    if isinstance(val, dict):
        return any(has_value(v) for v in val.values())
    if isinstance(val, (list, tuple)):
        return len(val) > 0
    return True


def _check_step(step: str) -> None:
    if step not in STEPS:
        raise ValueError(f"unknown journey step '{step}'")


def fields_for(step: str) -> list[dict]:
    _check_step(step)
    return [f for f in FIELDS if f["step"] == step]


def relevance(field: dict, answers: dict) -> bool | None:
    cond = field.get("condition")
    return True if cond is None else cond(answers)


def open_fields(step: str, answers: dict) -> list[dict]:
    """Unanswered, relevant fields of `step`, in stage order."""
    return [f for f in fields_for(step)
            if relevance(f, answers) is True and not has_value(answers.get(f["key"]))]


def next_questions(step: str, answers: dict, limit: int = 1) -> list[dict]:
    """The next `limit` open fields as public question dicts (no condition callable)."""
    return [public(f) for f in open_fields(step, answers)[:max(0, limit)]]


def required_fields(step: str, answers: dict) -> list[dict]:
    """Required fields of `step` that currently apply (condition True)."""
    return [f for f in fields_for(step) if f["required"] and relevance(f, answers) is True]


def step_prerequisites(step: str) -> tuple[str, ...]:
    _check_step(step)
    return _PREREQS[step]


def public(field: dict) -> dict:
    return {k: v for k, v in field.items() if k != "condition"}
