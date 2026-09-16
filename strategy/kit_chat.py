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
                           ["tone_pillars", "voice_do", "voice_dont", "message_hierarchy"]),
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
    return json.loads(cleaned)


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
    system = _SYSTEM.format(agent_name=agent_name, fields=", ".join(fields))
    current = _current_values(kit, fields)
    user_payload = (
        f"Current values for your fields:\n{json.dumps(current, indent=2)}\n\n"
        f"Ingested brand-plan document text:\n{pdf_text or '(no document ingested yet)'}\n\n"
        f"Conversation so far:\n{convo or '(none)'}\n\n"
        f"User: {user_message}"
    )
    return system, user_payload, fields


def _call_llm(system: str, user_payload: str) -> dict:
    client = conversation_llm._get_client()
    resp = client.messages.create(model=conversation_llm.MODEL, max_tokens=2000,
                                   system=system, messages=[{"role": "user", "content": user_payload}])
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return _parse_envelope(text)


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
