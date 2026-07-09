"""Channel Selection Template (Sheet 7 of the Customer Engagement Planning Toolkit
workbook): "Select channels based on Purpose, Availability, Preference and
Potential." Scores the toolkit's 6 named channels against the existing channel-mix
engine (rules.py / engine.py) rather than inventing a parallel model.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from rules import PERSONA_MULTIPLIERS  # noqa: E402

# Which of rules.CHANNEL_TOUCHPOINTS bucket each toolkit channel belongs to.
_CHANNEL_TO_BUCKET = {
    "Email": "Owned digital",
    "Website": "Owned digital",
    "Webinar": "Events",
    "Video": "Reach",
    "Social": "Reach",
    "Programmatic/Search": "Reach",
}

# Toolkit's 5 purpose columns (Sheet 7 header row 5) each channel best serves --
# a fixed characteristic profile, independent of persona/stage inputs.
_PURPOSE_PROFILE = {
    "Email": ["Frequency", "Relation building"],
    "Website": ["Impact", "Reach patients"],
    "Webinar": ["Impact", "Relation building"],
    "Video": ["Impact", "Reach"],
    "Social": ["Reach", "Frequency"],
    "Programmatic/Search": ["Reach", "Reach patients"],
}


def _priority_band(pct: float) -> str:
    if pct >= 25:
        return "High"
    if pct >= 10:
        return "Medium"
    return "Low"


def build_channel_selection(channel_mix_pct: dict[str, float], recommended_touchpoints: dict[str, list[str]],
                            persona: str) -> dict:
    mult = PERSONA_MULTIPLIERS.get(persona, {})
    rows = []
    for channel, purposes in _PURPOSE_PROFILE.items():
        bucket = _CHANNEL_TO_BUCKET[channel]
        pct = channel_mix_pct.get(bucket, 0)
        available = bucket in recommended_touchpoints and pct > 0
        rows.append({
            "channel": channel,
            "bucket": bucket,
            "purpose": purposes,
            "availability": "Current" if available else "Future",
            "preference_affinity": round(mult.get(bucket, 1.0), 2),
            "brand_priority": _priority_band(pct),
            "channel_mix_pct": pct,
        })
    rows.sort(key=lambda r: -r["channel_mix_pct"])
    return {
        "toolkit_reference": "Channel Selection Template (Sheet 7)",
        "guidance": "Select channels fit for purpose: increase frequency, impact, reach, build relationships, or facilitate patient reach.",
        "channels": rows,
        "caveat": "Availability/priority are derived from this brand's illustrative channel-mix split, not measured MMx or actual martech-availability data -- confirm 'Future' rows against real platform access before committing budget.",
    }
