"""Message Flow Template + Design Message Flow (Sheets 6 & 9 of the Customer
Engagement Planning Toolkit workbook). Builds the brand-plan key-message pool, the
4 selected key messages with their supporting messages, and the non-opener branch
that Sheet 9's diagram describes ("When NO impacts opened" -> campaign-summary
fallback) -- a mechanic the vault doc's Sec.5 calls out but bam.build_micro_journeys
does not implement.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from bam import KEY_MESSAGE_TOPICS, MESSAGE_LADDER, OPTIONAL_TOPICS, build_bam_chart  # noqa: E402
from rules import STAGE_BY_KEY  # noqa: E402

_KB_SOURCE_LABELS = {"clinicaltrials": "ClinicalTrials.gov", "pubmed": "PubMed", "openfda": "openFDA",
                     "dailymed": "DailyMed", "google_trends": "Google Trends"}

# Fallback placeholder text in the toolkit's own bracket convention (Sheet 6), used
# when no real proof point or KB document is available for a topic's 3rd supporting slot.
_PLACEHOLDER = "[Support message datapoint -- pending brand-team input]"


def _first_kb_title(kb_grounding: dict, scope: str = "brand") -> str | None:
    section = (kb_grounding or {}).get(scope, {})
    for src, items in section.items():
        if items:
            return f"{_KB_SOURCE_LABELS.get(src, src)}: {items[0]['title']}"
    return None


def _supporting_messages(topic: str, proof_points: list[str], kb_grounding: dict) -> list[str]:
    matched = [p for p in proof_points if topic.split(" &")[0].lower() in p.lower()]
    msgs = matched[:1] or proof_points[:1] or [f"{topic} proof point -- pending MLR-cleared claim"]
    kb_title = _first_kb_title(kb_grounding, "brand") or _first_kb_title(kb_grounding, "therapy_area")
    msgs.append(kb_title or _PLACEHOLDER)
    msgs.append(_PLACEHOLDER)
    return msgs[:3]


def ground_in_brand_kit(flow: dict, kit: dict | None) -> dict:
    """Re-point a built flow at the brand's OWN approved claims: the pool becomes the hub's
    message pool and each rung leads with the hub claim (plus study citation) substantiating
    it. Mutates and returns `flow`; a falsy kit is a no-op.

    Shared by the initial build (orchestrator) and by a ladder rebuilt from the user's rung
    picks (studio_run.apply_answer) -- rebuilding without this silently drops the brand's
    real claims back to generic proof points."""
    if not kit:
        return flow
    import brand_kit  # lazy: keeps this module importable without the kit layer

    if kit.get("message_pool"):
        flow["brand_plan_key_message_pool"] = list(kit["message_pool"])
    for key_message in flow.get("key_messages") or []:
        claim = brand_kit.claim_for_topic(kit, key_message["topic"])
        if claim and claim not in key_message["supporting_messages"]:
            key_message["supporting_messages"] = [claim] + list(key_message["supporting_messages"])[:2]
    flow["caveat"] = (flow.get("caveat", "") + " Key-message pool and lead supporting claims "
                      f"sourced verbatim from the {kit.get('source_label', 'brand intelligence hub')}.")
    return flow


def _ladder_order(topics: list[str]) -> list[str]:
    """Sort selected rungs into the fixed clinical ladder order, optional topics last.

    Selection and sequence are separate decisions: a planner picks *which* rungs are in
    scope, but the order they are told in is a clinical convention, not a preference."""
    ladder = [t for t in MESSAGE_LADDER if t in topics]
    optional = [t for t in OPTIONAL_TOPICS if t in topics]
    unknown = [t for t in topics if t not in MESSAGE_LADDER and t not in OPTIONAL_TOPICS]
    return ladder + unknown + optional


def build_message_flow(stage_key: str, kb_grounding: dict | None = None,
                       selected_topics: list[str] | None = None) -> dict:
    """Message ladder for the stage. `selected_topics` is the user's multi-select answer;
    when absent, the stage's own rungs are used and padded up to 4 from the ladder.

    Pricing is never added by padding -- it only appears if explicitly selected."""
    stage = STAGE_BY_KEY.get(stage_key, STAGE_BY_KEY["aware"])
    kb_grounding = kb_grounding or {}
    bam = build_bam_chart(stage_key)

    chosen = [t for t in (selected_topics or []) if t in KEY_MESSAGE_TOPICS]
    if not chosen:
        # Stage-prioritized rungs, padded out to 4 from the ladder only (toolkit ships 4
        # key-message slots). Padding never reaches into OPTIONAL_TOPICS.
        chosen = list(bam["key_message_topics"])
        for topic in MESSAGE_LADDER:
            if len(chosen) >= 4:
                break
            if topic not in chosen:
                chosen.append(topic)
    selected_topics = _ladder_order(chosen)

    key_messages = [
        {"topic": topic, "supporting_messages": _supporting_messages(topic, stage["proof_points"], kb_grounding)}
        for topic in selected_topics
    ]

    non_opener_branch = {
        "trigger": "When NO impacts opened",
        "node": "Campaign summary for non-openers",
        "campaign_summary": [f"{km['topic']} summary: {km['supporting_messages'][0]}" for km in key_messages],
    }

    return {
        "toolkit_reference": "Message Flow Template (Sheet 6) + Design Message Flow (Sheet 9)",
        "brand_plan_key_message_pool": KEY_MESSAGE_TOPICS,
        "message_ladder": MESSAGE_LADDER,
        "ladder_sequence": selected_topics,
        "optional_topics": OPTIONAL_TOPICS,
        "de_prioritized_messages": [t for t in KEY_MESSAGE_TOPICS if t not in selected_topics],
        "key_messages": key_messages,
        "non_opener_branch": non_opener_branch,
        "caveat": "Supporting messages are drafted from the stage's proof points and, where indexed, real KB document titles -- MLR-cleared claim language must still be substituted before use.",
    }
