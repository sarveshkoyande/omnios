"""The product's vocabulary (docs/brainstorms/2026-09-24-brand-campaign-ia-ideas-2-7-requirements.md,
N-R1): one meaning per term, used by prompts and exports. frontend/src/glossary.ts is the
front ends' copy; scripts/verify_brand_hierarchy.py checks the two stay identical.

Only user-facing words live here. Internal identifiers (routes, modules, columns, JSON
keys) keep their existing names (N-KD2).
"""
from __future__ import annotations

TERMS: dict[str, tuple[str, str]] = {
    "brand": ("Brand", "The owning entity, with its brief and brand kit."),
    "brand_kit": ("Brand kit", "The brand's approved content: audiences, message house, compliance."),
    "engagement_plan": ("Engagement Plan", "A brand's programme of campaigns for a period, for example Q3 2026. A brand has many."),
    "campaign": ("Campaign", "One initiative inside an engagement plan."),
    "campaign_plan": ("Campaign Plan", "The phased planning document for one campaign. Optional."),
    "flow": ("Flow", "One channel-by-channel sequence inside a campaign. A campaign has many."),
}


def label(key: str) -> str:
    return TERMS[key][0]
