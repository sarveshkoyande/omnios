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


# ------------------------------------------------------------------ posture options ---
# A brand team does not choose between six mix buckets -- it chooses a go-to-market posture
# and then argues about the split underneath it. These are the three postures a pharma
# planner recognises, each anchored on one rules.py bucket.
POSTURES = [
    {"label": "Field-led", "anchor": "Field",
     "rationale": "Reps carry the message; digital sustains reach between calls."},
    {"label": "Event-led", "anchor": "Events",
     "rationale": "Congress and speaker moments carry the message; digital follows up on attendance."},
    {"label": "Own Digital", "anchor": "Owned digital",
     "rationale": "Email and web carry the message at scale; field concentrates on the top tier."},
]

# The concrete line items a brand team plans and buys against (the MMx vocabulary), mapped
# onto the mix buckets. Owned digital covers two distinct line items, so it splits.
_MMX_CHANNELS = [
    ("Email", "Owned digital", 0.6),
    ("Web", "Owned digital", 0.4),
    ("Field", "Field", 1.0),
    ("Paid media", "Reach", 1.0),
    ("Events", "Events", 1.0),
    ("Peer-to-peer", "Peer", 1.0),
]
_MAPPED_BUCKETS = {bucket for _, bucket, _ in _MMX_CHANNELS}

# How hard a posture tilts the base mix toward its anchor bucket. Directional, not measured:
# enough to make the three postures visibly different without erasing the affinity signal.
_ANCHOR_TILT = 1.9


def posture_distribution(channel_mix_pct: dict[str, float], anchor: str) -> list[dict]:
    """Split across the MMx channels for one posture: the base mix tilted toward `anchor`,
    renormalised to 100, then projected onto the concrete channels."""
    tilted = {bucket: pct * (_ANCHOR_TILT if bucket == anchor else 1.0)
              for bucket, pct in channel_mix_pct.items()}
    # A bucket the brand has no mix for still has to carry its posture, or "Field-led" can
    # come back with no field spend at all.
    tilted.setdefault(anchor, 0.0)
    if tilted[anchor] <= 0:
        tilted[anchor] = max(tilted.values(), default=1.0) or 1.0
    # Normalise over the buckets that actually have an MMx line item. Dividing by the full
    # bucket total instead would quietly lose any unmapped bucket's share and the split
    # would present as 97% -- the first thing a brand manager checks is that it adds up.
    total = sum(pct for bucket, pct in tilted.items() if bucket in _MAPPED_BUCKETS) or 1.0
    rows = []
    for channel, bucket, share in _MMX_CHANNELS:
        pct = round(100 * tilted.get(bucket, 0.0) * share / total, 1)
        if pct > 0:
            rows.append({"channel": channel, "pct": pct})
    rows.sort(key=lambda r: -r["pct"])
    if rows:  # absorb rounding drift into the largest line so the split always reads 100
        rows[0]["pct"] = round(rows[0]["pct"] + (100 - sum(r["pct"] for r in rows)), 1)
    return rows


def build_posture_options(channel_mix_pct: dict[str, float]) -> list[dict]:
    """The three postures, each with its MMx split and a one-line headline. Ordered by how
    well the brand's own affinity mix already supports the anchor, so the recommendation is
    the posture the data leans to rather than a fixed favourite."""
    options = []
    for posture in POSTURES:
        distribution = posture_distribution(channel_mix_pct, posture["anchor"])
        headline = " / ".join(f"{row['channel']} {row['pct']:.0f}%" for row in distribution[:4])
        options.append({**posture, "distribution": distribution, "headline": headline,
                        "anchor_affinity": channel_mix_pct.get(posture["anchor"], 0.0)})
    options.sort(key=lambda o: -o["anchor_affinity"])
    return options


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
