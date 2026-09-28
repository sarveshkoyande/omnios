"""The Flow Planner's three model calls, and what happens without them.

Ported from the reference project's `app/flow/llm.py`, with the model client
swapped: the reference project calls AWS Bedrock directly; this port goes
through `strategy.conversation_llm` (Azure AI Foundry, then Gemini), the only
LLM path OmniOS has. The three calls, their prompts (`assets/prompts/
flow_planner/*.md`, copied verbatim) and their JSON-validation/fallback logic
are otherwise unchanged.

The SOP is a rule table almost everywhere. These are the places it is not -
the three points where the document itself says to look at free text and use
judgement:

    row 9   segment names, "find from the Survey Sheet Segment Details or the
            Question n Answer Texts and input as Recommendation"
    row 7   whether the campaign captures from an unbranded source, read off
            the campaign goal
    row 7   which send was the last touchpoint in that unbranded flow

Each call is narrow, returns strict JSON that is validated before anything is
believed, and returns None on any failure. None is not an error path here: the
SOP's own instruction in all three cases is "else leave TBD", so a model that
is switched off, unreachable, or unconvincing produces exactly the journey the
SOP prescribes for missing information, plus a clarifying question.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
from dataclasses import dataclass, field

from strategy import conversation_llm

_PROMPT_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "assets" / "prompts" / "flow_planner"

MAX_TOKENS = 512


@dataclass
class PromptTemplate:
    id: str
    version: str
    body: str
    sha256: str

    def stamp(self) -> dict:
        return {"prompt_id": self.id, "prompt_version": self.version,
                "prompt_sha256": self.sha256[:16]}


@dataclass
class ModelCall:
    """What a call produced, and enough to reproduce it."""
    value: object = None
    used: bool = False
    prompt: dict = field(default_factory=dict)
    model_id: str | None = None
    error: str | None = None


_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_cache: dict[str, PromptTemplate] = {}


def load_prompt(name: str) -> PromptTemplate:
    if name in _cache:
        return _cache[name]
    raw = (_PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")
    meta, body = {}, raw
    m = _FRONT_MATTER.match(raw)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        body = raw[m.end():]
    tpl = PromptTemplate(
        id=meta.get("id", name), version=meta.get("version", "0.0.0"),
        body=body.strip(),
        sha256=hashlib.sha256(body.strip().encode("utf-8")).hexdigest())
    _cache[name] = tpl
    return tpl


def available() -> bool:
    return conversation_llm.llm_available()


def _fence(label: str, text: str) -> str:
    """Wrap campaign text so it cannot be read as instruction.

    Delimiter and role separation, per the prompt-injection control: document
    content is passed as data, never as instruction. The fence is explicit in
    the text as well as structural, because a model that loses the structure
    should still see the boundary.
    """
    body = (text or "").strip() or "(none)"
    return f"<{label}>\n{body}\n</{label}>"


def _invoke(template: PromptTemplate, user_text: str) -> ModelCall:
    """One call, one retry on invalid JSON. Any failure returns rather than
    raises -- the SOP's own instruction for an unavailable model is "leave
    TBD", not "fail the generation"."""
    if not available():
        return ModelCall(used=False, error="disabled")

    provider = conversation_llm.active_provider()
    model_id = conversation_llm.MODEL if provider == "azure-foundry" else conversation_llm.GEMINI_MODEL
    try:
        client = conversation_llm._get_client()

        def _call(extra: str = "") -> str:
            resp = client.messages.create(
                model=model_id, max_tokens=MAX_TOKENS, system=template.body,
                messages=[{"role": "user", "content": user_text + extra}])
            return next((b.text for b in resp.content if b.type == "text"), "")

        text = _call()
        value = _parse_json(text)
        if value is None:
            text = _call("\n\nYour previous response was not valid JSON. Return only "
                         "one raw JSON object -- no markdown fences, no prose outside "
                         "it, strings escaped.")
            value = _parse_json(text)
    except Exception as exc:  # noqa: BLE001 -- an unreachable model degrades to TBD
        return ModelCall(used=True, error=f"{type(exc).__name__}: {exc}",
                         prompt=template.stamp(), model_id=model_id)

    return ModelCall(value=value, used=True, prompt=template.stamp(), model_id=model_id)


def invoke_raw(template: PromptTemplate, user_text: str) -> str | None:
    """Like `_invoke`, but for a prompt that asks for plain text, not JSON (the flow
    editor's opening line) -- no parsing, no retry-on-bad-JSON. None on any failure or
    when no provider is configured, same "degrade quietly" contract as `_invoke`."""
    if not available():
        return None
    provider = conversation_llm.active_provider()
    model_id = conversation_llm.MODEL if provider == "azure-foundry" else conversation_llm.GEMINI_MODEL
    try:
        client = conversation_llm._get_client()
        resp = client.messages.create(
            model=model_id, max_tokens=MAX_TOKENS, system=template.body,
            messages=[{"role": "user", "content": user_text}])
        return next((b.text for b in resp.content if b.type == "text"), "").strip() or None
    except Exception:  # noqa: BLE001
        return None


def _parse_json(text: str) -> dict | None:
    """The JSON the prompt asked for, or None. Never a partial guess."""
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"\A```[a-z]*\n|\n```\Z", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _clean_names(raw: object, limit: int = 8) -> list[str]:
    """Strings only, trimmed, de-duplicated, capped. Order preserved."""
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        name = item.strip()
        if name and name not in out:
            out.append(name)
    return out[:limit]


# --- the three calls -------------------------------------------------------

def recommend_segment_names(goal: str, survey_text: str) -> ModelCall:
    """SOP row 9. Returns [] rather than None when the model finds nothing."""
    call = _invoke(load_prompt("segment_names"),
                   _fence("campaign_goal", goal) + "\n\n"
                   + _fence("survey_question_and_answer_text", survey_text))
    if call.value is None:
        return call
    call.value = _clean_names(call.value.get("segments"))
    return call


def detect_unbranded_source(goal: str) -> ModelCall:
    """SOP row 7. {"present": bool, "campaign_code": str | None}."""
    call = _invoke(load_prompt("unbranded_source"), _fence("campaign_goal", goal))
    if call.value is None:
        return call
    raw = call.value
    code = raw.get("campaign_code")
    call.value = {
        "present": bool(raw.get("present")),
        "campaign_code": code.strip() if isinstance(code, str) and code.strip() else None,
    }
    return call


def recommend_last_touchpoint(goal: str, touchpoints: list[str]) -> ModelCall:
    """SOP row 7, Decision 1. The chosen name must be one we supplied."""
    call = _invoke(load_prompt("last_touchpoint"),
                   _fence("campaign_goal", goal) + "\n\n"
                   + _fence("touchpoints", "\n".join(touchpoints)))
    if call.value is None:
        return call
    raw = call.value
    chosen = raw.get("touchpoint")
    code = raw.get("question_code")
    # A name we did not offer is a hallucination, not a recommendation.
    if not isinstance(chosen, str) or chosen.strip() not in touchpoints:
        chosen = None
    call.value = {
        "touchpoint": chosen.strip() if chosen else None,
        "question_code": code.strip() if isinstance(code, str) and code.strip() else None,
    }
    return call
