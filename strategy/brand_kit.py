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

import datetime
import functools
import json
import pathlib
import sys

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
KITS_JSON = BASE_DIR / "config" / "brand_kits.json"


def kit_file_mtime() -> str | None:
    """When config/brand_kits.json was last modified, as an ISO timestamp. This is the ONE
    real "last updated" signal that exists anywhere in this data -- there is no per-section
    or per-field change history yet (the kit is still committed config, not a versioned
    record; see idea 3/6 in the brand-workspace ideation doc). Every section in the UI
    shares this same value rather than a fabricated per-section date -- it is honest about
    tracking the whole file, not a claim about what specifically changed."""
    try:
        ts = KITS_JSON.stat().st_mtime
    except OSError:
        return None
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()

# Standard regulatory-territory codes a campaign can be scoped to. This is a fixed reference
# list, not brand data -- it lets the UI show which territories a given kit is NOT yet
# configured for (visibly, honestly) without inventing per-territory content for any of
# them. A kit only "operates" in the territories named in its own `territories` field.
KNOWN_TERRITORIES = ["US", "EU", "UK", "Japan", "Canada"]


@functools.lru_cache(maxsize=1)
def _load() -> dict:
    if not KITS_JSON.exists():
        return {}
    try:
        return json.loads(KITS_JSON.read_text(encoding="utf-8")).get("kits", {})
    except (OSError, json.JSONDecodeError):
        return {}


def list_brands() -> list[dict]:
    """Every brand holding a kit, as a lightweight roster for a brand switcher.

    Deliberately thin -- name plus the few identifying fields a chooser needs. Callers that
    want the whole record ask for `kit_for()`; shipping 19 claims and 13 components in a
    list response would make the switcher pay for content it never renders."""
    return [
        {
            "brand": name,
            "generic": kit.get("generic", ""),
            "company": kit.get("company", ""),
            "therapy_area": kit.get("therapy_area", ""),
            "indication": kit.get("indication", ""),
            "territories": kit.get("territories", []),
        }
        for name, kit in _load().items()
    ]


def kit_for(brand: str) -> dict | None:
    """The kit for `brand` (case-insensitive), or None."""
    if not brand:
        return None
    kits = _load()
    for name, kit in kits.items():
        if name.lower() == brand.strip().lower():
            return kit
    return None


def apply_diff(brand: str, fields: dict) -> dict:
    """Write `fields` (field name -> new value) into `brand`'s entry in
    config/brand_kits.json, preserving every other field and the file's existing key
    order. This is the ONLY place that ever writes to brand_kits.json outside of manual
    editing -- everything else in this module only reads it. Callers (kit_drafts.publish_draft)
    are expected to have already resolved `fields` down to just the user-accepted subset
    of an agent's proposed diff; this function does not itself gate or validate content,
    it only applies what it's given.

    Clears `_load()`'s cache so the change is visible on the next read without a server
    restart -- the staleness gap that made an earlier session's direct-JSON-edit need a
    manual restart to show up."""
    if not KITS_JSON.exists():
        raise FileNotFoundError(str(KITS_JSON))
    data = json.loads(KITS_JSON.read_text(encoding="utf-8"))
    kits = data.get("kits", {})
    key = next((k for k in kits if k.lower() == brand.strip().lower()), None)
    if key is None:
        raise KeyError(f"no brand kit for '{brand}'")
    kits[key].update(fields)
    KITS_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _load.cache_clear()
    return kits[key]


def create_brand(brand: str, territories: list[str] | None = None) -> dict:
    """Add a brand-new, empty-but-valid kit to config/brand_kits.json and return it.

    Every field the cockpit's BrandKit type declares as required is present with an
    honest empty value (empty string/array/object) rather than a placeholder-looking
    default -- the UI's own "Not captured" / "Not available in this kit" treatment
    already handles rendering an empty field correctly, so a brand-new kit looks like
    every other kit's honest-gap state from the moment it's created, not like it's
    missing something the loader forgot to fill in.

    `territories` defaults to ["US"] (not empty, and not left for the caller to forget)
    specifically so the cockpit's territory-gated kit fetch (`getBrandKit(brand,
    territory)`) has a market to resolve against immediately -- an empty territories
    list would leave the new brand's workspace view stuck on "Loading..." with nothing
    to select. The New Brand setup flow (R2) always passes the user's confirmed
    territory explicitly; the default only covers other callers.

    Raises ValueError if the name is blank, or KeyError if a kit with this name
    (case-insensitively) already exists."""
    name = brand.strip()
    if not name:
        raise ValueError("brand name is required")
    if not KITS_JSON.exists():
        raise FileNotFoundError(str(KITS_JSON))
    data = json.loads(KITS_JSON.read_text(encoding="utf-8"))
    kits = data.setdefault("kits", {})
    if any(k.lower() == name.lower() for k in kits):
        raise KeyError(f"a brand kit named '{name}' already exists")

    skeleton = {
        "source_label": f"{name} (new, not yet set up)",
        "source_note": "New brand -- created via the cockpit's + Brand flow. No content ingested yet.",
        "company": "",
        "generic": "",
        "therapy_area": "",
        "indication": "",
        "territories": territories or ["US"],
        "lifecycle_stage": "",
        "success_measure": "",
        "branded": "",
        "primary_audience": "",
        "fiscal_frame": "",
        "tagline": "",
        "core_claim": "",
        "positioning_statement": "",
        "message_hierarchy": [],
        "approved_indication": "",
        "safety_reference": "",
        "clinical_data": [],
        "tone_pillars": [],
        "voice_do": [],
        "voice_dont": [],
        "guardrails": {"dos": [], "donts": []},
        "concepts": [],
        "message_pool": [],
        "claims": [],
        "references": [],
        "components": [],
        "personas": {"hcp": [], "patient": [], "payer": []},
        "competitors": [],
        "care_continuum": {},
        "identity": {"palette": [], "typography": ""},
    }
    kits[name] = skeleton
    KITS_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _load.cache_clear()
    return skeleton


def infer_brand_name(text: str) -> str:
    """Step 1 of the New Brand setup flow: read the ingested brand-plan document and
    name the brand it's about, instead of asking the user to type it -- the document
    already states it, usually in the first paragraph or a title.

    Never raises -- on any failure (LLM unavailable, empty/unusable reply) returns ""
    so the caller can fall back to asking the user to type the name themselves, same
    resilience contract as every other LLM call site in this repo."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import conversation_llm  # noqa: E402  (local import: keeps this module's own import
    # list free of the LLM dependency for callers that never touch this function)

    if not text.strip() or not conversation_llm.llm_available():
        return ""
    system = (
        "You are given the text of a pharma brand-plan document. Reply with ONLY the "
        "brand or drug name this document is about -- no titles, no punctuation, no "
        "explanation, just the name as it would appear in a brand switcher. If the "
        "document genuinely does not name a brand, reply with exactly: UNKNOWN"
    )
    try:
        client = conversation_llm._get_client()
        resp = client.messages.create(model=conversation_llm.MODEL, max_tokens=6000,
                                       system=system,
                                       messages=[{"role": "user", "content": text[:4000]}])
        name = next((b.text for b in resp.content if b.type == "text"), "").strip()
        name = name.strip('"\' \n')
        if not name or name.upper() == "UNKNOWN" or len(name) > 80:
            return ""
        return name
    except Exception:  # noqa: BLE001 -- never raise on an LLM failure
        return ""


def generate_random_brand_plan() -> dict:
    """Fabricates a complete fictional pharma brand-plan document from scratch -- for the
    New Brand setup flow's "generate one for me" escape hatch, when the user doesn't have
    a real brand-plan document handy but still wants to try the flow end-to-end. Returns
    {"name": ..., "text": ...} so the caller can feed `text` through the exact same
    ingestion path a real uploaded document takes (infer_brand_name would just re-derive
    `name` from it; returning both saves that round trip).

    Never raises -- on any failure (LLM unavailable, bad reply) returns {"name": "", "text": ""}
    so the caller can show an error and let the user upload a real file instead, same
    resilience contract as every other LLM call site in this repo."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import conversation_llm  # noqa: E402  (local import, see infer_brand_name above)

    if not conversation_llm.llm_available():
        return {"name": "", "text": ""}
    system = (
        "You invent entirely fictional pharma brand-plan documents for product demos -- "
        "never a real, currently-marketed drug. Invent a plausible brand name, generic "
        "name, company, therapy area, indication, and a short brand-plan narrative "
        "(6-10 paragraphs) covering: brand story/positioning, key clinical claims (with "
        "invented but plausible efficacy/safety data), target HCP and patient personas, "
        "competitive landscape, and messaging pillars. Reply with ONLY the document "
        "text -- no preamble, no markdown headers -- but make sure the very first line "
        "is exactly: Brand: <the brand name>"
    )
    try:
        client = conversation_llm._get_client()
        resp = client.messages.create(model=conversation_llm.MODEL, max_tokens=6000,
                                       system=system,
                                       messages=[{"role": "user", "content": "Generate one."}])
        text = next((b.text for b in resp.content if b.type == "text"), "").strip()
        if not text:
            return {"name": "", "text": ""}
        first_line = text.splitlines()[0]
        name = first_line.split(":", 1)[1].strip() if ":" in first_line else ""
        if not name or len(name) > 80:
            name = infer_brand_name(text)
        return {"name": name, "text": text}
    except Exception:  # noqa: BLE001 -- never raise on an LLM failure
        return {"name": "", "text": ""}


def is_available_in(kit: dict, territory: str) -> bool:
    """Whether `kit` is configured to run in `territory` (case-insensitive). A campaign
    should never be launchable in a market its brand kit hasn't been built for -- this is
    the actual gate, not just a display label."""
    return territory.strip().lower() in {t.lower() for t in kit.get("territories", [])}


def resolve_territory(kit: dict, territory: str | None) -> dict:
    """The kit as it applies to `territory`: the base kit's own fields (its content IS the
    primary/default territory -- there is no separate "US override" entry) with any
    `territory_content[territory]` override shallow-merged on top for every other
    configured territory. Every override in this kit is hand-authored and marked
    `illustrative: true` with a `note` explaining it is a placeholder -- never silently
    invented here. Returns a copy; never mutates the cached kit. `kit_for()` itself is left
    untouched so the plan-grounding call sites (orchestrator, studio_run) keep working
    against the base kit exactly as before."""
    merged = dict(kit)
    overrides = merged.pop("territory_content", {}) or {}
    match = next((v for k, v in overrides.items() if territory and k.lower() == territory.strip().lower()), None)
    if match:
        merged.update(match)
    merged["territory"] = territory or (kit.get("territories") or [None])[0]
    merged["illustrative"] = bool(match.get("illustrative")) if match else False
    merged["updated_at"] = kit_file_mtime()
    return merged


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
        return f"{kit['core_claim']}: {kit.get('tagline', '')}".strip(": ")
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
