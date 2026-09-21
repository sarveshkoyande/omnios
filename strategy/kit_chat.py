"""The brand-plan update flow's per-section chat agents + kickoff orchestrator.

Five sections, each scoped to a fixed subset of BrandKit fields (KIT_SECTIONS below) --
mirrors strategy/tab_chat.py's per-(project, stage) persisted-thread shape, but scoped to
kit-update sections instead of workspace tabs, and every agent turn proposes a
{field: {current, proposed}} diff (strategy/kit_drafts.py) rather than writing the kit
directly.

kickoff() is the orchestrator (fired once per section, concurrently, from the ingest
endpoint in app/server.py): each section's agent drafts a first-pass diff from the
ingested PDF text, grounded ONLY in that section's own fields on the *committed* kit --
never another section's in-progress draft, so no tab's unpublished edit can leak into
another tab's proposal before either publishes.

Same never-raise resilience contract as every other LLM call site in this repo: on
failure, upsert an empty diff with a plain-text explanation rather than raising.
"""
from __future__ import annotations

import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import brand_kit  # noqa: E402
import conversation_llm  # noqa: E402
import kit_drafts  # noqa: E402

# section -> (agent label, BrandKit field names this section owns). This table is the
# single boundary the grounding functions and the frontend diff UI both read from.
KIT_SECTIONS: dict[str, tuple[str, list[str]]] = {
    "kit-brand-details": ("Brand Details Agent",
                           ["indication", "fiscal_frame", "key_objective", "market_share",
                            "tagline", "core_claim", "positioning_statement"]),
    "kit-brand-persona": ("Brand Persona Agent",
                           ["tone_pillars", "voice_do", "voice_dont", "message_hierarchy",
                            "brand_personification"]),
    "kit-guardrails": ("Guardrails Agent", ["guardrails"]),
    "kit-hcp-persona": ("HCP Persona Agent", ["personas"]),
    "kit-hcp-segmentation": ("HCP Segmentation Agent", ["personas", "competitors"]),
}

_SYSTEM = """You are the {agent_name} for a pharma omnichannel brand-kit update flow.

You own ONLY these brand-kit fields for this section: {fields}. Never propose a change to
any other field -- another agent owns it.

You are given the brand's CURRENT committed values for your fields, and the TEXT of an
ingested brand-plan document. Compare them and propose updates ONLY where the document text
clearly supports a specific new value for one of your fields. If the document says nothing
relevant to a field, leave that field out of your diff entirely -- do not invent, guess, or
extrapolate a value. This is pharma content; a fabricated claim is worse than an empty diff.

Reply with ONLY one raw JSON object, no markdown fences, no prose outside it:
{{"reply": "<one or two sentences, plain language, describing what you found or didn't>",
  "diff": {{"<field_name>": <proposed new value, same shape as the current value>, ...}}}}

If nothing in the document supports a change to any of your fields, return an empty "diff"
object and say so plainly in "reply" -- never fabricate a field to have something to show."""

# Per-section addendum to _SYSTEM, appended only for the two sections this generates
# marketer-depth prose/structured content for -- every other section's prompt is
# byte-identical to before this dict existed (empty string, no change). A prose field
# is the highest-risk surface for a model to pad with generic filler, so both entries
# repeat the no-fabrication rule from _SYSTEM in their own terms.
_SECTION_GUIDANCE: dict[str, str] = {
    "kit-hcp-persona": """

For "personas" specifically: profile each HCP in personas.hcp the way a pharma
marketing team actually profiles one -- not just name/who/tier/voice. Where the
document text supports it, also propose per-HCP: practice_setting (setting, patient
volume, whatever is actually stated), goals (what they're trying to achieve for
patients), barriers (what gets in the way today), channel_preference (how they prefer
to be reached), objections (real reservations about the brand or therapy class), and
message_resonance (which message-hierarchy pillar lands best, and why). Also propose a
narrative: 2-4 sentences of prose describing this HCP the way a marketer writes a
persona bio -- not a restatement of the structured fields, actual connected prose.
Leave any of these sub-fields off a persona entirely when the document doesn't support
it for that specific HCP -- do not invent a generic-sounding goal or barrier just to
fill the shape. A missing sub-field is correct; a fabricated one is not.

CRITICAL: "personas" is one whole-object field -- your proposed "personas" value is
NOT merged with the current one, it REPLACES it entirely. Your proposed personas.hcp
array MUST include every persona from the CURRENT value, unchanged, except the one(s)
the document text actually gives you new information about. Never drop, omit, or
silently replace a persona the document didn't mention. Similarly, always include the
current personas.patient and personas.payer arrays unchanged unless the document
specifically supports a change to one of them. Dropping an untouched persona is data
loss, not an update -- treat it as seriously as fabricating one.""",
    "kit-brand-persona": """

For "brand_personification" specifically: describe this brand as if it were a person,
grounded in its existing tone_pillars/voice_do/voice_dont and whatever the ingested
document adds. Propose archetype (a short label, e.g. "The Trusted Expert"), traits (3-5
personality adjectives or short phrases), and narrative (2-4 sentences of prose painting
the brand as a person -- not a restatement of the tone pillars as a list). Same rule as
everywhere else: only propose this field when the brand's actual voice/tone material
supports a specific characterization -- a generic "confident and caring" archetype that
could describe any brand is not grounded, it's filler.""",
    # kit-hcp-segmentation also owns "personas" (for patient/payer) -- same
    # whole-object-replace hazard as kit-hcp-persona above, discovered while verifying
    # that section's new guidance: pre-existing risk, not introduced by this plan, but
    # cheap to close in the same place with the same one clause.
    "kit-hcp-segmentation": """

CRITICAL: "personas" is one whole-object field -- your proposed value REPLACES the
current one entirely, it is not merged. Always include personas.hcp unchanged unless
the document specifically supports a change to it, and likewise for whichever of
personas.patient/personas.payer you are not actively updating. Never drop an untouched
persona -- that is data loss, not an update.""",
}


def _strip_fence(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


def _parse_envelope(text: str) -> dict:
    cleaned = _strip_fence(text)
    if not cleaned:
        raise ValueError("empty response")
    if not cleaned.startswith("{"):
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            cleaned = cleaned[start:end + 1]
    # strict=False: the model asked for multi-sentence "narrative" prose (U3's persona
    # depth) reliably emits a literal newline inside a JSON string value rather than
    # the escaped \n strict JSON requires -- confirmed by reproducing "Unterminated
    # string"/"Expecting property name" failures on every retry attempt against
    # otherwise well-formed output. strict=False accepts literal control characters
    # inside strings (the one thing wrong with this output) without loosening any other
    # part of JSON's grammar.
    return json.loads(cleaned, strict=False)


def _short_error(e: Exception) -> str:
    """A user-facing summary of an LLM/parse failure -- never the raw exception text.

    Some providers (Azure's DefaultAzureCredential in particular) raise multi-paragraph
    messages listing every credential type they tried, which is meaningless to a brand-kit
    reviewer and was leaking straight into the chat reply. The real exception is still
    available server-side (the caller logs it); this only shortens what the user sees."""
    text = str(e).strip().splitlines()[0] if str(e).strip() else e.__class__.__name__
    if len(text) > 140:
        text = text[:140].rstrip() + "..."
    return text


def _current_values(kit: dict, fields: list[str]) -> dict:
    return {f: kit.get(f) for f in fields}


def _build_diff(current: dict, proposed: dict, allowed_fields: list[str]) -> dict:
    """{field: {current, proposed}} for every proposed field that is in this section's
    allowed set AND actually differs from the current value -- dropping any field outside
    the section's lane is the defense against the agent inventing a field out of scope."""
    diff = {}
    for field, new_value in (proposed or {}).items():
        if field not in allowed_fields:
            continue
        if new_value == current.get(field):
            continue
        diff[field] = {"current": current.get(field), "proposed": new_value}
    return diff


def _grounding_prompt(kit: dict, section: str, pdf_text: str, convo: str, user_message: str) -> tuple[str, str, list[str]]:
    agent_name, fields = KIT_SECTIONS[section]
    system = _SYSTEM.format(agent_name=agent_name, fields=", ".join(fields)) + _SECTION_GUIDANCE.get(section, "")
    current = _current_values(kit, fields)
    user_payload = (
        f"Current values for your fields:\n{json.dumps(current, indent=2)}\n\n"
        f"Ingested brand-plan document text:\n{pdf_text or '(no document ingested yet)'}\n\n"
        f"Conversation so far:\n{convo or '(none)'}\n\n"
        f"User: {user_message}"
    )
    return system, user_payload, fields


def _call_llm(system: str, user_payload: str) -> dict:
    """One turn, with one retry on malformed JSON -- same pattern as tab_chat.py's
    operations agent. The richer HCP/Brand persona payloads (nested arrays, prose
    narrative fields) give the model more surface area to produce invalid JSON on
    (an unescaped quote inside a narrative sentence, a dropped comma) than the
    original short-field sections did, so a bare first-try parse is no longer
    reliable enough for those two sections specifically -- but the retry is generic
    and helps every section equally."""
    client = conversation_llm._get_client()

    def _call(extra: str = "") -> dict:
        # 2000 was too small once the persona sections asked for prose + multiple
        # structured sub-fields: the Gemini path is a reasoning model, and max_tokens
        # here caps reasoning tokens AND the visible JSON output together -- a
        # reproduced failure showed ~1400 of 2000 tokens spent on internal reasoning
        # before the model even started the JSON, truncating the response mid-string
        # every time. 6000 leaves enough headroom for both on the richest section.
        resp = client.messages.create(model=conversation_llm.MODEL, max_tokens=6000,
                                       system=system, messages=[{"role": "user", "content": user_payload + extra}])
        text = next((b.text for b in resp.content if b.type == "text"), "")
        return _parse_envelope(text)

    try:
        return _call()
    except (ValueError, json.JSONDecodeError):
        return _call("\n\nYour previous response was not valid JSON. Return only one raw "
                      "JSON object with exactly two keys, \"reply\" and \"diff\" -- no markdown "
                      "fences, no prose outside the object, every string properly escaped.")


def kickoff(project_id: str, brand: str, section: str, pdf_text: str) -> dict:
    """Orchestrator entry point (A3): one section's auto-drafted first pass from the
    ingested PDF text. Never raises."""
    if section not in KIT_SECTIONS:
        raise ValueError(f"unknown kit-update section '{section}'")
    kit = brand_kit.kit_for(brand)
    if not kit:
        return kit_drafts.upsert_draft(project_id, brand, section, "drafting",
                                        {}) | {"reply": f"No brand kit found for '{brand}'."}
    if not conversation_llm.llm_available():
        return kit_drafts.upsert_draft(project_id, brand, section, "drafting", {}) | {
            "reply": "The LLM isn't configured, so I can't draft anything yet -- "
                     "you can still edit this section manually once that's wired up."}

    system, user_payload, fields = _grounding_prompt(kit, section, pdf_text, "", "Draft a first pass from the ingested document.")
    try:
        envelope = _call_llm(system, user_payload)
        diff = _build_diff(_current_values(kit, fields), envelope.get("diff") or {}, fields)
        reply = envelope.get("reply") or "Done."
        status = "awaiting_review" if diff else "drafting"
        draft = kit_drafts.upsert_draft(project_id, brand, section, status, diff)
        return {**draft, "reply": reply}
    except Exception as e:  # noqa: BLE001 -- never raise on an LLM/parse failure
        print(f"[kit_chat] kickoff failed for {brand}/{section}: {e!r}")  # full detail server-side only
        draft = kit_drafts.upsert_draft(project_id, brand, section, "drafting", {})
        return {**draft, "reply": f"Couldn't draft this section automatically ({_short_error(e)}). "
                                   "Nothing was changed -- tell me what to update instead."}


async def kickoff_all(project_id: str, brand: str, pdf_text: str) -> list[dict]:
    """Fires kickoff() for every section concurrently (R7) -- the orchestrator's whole job.
    Each section writes to its own (project, brand, section) row, so there's no cross-write
    between the concurrent calls."""
    results = await asyncio.gather(*[
        asyncio.to_thread(kickoff, project_id, brand, section, pdf_text)
        for section in KIT_SECTIONS
    ])
    return list(results)


def ask(project_id: str, brand: str, section: str, message: str, history: list[dict] | None = None) -> dict:
    """A normal chat turn (R5) -- the agent may revise its proposed diff based on the
    user's reply. Never raises."""
    if section not in KIT_SECTIONS:
        return {"reply": f"Unknown section '{section}'."}
    kit = brand_kit.kit_for(brand)
    if not kit:
        return {"reply": f"No brand kit found for '{brand}'."}
    if not conversation_llm.llm_available():
        return {"reply": "The LLM isn't configured, so I can't answer right now."}

    convo = "\n".join(f"{m.get('role')}: {m.get('text')}" for m in (history or [])[-20:])
    system, user_payload, fields = _grounding_prompt(kit, section, "(already ingested this session)", convo, message)
    try:
        envelope = _call_llm(system, user_payload)
        diff = _build_diff(_current_values(kit, fields), envelope.get("diff") or {}, fields)
        reply = envelope.get("reply") or "Done."
        if diff:
            kit_drafts.upsert_draft(project_id, brand, section, "awaiting_review", diff)
        return {"reply": reply, "diff": diff}
    except Exception as e:  # noqa: BLE001
        print(f"[kit_chat] ask failed for {brand}/{section}: {e!r}")  # full detail server-side only
        return {"reply": f"Couldn't process that ({_short_error(e)})."}
