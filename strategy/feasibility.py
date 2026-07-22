"""Omnichannel CX Feasibility Checklist (Sheet 5 of the Customer Engagement Planning
Toolkit workbook) -- the real 16-question, 4-category, Simple/Medium/Complex-scored
checklist, transcribed verbatim from the source workbook (see
cx_planning_toolkit_exact.md). This is the "low-effort, high-value reuse candidate"
flagged in 'Omni OS -- Customer Engagement Workshop Methodology (BAM Charts & CX
Toolkit).md' Sec.8 -- it replaces bam.py's free-text-only assess_cx_maturity() guess
as the source of truth for CX maturity, while still only auto-answering what's
genuinely inferable from state (never interrogating the user with all 16 questions
up front, per that doc's own design note).
"""
from __future__ import annotations

NOT_CAPTURED = "Not yet captured: confirm with brand team"

# Each question: id, category, text, and its 3 real answer-tier options
# (index 0 = Simple, 1 = Medium, 2 = Complex), transcribed verbatim from Sheet 5.
QUESTIONS = [
    {"id": "q1", "category": "Understanding of customer",
     "text": "How many specialties (e.g., HCP specialties) would you like to impact?",
     "tiers": ["1", "2", ">2"]},
    {"id": "q2", "category": "Understanding of customer",
     "text": "How many opt-ins do you have in your database for the selected specialty that will be targeted?",
     "tiers": ["<500", "> 500 < 1500", ">1500"]},
    {"id": "q3", "category": "Understanding of customer",
     "text": "How many of your customers are identified in the database per segment/archetype/ digital target group/ adoption ladder?",
     "tiers": ["0% - 20%", "21% – 50%", ">50%"]},
    {"id": "q4", "category": "Content design",
     "text": "How many existing assets can be leveraged in the CX journey?",
     "tiers": ["<20%", ">20%<50%", ">50%"]},
    {"id": "q5", "category": "Content design",
     "text": "How many existing content is modular or can be personalized?",
     "tiers": ["<30%", ">30%<60%", ">60%"]},
    {"id": "q6", "category": "Campaign Planning",
     "text": "Is SFMC implemented?", "tiers": ["No", "Working on it", "Currently used"]},
    {"id": "q7", "category": "Campaign Planning",
     "text": "Do you have a tagging system implemented?", "tiers": ["No", "Working on it", "Currently used"]},
    {"id": "q8", "category": "Campaign Planning",
     "text": "Do you have implemented an analytical model with different channels and sources of data that can be connected to each other?",
     "tiers": ["No", "Working on it", "Currently used"]},
    {"id": "q9", "category": "Campaign Planning",
     "text": "Do you have a dashboard system defined to view data?", "tiers": ["No", "Working on it", "Currently used"]},
    {"id": "q10", "category": "Campaign Planning",
     "text": "Have you ever launched a complete CX journey (journey with a message flow aligned to the steps of the adoption/scientific ladder) before?",
     "tiers": ["No", "Isolated impacts", "Yes"]},
    {"id": "q11", "category": "Campaign Planning",
     "text": "How many newsletters (approx. estimate) do you want to produce/create?", "tiers": ["<5", "> 5 < 8", ">8"]},
    {"id": "q12", "category": "Campaign Planning",
     "text": "How many channels are currently used (e.g., email, RTE, SMS, LinkedIn, Facebook, 3rd parties, programmatic, field force…)",
     "tiers": ["<2", "> 2 < 4", ">4"]},
    {"id": "q13", "category": "Campaign Planning",
     "text": "Have you ever launched concrete CX campaigns to the HCPs who did not open your previous emails?",
     "tiers": ["No", "Planned for near future", "Yes"]},
    {"id": "q14", "category": "Campaign Planning",
     "text": "How long would you like your CX campaign to last?", "tiers": ["<6 weeks", "> 6 weeks <8 weeks", ">8 weeks"]},
    {"id": "q15", "category": "Experience",
     "text": "What is the level of experience you have with omnichannel campaigns?", "tiers": ["Low", "Medium", "High"]},
    {"id": "q16", "category": "Experience",
     "text": "What level of personalization would you like to achieve (e.g., content, formats, salutation, subjects, tone, microjourneys, channels, full campaigns …)?",
     "tiers": [">30%", ">30%<50%", ">50%"]},
]

CATEGORIES = ["Understanding of customer", "Content design", "Campaign Planning", "Experience"]

_TIER_LABELS = ["Simple", "Medium", "Complex"]

_SFMC_HINTS = {"currently used": 2, "sfmc is live": 2, "already have sfmc": 2, "sfmc implemented": 2,
               "working on it": 1, "no sfmc": 0, "not have sfmc": 0, "dont have sfmc": 0, "don't have sfmc": 0}


def _infer(text: str, hints: dict[str, int]) -> int | None:
    for phrase, tier in hints.items():
        if phrase in text:
            return tier
    return None


def _auto_answer(question_id: str, maturity_notes: str, channel_mix_pct: dict[str, float]) -> tuple[int | None, str]:
    """Returns (tier_index or None, answer_label) for whatever is inferable from
    existing state -- never guesses beyond what the state actually volunteers."""
    text = (maturity_notes or "").lower()

    if question_id == "q6":  # SFMC implemented
        tier = _infer(text, _SFMC_HINTS)
        if tier is not None:
            return tier, QUESTIONS[5]["tiers"][tier]
    elif question_id == "q7":  # tagging system
        if "tagging system" in text or "tagging categorization" in text:
            return 2, QUESTIONS[6]["tiers"][2]
        if "no tagging" in text:
            return 0, QUESTIONS[6]["tiers"][0]
    elif question_id == "q8":  # analytical model
        if "ai-driven" in text or "analytical model" in text:
            return 2, QUESTIONS[7]["tiers"][2]
    elif question_id == "q9":  # dashboard
        if "dashboard system" in text or "dashboard" in text and "no dashboard" not in text:
            return 2, QUESTIONS[8]["tiers"][2]
        if "no dashboard" in text:
            return 0, QUESTIONS[8]["tiers"][0]
    elif question_id == "q10":  # launched a complete CX journey before
        if "launched a complete cx" in text or "mature omnichannel" in text:
            return 2, QUESTIONS[9]["tiers"][2]
        if "never launched" in text or "no cx journey" in text or "first omnichannel" in text or "just started" in text or "new to omnichannel" in text or "starting from scratch" in text:
            return 0, QUESTIONS[9]["tiers"][0]
    elif question_id == "q12":  # channels currently used
        active = sum(1 for pct in (channel_mix_pct or {}).values() if pct and pct > 0)
        if active:
            tier = 0 if active < 2 else (1 if active < 4 else 2)
            label = QUESTIONS[11]["tiers"][tier]
            return tier, f"{label} ({active} of the mix's channel buckets active)"

    return None, ""


def _tier_to_label(avg: float) -> str:
    if avg < 1.5:
        return "Simple"
    if avg < 2.5:
        return "Medium"
    return "Complex"


def build_feasibility_checklist(maturity_notes: str = "", channel_mix_pct: dict[str, float] | None = None) -> dict:
    channel_mix_pct = channel_mix_pct or {}
    answered_rows = []
    scored_tiers: list[int] = []

    for q in QUESTIONS:
        tier, label = _auto_answer(q["id"], maturity_notes, channel_mix_pct)
        if tier is not None:
            scored_tiers.append(tier)
            answered_rows.append({**q, "answer": label, "answer_tier": _TIER_LABELS[tier], "auto_answered": True})
        else:
            # Default to Medium for scoring purposes (matches bam.py's prior default
            # for "no signal volunteered") but the answer itself stays honestly blank.
            scored_tiers.append(1)
            answered_rows.append({**q, "answer": NOT_CAPTURED, "answer_tier": None, "auto_answered": False})

    by_category = {}
    for cat in CATEGORIES:
        cat_tiers = [scored_tiers[i] for i, q in enumerate(QUESTIONS) if q["category"] == cat]
        avg = sum(cat_tiers) / len(cat_tiers)
        by_category[cat] = {"avg_tier": round(avg, 2), "level": _tier_to_label(avg)}

    overall_avg = sum(scored_tiers) / len(scored_tiers)
    answered_count = sum(1 for r in answered_rows if r["auto_answered"])

    return {
        "toolkit_reference": "Omnichannel CX feasibility checklist (Sheet 5)",
        "questions": answered_rows,
        "by_category": by_category,
        "overall_level": _tier_to_label(overall_avg),
        "overall_avg_tier": round(overall_avg, 2),
        "auto_answered_count": answered_count,
        "total_questions": len(QUESTIONS),
        "rationale": (
            f"{answered_count} of {len(QUESTIONS)} questions were auto-answered from signals already "
            "volunteered in chat or captured in the channel mix; the remainder defaulted to Medium for "
            "scoring purposes and are flagged for brand-team confirmation rather than guessed."
        ),
        "caveat": "This is the toolkit's real feasibility checklist (Sheet 5), scored where state permits and left explicitly unanswered elsewhere -- confirm the unanswered rows with the brand team before treating the tier as final.",
    }
