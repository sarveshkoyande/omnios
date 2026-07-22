"""Rules-based (+ optional LLM sharpening) extraction of key details from an uploaded
strategic-plan document, to ground the Tactical Plan / Campaign Brief sections.

Deliberately tolerant: PDF text extraction (`document_intake.extract_text`) linearizes a
slide deck's visual layout into plain lines, so headings and body text don't always land
on predictable boundaries. Every regex here is a best-effort pull, never a hard parse --
missing matches just mean the calling section falls back to Omni OS's own strategy ctx
(see plan_document.py's `_sec_tactical_*` functions), same degrade-gracefully idiom used
throughout the app.
"""
from __future__ import annotations

import json
import re

_MAX_ITEMS = 6
_SNIPPET_LEN = 220

_CSF_LINE_RE = re.compile(r"^[ \t]*(?:CSF\s*#?\s*\d+|[1-3])\s+([A-Z][^\n]{10,120})$", re.MULTILINE)
_GUARDRAIL_RE = re.compile(
    r"GUARDRAIL[S]?\s*[:\n]\s*(.{20,400}?)(?:\n\s*\n|\n[A-Z][A-Z &/]{6,}|\Z)", re.IGNORECASE | re.DOTALL)
_EVIDENCE_RE = re.compile(r"\b((?:[Mm]edian\s+)?(?:OS|PFS|ORR|DoR|HR)\b[^\n]{0,120}\d[^\n]{0,80})")
_FOCUS_RE = re.compile(r"\b(IDENTIFY|ESTABLISH)\b[ \t]*\n?[ \t]*([A-Z][^\n]{10,160})", re.MULTILINE)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _dedupe(items: list[str], limit: int = _MAX_ITEMS) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if not it:
            continue
        key = it.lower()[:60]
        if key in seen:
            continue
        seen.add(key)
        out.append(it[:_SNIPPET_LEN])
        if len(out) >= limit:
            break
    return out


def _extract_rules_based(text: str) -> dict:
    csfs = _dedupe([_clean(m) for m in _CSF_LINE_RE.findall(text)])
    guardrails = _dedupe([_clean(m) for m in _GUARDRAIL_RE.findall(text)])
    evidence = _dedupe([_clean(m) for m in _EVIDENCE_RE.findall(text)])
    focus = _dedupe([f"{label}: {_clean(desc)}" for label, desc in _FOCUS_RE.findall(text)], limit=2)
    return {
        "csfs": csfs,
        "guardrails": guardrails,
        "evidence": evidence,
        "positioning": focus[-1] if focus else "",
    }


def _llm_sharpen(text: str) -> dict | None:
    """Optional: ask the LLM for a cleaner cut of the same fields. Falls back to None (caller
    keeps the rules-based dict) on any failure -- mirrors
    campaign_ops.py::_llm_fill_operational_detail."""
    try:
        import conversation_llm
        if not conversation_llm.llm_available():
            return None
        client = conversation_llm._get_client()
        sys_prompt = (
            "You read excerpts from a pharma brand strategic-plan document and pull out its key "
            "planning details. Return STRICT JSON only, no markdown fences, with exactly these keys: "
            "csfs (list of up to 4 short strings, each a named Critical Success Factor), "
            "guardrails (list of up to 6 short compliance/guardrail statements), "
            "evidence (list of up to 4 short strings, each one clinical/efficacy datapoint with its "
            "number), positioning (one sentence, the brand's core strategic positioning statement). "
            "Only use facts present in the text; do not invent numbers or claims. If a field isn't "
            "present in the text, return an empty list/string for it."
        )
        resp = client.messages.create(
            model=conversation_llm.MODEL, max_tokens=700, system=sys_prompt,
            messages=[{"role": "user", "content": text[:16000]}],
        )
        out_text = next((b.text for b in resp.content if b.type == "text"), "").strip()
        if out_text.startswith("```"):
            out_text = out_text.strip("`")
            out_text = out_text[4:] if out_text.lower().startswith("json") else out_text
        data = json.loads(out_text.strip())
        for key in ("csfs", "guardrails", "evidence"):
            if not isinstance(data.get(key), list):
                data[key] = []
        if not isinstance(data.get("positioning"), str):
            data["positioning"] = ""
        return data
    except Exception:  # noqa: BLE001 -- sharpening only, rules-based extraction always stands in
        return None


def extract_strategic_source(text: str, source_name: str = "") -> dict | None:
    """Best-effort extraction of CSFs/guardrails/evidence/positioning from an uploaded
    strategic-plan document's extracted text. Returns None for empty input; otherwise
    always returns a dict (fields may just be empty lists if nothing matched)."""
    if not text or not text.strip():
        return None
    rules_based = _extract_rules_based(text)
    sharpened = _llm_sharpen(text)
    result = sharpened if sharpened and any(sharpened.get(k) for k in ("csfs", "guardrails", "evidence")) \
        else rules_based
    result.setdefault("positioning", rules_based.get("positioning", ""))
    result["source_name"] = source_name
    result["has_content"] = bool(result.get("csfs") or result.get("guardrails") or result.get("evidence"))
    return result
