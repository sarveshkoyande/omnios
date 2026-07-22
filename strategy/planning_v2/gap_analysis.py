"""Stage 4 — Gap analysis.

Compares the enriched `StrategicContext` (+ `EnrichmentBundle`) against the
`TacticalPlan` schema and classifies every field that needs a business
decision into one of three buckets:

  - present    — the document/KG/signals already answer it directly. No Gap
                 object is emitted; there is nothing to log or ask.
  - inferable  — not directly stated, but a reasonable expert default or a
                 strong enrichment signal resolves it. Emits a `Gap` with
                 `inferable=True`, a `suggested_default`, and NO question —
                 this is the record of an assumption made on the user's
                 behalf, not something to interrupt them with.
  - true gap   — genuinely unresolved by document, KG, or signals, AND no
                 sensible expert prior exists. Emits a `Gap` with
                 `inferable=False` and a `question` — this is the only
                 bucket stage 5 (pointed questions) is allowed to surface.

This classification is delegated to the LLM (reusing `conversation_llm`, not a
second client) rather than a hand-rolled keyword-matching rule table: "is this
genuinely missing, or could I have inferred it" is exactly the kind of
judgment call a fixed heuristic gets wrong in both directions (too eager to
ask, or silently inventing a fact it shouldn't have). The hard rules the brief
cares about — cap the set, rank by impact, tie to a section, never ask what
stage 3/4 could resolve — are enforced structurally by `Gap`'s own validators
plus the filtering in `questions.py`, not left to the model's discretion.
"""
from __future__ import annotations

import json

from pydantic import ValidationError

from strategy import conversation_llm
from strategy.planning_v2.enrich import EnrichmentBundle
from strategy.planning_v2.models import Gap, StrategicContext, TacticalPlan

KNOWN_SECTIONS = sorted(set(TacticalPlan.model_fields) - {"provenance"})

_SCHEMA_HINT = f"""The Tactical Plan has these sections (use these EXACT names for
"tactical_section_blocked" — no others):
{json.dumps(KNOWN_SECTIONS)}

For each section that needs a business decision to populate meaningfully, decide whether
the information needed is:
  - PRESENT — the strategic context or enrichment evidence already states it directly.
    Do not emit anything for this field.
  - INFERABLE — not directly stated, but a reasonable expert default (pharma omnichannel
    planning convention) or a strong enrichment signal resolves it well enough to proceed.
    Emit a Gap with "inferable": true, a concrete "suggested_default", and "question": null.
  - TRUE GAP — genuinely unresolved and no sensible default exists; the tactical section
    cannot be responsibly populated without asking. Emit a Gap with "inferable": false, a
    "question" a real planner would ask, and a "suggested_default" the user can accept
    instead of typing (never leave suggested_default null for a true gap either).

Rules (hard requirements):
- Never emit a gap for something already present in the strategic context or enrichment
  evidence — check both closely before deciding something is missing.
- Rank every emitted Gap by "impact_rank" (1 = most consequential to the tactical plan's
  shape/content; higher numbers = less consequential). Ranks must be unique, starting at 1.
- Tie every Gap to exactly one "tactical_section_blocked" from the list above.
- "sources_attempted" must list every source you actually checked before concluding this
  field needed a Gap record — normally ["document", "knowledge_graph", "market_signals"].
- Prefer INFERABLE over TRUE GAP whenever a defensible default exists — the question set
  downstream is capped at 5-8 items, so only genuinely decision-changing unknowns should
  be true gaps.
- Emit at most 12 Gap records total, covering only sections that materially need a
  decision — not one per section for its own sake. Keep "why_needed", "question", and
  "suggested_default" each to one concise sentence so the full response fits comfortably.

Return ONLY a single raw JSON object (no markdown fences, no prose) of this exact shape:
{{"gaps": [
  {{"field": str, "tactical_section_blocked": str, "why_needed": str, "inferable": bool,
    "sources_attempted": ["document"|"knowledge_graph"|"market_signals", ...],
    "question": str | null, "suggested_default": str | null, "impact_rank": int}}
]}}"""


def analyze_gaps(sco: StrategicContext, bundle: EnrichmentBundle) -> list[Gap]:
    client = conversation_llm._get_client()
    system = (
        "You are the gap-analysis stage of a pharma strategic-to-tactical planning engine. "
        "You compare a strategic context (already extracted from a document and enriched "
        "with knowledge-graph notes and market signals) against what a Tactical Plan needs, "
        "and decide exactly what's missing versus what can be reasonably inferred.\n\n" + _SCHEMA_HINT
    )
    payload = {
        "strategic_context": sco.model_dump(mode="json"),
        "enrichment_evidence": {
            "knowledge_graph_hits": [h.model_dump(mode="json") for h in bundle.kg_hits],
            "market_signal_hits": [h.model_dump(mode="json") for h in bundle.signal_hits],
        },
    }
    data = _call_and_parse(client, system, json.dumps(payload))
    return _build_gaps(data)


def _build_gaps(data: dict) -> list[Gap]:
    gaps: list[Gap] = []
    errors: list[str] = []
    for row in data.get("gaps", []):
        try:
            gaps.append(Gap(**row))
        except ValidationError as exc:
            errors.append(f"{row.get('field', '?')}: {exc}")
    if errors:
        print(f"[planning_v2.gap_analysis] dropped {len(errors)} malformed gap(s): {errors}")

    bad_sections = [g.field for g in gaps if g.tactical_section_blocked not in KNOWN_SECTIONS]
    if bad_sections:
        raise ValueError(
            f"gap analysis returned unknown tactical_section_blocked for field(s) {bad_sections} "
            f"— must be one of {KNOWN_SECTIONS}"
        )

    ranks = [g.impact_rank for g in gaps]
    if len(ranks) != len(set(ranks)):
        # Re-rank deterministically by original order rather than failing the whole stage —
        # a duplicate rank is a formatting slip, not a reason to lose the analysis.
        for i, g in enumerate(gaps, start=1):
            g.impact_rank = i
    return sorted(gaps, key=lambda g: g.impact_rank)


def _call_and_parse(client, system: str, user: str) -> dict:
    text = _call_llm(client, system, user)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        repair_user = (
            f"Your previous response was not valid JSON: {exc}\n\n"
            f"Here is what you returned:\n{text}\n\n"
            "Return the corrected JSON only, same shape, no markdown fences, no prose."
        )
        text = _call_llm(client, system, repair_user)
        return json.loads(text)


def _call_llm(client, system: str, user: str) -> str:
    resp = client.messages.create(
        model=conversation_llm.MODEL,
        max_tokens=8000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = next(b.text for b in resp.content if b.type == "text").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[4:] if text.lower().startswith("json") else text
    return text.strip()
