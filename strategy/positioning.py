"""Generates a classic positioning statement (For [target] who [need], [brand] is
a [category] that [benefit]. Unlike [alternative], [brand] [differentiation].)
populated from the journey-stage framework (rules.py) and, where competitors are
supplied, real competitive signals (competitive/swot.py) rather than invented claims.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from rules import STAGE_BY_KEY  # noqa: E402
from competitive.swot import build_swot, generate_options  # noqa: E402


def build_positioning_statement(
    brand: str, therapy_area: str, persona: str, stage_key: str, competitors: list[str] | None = None
) -> dict:
    stage = STAGE_BY_KEY[stage_key]
    competitors = [c for c in (competitors or []) if c.strip()]

    swot_result = None
    top_strength = None
    strongest_competitor_name = None
    if competitors:
        swot_result = build_swot(brand, competitors, therapy_area, refresh=False)
        strengths = swot_result["swot"]["strengths"]
        if strengths and "No clear quantitative strength" not in strengths[0]:
            top_strength = strengths[0]
        threats = swot_result["swot"]["threats"]
        if threats and "No standout competitor threat" not in threats[0]:
            strongest_competitor_name = swot_result["competitors"][0]["brand"] if swot_result["competitors"] else None
            for c in swot_result["competitors"]:
                if c["brand"] in threats[0]:
                    strongest_competitor_name = c["brand"]
                    break

    alternative = strongest_competitor_name or "standard of care / current treatment approach"
    category = f"treatment option for {therapy_area}" if therapy_area else "treatment option"
    differentiation = top_strength or stage["proof_points"][0] if stage["proof_points"] else stage["messaging_type"]

    barrier = stage["core_barrier"].strip('"')
    statement = (
        f'For {persona} HCPs treating patients where the current barrier is "{barrier}", '
        f'{brand} is a {category} that helps them move from "{stage["current_belief"]}" to '
        f'"{stage["desired_belief"]}". Unlike {alternative}, {brand} leads with: {differentiation}'
    )

    if swot_result:
        messaging_options, audience_options = swot_result["messaging_options"], swot_result["audience_options"]
    else:
        messaging_options, audience_options = generate_options(
            {"brand": brand, "trials_active": 0, "trends_avg_interest": 0, "fda_label_count": 0, "pubmed_recent_2yr": 0},
            [],
            therapy_area,
        )

    return {
        "positioning_statement": statement,
        "proof_points": stage["proof_points"],
        "tone_constraint": stage["tone_constraint"],
        "alternative_angles": messaging_options,
        "target_audience_notes": audience_options,
        "grounded_in_competitive_data": bool(competitors),
        "caveat": "This is a template-generated positioning statement using the journey-stage framework and (if competitors were supplied) real competitive signals -- treat as a first draft for brand-team refinement, not a final MLR-ready claim.",
    }
