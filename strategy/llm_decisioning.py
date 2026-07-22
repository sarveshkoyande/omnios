"""LLM-first decision helpers for the active Planning Studio path.

The deterministic planning code still builds a complete draft so the app remains usable
when Foundry or Cognee is unavailable. This module is the LLM decision layer on top:
it reads the captured brief, uploaded strategic-source extraction, Cognee/process-graph
grounding, and deterministic draft, then asks the Foundry-backed model to interpret,
question, recommend, and synthesize.
"""
from __future__ import annotations

import copy
import json
import re
import sys
import os
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import conversation_llm
import process_knowledge
import decision_spine


def _strip_json(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[4:] if text.lower().startswith("json") else text
    return text.strip()


def _parse_json_or_raise(text: str) -> dict:
    text = _strip_json(text)
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            return json.loads(match.group(0))
        raise


def _diagnostics(extra: dict | None = None) -> dict:
    data = {
        "resource": conversation_llm.RESOURCE,
        "endpoint_override": bool(conversation_llm.ENDPOINT),
        "endpoint": conversation_llm.ENDPOINT or f"https://{conversation_llm.RESOURCE}.services.ai.azure.com/anthropic/",
        "model": conversation_llm.MODEL,
        "api_version": conversation_llm.API_VERSION or "",
        "api_key_loaded": bool(os.environ.get(conversation_llm.API_KEY_ENV)),
    }
    if extra:
        data.update(extra)
    return data


_LAST_STATUS = {
    "engine": "azure-foundry",
    "ok": None,
    "detail": "not yet attempted",
    "ts": None,
    "diagnostics": _diagnostics(),
}


def _set_status(ok: bool | None, detail: str, diagnostics: dict | None = None) -> None:
    global _LAST_STATUS
    _LAST_STATUS = {
        "engine": "azure-foundry",
        "ok": ok,
        "detail": detail,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "diagnostics": _diagnostics(diagnostics),
    }


def get_llm_status() -> dict:
    return dict(_LAST_STATUS)


def _call_json(system: str, payload: dict, max_tokens: int = 1400) -> dict:
    client = conversation_llm._get_client()
    user = json.dumps(payload, ensure_ascii=False)
    resp = client.messages.create(
        model=conversation_llm.MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = next(b.text for b in resp.content if b.type == "text")
    try:
        return _parse_json_or_raise(text)
    except Exception:
        repair_system = (
            "You are a JSON repair tool. Convert the user's content into strict JSON only. "
            "Return only the repaired JSON object, no markdown, no commentary."
        )
        repair = client.messages.create(
            model=conversation_llm.MODEL,
            max_tokens=max_tokens,
            system=repair_system,
            messages=[{"role": "user", "content": text}],
        )
        repair_text = next(b.text for b in repair.content if b.type == "text")
        return _parse_json_or_raise(repair_text)


def _ctx_pack(ctx: dict, step: dict | None = None) -> dict:
    topics = list(step.get("topics", [])) if step else list(process_knowledge.BRIEF_TOPICS)
    graph_hits = {}
    try:
        # Uses the existing Cognee-backed process knowledge seam. Returns {} when the graph
        # is disabled/unavailable, preserving graceful fallback while still being graph-first
        # whenever the local knowledge layer is ready.
        graph_hits = process_knowledge.ground_many(
            topics,
            ctx.get("brand", ""),
            ctx.get("therapy_area", ""),
            max_chars=900,
        )
    except Exception:  # noqa: BLE001
        graph_hits = ctx.get("process_grounding") or {}

    return {
        "brief": ctx.get("brief") or ctx.get("slots") or {},
        "brief_grounding": ctx.get("brief_grounding") or {},
        "brand": ctx.get("brand"),
        "therapy_area": ctx.get("therapy_area"),
        "inferred": ctx.get("inferred") or {},
        "strategic_source": ctx.get("strategic_source") or {},
        "brand_kit": ctx.get("brand_kit") or {},
        "competitors": ctx.get("competitors") or [],
        "bam": ctx.get("bam") or {},
        "message_flow": ctx.get("message_flow") or {},
        "strategy": ctx.get("strategy") or {},
        "kpi": ctx.get("kpi") or {},
        "process_graph_hits": graph_hits,
        "decision_stage": decision_spine.stage_for(step["id"]) if step else None,
    }


def _clean_text(value, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _clean_option(value, fallback: dict | None = None) -> dict | None:
    fallback = fallback or {}
    if isinstance(value, str):
        label = value.strip()
        source = ""
    elif isinstance(value, dict):
        label = str(value.get("label") or "").strip()
        source = str(value.get("source") or "").strip()
    else:
        label = ""
        source = ""
    if not label:
        label = str(fallback.get("label") or "").strip()
    if not source:
        source = str(fallback.get("source") or "").strip()
    if not label:
        return None
    option = {"label": label}
    if source:
        option["source"] = source
    return option


def _normalize_ask_payload(out: dict, draft: dict, step: dict) -> dict:
    """Accept only the defined StudioAsk JSON shape; fall back field-by-field to draft."""
    merged = copy.deepcopy(draft)
    if not isinstance(out, dict):
        out = {}

    text = _clean_text(out.get("text"), "")
    if text:
        merged["text"] = text
    elif not _clean_text(merged.get("text")):
        merged["text"] = _clean_text(merged.get("question_focus") or step.get("ask"), "Confirm the next planning decision.")

    for key in ("evidence_basis", "why", "recommendation_reason"):
        value = _clean_text(out.get(key), "")
        if value:
            merged[key] = value

    rec = _clean_option(out.get("recommendation"), merged.get("recommendation") or {})
    if rec:
        merged["recommendation"] = rec
    else:
        fallback_label = _clean_text(merged.get("question_focus") or step.get("ask"), "Confirm the recommended path")
        merged["recommendation"] = {"label": fallback_label, "source": "grounded fallback"}

    raw_options = out.get("options") if isinstance(out.get("options"), list) else merged.get("options") or []
    cleaned_options: list[dict] = []
    seen = {merged["recommendation"]["label"].strip().lower()}
    for item in raw_options:
        option = _clean_option(item)
        if not option:
            continue
        key = option["label"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned_options.append(option)
    merged["options"] = cleaned_options[:3]

    if "free_text" in out:
        merged["free_text"] = bool(out.get("free_text"))
    else:
        merged["free_text"] = bool(merged.get("free_text", True))

    if not _clean_text(merged.get("recommendation_reason")):
        merged["recommendation_reason"] = _clean_text(merged.get("why") or merged.get("evidence_basis"), "")
    return merged


def refine_studio_ask(ctx: dict, step: dict, draft: dict) -> dict:
    """Rewrite the grounded draft into a natural, LLM-authored question.

    Falls back to the draft only when Foundry is genuinely unavailable or errors.
    """
    if not draft:
        return draft
    if not conversation_llm.llm_available():
        out = copy.deepcopy(draft)
        out["source"] = "deterministic-fallback"
        out["llm_status"] = {
            "engine": "azure-foundry",
            "ok": False,
            "detail": "Claude not configured enough to attempt; using deterministic fallback.",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "diagnostics": _diagnostics({"llm_available": False}),
        }
        _set_status(False, out["llm_status"]["detail"], {"llm_available": False})
        return out

    try:
        start = time.time()
        prompt_draft = copy.deepcopy(draft)
        prompt_draft.pop("text", None)
        prompt_draft.pop("llm_status", None)
        prompt_draft.pop("source", None)
        payload = {
            "step": step,
            "draft": prompt_draft,
            "required_schema": {
                "text": "string, non-empty, one concise question under 28 words",
                "evidence_basis": "string, non-empty",
                "why": "string, non-empty",
                "recommendation": {"label": "string, non-empty", "source": "string, non-empty"},
                "recommendation_reason": "string, non-empty, 1-2 short sentences",
                "options": [{"label": "string, non-empty", "source": "string, non-empty"}],
                "free_text": "boolean",
            },
            "context": _ctx_pack(ctx, step),
            "guidance": {
                "tone": "natural, specific, grounded, slightly conversational",
                "requirements": [
                    "Keep text to one concise question, ideally under 28 words.",
                    "Write the question from scratch; do not reuse any existing draft sentence or template wording.",
                    "Return every field in required_schema with the exact types shown.",
                    "Never return blank labels, blank sources, empty recommendation, or empty option rows.",
                    "Use the uploaded strategic-source extraction when present.",
                    "Use the SME process graph and brief grounding to shape the question.",
                    "Keep the recommendation/options tightly grounded in the actual context.",
                    "Provide recommendation_reason as 1-2 short sentences explaining why the recommended option is the best grounded default.",
                    "Never invent facts not supported by the input context.",
                ],
            },
        }
        system = (
            "You rewrite one planning-studio ask card for a pharma omnichannel planning tool.\n"
            "Return STRICT JSON only with keys: text, evidence_basis, why, recommendation, recommendation_reason, options, free_text.\n"
            "Required shape: recommendation is an object with non-empty label and source; options is an array of objects with non-empty label and source; free_text is boolean.\n"
            "Do not return empty strings, nulls, markdown, comments, or extra keys.\n"
            "Text must be one concise question, ideally under 28 words, with no long setup paragraph. The question must be freshly written from scratch, not a paraphrase of any draft text. Use question_focus,\n"
            "context, the uploaded strategic-source extraction, and SME grounding to make it feel natural, specific,\n"
            "and varied across sections. Recommendation and options must stay grounded. recommendation_reason should explain the recommended option's rationale in 1-2 short sentences. If a detail is not supported,\n"
            "leave it out rather than inventing it."
        )
        out = _call_json(system, payload, max_tokens=900)
        merged = _normalize_ask_payload(out, draft, step)
        merged["source"] = "ai"
        status = {
            "engine": "azure-foundry",
            "ok": True,
            "detail": "Claude answered this studio ask.",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "diagnostics": _diagnostics({"latency_ms": int((time.time() - start) * 1000)}),
        }
        _set_status(True, status["detail"], {"latency_ms": int((time.time() - start) * 1000)})
        merged["llm_status"] = status
        return merged
    except Exception as exc:  # noqa: BLE001
        short = str(exc).strip().splitlines()[0][:500]
        detail = f"Claude ask rewrite failed ({short}); used deterministic fallback."
        error_diagnostics = {
            "exception_type": type(exc).__name__,
            "exception": short,
        }
        _set_status(False, detail, error_diagnostics)
        out = copy.deepcopy(draft)
        out["source"] = "deterministic-fallback"
        out["llm_status"] = {
            "engine": "azure-foundry",
            "ok": False,
            "detail": detail,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "diagnostics": _diagnostics(error_diagnostics),
        }
        return out


def enhance_campaign_brief(ctx: dict, draft: dict) -> dict:
    """LLM-synthesize a brief summary while preserving the structured draft.

    The draft still carries the structured plan data, but the LLM can add a concise
    synthesis that reflects the uploaded strategic document and the SME knowledge base.
    """
    if not draft:
        return draft
    if not conversation_llm.llm_available():
        out = copy.deepcopy(draft)
        out.setdefault("source_summary", draft.get("source_summary") or {})
        out["source_summary"].setdefault(
            "basis",
            "Deterministic Campaign Brief composed from the captured brief, decision records, campaign-ops skeleton, and SME process grounding.",
        )
        out["llm_status"] = {"engine": "azure-foundry", "ok": False,
                              "detail": "Claude not reachable or not configured; using deterministic brief fallback.",
                              "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        _set_status(False, out["llm_status"]["detail"])
        return out

    try:
        prompt_draft = copy.deepcopy(draft)
        payload = {
            "draft": prompt_draft,
            "context": _ctx_pack(ctx, None),
            "guidance": {
                "goal": "Write a concise, natural-language synthesis that reflects the actual campaign, the SME knowledge base, and any uploaded strategic-source document.",
                "requirements": [
                    "Do not remove structured fields from the draft.",
                    "Add or refresh source_summary basis/insights in a way that references the actual strategic source if present.",
                    "Use the brief and campaign-op context to keep the brief human and specific, not generic.",
                ],
            },
        }
        system = (
            "You synthesize a pharma campaign brief from structured planning data.\n"
            "Return STRICT JSON only with the same top-level keys as the draft, preserving nested structure.\n"
            "You may improve source_summary, add concise llm_synthesis or notes fields, and tighten language, but do not\n"
            "invent facts or discard structured content. Use the uploaded strategic source and SME grounding when present."
        )
        out = _call_json(system, payload, max_tokens=1200)
        merged = copy.deepcopy(draft)
        for key, value in out.items():
            if value is not None:
                merged[key] = value
        merged.setdefault("source_summary", draft.get("source_summary") or {})
        merged["source_summary"].setdefault("basis", "LLM-synthesized campaign brief grounded in the captured brief and SME knowledge.")
        status = {
            "engine": "azure-foundry",
            "ok": True,
            "detail": "Claude synthesized the campaign brief.",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        _set_status(True, status["detail"])
        merged["llm_status"] = status
        return merged
    except Exception as exc:  # noqa: BLE001
        short = str(exc).strip().splitlines()[0][:200]
        detail = f"Claude brief synthesis failed ({short}); used deterministic fallback."
        _set_status(False, detail)
        out = copy.deepcopy(draft)
        out.setdefault("source_summary", draft.get("source_summary") or {})
        out["source_summary"].setdefault(
            "basis",
            "Deterministic Campaign Brief composed from the captured brief, decision records, campaign-ops skeleton, and SME process grounding.",
        )
        out["llm_status"] = {"engine": "azure-foundry", "ok": False, "detail": detail,
                              "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        return out
