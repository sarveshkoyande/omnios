"""The grounding seam between the planning agents and the cognee knowledge layer.

`memory_cognee` is the raw graph memory (async add/cognify/recall). This module is the thin,
*synchronous*, fail-safe layer the deterministic orchestrator actually calls: each agent stage
asks for the firm's own SME knowledge on its topic (for example `ground("channel_budget", brand,
ta)`) and gets back a short piece of process knowledge recalled from the ingested SME Knowledge
docs, or nothing if the knowledge layer isn't available. It is designed so that a missing API key,
an un-ingested graph, or any cognee error degrades to "no grounding" and the pipeline produces
exactly what it does today. Grounding enriches a plan; it is never load-bearing.

Why a separate module from memory_cognee:
  * memory_cognee is async and generic; the orchestrator is a synchronous generator. This
    bridges the two safely (works whether or not an event loop is already running).
  * Topic -> query lives here as the shared vocabulary, so every agent asks the graph the same
    way and answers are cached once per process.
  * The enable switch (OMNI_PROCESS_GROUNDING=0) and the graceful-degradation contract live in
    one place, so grounding can be turned off for tests/speed without touching agent code.
"""
from __future__ import annotations

import os
import threading
import time

SOURCE_LABEL = "Omni OS process knowledge"

# Grounding is best-effort (see module docstring) -- a slow or lock-contended graph store must
# never stall the plan run itself. Each recall gets this long before it's abandoned in favor of
# "no grounding for this topic" rather than hanging the whole Align phase.
_RECALL_TIMEOUT_SEC = 8.0

# Process-lifetime cache shared by the sync (ground) and concurrent (ground_all) paths, keyed by
# the exact recall query -> joined guidance text ('' means "asked, nothing came back").
_CACHE: dict[str, str] = {}

# Stable topic keys -> the question each agent stage asks the process graph. {brand} and
# {therapy_area} are filled per run; a topic maps to one orchestrator agent's remit (see the
# 9-stage playbook: Stage 0 intake -> planner, 1-2 -> intel, 3-4 -> strategy, 5/7 -> activation,
# 6/creative -> inspiration, 8 -> planner/governance).
TOPICS: dict[str, str] = {
    "intake_context": (
        "According to the SME Knowledge base, what business and brand context should be established "
        "before planning a campaign, and what makes a strong campaign brief for {brand} in {therapy_area}?"
    ),
    "market_landscape": (
        "According to the SME Knowledge base, how should market and competitive landscape analysis be done "
        "for a pharma brand like {brand} in {therapy_area}? What data sources and outputs matter?"
    ),
    "segmentation_targeting": (
        "According to the SME Knowledge base, how should HCP segments be prioritised and targeted (where to "
        "play) for {therapy_area}? What variables and audience benchmarks define a target customer group?"
    ),
    "journey_messaging": (
        "According to the SME Knowledge base, how should the customer journey and messaging architecture "
        "(current vs desired belief, BAM chart, key messages) be built for {brand} in {therapy_area}?"
    ),
    "competitive_positioning": (
        "According to the SME Knowledge base, how should a positioning statement and value proposition (how "
        "to win) be written for {brand} in {therapy_area} against its competitors?"
    ),
    "channel_budget": (
        "According to the SME Knowledge base, how should channel mix, touchpoints and budget be allocated for "
        "{therapy_area}? What channel-affinity and rep-access constraints and engagement benchmarks apply?"
    ),
    "creative_content": (
        "According to the SME Knowledge base, what makes strong creative and content for a pharma omnichannel "
        "campaign, and how should existing content and award-winning precedents steer the {therapy_area} creative?"
    ),
    "measurement_kpi": (
        "According to the SME Knowledge base, how should the measurement framework and KPIs be designed for a "
        "pharma campaign: leading vs lagging indicators, benchmarks, and review cadence?"
    ),
    "risk_governance": (
        "According to the SME Knowledge base, what risks and governance cadence should a pharma omnichannel "
        "campaign plan include, and how is a risk register scored and owned?"
    ),
}

# A compact brief-specific slice the planner and strategy agents should consult first, before the
# broader phase-level grounding is rendered elsewhere in the plan.
BRIEF_TOPICS = (
    "intake_context",
    "risk_governance",
    "segmentation_targeting",
    "journey_messaging",
    "competitive_positioning",
    "channel_budget",
    "measurement_kpi",
)


def enabled() -> bool:
    """Grounding is on unless explicitly disabled. Off => every ground() returns None and the
    pipeline behaves exactly as it did before the knowledge layer existed."""
    return os.environ.get("OMNI_PROCESS_GROUNDING", "1").strip().lower() not in {"0", "false", "no", "off"}


def _run_async(coro):
    """Run an async coroutine to completion from synchronous code, whether or not the calling
    thread already has a running event loop."""
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

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
        import asyncio

        from memory_cognee import recall

        hits = _run_async(asyncio.wait_for(recall(query), timeout=_RECALL_TIMEOUT_SEC))
        text = _join(hits)
    except Exception as exc:  # noqa: BLE001 - import/key/graph/network/timeout failure => no grounding
        print(f"[process_knowledge] recall failed (grounding skipped): {exc}")
        text = ""
    _CACHE[query] = text
    return text


def _with_feedback(topic: str, guidance: str, brand: str = "", therapy_area: str = "") -> tuple[str, list[dict]]:
    try:
        from strategy import cognee_feedback
    except Exception:  # noqa: BLE001
        import cognee_feedback  # type: ignore

    rows = cognee_feedback.matching_feedback(topic, brand=brand, therapy_area=therapy_area)
    overlay = cognee_feedback.feedback_guidance(topic, brand=brand, therapy_area=therapy_area)
    if overlay:
        guidance = (guidance.strip() + "\n\n" + overlay).strip() if guidance else overlay
    return guidance, rows


async def _arecall_all(queries: list[str]) -> None:
    """Populate _CACHE for every not-yet-cached query, recalling them SEQUENTIALLY on one event
    loop. Sequential is required because cognee's graph store takes an exclusive file lock per
    connection. Each recall is individually timeout-bounded so one slow/lock-contended topic
    can't stall every topic behind it."""
    import asyncio

    from memory_cognee import recall

    for q in queries:
        if q in _CACHE:
            continue
        try:
            _CACHE[q] = _join(await asyncio.wait_for(recall(q), timeout=_RECALL_TIMEOUT_SEC))
        except Exception as exc:  # noqa: BLE001 - one topic's failure must not sink the batch
            print(f"[process_knowledge] recall failed for one topic (grounding skipped): {exc}")
            _CACHE[q] = ""


def ground(topic: str, brand: str = "", therapy_area: str = "", max_chars: int = 600) -> dict | None:
    """Return documented process guidance for one agent-stage `topic`, or None if the knowledge
    layer has nothing / is unavailable."""
    template = TOPICS.get(topic)
    if not template:
        return None
    query = template.format(brand=brand or "the brand", therapy_area=therapy_area or "the therapy area")
    guidance = _recall_cached(query)
    guidance, _feedback_rows = _with_feedback(topic, guidance, brand=brand, therapy_area=therapy_area)
    if not guidance:
        return None
    if max_chars and len(guidance) > max_chars:
        guidance = guidance[: max_chars - 1].rstrip() + "..."
    source = SOURCE_LABEL if not _feedback_rows else f"{SOURCE_LABEL} + human feedback"
    return {"topic": topic, "guidance": guidance, "source": source, "feedback_count": len(_feedback_rows)}


def ground_all(brand: str = "", therapy_area: str = "", topics: list[str] | None = None,
               max_chars: int = 600) -> dict[str, dict]:
    """Ground several topics for one plan run in a single concurrent batch and return only the
    topics that produced guidance."""
    keys = [t for t in (topics or list(TOPICS)) if t in TOPICS]
    queries = {
        t: TOPICS[t].format(brand=brand or "the brand", therapy_area=therapy_area or "the therapy area")
        for t in keys
    }
    if enabled():
        try:
            _run_async(_arecall_all(list(queries.values())))
        except Exception as exc:  # noqa: BLE001 - batch failure => fall through to per-topic (also safe)
            print(f"[process_knowledge] batch recall failed (grounding skipped): {exc}")
    out: dict[str, dict] = {}
    for t in keys:
        text = _CACHE.get(queries[t], "")
        text, feedback_rows = _with_feedback(t, text, brand=brand, therapy_area=therapy_area)
        if not text:
            continue
        if max_chars and len(text) > max_chars:
            text = text[: max_chars - 1].rstrip() + "..."
        source = SOURCE_LABEL if not feedback_rows else f"{SOURCE_LABEL} + human feedback"
        out[t] = {"topic": t, "guidance": text, "source": source, "feedback_count": len(feedback_rows)}
    return out


def ground_many(topics: list[str], brand: str = "", therapy_area: str = "",
                max_chars: int = 600) -> dict[str, dict]:
    """ground() several topics at once; returns only the topics that produced guidance."""
    return ground_all(brand=brand, therapy_area=therapy_area, topics=topics, max_chars=max_chars)


def brief_grounding(brand: str = "", therapy_area: str = "", max_chars: int = 500) -> dict[str, dict]:
    """Return the brief-shaping SME topics the planner and strategy agents should consult first."""
    return ground_all(brand=brand, therapy_area=therapy_area, topics=list(BRIEF_TOPICS), max_chars=max_chars)


def health() -> dict:
    """Quick status for diagnostics / a UI badge: is grounding enabled, and does a probe recall
    return anything (i.e. has the graph been ingested)?"""
    if not enabled():
        return {"enabled": False, "graph_ready": False, "note": "OMNI_PROCESS_GROUNDING disabled"}
    return {
        "enabled": True,
        "graph_ready": None,
        "note": "grounding enabled; run a request probe to test live Cognee extraction",
    }


def topic_query(topic: str, brand: str = "", therapy_area: str = "") -> str:
    template = TOPICS.get(topic)
    if not template:
        return ""
    return template.format(brand=brand or "the brand", therapy_area=therapy_area or "the therapy area")


def diagnose_request(brand: str = "", therapy_area: str = "", topics: list[str] | None = None,
                     max_chars: int = 1200) -> dict:
    """Request-level inspection payload for the diagnostics UI."""
    keys = [t for t in (topics or list(BRIEF_TOPICS)) if t in TOPICS]
    started = time.time()
    rows = []
    grounded = ground_many(keys, brand=brand, therapy_area=therapy_area, max_chars=max_chars)
    for topic in keys:
        result = grounded.get(topic)
        feedback_rows = []
        try:
            from strategy import cognee_feedback
        except Exception:  # noqa: BLE001
            import cognee_feedback  # type: ignore
        try:
            feedback_rows = cognee_feedback.matching_feedback(topic, brand=brand, therapy_area=therapy_area)
        except Exception:
            feedback_rows = []
        rows.append({
            "topic": topic,
            "query": topic_query(topic, brand=brand, therapy_area=therapy_area),
            "has_guidance": bool(result and result.get("guidance")),
            "guidance": (result or {}).get("guidance", ""),
            "source": (result or {}).get("source", SOURCE_LABEL),
            "feedback": feedback_rows,
        })
    return {
        "health": health(),
        "brand": brand,
        "therapy_area": therapy_area,
        "enabled": enabled(),
        "topics": rows,
        "elapsed_ms": int((time.time() - started) * 1000),
    }
