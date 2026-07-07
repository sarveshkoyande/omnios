"""Generates a balanced-scorecard-style measurement framework (leading indicators,
lagging indicators, operational KPIs) for a given journey stage and channel mix --
synthesized from the stage's own promotion signal (rules.py) plus standard
per-channel engagement metrics used in real HCP engagement scorecards.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from rules import STAGE_BY_KEY  # noqa: E402

LEADING_INDICATORS_BY_CHANNEL = {
    "Reach": ["Impressions delivered", "Click-through rate", "Unbranded content completion rate"],
    "Owned digital": ["Email open rate", "Email click rate", "Website session duration (3+ min threshold)", "Portal/app login frequency"],
    "Events": ["Webinar registration rate", "Webinar attendance/completion rate", "Congress booth/session visits"],
    "Field": ["Rep call completion rate", "Detail acceptance rate", "Sample/starter requests"],
    "Peer": ["Advisory board participation rate", "Speaker program acceptance rate", "Peer-referral mentions"],
    "Patient-adjacent": ["Patient support program enrollment rate", "EHR point-of-care alert click-through rate"],
}

LAGGING_INDICATORS = [
    "TRx/NRx trend for the target segment",
    "Market share vs. the competitive set",
    "Patient persistence / adherence rate (once patient-adjacent channels are active)",
    "Advocacy indicators -- speaker program acceptance, peer-referral pattern (Adoption -> Champion transition)",
]

OPERATIONAL_KPIS = [
    "MLR review cycle time (days from submission to approval)",
    "Content utilization rate across channels (approved assets actually deployed vs. produced)",
    "Consent/opt-in coverage rate across the target HCP list",
    "Data completeness / match rate across CRM + CDP + claims sources feeding the NBA engine",
]


def build_kpi_framework(stage_key: str, channel_mix_pct: dict[str, float] | None = None) -> dict:
    stage = STAGE_BY_KEY[stage_key]
    channel_mix_pct = channel_mix_pct or {}

    leading = [f"{stage['promotion_signal']} (primary stage-promotion signal for {stage['label']})"]
    for channel, pct in channel_mix_pct.items():
        if pct and pct > 0:
            leading.extend(LEADING_INDICATORS_BY_CHANNEL.get(channel, []))

    return {
        "stage": stage["label"],
        "leading_indicators": leading,
        "lagging_indicators": LAGGING_INDICATORS,
        "operational_kpis": OPERATIONAL_KPIS,
        "cadence_note": (
            "Review leading indicators monthly (or bi-weekly for always-on digital channels), lagging indicators "
            "quarterly alongside claims/Rx data refreshes, and operational KPIs continuously -- mirrors the "
            "QBR / monthly brand review / bi-weekly brand review / operational-meeting cadence documented in the "
            "Ipsen NA Omnichannel Playbook (see the main Deep Dive doc's real-world validation section)."
        ),
        "caveat": "8-10 of these should be selected as the brand's actual tracked KPIs, not all of them -- real brand plans deliberately limit to a focused scorecard rather than tracking everything.",
    }
