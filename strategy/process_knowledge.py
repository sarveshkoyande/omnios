"""The grounding seam between the planning agents and the cognee knowledge layer.

`memory_cognee` is the raw graph memory (async add/cognify/recall). This module is the thin,
*synchronous*, fail-safe layer the deterministic orchestrator actually calls: each agent stage
asks for the firm's own documented guidance on its topic (`ground("channel_budget", brand, ta)`)
and gets back a short piece of process knowledge recalled from the ingested Omni OS docs — or
nothing, if the knowledge layer isn't available. It is designed so that a missing API key, an
un-ingested graph, or any cognee error degrades to "no grounding" and the pipeline produces
exactly what it does today. Grounding enriches a plan; it is never load-bearing.

Why a separate module from memory_cognee:
  * memory_cognee is async and generic; the orchestrator is a synchronous generator. This
    bridges the two safely (works whether or not an event loop is already running).
  * Topic → query lives here as the shared vocabulary, so every agent asks the graph the same
    way and answers are cached once per process.
  * The enable switch (OMNI_PROCESS_GROUNDING=0) and the graceful-degradation contract live in
    one place, so grounding can be turned off for tests/speed without touching agent code.
"""
from __future__ import annotations

import os
import threading

SOURCE_LABEL = "Omni OS process knowledge"

# Process-lifetime cache shared by the sync (ground) and concurrent (ground_all) paths, keyed by
# the exact recall query -> joined guidance text ('' means "asked, nothing came back").
_CACHE: dict[str, str] = {}

# Stable topic keys → the question each agent stage asks the process graph. {brand} and
# {therapy_area} are filled per run; a topic maps to one orchestrator agent's remit (see the
# 9-stage playbook: Stage 0 intake → planner, 1–2 → intel, 3–4 → strategy, 5/7 → activation,
# 6/creative → inspiration, 8 → planner/governance).
TOPICS: dict[str, str] = {
    "intake_context": (
        "What business and brand context should be established before planning a campaign, "
        "and what makes a strong campaign brief for {brand} in {therapy_area}?"
    ),
    "market_landscape": (
        "How should market and competitive landscape analysis be done for a pharma brand like "
        "{brand} in {therapy_area}? What data sources and outputs matter?"
    ),
    "segmentation_targeting": (
        "How should HCP segments be prioritised and targeted (where to play) for {therapy_area}? "
        "What variables and audience benchmarks define a target customer group?"
    ),
    "journey_messaging": (
        "How should the customer journey and messaging architecture (current vs desired belief, "
        "BAM chart, key messages) be built for {brand} in {therapy_area}?"
    ),
    "competitive_positioning": (
        "How should a positioning statement and value proposition (how to win) be written for "
        "{brand} in {therapy_area} against its competitors?"
    ),
    "channel_budget": (
        "How should channel mix, touchpoints and budget be allocated for {therapy_area}? What "
        "channel-affinity and rep-access constraints and engagement benchmarks apply?"
    ),
    "creative_content": (
        "What makes strong creative and content for a pharma omnichannel campaign, and how should "
        "existing content and award-winning precedents steer the {therapy_area} creative?"
    ),
    "measurement_kpi": (
        "How should the measurement framework and KPIs be designed for a pharma campaign — leading "
        "vs lagging indicators, benchmarks, and review cadence?"
    ),
    "risk_governance": (
        "What risks and governance cadence should a pharma omnichannel campaign plan include, and "
        "how is a risk register scored and owned?"
    ),
}


def enabled() -> bool:
    """Grounding is on unless explicitly disabled. Off => every ground() returns None and the
    pipeline behaves exactly as it did before the knowledge layer existed."""
    return os.environ.get("OMNI_PROCESS_GROUNDING", "1").strip().lower() not in {"0", "false", "no", "off"}


def _run_async(coro):
    """Run an async coroutine to completion from synchronous code, whether or not the calling
    thread already has a running event loop (FastAPI runs the SSE generator in a worker thread
    with no loop, but be robust either way)."""
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)  # common path: no loop in this thread

    # A loop is already running in this thread — run the coroutine on a private loop in a
    # separate thread and block for the result, so we never re-enter the running loop.
    result: dict = {}

    def _worker():
        try:
            result["value"] = asyncio.run(coro)
        except Exception as exc:  # noqa: BLE001 - carried out to the caller's try/except
            result["error"] = exc

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join()
    if "error" in result:
        raise result["error"]
    return result.get("value")


def _join(hits) -> str:
    return "\n\n".join(h.strip() for h in (hits or []) if isinstance(h, str) and h.strip())


def _recall_cached(query: str) -> str:
    """Recall one query against the graph, cached for the process lifetime. Returns the joined
    guidance text, or '' on any failure / empty graph. Never raises."""
    if not enabled():
        return ""
    if query in _CACHE:
        return _CACHE[query]
    try:
        from memory_cognee import recall
        hits = _run_async(recall(query))
        text = _join(hits)
    except Exception as exc:  # noqa: BLE001 - import/key/graph/network failure => no grounding
        print(f"[process_knowledge] recall failed (grounding skipped): {exc}")
        text = ""
    _CACHE[query] = text
    return text


async def _arecall_all(queries: list[str]) -> None:
    """Populate _CACHE for every not-yet-cached query, recalling them SEQUENTIALLY on one event
    loop. Sequential is required, not just polite: cognee's graph store (Ladybug) takes an
    exclusive file lock per connection, so firing recalls concurrently makes them collide with
    'Could not set lock' (OS error 33) and every topic silently loses its grounding. One query
    failing is cached as '' (that topic renders ungrounded) and never breaks the rest."""
    from memory_cognee import recall

    for q in queries:
        if q in _CACHE:
            continue
        try:
            _CACHE[q] = _join(await recall(q))
        except Exception as exc:  # noqa: BLE001 - one topic's failure must not sink the batch
            print(f"[process_knowledge] recall failed for one topic (grounding skipped): {exc}")
            _CACHE[q] = ""


def ground(topic: str, brand: str = "", therapy_area: str = "", max_chars: int = 600) -> dict | None:
    """Return documented process guidance for one agent-stage `topic`, or None if the knowledge
    layer has nothing / is unavailable. Shape:
        {"topic": ..., "guidance": <str>, "source": "Omni OS process knowledge"}
    Callers attach this to their plan section as grounded rationale; None means render as today.
    """
    template = TOPICS.get(topic)
    if not template:
        return None
    query = template.format(brand=brand or "the brand", therapy_area=therapy_area or "the therapy area")
    guidance = _recall_cached(query)
    if not guidance:
        return None
    if max_chars and len(guidance) > max_chars:
        guidance = guidance[: max_chars - 1].rstrip() + "…"
    return {"topic": topic, "guidance": guidance, "source": SOURCE_LABEL}


def ground_all(brand: str = "", therapy_area: str = "", topics: list[str] | None = None,
               max_chars: int = 600) -> dict[str, dict]:
    """Ground several topics for one plan run in a single concurrent batch and return only the
    topics that produced guidance. This is what the orchestrator calls once per run to fill
    ctx['process_grounding']; each agent section then reads its topic from that dict.

    Returns {} (and the pipeline renders exactly as before) if grounding is disabled or the
    knowledge layer is unavailable."""
    if not enabled():
        return {}
    keys = [t for t in (topics or list(TOPICS)) if t in TOPICS]
    queries = {t: TOPICS[t].format(brand=brand or "the brand",
                                   therapy_area=therapy_area or "the therapy area") for t in keys}
    try:
        _run_async(_arecall_all(list(queries.values())))
    except Exception as exc:  # noqa: BLE001 - batch failure => fall through to per-topic (also safe)
        print(f"[process_knowledge] batch recall failed (grounding skipped): {exc}")
    out: dict[str, dict] = {}
    for t in keys:
        text = _CACHE.get(queries[t], "")
        if not text:
            continue
        if max_chars and len(text) > max_chars:
            text = text[: max_chars - 1].rstrip() + "…"
        out[t] = {"topic": t, "guidance": text, "source": SOURCE_LABEL}
    return out


def ground_many(topics: list[str], brand: str = "", therapy_area: str = "",
                max_chars: int = 600) -> dict[str, dict]:
    """ground() several topics at once; returns only the topics that produced guidance."""
    return ground_all(brand=brand, therapy_area=therapy_area, topics=topics, max_chars=max_chars)


def health() -> dict:
    """Quick status for diagnostics / a UI badge: is grounding enabled, and does a probe recall
    return anything (i.e. has the graph been ingested)?"""
    if not enabled():
        return {"enabled": False, "graph_ready": False, "note": "OMNI_PROCESS_GROUNDING disabled"}
    probe = _recall_cached(TOPICS["channel_budget"].format(brand="the brand", therapy_area="oncology"))
    return {"enabled": True, "graph_ready": bool(probe),
            "note": "graph returns guidance" if probe else "graph empty or unavailable — run ingest_process_knowledge"}
