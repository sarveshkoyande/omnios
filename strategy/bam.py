"""BAM chart, PP/NPP channel split, micro-journeys & CX-maturity -- the mechanics
described in 'Omni OS -- Customer Engagement Workshop Methodology (BAM Charts & CX
Toolkit).md' (Rohan Seth session + Indegene's own Customer Engagement Planning
Toolkit), applied on top of the existing journey-stage/channel-mix engine rather than
replacing it. Every function here is a heuristic derived from that doc, same caveat
status as the rest of strategy/rules.py -- directional, not measured.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from rules import STAGE_BY_KEY, STAGES  # noqa: E402

# The toolkit's / Rohan's "every brand has by default 4 message topics" rule, ordered as the
# clinical ladder a pharma reviewer expects to read: what the drug does (mechanism), what
# that achieves (efficacy), what it costs the patient clinically (safety), then how to give
# it (dosing). Order is the point -- the old pool had no mechanism rung at all and led on
# dosing, which is the end of the argument presented as the start of it.
MESSAGE_LADDER = ["Mechanism of action", "Efficacy & trial results", "Safety", "Dosing"]

# Pricing is an access conversation, not a clinical one. Mixing it into the ladder is the
# "different concepts" problem -- it stays selectable, but never ships by default.
OPTIONAL_TOPICS = ["Pricing"]

KEY_MESSAGE_TOPICS = MESSAGE_LADDER + OPTIONAL_TOPICS

# Which rungs best close each stage's current->desired belief gap -- a heuristic reading of
# the stage's messaging_type/proof_points, not a measured mapping. Selections are re-sorted
# into MESSAGE_LADDER order downstream, so these lists express relevance, not sequence.
_STAGE_TOPICS = {
    "unaware": ["Mechanism of action", "Efficacy & trial results"],
    "aware": ["Mechanism of action", "Efficacy & trial results", "Safety"],
    "interested": ["Efficacy & trial results", "Safety"],
    "trial": ["Safety", "Dosing"],
    "adoption": ["Safety", "Efficacy & trial results"],
    "champion": ["Efficacy & trial results", "Mechanism of action"],
}

# Rohan's PP (Personal Promotion) / NPP (Non-Personal Promotion) / Hybrid construct,
# mapped onto the existing 6 channel-mix buckets from rules.py.
CHANNEL_PP_NPP = {
    "Reach": "NPP",
    "Owned digital": "NPP",
    "Events": "Hybrid (congresses/ad-boards/speaker programs sit between PP and NPP)",
    "Field": "PP",
    "Peer": "Hybrid (advisory boards/KOL programs blend personal reach with broadcast influence)",
    "Patient-adjacent": "NPP",
}

_STAGE_KEYS = [s["key"] for s in STAGES]

_MATURITY_SIGNALS = {
    "simple": ["no sfmc", "not implemented", "no tagging", "no dashboard", "never launched",
               "first omnichannel", "starting from scratch", "no cx journey", "don't have sfmc",
               "dont have sfmc", "not have sfmc", "no crm", "just started", "new to omnichannel"],
    "complex": ["sfmc implemented", "tagging system", "dashboard system", "launched a complete cx",
                "highly personalized", "modular content", "ai-driven", "multiple channels already",
                "sfmc is live", "already have sfmc", "mature omnichannel"],
}


def build_bam_chart(stage_key: str) -> dict:
    """The BAM (Behavior/Attitude/Modification) chart for the brand's current journey stage:
    current vs. desired behavior/attitude (the A->B shift) plus the key-message topics chosen
    to close that gap."""
    stage = STAGE_BY_KEY.get(stage_key, STAGE_BY_KEY["unaware"])
    idx = _STAGE_KEYS.index(stage["key"]) if stage["key"] in _STAGE_KEYS else 0
    next_stage = STAGES[idx + 1] if idx + 1 < len(STAGES) else stage
    return {
        "stage_label": stage["label"],
        "current_state": {"belief": stage["current_belief"], "mental_state": stage["mental_state"],
                           "core_barrier": stage["core_barrier"]},
        "desired_state": {"belief": stage["desired_belief"], "next_stage_label": next_stage["label"]},
        "a_to_b_shift": f"“{stage['current_belief']}” → “{stage['desired_belief']}”",
        "key_message_topics": _STAGE_TOPICS.get(stage["key"], ["Efficacy & trial results"]),
        "all_topics": KEY_MESSAGE_TOPICS,
    }


def classify_pp_npp(channel_mix_pct: dict[str, float]) -> list[dict]:
    """Buckets each channel-mix category into PP / NPP / Hybrid per Rohan's construct."""
    return [
        {"channel": ch, "pct": pct, "bucket": CHANNEL_PP_NPP.get(ch, "NPP")}
        for ch, pct in sorted(channel_mix_pct.items(), key=lambda kv: -kv[1])
    ]


def build_micro_journeys(stage_key: str, recommended_touchpoints: dict[str, list[str]]) -> dict:
    """Rohan's correction to the 'one big SFMC journey' assumption: 2-3 parallel micro-journeys,
    each targeting a specific moment, plus the 15-day interim pivot/no-pivot governance check."""
    stage = STAGE_BY_KEY.get(stage_key, STAGE_BY_KEY["unaware"])
    all_tps = [tp for tps in recommended_touchpoints.values() for tp in tps]

    def _pick(*keywords: str, fallback: str) -> str:
        for tp in all_tps:
            if any(kw.lower() in tp.lower() for kw in keywords):
                return tp
        return fallback

    journeys = [
        {"name": f"{stage['label'].split('. ', 1)[-1]} core journey",
         "trigger": stage["promotion_signal"],
         "primary_touchpoint": _pick("email", "detail", "rep", fallback=all_tps[0] if all_tps else "Branded email"),
         "content_readiness": "Existing stock content (no PRC/MLR cycle needed)"},
        {"name": "Congress / event micro-journey",
         "trigger": "Congress or webinar registration",
         "primary_touchpoint": _pick("congress", "webinar", "symposia", fallback="Congress booths/symposia"),
         "content_readiness": "May need new derivative content -> PRC/MLR cycle required"},
        {"name": "Virtual-rep coverage micro-journey",
         "trigger": "Gap between physical rep visits (reps may see an HCP as rarely as once per 6 months)",
         "primary_touchpoint": _pick("email", "clm", "digital", fallback="Branded email/nurture flows"),
         "content_readiness": "Existing stock content (no PRC/MLR cycle needed)"},
    ]
    return {
        "journeys": journeys,
        "interim_check": "15-day interim checkpoint to decide pivot / no-pivot, with pivot criteria defined before launch, not improvised.",
    }


def has_maturity_signal(text: str) -> bool:
    """True if the free text volunteers any CX-maturity signal (SFMC/tagging/dashboard mentions,
    'just started', etc.) worth remembering for assess_cx_maturity() later. Used by the chat's
    opportunistic capture -- never asked for directly, only picked up if the user says it."""
    t = (text or "").lower()
    return any(sig in t for sig in _MATURITY_SIGNALS["simple"] + _MATURITY_SIGNALS["complex"])


def assess_cx_maturity(notes: str, channel_mix_pct: dict[str, float] | None = None) -> dict:
    """Simple/Medium/Complex CX-maturity read. Scoring now delegates to
    feasibility.build_feasibility_checklist() (the toolkit's real 16-question, 4-category
    checklist) instead of a bare keyword guess -- has_maturity_signal() above still does
    the opportunistic chat capture that feeds that checklist's auto-answers, per this
    doc's design note not to interrogate the user with the full checklist up front."""
    from feasibility import build_feasibility_checklist  # noqa: E402 (local import avoids a cycle at module load)
    checklist = build_feasibility_checklist(notes, channel_mix_pct)
    return {
        "level": checklist["overall_level"],
        "rationale": checklist["rationale"],
        "notes": notes or "",
        "feasibility_checklist": checklist,
    }
