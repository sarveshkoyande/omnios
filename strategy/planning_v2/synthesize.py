"""Stage 6 — Synthesize.

Generates the `TacticalPlan` and `BusinessRequirementsBrief` from the enriched
`StrategicContext`, the enrichment evidence, and the (by now resolved) `Gap`
list — every gap should be `inferable=True` by this point, either because
stage 4 inferred it originally or because the user answered it and
`questions.apply_answer()` folded the answer back in as a resolved
assumption. Synthesis does not re-litigate what's missing; it builds the plan
from what's now known.

Reuses the existing LLM client wrapper (`conversation_llm`), not a new one.
The compliance validator (Phase 6, `compliance.py`) runs as a SEPARATE pass
over this stage's output — this module is not responsible for policing its
own compliance, per the brief's explicit instruction not to trust generation
to self-police.
"""
from __future__ import annotations

import json

from pydantic import ValidationError

from strategy import conversation_llm
from strategy.planning_v2.enrich import EnrichmentBundle
from strategy.planning_v2.models import BusinessRequirementsBrief, Gap, StrategicContext, TacticalPlan

MAX_TOKENS = 16000

_SCHEMA_HINT = """Return ONLY a single raw JSON object (no markdown fences, no prose before or
after) of this exact shape:

{
  "tactical_plan": {
    "strategic_recap": str,
    "investment_thesis": str,
    "flighting": {"summary": str, "items": [obj], "csf_mapping": [str], "guardrails": [str]},
    "field_approach": {"summary": str, "items": [obj], "csf_mapping": [str], "guardrails": [str]},
    "targeting_matrix": {"summary": str, "items": [obj], "csf_mapping": [str], "guardrails": [str]},
    "omnichannel_strategy": [{"channel": str, "role": str,
                               "branded_or_unbranded": "branded"|"unbranded"|"both",
                               "csf_mapping": [str]}],
    "media_flighting": {"summary": str, "items": [obj], "csf_mapping": [str], "guardrails": [str]},
    "trigger_based_engagement": {"summary": str, "items": [obj], "csf_mapping": [str], "guardrails": [str]},
    "content_inventory": {"summary": str, "items": [obj], "csf_mapping": [str], "guardrails": [str]},
    "congress_scientific_exchange": {"summary": str, "items": [obj], "csf_mapping": [str], "guardrails": [str]},
    "peer_to_peer": {"summary": str, "items": [obj], "csf_mapping": [str], "guardrails": [str]},
    "nurse_app_education": {"summary": str, "items": [obj], "csf_mapping": [str], "guardrails": [str]},
    "account_strategy": {"summary": str, "items": [obj], "csf_mapping": [str], "guardrails": [str]},
    "account_focus": {"summary": str, "items": [obj], "csf_mapping": [str], "guardrails": [str]},
    "patient_strategy": {"summary": str, "items": [obj], "gated": bool, "gating_logic": str},
    "testing_enablement_digital": {"summary": str, "items": [obj], "csf_mapping": [str], "guardrails": [str]},
    "measurement": [{"csf_id": str, "leading_indicators": [str], "lagging_indicators": [str],
                      "targets": {"<kpi name>": {"value": number|str|null, "is_placeholder": bool, "note": str}}}],
    "appendices": {"competitive_context": str, "measurement": str, "guardrails_recap": [str]},
    "provenance": {"<dotted field path>": [{"source_type": "document"|"knowledge_graph"|
                    "market_signals"|"expert_prior", "source_id": str, "detail": str, "confidence": number|null}]}
  },
  "brb": {
    "initiative_summary": str,
    "workstreams": [{"name": str, "tactical_sections": [str], "deliverables": [str],
                      "proposed_owning_team": str, "dependencies": [str], "parallelizable": bool,
                      "suggested_sla": str}],
    "compliance_checkpoints": [{"checkpoint_type": "mlr_gate"|"firewall_point", "location": str,
                                 "description": str}]
  }
}

Rules:
- Keep it concise: 2-4 "items" per TacticalSection, 1-2 sentence "summary" per section, at
  most 3-4 "measurement" rows. Depth matters less here than every section being genuinely
  grounded — do not pad with filler items just to look thorough.
- Ground every tactical section in the strategic context's critical_success_factors — every
  csf_mapping / csf_id you write must reference a CSF id that actually exists in the input.
- Every budget, volume, share, and KPI figure in "measurement[].targets" MUST use the
  {"value","is_placeholder","note"} shape with "is_placeholder": true and a note explaining it
  requires brand-team data, UNLESS the strategic context or a resolved gap's suggested_default
  explicitly supplied that number — in that case still include it but you may set
  is_placeholder to false with a note citing where the number came from.
- patient_strategy.gated MUST mirror the strategic context's patient audience gating_status
  ("gated" -> true, "open" -> false). If gated, populate gating_logic with what must clear
  before patient tactics activate.
- Every workstream in the BRB must map to at least one real tactical_plan section name from
  the shape above.
- compliance_checkpoints must include at minimum: one mlr_gate covering any HCP-facing
  efficacy/claims content, and one firewall_point if any account/field content differs from
  medical-only content (first-line, combination, or investigational discussion).
- Do not invent clinical facts, budgets, or competitive claims beyond what the strategic
  context, enrichment evidence, and resolved gaps already establish.
- provenance keys should reference where each non-obvious section's content came from — cite
  "expert_prior" with a short rationale for anything synthesized from planning convention
  rather than a specific source.
"""


def synthesize(sco: StrategicContext, bundle: EnrichmentBundle, gaps: list[Gap]) -> tuple[TacticalPlan, BusinessRequirementsBrief]:
    unresolved = [g.field for g in gaps if not g.inferable]
    if unresolved:
        raise ValueError(
            f"synthesize() called with unresolved true gaps still open: {unresolved} — "
            "resolve them via questions.apply_answer() (or accept their suggested_default) "
            "before synthesis; stage 6 does not re-derive what stage 4/5 already flagged."
        )

    client = conversation_llm._get_client()
    system = (
        "You are the synthesis stage of a pharma strategic-to-tactical planning engine. "
        "You turn a fully-resolved strategic context (document facts + knowledge-graph/"
        "market-signal enrichment + resolved gaps) into a structured Tactical Plan and "
        "Business Requirements Brief. You are NOT the compliance check — a separate "
        "validator reviews your output after — but you should still ground every section "
        "in the strategic context rather than inventing content.\n\n" + _SCHEMA_HINT
    )
    payload = {
        "strategic_context": sco.model_dump(mode="json"),
        "enrichment_evidence": {
            "knowledge_graph_hits": [h.model_dump(mode="json") for h in bundle.kg_hits],
            "market_signal_hits": [h.model_dump(mode="json") for h in bundle.signal_hits],
        },
        "resolved_gaps": [g.model_dump(mode="json") for g in gaps],
    }

    data = _call_and_parse(client, system, json.dumps(payload))
    try:
        return TacticalPlan(**data["tactical_plan"]), BusinessRequirementsBrief(**data["brb"])
    except (ValidationError, KeyError) as exc:
        repair_user = (
            f"Your previous JSON output failed validation with this error:\n{exc}\n\n"
            f"Here is the JSON you returned:\n{json.dumps(data)}\n\n"
            "Return a corrected JSON object matching the same {\"tactical_plan\":..., \"brb\":...} shape, "
            "fixing only what's wrong."
        )
        data = _call_and_parse(client, system, repair_user)
        return TacticalPlan(**data["tactical_plan"]), BusinessRequirementsBrief(**data["brb"])


def _call_and_parse(client, system: str, user: str) -> dict:
    text = _call_llm(client, system, user)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        # One syntax-repair round trip before giving up — a near-miss (stray comma, an
        # unescaped quote) is a formatting slip, not a reason to fail the whole stage.
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
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = next(b.text for b in resp.content if b.type == "text").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[4:] if text.lower().startswith("json") else text
    return text.strip()
