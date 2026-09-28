"""Routes a free-text question from the Cockpit's Ask bar to the agent(s) best suited to it.

LLM-only by design: there is no keyword or regex fallback. When no LLM is configured or the
call fails, the caller gets `AgentRouterUnavailable` and must say so plainly rather than guess.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import conversation_llm  # noqa: E402

_SYSTEM = """You route a pharma marketer's question to the right agents in Omni OS, an \
omnichannel campaign planning tool. You are given the question, the active brand (or none), \
and the list of agents with their id, name, summary and whether they are available yet.

Pick up to 3 agents that genuinely fit, best first. Prefer available agents; include an \
unavailable one only if it is clearly the right fit. If the message is a greeting, small \
talk, or nothing fits, pick none.

Reply with JSON only, no prose around it:
{"agent_ids": ["<id>", ...], "reply": "<one short sentence to the user>"}

The reply is plain text, at most 25 words. If you picked agents, say briefly why they fit. \
If you picked none, say what Omni can help with (planning, segmentation, channels, flows, \
briefs, market signals) and invite them to rephrase."""


class AgentRouterUnavailable(RuntimeError):
    """No LLM configured, or the call failed -- the UI must not substitute a guess."""


def _complete(payload: dict) -> str:
    provider = conversation_llm.active_provider()
    if provider == "azure-foundry":
        client = conversation_llm._get_client()
        resp = client.messages.create(
            model=conversation_llm.MODEL,
            max_tokens=300,
            system=_SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload)}],
        )
        return next(b.text for b in resp.content if b.type == "text")
    if provider == "gemini":
        import litellm
        resp = litellm.completion(
            model=conversation_llm.GEMINI_MODEL,
            api_key=conversation_llm._gemini_key(),
            max_tokens=300,
            messages=[{"role": "system", "content": _SYSTEM},
                      {"role": "user", "content": json.dumps(payload)}],
        )
        return resp.choices[0].message.content
    raise AgentRouterUnavailable("No LLM is configured.")


def route_question(question: str, brand: str | None, agents: list[dict]) -> dict:
    """Returns {"agent_ids": [...], "reply": str}. Unknown ids the model invents are dropped."""
    payload = {"question": question, "active_brand": brand or "all brands", "agents": agents}
    try:
        data = conversation_llm._parse_json_reply(_complete(payload))
    except AgentRouterUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 -- surfaced to the UI as "unavailable", never guessed
        raise AgentRouterUnavailable(str(exc)) from exc
    known = {a["id"] for a in agents}
    ids = [i for i in (data.get("agent_ids") or []) if i in known][:3]
    return {"agent_ids": ids, "reply": str(data.get("reply") or "").strip()}
