"""Stage 2 — Extract.

Reads an `IngestedDocument` (stage 1) closely and populates a `StrategicContext`
object, citing a document page/section per fact via the model's `provenance`
dict. This stage only reads the document itself — no knowledge-graph or
market-signal enrichment happens here (that's stage 3, `enrich.py`); the point
of keeping them separate is so gap analysis (stage 4) can tell "the document
said this" apart from "we inferred this from outside context."

Reuses the existing LLM client wrapper (`strategy/conversation_llm.py`) rather
than building a second one, per the brief.
"""
from __future__ import annotations

import json
from pydantic import ValidationError

from strategy import conversation_llm
from strategy.planning_v2.ingest import IngestedDocument
from strategy.planning_v2.models import StrategicContext

MAX_DOC_CHARS = 60_000  # generous cap for a full strategic-plan deck/doc, well under model context

_SCHEMA_HINT = """Return ONLY a single raw JSON object (no markdown fences, no prose before or
after) matching exactly this shape:

{
  "brand": {"name": str, "molecule": str, "indication": str, "modality": str},
  "strategic_focus": [{"imperative": str, "definition": str}],
  "market_landscape": {"disease": str, "prevalence": str, "standard_of_care": str,
                        "prognosis": str, "competitive_class": str},
  "competitive_dynamics": {"class_context": str, "differentiation": str,
                            "comparison_guardrails": [str]},
  "challenges": [str],
  "opportunities": [str],
  "critical_success_factors": [{"id": str, "key_insight": str, "strategies": [str],
                                 "tactical_focus": [str], "guardrail": str}],
  "audiences": [{"role": "hcp"|"pathology"|"nurse_and_app"|"medical"|"patient",
                  "description": str, "needs": [str],
                  "gating_status": "open"|"gated"|"not_applicable", "gating_reason": str}],
  "account_archetypes": [{"type": str, "role": str, "characteristics": [str]}],
  "evidence": [{"trial_design": str, "endpoints": [str], "values": {str: str},
                "fair_balance_requirements": [str]}],
  "guardrails": [str],
  "references": [str],
  "provenance": {
    "<dotted field path, e.g. 'brand.name' or 'critical_success_factors.csf1'>":
      [{"source_type": "document", "source_id": "<the [p.N] / [slide.N] / [section.X] tag this fact came from>",
         "detail": "<short quote or paraphrase>", "confidence": <0.0-1.0 or null>}]
  }
}

Rules:
- Every non-empty field you populate from the document MUST have a matching provenance
  entry citing the exact source_id tag(s) (e.g. "p.4", "slide.12", "section.Market Landscape")
  the fact came from. Copy source_id tags verbatim from the bracketed tags in the document text.
- Only extract what the document actually states or clearly implies. Do NOT invent clinical
  facts, trial values, or competitive claims that are not in the text.
- If a whole field is genuinely absent from the document, leave it empty ("" or [] as
  appropriate) rather than guessing — stage 4 (gap analysis) handles what's missing, not you.
- critical_success_factors ids must be short unique slugs (e.g. "csf1", "csf2").
- gating_status for the "patient" audience MUST be "gated" unless the document explicitly
  states patient-facing materials are cleared/available, in which case use "open"; if the
  document says nothing about patient materials at all, use "gated" with
  gating_reason "Not addressed in source document; gating status assumed conservative default."
"""


def extract_strategic_context(doc: IngestedDocument, *, max_doc_chars: int = MAX_DOC_CHARS) -> StrategicContext:
    client = conversation_llm._get_client()
    document_text = doc.tagged_text(max_chars=max_doc_chars)

    system = (
        "You are the extraction stage of a pharma strategic-to-tactical planning engine. "
        "You read a strategic plan document closely and populate a structured Strategic "
        "Context Object from it, citing the exact source location for every fact you pull "
        "out. You never invent facts and you never fill gaps with guesses — that is a later "
        "stage's job.\n\n" + _SCHEMA_HINT
    )
    user = f"Document: {doc.filename} ({doc.format})\n\n{document_text}"

    data = _call_and_parse(client, system, user)
    try:
        return StrategicContext(**data)
    except ValidationError as exc:
        # One repair pass: hand the model its own output plus the validation error and ask
        # it to fix only what's broken, rather than failing the whole stage on a near-miss.
        repair_user = (
            f"Your previous JSON output failed validation with this error:\n{exc}\n\n"
            f"Here is the JSON you returned:\n{json.dumps(data)}\n\n"
            "Return a corrected JSON object matching the same schema, fixing only what's wrong."
        )
        data = _call_and_parse(client, system, repair_user)
        return StrategicContext(**data)  # let this raise if still broken — a real bug, not a retry-forever case


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
