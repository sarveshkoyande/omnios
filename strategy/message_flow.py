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
from bam import KEY_MESSAGE_TOPICS, build_bam_chart  # noqa: E402
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


def build_message_flow(stage_key: str, kb_grounding: dict | None = None) -> dict:
    stage = STAGE_BY_KEY.get(stage_key, STAGE_BY_KEY["aware"])
    kb_grounding = kb_grounding or {}
    bam = build_bam_chart(stage_key)

    # Selected key messages: the stage-prioritized topics from bam.py, padded out to
    # 4 with the remaining default topics (toolkit always ships 4 key-message slots).
    selected_topics = list(bam["key_message_topics"])
    for t in KEY_MESSAGE_TOPICS:
        if len(selected_topics) >= 4:
            break
        if t not in selected_topics:
            selected_topics.append(t)

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
        "de_prioritized_messages": [t for t in KEY_MESSAGE_TOPICS if t not in selected_topics],
        "key_messages": key_messages,
        "non_opener_branch": non_opener_branch,
        "caveat": "Supporting messages are drafted from the stage's proof points and, where indexed, real KB document titles -- MLR-cleared claim language must still be substituted before use.",
    }
