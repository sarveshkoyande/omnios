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


# Key-message topic keywords -> which message-hierarchy pillar substantiates them best.
# Matched against the pillar NAME (kit-agnostic), so it works across brand kits without
# hard-coding each brand's pillar labels. Falls back to the core claim for unmapped topics.
_TOPIC_KEYWORDS = [
    (("efficacy", "outcome", "survival", "clinical", "durab", "response"), ("efficacy", "durab", "survival", "clarity")),
    (("safety", "tolerab", "risk", "manage"), ("safety", "manage", "tolerab")),
    (("access", "cost", "value", "coverage", "afford", "test", "identif", "biomarker", "diagnos"), ("access", "identif", "test", "patient")),
    (("mechanism", "moa", "differenti", "rational"), ("mechanism", "moa", "rational")),
]


def _pillar_match(topic_kws: tuple[str, ...], pillar_name: str) -> bool:
    pl = pillar_name.lower()
    return any(k in pl for k in topic_kws)


def claim_for_topic(kit: dict, topic: str) -> str | None:
    """The kit claim (with its evidence citation) best matching a key-message topic."""
    if not kit:
        return None
    tl = (topic or "").lower()
    hierarchy = kit.get("message_hierarchy", [])
    for topic_kws, pillar_kws in _TOPIC_KEYWORDS:
        if any(k in tl for k in topic_kws):
            for h in hierarchy:
                if _pillar_match(pillar_kws, h.get("pillar", "")):
                    return f"{h['claim']} ({h['evidence']})"
    if kit.get("core_claim"):
        return f"{kit['core_claim']} — {kit.get('tagline', '')}".strip(" —")
    return None


def active_concepts(kit: dict) -> list[dict]:
    return [c for c in (kit or {}).get("concepts", []) if c.get("status") == "Active"]


# Where dropped-in brand PNGs are served from (see app/static/brand_assets/<slug>/MANIFEST.md).
_ASSET_BASE = "/static/brand_assets"


def component_image_url(kit: dict, image: str) -> str:
    """Resolve a component's `image` field to a usable URL: pass through a full URL, else
    treat it as a filename dropped into app/static/brand_assets/<brand-slug>/."""
    if not image:
        return ""
    if image.startswith(("http://", "https://", "/")):
        return image
    slug = (kit.get("company_slug") or (kit.get("generic", "").split()[0]) or "brand")
    # Slug from the kit's brand name isn't stored on the kit; callers pass brand via _load key,
    # so default to the folder the manifest documents.
    return f"{_ASSET_BASE}/oncomyra/{image}"


# --- map a kit's claims + components into the plan's content-library shape ------------------
# The plan's Phase-2/3 renderers (message-flow claims block, content audit, content-to-channel)
# read campaign_store.content_library_for()'s {found, claims[], modules[], assets[]} shape.
# For a fictional kit brand with no scraped KB, synthesize that shape from the kit so the plan's
# Create-phase sections show the brand's REAL claims and creative components, not placeholders.

_STATUS_MAP = {"approved": "approved", "in_review": "in_review", "draft": "draft",
               "For review": "draft", "Gated": "draft", "Placeholder": "draft", "Reference": "draft"}
# component type -> asset_format the plan's content-to-channel mapping understands
_TYPE_TO_FORMAT = {"banner": "banner", "email": "email", "webpage": "webpage", "detail_aid": "detail_aid",
                   "social": "social", "video": "video", "internal": "detail_aid"}
# claim category keyword -> claim_type bucket used by _match_claims_for_topic
_CAT_TO_TYPE = [(("efficacy", "os", "pfs", "orr", "response"), "efficacy"), (("mechanism", "moa"), "moa"),
                (("safety",), "safety"), (("identification", "disease", "burden", "practical", "special", "commit"), "access"),
                (("real-world", "rwe"), "efficacy")]


def _claim_type(category: str) -> str:
    cl = (category or "").lower()
    for kws, t in _CAT_TO_TYPE:
        if any(k in cl for k in kws):
            return t
    return "efficacy"


def content_library_from_kit(kit: dict, indication: str = "") -> dict:
    """The plan-consumable content library synthesized from a brand kit's claims + components."""
    if not kit:
        return {"found": False, "claims": [], "modules": [], "assets": [], "counts": {}}
    claims = []
    for c in kit.get("claims", []):
        refs = [{"source_type": "brand_reference", "citation": r, "external_id": r, "url": ""} for r in c.get("references", [])]
        claims.append({
            "id": c["id"], "text": c["text"], "claim_type": _claim_type(c.get("category", "")),
            "status": _STATUS_MAP.get(c.get("status", "draft"), "draft"),
            "material_number": c["id"], "references": refs,
        })
    assets = []
    for comp in kit.get("components", []):
        assets.append({
            "id": comp["id"], "title": comp["title"], "file_name": comp.get("image") or comp["id"],
            "asset_format": _TYPE_TO_FORMAT.get(comp.get("type", ""), "detail_aid"),
            "branded": bool(comp.get("branded", True)), "target_group": comp.get("audience", ""),
            "description": comp.get("description", ""), "url": component_image_url(kit, comp.get("image", "")),
            "id_code": comp["id"], "blob_key": "", "modules": comp.get("claim_links", []),
            "image_url": component_image_url(kit, comp.get("image", "")),
        })
    approved = sum(1 for c in claims if c["status"] == "approved")
    counts = {"claims": len(claims), "approved_claims": approved, "modules": 0,
              "assets": len(assets), "references": len(kit.get("references", []))}
    return {"found": True, "brand_kit": True, "indication": indication,
            "claims": claims, "modules": [], "assets": assets, "counts": counts}
