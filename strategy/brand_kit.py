"""Brand intelligence kit loader (config/brand_kits.json).

A kit is a brand's own captured intelligence hub -- story, message hierarchy, claims,
guardrails, campaign concepts, personas and live market signals -- scraped verbatim from
the brand's hub site (e.g. Nuvexa's https://commongoods.netlify.app/). When a plan is
generated for a brand with a kit, the agents ground the plan in this real brand content:

  * the Engagement Planner Agent frames the brief and Brand foundation section from it,
  * the Strategy & Positioning Agent sources the key-message pool + supporting claims from it,
  * the Market & Competitive Intelligence Agent uses its named competitors and live signals
    when the public knowledge base has nothing for the (possibly fictional) brand,
  * the Creative Inspiration Agent surfaces its active/legacy/emerging campaign concepts,
  * guardrails (dos & don'ts) land in the plan's Risk & governance section.

Brands without a kit are completely unaffected -- every consumer checks `kit_for(brand)`
for None first.
"""
from __future__ import annotations

import functools
import json
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
KITS_JSON = BASE_DIR / "config" / "brand_kits.json"


@functools.lru_cache(maxsize=1)
def _load() -> dict:
    if not KITS_JSON.exists():
        return {}
    try:
        return json.loads(KITS_JSON.read_text(encoding="utf-8")).get("kits", {})
    except (OSError, json.JSONDecodeError):
        return {}


def kit_for(brand: str) -> dict | None:
    """The kit for `brand` (case-insensitive), or None."""
    if not brand:
        return None
    kits = _load()
    for name, kit in kits.items():
        if name.lower() == brand.strip().lower():
            return kit
    return None


# Key-message topics (bam.KEY_MESSAGE_TOPICS wording) -> which message-hierarchy pillar's
# claim substantiates them best. Falls back to the core claim for unmapped topics.
_TOPIC_TO_PILLAR = [
    (("efficacy", "outcome", "survival", "clinical", "durab"), "Durability"),
    (("safety", "tolerab", "risk"), "Durability"),
    (("access", "cost", "value", "coverage", "afford"), "Access"),
    (("patient", "population", "type", "differenti", "versatil", "mechanism", "moa", "dosing"), "Versatility"),
]


def claim_for_topic(kit: dict, topic: str) -> str | None:
    """The kit claim (with its evidence citation) best matching a key-message topic."""
    if not kit:
        return None
    tl = (topic or "").lower()
    hierarchy = kit.get("message_hierarchy", [])
    by_pillar = {h["pillar"]: h for h in hierarchy}
    for keywords, pillar in _TOPIC_TO_PILLAR:
        if any(k in tl for k in keywords) and pillar in by_pillar:
            h = by_pillar[pillar]
            return f"{h['claim']} ({h['evidence']})"
    if kit.get("core_claim"):
        return f"{kit['core_claim']} — {kit.get('tagline', '')}".strip(" —")
    return None


def active_concepts(kit: dict) -> list[dict]:
    return [c for c in (kit or {}).get("concepts", []) if c.get("status") == "Active"]
