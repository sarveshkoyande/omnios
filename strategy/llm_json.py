"""One JSON-returning LLM call for the redesigned Cockpit's assistants (Ask routing, Refine,
Check guidelines, Chat). Uses whichever provider strategy/conversation_llm.py has configured.

There is deliberately no rules/keyword fallback here (redesign rule R1): when no LLM is
configured or the call fails, callers get `LLMUnavailable` and must say so plainly (R2).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import conversation_llm  # noqa: E402


class LLMUnavailable(RuntimeError):
    """No LLM configured, or the call/parse failed."""


def _complete(system: str, payload: dict, max_tokens: int) -> str:
    provider = conversation_llm.active_provider()
    if provider == "azure-foundry":
        client = conversation_llm._get_client()
        resp = client.messages.create(
            model=conversation_llm.MODEL, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
        return next(b.text for b in resp.content if b.type == "text")
    if provider == "gemini":
        import litellm
        # Gemini 2.5 counts its hidden "thinking" against max_tokens, which truncated these
        # JSON replies mid-object. These are structured extraction calls, so thinking is off.
        resp = litellm.completion(
            model=conversation_llm.GEMINI_MODEL, api_key=conversation_llm._gemini_key(), max_tokens=max_tokens,
            reasoning_effort="disable",
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
        return resp.choices[0].message.content
    raise LLMUnavailable("No LLM is configured.")


def _parse(text: str) -> dict:
    """The reply's JSON object, tolerating a markdown fence or a sentence around it."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in the reply")
    return json.loads(text[start:end + 1])


def complete_json(system: str, payload: dict, max_tokens: int = 2000) -> dict:
    """One retry on an unparseable reply, then LLMUnavailable."""
    last: Exception | None = None
    for _ in range(2):
        try:
            return _parse(_complete(system, payload, max_tokens))
        except LLMUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 -- surfaced as "unavailable", never guessed around
            last = exc
    raise LLMUnavailable(str(last)) from last
