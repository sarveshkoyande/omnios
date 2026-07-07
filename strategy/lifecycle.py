"""Infers a default HCP persona and journey stage from a brand's product-lifecycle
phase, so the auto-run pipeline needs only brand + therapy area + lifecycle phase --
no manual persona/journey-stage picking. Grounded in the Rogers adoption-curve logic
already used in rules.py (launch targets innovators/KOLs first, etc.); each inferred
choice is surfaced back to the user as an editable default, not a hidden decision.
"""
from __future__ import annotations

LIFECYCLE_STAGES = [
    {
        "key": "launch",
        "label": "Launch / Pre-launch",
        "description": "Product is newly approved or about to launch -- goal is building initial comprehension among the innovators/KOLs who move first.",
        "default_persona": "KOL / DOL",
        "default_stage_key": "aware",
    },
    {
        "key": "growth",
        "label": "Growth (early-to-late majority adoption)",
        "description": "Product has initial traction -- goal is converting the broader prescriber base from belief to first prescription.",
        "default_persona": "Fast-follower",
        "default_stage_key": "interested",
    },
    {
        "key": "mature",
        "label": "Mature / established in-line",
        "description": "Product is routinely prescribed -- goal is defending share of mind against complacency and competitive switching.",
        "default_persona": "Guideline-follower",
        "default_stage_key": "adoption",
    },
    {
        "key": "loe",
        "label": "LOE-facing / decline",
        "description": "Loss of exclusivity approaching -- goal is locking in advocates/champions and efficient digital-first retention before generic erosion.",
        "default_persona": "Digital-first",
        "default_stage_key": "champion",
    },
]

LIFECYCLE_BY_KEY = {s["key"]: s for s in LIFECYCLE_STAGES}


def infer_persona_and_stage(lifecycle_key: str) -> dict:
    lifecycle = LIFECYCLE_BY_KEY.get(lifecycle_key)
    if lifecycle is None:
        raise ValueError(f"Unknown lifecycle key: {lifecycle_key}")
    return {
        "persona": lifecycle["default_persona"],
        "stage_key": lifecycle["default_stage_key"],
        "lifecycle_label": lifecycle["label"],
        "rationale": lifecycle["description"],
    }


def list_lifecycle_options() -> list[dict]:
    return [{"key": s["key"], "label": s["label"], "description": s["description"]} for s in LIFECYCLE_STAGES]
