"""Target Customer Group Template (Sheet 3 of the Customer Engagement Planning
Toolkit workbook) -- the formalized, fill-in-the-template version of a BAM chart
(see bam.py's docstring). Synthesizes the three distribution questions (ABCD
segmentation, adoption/scientific-ladder position, digital-preference split) and
the personalization recommendation (toolkit Q16) from persona + journey stage,
the same illustrative-heuristic-on-real-inputs pattern as the rest of strategy/.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from rules import PERSONA_MULTIPLIERS, STAGE_BY_KEY, STAGES  # noqa: E402

_STAGE_KEYS = [s["key"] for s in STAGES]

# Toolkit's ABCD segmentation (Sheet 3, Q13) read as a value/engagement tier --
# A = highest-priority/most-engaged segment, D = lowest. Base weights by journey
# stage: earlier-funnel stages skew toward a broader, lower-tier population (more
# HCPs still to move); later stages skew toward a narrower, higher-tier population
# (already-engaged prescribers being deepened/defended).
_ABCD_BASE_BY_STAGE = {
    "unaware": {"A": 5, "B": 15, "C": 35, "D": 45},
    "aware": {"A": 10, "B": 25, "C": 40, "D": 25},
    "interested": {"A": 20, "B": 35, "C": 30, "D": 15},
    "trial": {"A": 30, "B": 40, "C": 20, "D": 10},
    "adoption": {"A": 40, "B": 40, "C": 15, "D": 5},
    "champion": {"A": 60, "B": 30, "C": 8, "D": 2},
}

# Toolkit Sheet 3, Q15: digital-preference distribution buckets.
_DIGITAL_BUCKETS = ["High", "Digital", "F2F", "Low"]


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values()) or 1.0
    out = {k: round(v / total * 100, 1) for k, v in weights.items()}
    drift = round(100 - sum(out.values()), 1)
    if drift and out:
        top = max(out, key=out.get)
        out[top] = round(out[top] + drift, 1)
    return out


def _abcd_distribution(stage_key: str, persona: str) -> dict[str, float]:
    base = dict(_ABCD_BASE_BY_STAGE.get(stage_key, _ABCD_BASE_BY_STAGE["aware"]))
    # KOL/DOL and Guideline-follower personas skew toward higher-value tiers (A/B);
    # "Unknown / not yet consented" skews toward the unengaged tail (C/D).
    if persona in ("KOL / DOL", "Guideline-follower"):
        base["A"] *= 1.4
        base["B"] *= 1.15
        base["D"] *= 0.6
    elif persona == "Unknown / not yet consented":
        base["A"] *= 0.4
        base["B"] *= 0.7
        base["D"] *= 1.6
    return _normalize(base)


def _ladder_distribution(stage_key: str) -> dict[str, float]:
    """Toolkit Sheet 3, Q14: distribution across the 5-step adoption/scientific ladder,
    centered on the ladder step corresponding to the brand's current journey stage
    (rules.STAGES' 6 stages collapsed onto the toolkit's 5-step ladder)."""
    idx = _STAGE_KEYS.index(stage_key) if stage_key in _STAGE_KEYS else 0
    ladder_step = min(5, idx + 1)  # 1-indexed, champion (idx 5) caps at step 5
    weights = {}
    for step in range(1, 6):
        distance = abs(step - ladder_step)
        weights[str(step)] = max(1, 40 - distance * 15)
    return _normalize(weights)


def _digital_distribution(persona: str) -> dict[str, float]:
    mult = PERSONA_MULTIPLIERS.get(persona, {})
    digital_affinity = mult.get("Owned digital", 1.0)
    field_affinity = mult.get("Field", 1.0)
    weights = {
        "High": 25 * digital_affinity,
        "Digital": 30 * digital_affinity,
        "F2F": 25 * field_affinity,
        "Low": 20 * (field_affinity / max(digital_affinity, 0.1)),
    }
    return _normalize(weights)


def _personalization_recommendation(stage_key: str, persona: str, digital_dist: dict[str, float]) -> str:
    stage = STAGE_BY_KEY[stage_key]
    high_digital_share = digital_dist.get("High", 0) + digital_dist.get("Digital", 0)
    if high_digital_share >= 55:
        channel_note = "channel-level personalization (digital-first sequencing, self-serve e-detailing)"
    elif high_digital_share <= 30:
        channel_note = "content-level personalization delivered through rep/F2F channels rather than channel-mix changes"
    else:
        channel_note = "a blended content + channel personalization (some digital sequencing, rep still carries the core narrative)"
    return (
        f"For {persona} HCPs at the {stage['label']} stage, the highest-impact personalization lever is "
        f"{channel_note} -- content should stay anchored to {stage['messaging_type'].lower()}."
    )


# Sheet 3's full 16-question template, verbatim, grouped under its three blue band
# headings. Auto-answered rows come from persona/stage/BAM state; the rest are
# genuinely brand-team facts and stay open for alignment.
TCG_NEEDS_ALIGNMENT = "Needs alignment — the agent will ask you this in chat"

_TCG_QUESTIONS = [
    ("t1", "What does the target customer group represent and how are we addressing it?",
     "What segment are we targeting?"),
    ("t2", "What does the target customer group represent and how are we addressing it?",
     "Within the target segment, what demographic information do we have? (e.g., specialties, geography, patient pool etc.)"),
    ("t3", "What does the target customer group represent and how are we addressing it?",
     "Within the target segment, what are the strategic imperatives? (e.g., evolve treatment paradigm, ensure continuity of care, etc.)"),
    ("t4", "What does the target customer group represent and how are we addressing it?",
     "Within the target segment, what are the potential leverage points? (e.g., treatment/brand choice, etc.)"),
    ("t5", "What does the target customer group represent and how are we addressing it?",
     "Within the target segment, what are the potential behavioral objectives? (e.g., brand trialist from reduced safety concerns, etc.)"),
    ("t6", "What does the target customer group represent and how are we addressing it?",
     "To date, which initiatives or campaigns were or are conducted for this target segment? Is Medical driving some initiatives or campaigns?"),
    ("t7", "What do we know about the behavior of the target customer group?",
     "What demographic information would best represent the target group?"),
    ("t8", "What do we know about the behavior of the target customer group?",
     "What experience does the target group have regarding the disease and its treatment? (e.g., prescribing history, brand loyalty)"),
    ("t9", "What do we know about the behavior of the target customer group?",
     "What are the target group's needs and expectations regarding the disease and its treatment?"),
    ("t10", "What do we know about the behavior of the target customer group?",
     "What is the target group's attitude towards the Industry? What is the target group's attitude towards patients? What is the target group's attitude towards colleagues?"),
    ("t11", "What do we know about the behavior of the target customer group?",
     "What are the target group's current behavior & beliefs regarding the disease, and its treatment? (e.g., treatment philosophy, lifestyles, beliefs about the brand)"),
    ("t12", "What do we know about the behavior of the target customer group?",
     "What are the target group's current barriers & drivers regarding the disease, and its treatment?"),
    ("t13", "How should we personalize our engagement with the target customer group?",
     "What is the distribution and the focus of the segment regarding the ABCD segmentation?"),
    ("t14", "How should we personalize our engagement with the target customer group?",
     "What is the distribution and the focus of the segment regarding the adoption/scientific ladder?"),
    ("t15", "How should we personalize our engagement with the target customer group?",
     "What is the distribution and the focus of the segment regarding digital preferences?"),
    ("t16", "How should we personalize our engagement with the target customer group?",
     "Within the target segment, what type of target group personalization will be impactful? (e.g., concept, channel mix, content)"),
]


def build_tcg_template(persona: str, profile: dict, strategy: dict, bam: dict) -> dict:
    """Sheet 3's full 16-row template with responses auto-filled where the persona/
    stage/BAM state genuinely answers the question, and 'needs alignment' elsewhere."""
    sp = strategy["stage_profile"]
    m = strategy["messaging_architecture"]

    def _dist(d: dict, prefix: str = "") -> str:
        return ", ".join(f"{prefix}{k}: {v}%" for k, v in d.items())

    auto = {
        "t1": f"{persona} HCPs at the {strategy['inputs']['stage']} journey stage.",
        "t4": f"The {strategy['inputs']['stage']} stage transition — {sp['engagement_goal']}",
        "t5": f"BAM behavioral objective (A→B shift): {bam['a_to_b_shift']}",
        "t9": f"Mental state at this stage: {sp['mental_state']}",
        "t11": f"Current behavior & beliefs: “{m['current_belief']}”.",
        "t12": f"Core barrier: {sp['core_barrier']} Desired driver: “{m['desired_belief']}”.",
        "t13": _dist(profile["abcd_segmentation_pct"]),
        "t14": _dist(profile["adoption_ladder_pct"], prefix="Step "),
        "t15": _dist(profile["digital_preference_pct"]),
        "t16": profile["personalization_recommendation"],
    }
    rows = [{"id": qid, "band": band, "text": text,
             "answer": auto.get(qid, TCG_NEEDS_ALIGNMENT), "auto_answered": qid in auto}
            for qid, band, text in _TCG_QUESTIONS]
    return {
        "toolkit_reference": "Target Customer Group Template (Sheet 3)",
        "rows": rows,
        "open_questions": [r for r in rows if not r["auto_answered"]],
        "auto_answered_count": len(auto),
        "total_questions": len(rows),
        "caveat": profile["caveat"],
    }


def build_segment_profile(persona: str, stage_key: str) -> dict:
    stage = STAGE_BY_KEY.get(stage_key, STAGE_BY_KEY["aware"])
    abcd = _abcd_distribution(stage_key, persona)
    ladder = _ladder_distribution(stage_key)
    digital = _digital_distribution(persona)
    return {
        "toolkit_reference": "Target Customer Group Template (Sheet 3)",
        "questions": {
            "q13_abcd_segmentation": "What is the distribution and the focus of the segment regarding the ABCD segmentation?",
            "q14_adoption_ladder": "What is the distribution and the focus of the segment regarding the adoption/scientific ladder?",
            "q15_digital_preference": "What is the distribution and the focus of the segment regarding digital preferences?",
            "q16_personalization": "Within the target segment, what type of target group personalization will be impactful?",
        },
        "abcd_segmentation_pct": abcd,
        "adoption_ladder_pct": ladder,
        "digital_preference_pct": digital,
        "personalization_recommendation": _personalization_recommendation(stage_key, persona, digital),
        "current_behavior_beliefs": stage["current_belief"],
        "barriers_drivers": stage["core_barrier"],
        "caveat": "Segment distributions are an illustrative starting read from persona/journey-stage inputs, not measured segmentation data (Tandem/affinity-monitor) -- replace with real segment sizing once available.",
    }
