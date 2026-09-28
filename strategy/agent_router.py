"""Routes a free-text question from the Cockpit's Ask bar to the agent(s) best suited to it.

LLM-only by design: there is no keyword or regex fallback. When no LLM is configured or the
call fails, the caller gets `AgentRouterUnavailable` and must say so plainly rather than guess.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from llm_json import LLMUnavailable, complete_json  # noqa: E402

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

AgentRouterUnavailable = LLMUnavailable


def route_question(question: str, brand: str | None, agents: list[dict]) -> dict:
    """Returns {"agent_ids": [...], "reply": str}. Unknown ids the model invents are dropped."""
    data = complete_json(_SYSTEM, {"question": question, "active_brand": brand or "all brands", "agents": agents}, 300)
    known = {a["id"] for a in agents}
    ids = [i for i in (data.get("agent_ids") or []) if i in known][:3]
    return {"agent_ids": ids, "reply": str(data.get("reply") or "").strip()}
