"""Field-shape hints and the JSON envelope parser for brand-kit LLM proposals.

What remains of the retired brand-plan guided update flow (its per-section agents,
kickoff orchestrator and routes were removed when the Agentic Brand Journey replaced it,
plan docs/plans/2026-09-24-0629-feat-agentic-brand-journey-plan.md U8). The journey's
agent turns (strategy/brand_journey.py) reuse FIELD_SHAPES and parse_envelope.
"""
from __future__ import annotations

import json


# Explicit JSON shape for every structured (non-scalar) field an agent can propose,
# matching cockpit/src/types.ts's BrandKit interface field-for-field. "Same shape as the
# current value" (in _SYSTEM) is meaningless for a brand-new kit, whose skeleton fields
# start as empty arrays/objects (strategy/brand_kit.py's create_brand()) -- nothing to
# imitate -- so a first-pass kickoff on a freshly created brand had nothing to anchor a
# proposed shape to and would invent its own reasonable-looking but wrong one (e.g. a
# message_hierarchy object with hcp_messages/patient_messages instead of the array of
# {pillar, claim, evidence} the frontend renders; competitors as plain strings instead of
# {name, threat, detail}; personas with invented field names instead of
# name/who/tier/voice). The proposed value would still get written to
# config/brand_kits.json on publish, but the UI can't render it -- silently invisible,
# not an error. Included unconditionally (not just when the current value is empty) so
# an existing kit's own shape can't drift either.
FIELD_SHAPES: dict[str, str] = {
    "message_hierarchy": '[{"pillar": "<pillar name>", "claim": "<supporting claim>", '
                          '"evidence": "<citation or evidence for the claim>"}, ...]',
    "market_share": '{"current": "<e.g. \\"6%\\">", "target": "<e.g. \\"12%\\">"}',
    "guardrails": '{"dos": [{"category": "<short category>", "text": "<the do>"}], '
                  '"donts": [{"category": "<short category>", "text": "<the don\'t>"}]}',
    "competitors": '[{"name": "<competitor name>", "threat": "<Low, Medium, or High>", '
                    '"detail": "<why they matter>"}, ...]',
    "personas": '{"hcp": [{"name": "<persona name/title>", "who": "<who this persona is>", '
                '"tier": "<segment tier, e.g. Primary or Secondary>", '
                '"voice": "<how they speak / what tone resonates>"}], '
                '"patient": [<same base shape as hcp>], "payer": [<same base shape as hcp>]} '
                '-- every persona needs at least name/who/tier/voice; the marketer-depth '
                'sub-fields described below are additional, not a replacement for these.',
}


def _strip_fence(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


def parse_envelope(text: str) -> dict:
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
