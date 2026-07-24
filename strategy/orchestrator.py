"""Multi-agent orchestrator for the campaign-planning workspace.

`run_agents()` is a generator that yields events as each specialist agent works. The FastAPI
layer streams these events as Server-Sent Events so the UI can show the agents thinking in
real time. Every agent reuses the same real, data-backed functions the rest of the tool
uses -- the "agents" are genuine pipeline stages, not theatre.

The plan document builds PROGRESSIVELY (reworked 2026-07-11): the Engagement Planner Agent
opens by scaffolding the whole document (brief, governance, brand foundation, and an
owner-labelled placeholder for every other section), then each specialist's completion
fills its own sections in place -- a partial 'plan' event follows every agent's turn -- and
the planner returns at the end to synthesize the executive summary and open questions into
the final full document. Five broad-mandate agents (not ten narrow ones -- consolidated
2026-07-08 per feedback that the roster was too granular).
"""
from __future__ import annotations

import pathlib
import random
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from lifecycle import infer_persona_and_stage  # noqa: E402
from engine import generate_strategy, market_landscape  # noqa: E402
from positioning import build_positioning_statement  # noqa: E402
from kpi import build_kpi_framework  # noqa: E402
from bam import build_bam_chart, classify_pp_npp, build_micro_journeys, assess_cx_maturity  # noqa: E402
from precedent import find_precedent_campaigns  # noqa: E402
from competitive.discovery import discover_competitors  # noqa: E402
from competitive.swot import build_swot  # noqa: E402
from autorun import STANDARD_RISKS, GOVERNANCE_CADENCE  # noqa: E402
from segment_profile import build_segment_profile, build_tcg_template  # noqa: E402
from questionnaire import build_cx_questionnaire  # noqa: E402
from open_questions import build_open_questions  # noqa: E402
from plan_document import compose_plan, compose_plan_partial  # noqa: E402
from message_flow import build_message_flow  # noqa: E402
from channel_selection import build_channel_selection  # noqa: E402
import campaign_store  # noqa: E402  (content library query for the plan's Phase-2/3 sections)
import awards_store  # noqa: E402  (award-winning campaign matches for the precedent section)
import benchmarks  # noqa: E402  (industry baselines the intel/activation agents fill plan sections from)
import brand_kit as brand_kit_mod  # noqa: E402  (a brand's own captured intelligence hub)
from execution_plan import build_execution_work_plan, build_execution_raci  # noqa: E402
from test_measure_learn import build_test_measure_learn  # noqa: E402
import process_knowledge  # noqa: E402  (grounds each agent's section in the ingested Omni OS process docs)
import external_evidence  # noqa: E402  (live public-source datapoints agents cite to back decisions)
import campaign_ops  # noqa: E402  (Stage 3 campaign-operations journey-diagram synthesis)
import hcp_360  # noqa: E402  (synthetic HCP 360 panel -- grounds the strategy agent in real per-HCP facts)
import tactical_source  # noqa: E402  (best-effort CSF/guardrail/evidence pull from an uploaded strategic-plan doc)


# Which documented-process topic each agent consults for its section(s). Drives both the
# grounding callouts rendered in the plan (via ctx["process_grounding"]) and the visible
# "consulting the process knowledge" line in each agent's streamed turn.
_AGENT_TOPICS = {
    "planner": ["intake_context", "risk_governance"],
    "intel": ["market_landscape", "segmentation_targeting"],
    "strategy": ["journey_messaging", "competitive_positioning"],
    "inspiration": ["creative_content"],
    "activation": ["channel_budget", "measurement_kpi"],
}


def _grounding_bullet(ctx: dict, topic: str) -> str | None:
    """A short 'grounded in the firm's own process' bullet for an agent's streamed turn, or
    None when the knowledge layer had nothing for this topic."""
    g = (ctx.get("process_grounding") or {}).get(topic)
    if not g:
        return None
    txt = g["guidance"].replace("\n", " ").strip()
    if len(txt) > 180:
        txt = txt[:179].rstrip() + "…"
    return f"📖 Omni OS process — {txt}"


def _agent_grounding_bullets(ctx: dict, agent_id: str) -> list[str]:
    out = []
    for topic in _AGENT_TOPICS.get(agent_id, []):
        b = _grounding_bullet(ctx, topic)
        if b:
            out.append(b)
    # The intel agent owns the market read, so it's the one that cites the live external
    # datapoints pulled to back it.
    if agent_id == "intel":
        for d in (ctx.get("external_evidence") or [])[:3]:
            out.append(f"🔎 {d['label']}: {d['value']} — {d['source']} (as of {d['as_of']})")
    # The strategy agent owns segmentation/targeting, so it cites the HCP 360 panel's measured
    # numbers alongside its illustrative ABCD/TCG segmentation.
    if agent_id == "strategy":
        g = ctx.get("hcp_360_grounding") or {}
        if g:
            out.append(f"👥 HCP 360 ({g['confidence']}): {g['headline']}")
            if g.get("segment_breakdown"):
                top3 = sorted(g["segment_breakdown"].items(), key=lambda kv: -kv[1])[:3]
                out.append("👥 Writer segments: " + ", ".join(f"{v:.0f}% {k}" for k, v in top3))
            if g.get("top_content_tags"):
                out.append("👥 Top content affinity: " + ", ".join(g["top_content_tags"]))
    return out

# Each agent is named by its function. The Engagement Plan Composer (formerly "Cooper") is
# the plan's author: it opens the run by framing the document structure and closes it by
# writing the executive summary.
# Pipeline order == the order sections fill into the live document: planner scaffolds,
# then intel -> strategy -> inspiration -> activation each complete their own sections,
# then the planner returns to finalize. The UI shows a photo avatar (purely decorative)
# with `initials` as the monogram fallback if it fails to load.
AGENT_ROSTER = [
    {"id": "planner", "name": "Engagement Plan Composer", "role": "",
     "initials": "EP", "icon": "description"},
    {"id": "intel", "name": "Market & Competitive Intelligence Agent", "role": "",
     "initials": "MC", "icon": "travel_explore"},
    {"id": "strategy", "name": "Strategy & Positioning Agent", "role": "",
     "initials": "SP", "icon": "track_changes"},
    {"id": "inspiration", "name": "Creative Inspiration Agent", "role": "",
     "initials": "CI", "icon": "emoji_events"},
    {"id": "activation", "name": "Activation Planning Agent", "role": "",
     "initials": "AP", "icon": "payments"},
]


# ---------------------------------------------------------------------------
# Phase-by-phase interactive build. The plan is assembled ONE toolkit phase at a
# time: a small subset of agents visibly work that phase's sections, then the run
# STOPS for the human to validate/sign off (the phase's clarify questions) before
# the next phase's agents begin. The server drives one run_phase() stream per phase,
# advancing only when the user approves -- so the document is co-authored segment by
# segment with a human gate between each, never dumped as one finished artifact.
PHASE_ORDER = ["align", "select", "create", "deploy"]
PHASE_NO = {"align": 1, "select": 2, "create": 3, "deploy": 4}
PHASE_LABELS = {
    "align": "Align on customer understanding & CX objectives",
    "select": "Select relevant messages & channels",
    "create": "Create the omnichannel CX",
    "deploy": "Deploy the campaign",
}
# Which agents visibly work each phase (2-3 per step: "a couple of agents come together").
PHASE_AGENTS = {
    "align": ["planner", "intel", "strategy"],
    "select": ["strategy", "inspiration", "activation"],
    "create": ["inspiration", "activation"],
    "deploy": ["activation", "planner"],
}


def _phase_reveal(phase: str) -> set:
    """Every toolkit phase revealed once `phase` is reached (Align..phase inclusive)."""
    return set(PHASE_ORDER[: PHASE_ORDER.index(phase) + 1])


def _kb_count(section: dict) -> int:
    return sum(len(v) for v in section.values()) if section else 0


def _run(agent_id: str, say: str):
    """Running event carrying the agent's first-person 'what I'm doing' line for the chat."""
    return {"type": "agent", "id": agent_id, "status": "running", "say": say}


def _say(agent_id: str, text: str, to: str = ""):
    """A short conversational aside from one teammate, optionally addressed to another.

    These interleave with the main turns so the run reads as a team talking through the
    problem rather than a linear relay. Every line is grounded in what was actually just
    computed -- never filler."""
    return {"type": "banter", "id": agent_id, "to": to, "text": text}


# align's compute_plan_ctx() makes real, sequential network calls (ClinicalTrials.gov, PubMed,
# openFDA, cognee's process-knowledge graph) that can run 30-60s+ -- with nothing streamed
# during that window the client sits on a silent connection and it reads as hung. This runs
# alongside it on a background thread so the client keeps seeing something happen instead.
#
# Scripted in the SAME order compute_plan_ctx actually works through its sections (process/
# external grounding -> market & competitive intel -> strategy & positioning -> creative
# inspiration -> activation planning), so a line landing roughly lines up with real progress
# instead of being generic filler.
_PRECOMPUTE_HEARTBEAT_LINES = [
    lambda: _say("intel", "Cross-checking the firm's own playbook for this therapy area too.", to="planner"),
    lambda: _say("planner", "Take your time — grounded beats fast here.", to="intel"),
    lambda: _say("intel", "Sizing the competitive field and the addressable HCP universe now.", to="strategy"),
    lambda: _say("strategy", "Building the positioning read — where this brand can credibly win.", to="intel"),
    lambda: _say("strategy", "I'll have the journey-stage read ready the moment your numbers land.", to="intel"),
    lambda: _say("intel", "Benchmarking the channel mix against comparable launches.", to="planner"),
    lambda: _say("inspiration", "Pulling precedent campaigns and award-winning work for this therapy area.", to="strategy"),
    lambda: _say("activation", "Sketching the KPI framework so measurement is ready on arrival.", to="inspiration"),
    lambda: _say("planner", "Almost there — assembling everything into the first section now.", to="activation"),
]
# Once the scripted lines above run out, keep cycling this larger pool on a longer beat
# indefinitely -- shuffled and never repeating the immediately-previous line, so an unusually
# slow run reads as continued (varied) work rather than one message stuck on loop.
_PRECOMPUTE_HEARTBEAT_FALLBACK = [
    lambda: _say("planner", "Still with you — this one's taking longer than usual.", to="intel"),
    lambda: _say("intel", "One of the public sources is slow to respond; retrying rather than skipping it.", to="planner"),
    lambda: _say("intel", "ClinicalTrials.gov is being slow today — worth the wait for a real trial count.", to="planner"),
    lambda: _say("strategy", "No shortcuts on positioning — re-checking it against the competitive set.", to="intel"),
    lambda: _say("planner", "Quality over speed here — the plan only cites what actually checks out.", to="strategy"),
    lambda: _say("inspiration", "Still comparing against precedent campaigns for the best-fit creative angle.", to="planner"),
    lambda: _say("intel", "PubMed's queue is backed up; hanging on for the real publication count.", to="strategy"),
    lambda: _say("activation", "Cross-checking engagement benchmarks before locking the channel mix.", to="intel"),
    lambda: _say("planner", "This is the thorough part — worth it once the plan lands.", to="activation"),
    lambda: _say("strategy", "openFDA can be sluggish; staying on the line rather than guessing at the label.", to="planner"),
    lambda: _say("intel", "Re-running the competitor scan — first pass looked thin.", to="strategy"),
    lambda: _say("planner", "Nearly through the live pulls — thanks for hanging in there.", to="intel"),
]
_HEARTBEAT_TICK_SEC = 0.2
_HEARTBEAT_LINE_EVERY_SEC = 5.0
_HEARTBEAT_FALLBACK_EVERY_SEC = 7.0


def _shuffled_fallback_cycle():
    """Yield `_PRECOMPUTE_HEARTBEAT_FALLBACK` forever, reshuffled each lap, never repeating the
    line that just played at the seam between one lap and the next."""
    last = None
    while True:
        order = list(_PRECOMPUTE_HEARTBEAT_FALLBACK)
        random.shuffle(order)
        if last is not None and order[0] is last:
            order.append(order.pop(0))
        for line in order:
            last = line
            yield line


def precompute_heartbeat(done_event):
    """Yielded while a background thread runs compute_plan_ctx: an immediate 'intel is
    running' event (un-greys/shimmers that agent card client-side with zero new frontend
    code, since it's the same event shape run_phase() already emits), then grounded banter
    every few seconds until `done_event` (a threading.Event) is set -- looping a shuffled
    fallback set indefinitely once the scripted lines run out, so an unusually slow run never
    goes silent or repeats itself. Polls in short ticks so it stops promptly rather than
    over-sleeping past the real compute finishing."""
    yield _run("intel", "Pulling live evidence — ClinicalTrials.gov, PubMed and openFDA — "
                        "for what backs this brief…")
    line_idx = 0
    elapsed_since_line = 0.0
    fallback_cycle = _shuffled_fallback_cycle()
    while not done_event.is_set():
        time.sleep(_HEARTBEAT_TICK_SEC)
        if done_event.is_set():
            return
        elapsed_since_line += _HEARTBEAT_TICK_SEC
        if line_idx < len(_PRECOMPUTE_HEARTBEAT_LINES):
            if elapsed_since_line >= _HEARTBEAT_LINE_EVERY_SEC:
                yield _PRECOMPUTE_HEARTBEAT_LINES[line_idx]()
                line_idx += 1
                elapsed_since_line = 0.0
        elif elapsed_since_line >= _HEARTBEAT_FALLBACK_EVERY_SEC:
            yield next(fallback_cycle)()
            elapsed_since_line = 0.0


# The interactive build reveals the plan phase by phase: the run itself only ever reveals
# Phase 1 (Align) + the always-on base/supporting sections; the later phases unlock as the
# user answers each phase's clarify questions in chat (see open_questions.revealed_phases_for).
_RUN_REVEAL = {"align"}

# How long an agent's card holds the "running" state before flipping to "done" -- ctx is fully
# precomputed by the time run_phase() starts, so this is a deliberate pause (not real compute
# time) that gives the shimmer/working animation somewhere to actually be seen.
AGENT_TURN_PACING_SEC = 1.6


def _plan_partial(ctx: dict, done: set, fresh: str, revealed: set | None = None):
    """A progressive render of the plan document: sections owned by completed agents are
    real, the rest are owner-labelled placeholders. The UI swaps the plan pane in place, so
    the document visibly fills in as each agent finishes. `revealed` gates which toolkit
    phases are shown (defaults to Align only, for the legacy single-shot run)."""
    md, html_out, n_done, n_total = compose_plan_partial(
        ctx, done, fresh, revealed_phases=(revealed if revealed is not None else _RUN_REVEAL))
    return {"type": "plan", "html": html_out, "markdown": md, "partial": True,
            "sections_done": n_done, "sections_total": n_total, "fresh_agent": fresh}


def run_agents(brand: str, therapy_area: str, lifecycle_key: str, budget: float = 0, maturity_notes: str = "",
               indication: str = "", brief: dict | None = None):
    """Generator yielding orchestration events. The named teammates work as a group --
    each speaks in the chat (`say` on running, `summary` on done) as it picks up its
    piece, and the plan document on the right FILLS IN SECTION BY SECTION as each agent
    completes (a 'plan' event with partial=True follows every agent's turn; the final
    full document lands with partial=False). Terminal events: 'plan', 'result', 'done'."""
    yield {"type": "agents_init", "agents": AGENT_ROSTER}
    ctx: dict = {"brand": brand, "therapy_area": therapy_area, "lifecycle_key": lifecycle_key, "budget": budget,
                 "maturity_notes": maturity_notes, "indication": indication, "brief": brief or {}}
    ctx["slots"] = ctx["brief"]

    ind_note = f" for the {indication} indication" if indication else ""
    done_agents: set = set()

    # 1. Engagement Planner -- frames the document: brief, governance, caveats, and (when the
    # brand has a captured intelligence hub) the brand foundation. Every other section is
    # scaffolded as a labelled placeholder its owning agent will fill.
    yield _run("planner", f"Framing your Brand Engagement Plan for {brand}{ind_note} — scaffolding all four toolkit "
                          f"phases, locking the brief and governance, and checking for a brand intelligence kit…")
    inferred = infer_persona_and_stage(lifecycle_key)
    ctx["inferred"] = inferred
    yield {"type": "inferred", "persona": inferred["persona"], "lifecycle_label": inferred["lifecycle_label"]}
    kit = brand_kit_mod.kit_for(brand)
    ctx["brand_kit"] = kit
    # Recall the firm's documented process for every agent's remit up front (one concurrent
    # batch), so each agent's section can render its Omni OS grounding. {} => renders as before.
    ctx["process_grounding"] = process_knowledge.ground_all(brand, therapy_area)
    ctx["brief_grounding"] = process_knowledge.brief_grounding(brand, therapy_area)
    # Live external datapoints (public sources only) the agents cite to back decisions.
    ctx["external_evidence"] = external_evidence.datapoints(therapy_area, brand)
    done_agents.add("planner")
    _, _, n_done0, n_total0 = compose_plan_partial(ctx, done_agents, "")
    planner_summary = (f"Plan structure framed — **{n_total0}** sections scaffolded across the four toolkit phases. "
                       f"Brief, governance and caveats are locked; your agent fills the rest in live on the right.")
    planner_bullets = [inferred["rationale"],
                       f"{n_done0} of {n_total0} sections filled at kickoff; each remaining section is labelled with the agent that owns it"]
    if kit:
        planner_summary += (f" This brand ships its own intelligence hub — **{kit.get('tagline', '')}** platform, "
                            f"message hierarchy, guardrails and {len(kit.get('concepts', []))} campaign concepts are "
                            f"loaded into the Brand foundation section.")
        planner_bullets += [f"Brand kit: {kit.get('source_label', '')} — core claim “{kit.get('core_claim', '')}”",
                            f"{len((kit.get('guardrails') or {}).get('dos', []))} brand dos / "
                            f"{len((kit.get('guardrails') or {}).get('donts', []))} don'ts folded into Risk & governance"]
    if ctx.get("brief_grounding"):
        planner_bullets.append(f"SME brief grounding loaded: {len(ctx['brief_grounding'])} brief topics consulted before drafting")
    planner_bullets += _agent_grounding_bullets(ctx, "planner")
    yield {"type": "agent", "id": "planner", "status": "done", "summary": planner_summary,
           "detail": {"bullets": planner_bullets}}
    yield _plan_partial(ctx, done_agents, "planner")

    if kit:
        yield _say("planner", f"Structure's up. And we're not starting cold — the hub gives us "
                              f"“{kit.get('core_claim', '')}” with a three-pillar message hierarchy already MLR-framed.", to="intel")
        _sig = (kit.get("market_signals") or [{}])[0]
        if _sig.get("headline"):
            yield _say("intel", f"I can see the hub's live feed from here — “{_sig['headline']}”. "
                                f"I'll verify against the public data and size the landscape.", to="planner")
    else:
        yield _say("planner", "Structure's up — every pending section is tagged with who owns it. "
                              "Market read comes first; the rest builds on it.", to="intel")
        yield _say("intel", "On it. Lifecycle says " + inferred["lifecycle_label"].lower() +
                            " — I'll pull the live landscape and hunt competitors in the trial data.", to="planner")

    # 2. Market & Competitive Intelligence -- landscape, competitor discovery, SWOT, audience benchmarks
    yield _run("intel", f"Scanning the live market for {brand}, hunting competitors in the trial data, running the "
                        f"SWOT, and sizing the addressable audience from industry benchmarks…")
    market = market_landscape(brand, therapy_area)
    ctx["market"] = market
    b_n, t_n = _kb_count(market.get("brand", {})), _kb_count(market.get("therapy_area", {}))
    # The brand's own competitive intelligence outranks a keyword scan of trial records:
    # when a kit names the competitive set (e.g. Cabenuva/Dovato for Nuvexa), use it --
    # trial-data discovery surfaces historically-registered interventions, not the brands
    # actually taking share today.
    if kit and kit.get("competitors"):
        competitors = [c["name"] for c in kit["competitors"]][:4]
        comp_source = kit.get("source_label", "the brand intelligence hub")
    else:
        competitors = discover_competitors(therapy_area, brand, limit=5)
        comp_source = "public trial data"
    ctx["competitors"] = competitors
    yield {"type": "inferred", "competitors": competitors}
    swot_result = build_swot(brand, competitors, therapy_area, refresh=True) if competitors else None
    ctx["swot"] = swot_result
    audience_profile = benchmarks.maya_audience_profile(brand, therapy_area, inferred["persona"])
    ctx["audience_profile"] = audience_profile
    ctx["hcp_360_grounding"] = hcp_360.ground_segment(therapy_area, inferred["persona"])
    done_agents.add("intel")
    intel_summary = (
        f"{inferred['lifecycle_label']} → targeting **{inferred['persona']}** HCPs. Indexed **{b_n + t_n}** live documents. "
        + (f"Found **{len(competitors)}** competitor(s) via {comp_source}: {', '.join(competitors)}." if competitors
           else "No distinct competitors found in public trial data.")
        + (" SWOT run against the set." if swot_result else "")
    )
    if audience_profile["audience_size"]["total"]:
        intel_summary += f" Sized the audience: **{audience_profile['headline']}**."
    intel_bullets = [
        inferred["rationale"],
        f"{b_n} real documents on {brand}, {t_n} on {therapy_area} (FDA labels, ClinicalTrials.gov, PubMed, DailyMed, Google Trends)",
    ] + (competitors or ["ClinicalTrials.gov returned no distinct competing interventions"])
    if swot_result:
        s = swot_result["swot"]
        intel_bullets.append(f"SWOT: {len(s['strengths'])} strengths · {len(s['weaknesses'])} weaknesses · "
                             f"{len(s['opportunities'])} opportunities · {len(s['threats'])} threats")
    if audience_profile["audience_size"]["total"]:
        intel_bullets.append(f"Audience benchmark ({audience_profile['confidence']}): {audience_profile['headline']}")
        intel_bullets.append("I filled 3 Target-Customer-Group rows from industry benchmarks — flagged as agent-recommended in the plan.")
    intel_bullets += _agent_grounding_bullets(ctx, "intel")
    yield {"type": "agent", "id": "intel", "status": "done", "summary": intel_summary,
           "detail": {"bullets": intel_bullets}}
    yield _plan_partial(ctx, done_agents, "intel")

    if competitors:
        yield _say("strategy", f"{len(competitors)} live competitor(s) in {therapy_area} — that makes this a "
                               f"share-of-voice fight, not a category build. The SWOT gives me my positioning openings.", to="intel")
        yield _say("intel", f"Agreed. {competitors[0]} is the one to watch — it shows up across the data.", to="strategy")
    else:
        yield _say("strategy", f"No distinct competitors in the trial data — so we're building the category in "
                               f"{therapy_area}, not defending share. That changes the messaging job.", to="intel")
    yield _say("activation", f"Noting the **{inferred['lifecycle_label']}** stage — it'll drive how I weight the "
                             f"channel mix later.", to="intel")
    _acc = audience_profile["rep_access"]
    if audience_profile["audience_size"]["total"] and _acc.get("specialty_fully_accessible_pct"):
        yield _say("activation", f"Only {_acc['specialty_fully_accessible_pct']:.0f}% of {_acc['lead_specialty']} "
                                 f"providers are fully rep-accessible — I'll cap Field and push budget to the "
                                 f"channels they'll actually open.", to="intel")

    # 3. Strategy & Positioning -- journey/BAM/PP-NPP/micro-journeys/CX-maturity/TCG/message flow + positioning
    yield _run("strategy", "Mapping the journey stage and BAM-chart belief shift, splitting channels, building the "
                           "message flow, and drafting positioning…")
    strategy = generate_strategy(brand, therapy_area, inferred["persona"], inferred["stage_key"],
                                 ctx["brief_grounding"])
    ctx["strategy"] = strategy
    bam = build_bam_chart(inferred["stage_key"])
    pp_npp = classify_pp_npp(strategy["channel_mix_pct"])
    micro_journeys = build_micro_journeys(inferred["stage_key"], strategy["recommended_touchpoints"])
    cx_maturity = assess_cx_maturity(maturity_notes, strategy["channel_mix_pct"])
    segment_profile = build_segment_profile(inferred["persona"], inferred["stage_key"])
    tcg = build_tcg_template(inferred["persona"], segment_profile, strategy, bam,
                             agent_answers=ctx["audience_profile"]["answers"], agent_name="Market & Competitive Intelligence")
    message_flow = build_message_flow(inferred["stage_key"], strategy["kb_grounding"])
    # Ground the message flow in the brand's OWN claims when an intelligence kit exists:
    # the pool becomes the hub's message pool, and each key message leads with the hub
    # claim (with its study citation) that substantiates it.
    if kit:
        if kit.get("message_pool"):
            message_flow["brand_plan_key_message_pool"] = list(kit["message_pool"])
        for km in message_flow["key_messages"]:
            claim = brand_kit_mod.claim_for_topic(kit, km["topic"])
            if claim and claim not in km["supporting_messages"]:
                km["supporting_messages"] = [claim] + list(km["supporting_messages"])[:2]
        message_flow["caveat"] = (message_flow.get("caveat", "") + " Key-message pool and lead supporting claims "
                                  f"sourced verbatim from the {kit.get('source_label', 'brand intelligence hub')}.")
    ctx["tcg"] = tcg
    ctx["bam"] = bam
    ctx["pp_npp"] = pp_npp
    ctx["micro_journeys"] = micro_journeys
    ctx["cx_maturity"] = cx_maturity
    ctx["segment_profile"] = segment_profile
    ctx["message_flow"] = message_flow
    yield {"type": "inferred", "stage_label": strategy["inputs"]["stage"], "cx_maturity": cx_maturity["level"]}
    positioning = build_positioning_statement(brand, therapy_area, inferred["persona"], inferred["stage_key"], competitors)
    ctx["positioning"] = positioning
    done_agents.add("strategy")
    m = strategy["messaging_architecture"]
    strat_bullets = [
        f"A→B shift: {bam['a_to_b_shift']}",
        f"Key-message topics (of the 4 default): {', '.join(bam['key_message_topics'])}",
        f"CX maturity: {cx_maturity['level']} — {cx_maturity['rationale']}",
        f"Feasibility checklist: {cx_maturity['feasibility_checklist']['auto_answered_count']}/{cx_maturity['feasibility_checklist']['total_questions']} questions auto-answered from state",
        f"Positioning: {positioning['positioning_statement']}",
    ]
    if kit:
        strat_bullets.append(f"Message pool sourced from the brand hub: “{message_flow['brand_plan_key_message_pool'][0]}” + "
                             f"{len(message_flow['brand_plan_key_message_pool']) - 1} more")
    strat_summary = (
        f"Journey stage **{strategy['inputs']['stage']}**. Message: “{m['current_belief']}” → “{m['desired_belief']}”. "
        + ("Message pool grounded in the brand's own claims. " if kit else "")
        + "Positioning drafted."
    )
    if ctx.get("brief_grounding"):
        strat_bullets.append(f"SME brief grounding carried into strategy: {len(ctx['brief_grounding'])} topics")
    strat_bullets += _agent_grounding_bullets(ctx, "strategy")
    yield {"type": "agent", "id": "strategy", "status": "done", "summary": strat_summary, "detail": {"bullets": strat_bullets}}
    yield _plan_partial(ctx, done_agents, "strategy")

    yield _say("inspiration", f"“{m['current_belief']}” → “{m['desired_belief']}” is a creative brief in one line. "
                              f"Let me find award-winning work that pulled off the same belief change.", to="strategy")
    yield _say("strategy", f"Lead with {m['messaging_type'].lower()} — and CX maturity reads "
                           f"**{cx_maturity['level']}**, so don't over-engineer the orchestration.", to="activation")

    # 4. Creative Inspiration -- precedents, award campaigns, the brand's content library (and concept shelf)
    yield _run("inspiration", f"Searching real award-winning pharma campaigns for {therapy_area}, and pulling the "
                              f"brand's content library and concept shelf…")
    precedents = find_precedent_campaigns(therapy_area, brand, limit=3)
    ctx["precedents"] = precedents
    award_campaigns = awards_store.awards_for(brand=brand, therapy_area=therapy_area, limit=4)
    ctx["award_campaigns"] = award_campaigns
    # A kit brand's authored content library (claims + components WITH images) wins over any
    # lossy echo persisted from a prior run; non-kit brands use the scraped/persisted library.
    if kit and kit.get("components"):
        content_library = brand_kit_mod.content_library_from_kit(kit, indication)
    else:
        content_library = campaign_store.content_library_for(brand, indication)
    ctx["content_library"] = content_library
    done_agents.add("inspiration")
    matched_any = any(p["matched"] for p in precedents)
    lib_counts = content_library.get("counts", {})
    insp_summary = (
        f"Found **{len(precedents)}** precedent campaign(s)"
        + (" matched to this therapy area" if matched_any else " (no therapy-area match — showing the most recent winners instead)")
        + (f" and **{len(award_campaigns)}** award-winning campaign(s) relevant to this brand/therapy area." if award_campaigns else ".")
    )
    if content_library.get("found") and lib_counts.get("claims"):
        insp_summary += (f" Pulled **{lib_counts.get('claims', 0)}** library claims "
                         f"({lib_counts.get('approved_claims', 0)} MLR-approved) and "
                         f"**{lib_counts.get('assets', 0)}** existing content assets into the Create phase.")
    if kit and kit.get("concepts"):
        active_n = len(brand_kit_mod.active_concepts(kit))
        insp_summary += f" The brand's own shelf holds **{len(kit['concepts'])}** concepts ({active_n} active) — surfaced in §19."
    insp_bullets = [f"“{p['title']}” — {p['tier']} in {p['category']} ({p['agency_sponsor']}), {p['program']} {p['year']}"
                    for p in precedents] or ["No award-winning campaigns indexed yet"]
    insp_bullets += [f"🏆 {a['title']} — {a['award']} ({a['festival']} {a['year']}): {a['why_awarded'][:120]}…"
                     for a in award_campaigns[:2]]
    if kit and kit.get("concepts"):
        insp_bullets += [f"💡 {c['name']} [{c['status']}] — {c['description'][:110]}…" for c in kit["concepts"][:3]]
    insp_bullets += _agent_grounding_bullets(ctx, "inspiration")
    yield {"type": "agent", "id": "inspiration", "status": "done", "summary": insp_summary, "detail": {"bullets": insp_bullets}}
    yield _plan_partial(ctx, done_agents, "inspiration")

    if kit and brand_kit_mod.active_concepts(kit):
        _top_con = brand_kit_mod.active_concepts(kit)[0]
        yield _say("inspiration", f"The brand already has a platform on the shelf: **{_top_con['name']}**. "
                                  f"We extend it, we don't reinvent it — the creative job is continuity.", to="activation")
        yield _say("activation", "Then the mix funds the platform's hero moments, not a new campaign build. "
                                 "That's budget efficiency straight from the hub.", to="inspiration")
    elif award_campaigns:
        top_award = award_campaigns[0]
        yield _say("inspiration", f"The strongest reference is **{top_award['title']}** "
                                  f"({top_award['festival']} {top_award['year']}) — it won by making a hard "
                                  f"conversation easy to have.", to="activation")
        yield _say("activation", "Then the mix has to fund one hero asset, not spread thin across every channel. "
                                 "I'll protect budget for it.", to="inspiration")
    else:
        yield _say("activation", "No close creative precedent — so the channel plan carries more of the load. "
                                 "I'll lean on sequencing rather than a single hero idea.", to="inspiration")

    # 5. Activation Planning -- channel mix/budget + measurement/KPI + channel selection + execution plan
    yield _run("activation", "Modelling the channel mix, splitting the budget, building the KPI scorecard, and drafting the execution work plan…")
    channel_mix = strategy["channel_mix_pct"]
    budget_allocation = {ch: {"pct": pct, "amount": round(budget * pct / 100, 2) if budget else None}
                         for ch, pct in channel_mix.items()}
    ctx["budget_allocation"] = budget_allocation
    kpi = build_kpi_framework(inferred["stage_key"], channel_mix)
    ctx["kpi"] = kpi
    channel_selection = build_channel_selection(channel_mix, strategy["recommended_touchpoints"], inferred["persona"])
    execution_plan = build_execution_work_plan(micro_journeys)
    execution_raci = build_execution_raci()
    test_measure_learn = build_test_measure_learn(inferred["stage_key"], kpi["leading_indicators"])
    engagement_baseline = benchmarks.arjun_engagement_baseline(lifecycle_key, inferred["persona"], channel_mix)
    ctx["engagement_baseline"] = engagement_baseline
    # Fill Test-Measure-Learn's "what good looks like" from the benchmark matching what the
    # row actually MEASURES (not the channel it is tagged with -- those disagree). Volume
    # metrics like "impressions delivered" get no percentage band and are left untouched.
    for _row in test_measure_learn.get("rows", []):
        _t = benchmarks.measure_target(_row.get("measure", ""), _row.get("channels", ""), lifecycle_key)
        if _t:
            _row["what_good_looks_like"] = _t["what_good_looks_like"]
            _row["agent_recommended"] = True
            _row["agent_name"] = "Activation Planning"
    ctx["channel_selection"] = channel_selection
    ctx["execution_plan"] = execution_plan
    ctx["execution_raci"] = execution_raci
    ctx["test_measure_learn"] = test_measure_learn
    done_agents.add("activation")
    top = sorted(channel_mix.items(), key=lambda kv: -kv[1])[:2]
    top_str = ", ".join(f"{k} {v}%" for k, v in top)
    act_summary = (
        f"Emphasis on **{top_str}**" + (f" · ${int(budget):,} total" if budget else "")
        + f". **{len(kpi['leading_indicators'])}** leading / **{len(kpi['lagging_indicators'])}** lagging / "
          f"**{len(kpi['operational_kpis'])}** operational KPIs set. {execution_plan['total_weeks']}-week execution "
          f"work plan + RACI drafted."
    )
    act_summary += (f" Set engagement targets against industry baselines — "
                    f"**{engagement_baseline['emphasis'].lower()}**.")
    act_bullets = ([f"{ch}: {v['pct']}%" + (f" · ${int(v['amount']):,}" if v['amount'] else "")
                    for ch, v in sorted(budget_allocation.items(), key=lambda kv: -kv[1]['pct'])]
                   + [f"Target — {r['channel']}: {r['what_good_looks_like']}"
                      for r in engagement_baseline["channels"][:3] if r.get("target_low_pct") is not None]
                   + kpi["leading_indicators"][:2]
                   + [execution_plan["mlr_delay_note"]])
    act_bullets += _agent_grounding_bullets(ctx, "activation")
    yield {"type": "agent", "id": "activation", "status": "done", "summary": act_summary, "detail": {"bullets": act_bullets}}
    yield _plan_partial(ctx, done_agents, "activation")

    _eb = engagement_baseline["channels"][0] if engagement_baseline["channels"] else None
    if _eb and _eb.get("target_low_pct") is not None:
        yield _say("activation", f"Benchmark target for **{_eb['channel']}**: {_eb['what_good_looks_like']}. "
                                 f"That's the bar — I've written it into Test-Measure-Learn.", to="planner")
    if top:
        yield _say("planner", f"So the spine is **{top[0][0]}** at {top[0][1]}%. Everything's in — time to close the "
                              f"loop with the executive summary and the open questions.", to="activation")
    if content_library.get("found") and lib_counts.get("approved_claims"):
        yield _say("strategy", f"Before you seal it — the **{lib_counts['approved_claims']}** MLR-approved claims are "
                               f"wired into the message flow. Every claim in the plan traces to a source.", to="planner")

    # 6. Engagement Planner (finalize) -- questionnaires, open questions, executive summary, full document
    yield _run("planner", "Closing the loop — synthesizing the executive summary, collecting every open question for "
                          "your brand team, and finalizing the document…")
    cx_questionnaire = build_cx_questionnaire(brand, inferred["persona"], strategy, ctx["bam"], kpi)
    ctx["cx_questionnaire"] = cx_questionnaire
    open_qs = build_open_questions(cx_maturity["feasibility_checklist"], cx_questionnaire, ctx["tcg"])
    ctx["open_questions"] = open_qs
    n_open = sum(len(g["questions"]) for g in open_qs)
    result = _assemble_result(ctx)
    # Reveal only Phase 1 (Align) now; Select/Create/Deploy stay locked until the user
    # clarifies each phase in chat, so the document builds up one toolkit phase at a time.
    plan_markdown, plan_html, n_done_f, n_total_f = compose_plan_partial(ctx, None, "final", revealed_phases=_RUN_REVEAL)
    align_open = sum(len(g["questions"]) for g in open_qs if g.get("phase") == "align")
    yield {"type": "agent", "id": "planner", "status": "done", "final": True,
           "summary": (f"Phase 1 · **Align on customer understanding & CX objectives** is drafted and live on the right. "
                       f"Let's lock it together — I have {align_open} question(s) on it, then Phase 2 (messages & "
                       f"channels) unlocks. We'll build the plan one phase at a time."),
           "detail": {"bullets": [f"Align phase sections drafted; Select, Create and Deploy are locked until we align on this one",
                                  f"{n_open} 'needs alignment' items across {len(open_qs)} groups, sequenced by toolkit phase"]}}
    yield {"type": "plan", "html": plan_html, "markdown": plan_markdown, "partial": False,
           "sections_done": n_done_f, "sections_total": n_total_f, "fresh_agent": "final"}
    # ctx is included so the server can snapshot it for the persona 'apply feedback to plan'
    # action (which needs to re-run compose_plan with a patched budget mix later) -- the
    # server strips it before forwarding the event to the client, so it never hits the wire.
    yield {"type": "result", "result": result, "ctx": ctx}
    yield {"type": "narration", "text": (
        f"**Phase 1 · Align** is drafted for **{brand}** in **{therapy_area}** — you can see it on the right. "
        "The other three toolkit phases (Select → Create → Deploy) are shown locked beneath it and unlock one at a "
        "time as we align on each phase, so you watch the plan get stitched together section by section.\n\n"
        "Answer the Align questions I'm about to ask and I'll fold each into the plan live; once Align is set, "
        "**Select relevant messages & channels** unlocks next."
    )}
    yield {"type": "done"}


def compute_core_ctx(brand: str, therapy_area: str, lifecycle_key: str, budget: float = 0,
                     maturity_notes: str = "", indication: str = "", brief: dict | None = None) -> dict:
    """The FAST core of a plan ctx (sub-second): only what's needed to pose the first
    (customer-group) question — brand/therapy/lifecycle/brief plus the deterministic
    persona+stage inference and the local brand kit. Everything heavy (grounding, market,
    strategy, message flow, KPIs, …) is filled later by fill_plan_ctx, so the Studio run can
    pose its first ask in seconds instead of blocking minutes behind the full compute."""
    ctx: dict = {"brand": brand, "therapy_area": therapy_area, "lifecycle_key": lifecycle_key, "budget": budget,
                 "maturity_notes": maturity_notes, "indication": indication, "brief": brief or {}}
    ctx["slots"] = ctx["brief"]
    ctx["inferred"] = infer_persona_and_stage(lifecycle_key)
    ctx["brand_kit"] = brand_kit_mod.kit_for(brand)
    ctx["process_grounding"] = {}
    ctx["external_evidence"] = []
    ctx["strategic_source"] = None
    ctx["_core_only"] = True  # cleared by fill_plan_ctx once the heavy remainder is populated
    return ctx


def compute_plan_ctx(brand: str, therapy_area: str, lifecycle_key: str, budget: float = 0,
                     maturity_notes: str = "", indication: str = "", brief: dict | None = None,
                     lazy_grounding: bool = False) -> dict:
    """Full plan ctx = fast core + heavy fill. The classic phased flow calls this directly; the
    Studio flow poses its first ask from compute_core_ctx() and runs fill_plan_ctx() in the
    background so the first question isn't stuck behind minutes of market/strategy/grounding work."""
    ctx = compute_core_ctx(brand, therapy_area, lifecycle_key, budget, maturity_notes, indication, brief)
    return fill_plan_ctx(ctx, lazy_grounding=lazy_grounding)


def fill_plan_ctx(ctx: dict, lazy_grounding: bool = False, fast: bool = False) -> dict:
    """Populate the heavy remainder of a ctx built by compute_core_ctx (mutates in place):
    every agent's deterministic computation, plus cx_questionnaire + open_questions.

    `fast` (the Studio background fill) timeboxes/skips the three multi-minute calls that only
    feed LATER sections — live SWOT refresh, cognee brief-grounding, precedent-campaign search —
    so the next ask isn't stuck behind ~200s of network+LLM work. They degrade to cached/empty."""
    brand = ctx["brand"]; therapy_area = ctx["therapy_area"]; lifecycle_key = ctx["lifecycle_key"]
    budget = ctx["budget"]; maturity_notes = ctx["maturity_notes"]; indication = ctx["indication"]
    brief = ctx["brief"]; inferred = ctx["inferred"]; kit = ctx["brand_kit"]
    # Ground every agent's section in the firm's own documented process (Omni OS docs ingested
    # into cognee) + live external datapoints. These are the two HEAVY pulls (cognee recall +
    # ClinicalTrials/PubMed/openFDA network). With lazy_grounding (the Sequential Studio flow)
    # they are deferred: studio_run.ensure_grounding pulls each section's slice on demand and
    # prefetches the next during the ask pause. The classic phased flow keeps the eager pull.
    if lazy_grounding:
        ctx["process_grounding"] = {}
        ctx["external_evidence"] = []
    else:
        ctx["process_grounding"] = process_knowledge.ground_all(brand, therapy_area)
        ctx["external_evidence"] = external_evidence.datapoints(therapy_area, brand)

    # An uploaded strategic-plan document (captured by /api/upload alongside the brief) grounds
    # the Tactical Plan sections when present; None when no such document was uploaded, in which
    # case those sections fall back to Omni OS's own already-computed strategy ctx below.
    tactical_text = (brief or {}).get("tactical_source_text")
    ctx["strategic_source"] = (
        tactical_source.extract_strategic_source(tactical_text, (brief or {}).get("tactical_source_name", ""))
        if tactical_text else None
    )

    # -- Market & Competitive Intelligence --
    ctx["market"] = market_landscape(brand, therapy_area)
    if kit and kit.get("competitors"):
        competitors = [c["name"] for c in kit["competitors"]][:4]
    else:
        competitors = discover_competitors(therapy_area, brand, limit=5)
    ctx["competitors"] = competitors
    # SWOT live-refresh is tens of seconds and only feeds a later section. In fast mode SKIP it
    # (None = the same state as a no-competitor plan, which the renderers already handle) — no
    # background thread, since these external calls contend with cognee/network and blow up the
    # total time unpredictably. [[studio-lazy-grounding]] can backfill it per-section later.
    ctx["swot"] = None if fast else (build_swot(brand, competitors, therapy_area, refresh=True) if competitors else None)
    ctx["audience_profile"] = benchmarks.maya_audience_profile(brand, therapy_area, inferred["persona"])
    ctx["hcp_360_grounding"] = hcp_360.ground_segment(therapy_area, inferred["persona"])
    # cognee brief-grounding is ~80s here and every recall fails to {} anyway; skip it in fast mode.
    ctx["brief_grounding"] = {} if fast else process_knowledge.brief_grounding(brand, therapy_area)

    # -- Strategy & Positioning --
    strategy = generate_strategy(brand, therapy_area, inferred["persona"], inferred["stage_key"],
                                 ctx["brief_grounding"])
    ctx["strategy"] = strategy
    bam = build_bam_chart(inferred["stage_key"])
    micro_journeys = build_micro_journeys(inferred["stage_key"], strategy["recommended_touchpoints"])
    cx_maturity = assess_cx_maturity(maturity_notes, strategy["channel_mix_pct"])
    segment_profile = build_segment_profile(inferred["persona"], inferred["stage_key"])
    tcg = build_tcg_template(inferred["persona"], segment_profile, strategy, bam,
                             agent_answers=ctx["audience_profile"]["answers"], agent_name="Market & Competitive Intelligence")
    message_flow = build_message_flow(inferred["stage_key"], strategy["kb_grounding"])
    if kit:
        if kit.get("message_pool"):
            message_flow["brand_plan_key_message_pool"] = list(kit["message_pool"])
        for km in message_flow["key_messages"]:
            claim = brand_kit_mod.claim_for_topic(kit, km["topic"])
            if claim and claim not in km["supporting_messages"]:
                km["supporting_messages"] = [claim] + list(km["supporting_messages"])[:2]
        message_flow["caveat"] = (message_flow.get("caveat", "") + " Key-message pool and lead supporting claims "
                                  f"sourced verbatim from the {kit.get('source_label', 'brand intelligence hub')}.")
    ctx["bam"] = bam
    ctx["pp_npp"] = classify_pp_npp(strategy["channel_mix_pct"])
    ctx["micro_journeys"] = micro_journeys
    ctx["cx_maturity"] = cx_maturity
    ctx["segment_profile"] = segment_profile
    ctx["tcg"] = tcg
    ctx["message_flow"] = message_flow
    ctx["positioning"] = build_positioning_statement(brand, therapy_area, inferred["persona"],
                                                      inferred["stage_key"], competitors)

    # -- Creative Inspiration --
    # Precedent-campaign search is ~60s of network and only feeds later creative sections; skip in fast mode.
    ctx["precedents"] = [] if fast else find_precedent_campaigns(therapy_area, brand, limit=3)
    ctx["award_campaigns"] = awards_store.awards_for(brand=brand, therapy_area=therapy_area, limit=4)
    # A kit brand's authored content library (claims + creative components WITH images) is the
    # source of truth -- it wins over any lossy echo persisted into campaign_store from a prior
    # run. Non-kit brands use the scraped/persisted library as before.
    if kit and kit.get("components"):
        content_library = brand_kit_mod.content_library_from_kit(kit, indication)
    else:
        content_library = campaign_store.content_library_for(brand, indication)
    ctx["content_library"] = content_library

    # -- Activation Planning --
    channel_mix = strategy["channel_mix_pct"]
    ctx["budget_allocation"] = {ch: {"pct": pct, "amount": round(budget * pct / 100, 2) if budget else None}
                                for ch, pct in channel_mix.items()}
    kpi = build_kpi_framework(inferred["stage_key"], channel_mix)
    ctx["kpi"] = kpi
    ctx["channel_selection"] = build_channel_selection(channel_mix, strategy["recommended_touchpoints"], inferred["persona"])
    ctx["execution_plan"] = build_execution_work_plan(micro_journeys)
    ctx["execution_raci"] = build_execution_raci()
    test_measure_learn = build_test_measure_learn(inferred["stage_key"], kpi["leading_indicators"])
    engagement_baseline = benchmarks.arjun_engagement_baseline(lifecycle_key, inferred["persona"], channel_mix)
    ctx["engagement_baseline"] = engagement_baseline
    for _row in test_measure_learn.get("rows", []):
        _t = benchmarks.measure_target(_row.get("measure", ""), _row.get("channels", ""), lifecycle_key)
        if _t:
            _row["what_good_looks_like"] = _t["what_good_looks_like"]
            _row["agent_recommended"] = True
            _row["agent_name"] = "Activation Planning"
    ctx["test_measure_learn"] = test_measure_learn

    # -- Engagement Planner close (questionnaire + open questions) --
    ctx["cx_questionnaire"] = build_cx_questionnaire(brand, inferred["persona"], strategy, ctx["bam"], kpi)
    ctx["open_questions"] = build_open_questions(cx_maturity["feasibility_checklist"], ctx["cx_questionnaire"], ctx["tcg"])
    ctx.pop("_core_only", None)  # heavy remainder is now populated
    return ctx


# What each agent says while working / what it reports on finishing, per phase. Grounded in ctx.
def _agent_phase_turn(aid: str, phase: str, ctx: dict):
    """Yield the visible work of one agent for one phase: a 'running' line, then a 'done'
    summary + bullets. Pure theater over the already-computed ctx."""
    inferred = ctx["inferred"]
    brand, ta = ctx["brand"], ctx["therapy_area"]
    kit = ctx.get("brand_kit")

    if phase == "align" and aid == "planner":
        yield _run("planner", f"Framing the plan for {brand} — locking the brief, governance and the customer-"
                              f"understanding sections, and loading the brand intelligence kit…")
        s = "Brief, governance and the Align sections are framed."
        b = [inferred["rationale"]]
        if kit:
            s += f" Grounded in the brand's own hub — “{kit.get('core_claim', '')}”."
            b.append(f"Brand kit: {kit.get('source_label', '')}")
        return (yield {"type": "agent", "id": "planner", "status": "done", "summary": s, "detail": {"bullets": b}})

    if phase == "align" and aid == "intel":
        comps = ctx.get("competitors") or []
        ap = ctx.get("audience_profile") or {}
        yield _run("intel", f"Sizing the {ta} landscape, hunting competitors, and profiling the target customers…")
        s = (f"{inferred['lifecycle_label']} → targeting **{inferred['persona']}**. "
             + (f"**{len(comps)}** competitor(s): {', '.join(comps)}." if comps else "No distinct competitors found."))
        if ap.get("audience_size", {}).get("total"):
            s += f" Audience: **{ap['headline']}**."
        b = ([inferred["rationale"]] + (comps or ["No competing interventions in trial data"])
             + ([f"Audience benchmark: {ap['headline']}"] if ap.get("audience_size", {}).get("total") else []))
        return (yield {"type": "agent", "id": "intel", "status": "done", "summary": s, "detail": {"bullets": b}})

    if phase == "align" and aid == "strategy":
        bam = ctx["bam"]; cxm = ctx["cx_maturity"]; pos = ctx["positioning"]
        yield _run("strategy", "Mapping the journey stage and BAM belief-shift, scoring CX feasibility, and drafting "
                               "the target-customer-group profile and positioning…")
        s = (f"Belief shift **{bam['a_to_b_shift']}**. CX maturity **{cxm['level']}**. Positioning drafted.")
        b = [f"A→B shift: {bam['a_to_b_shift']}",
             f"CX maturity: {cxm['level']} — {cxm['rationale']}",
             f"Positioning: {pos['positioning_statement']}"]
        return (yield {"type": "agent", "id": "strategy", "status": "done", "summary": s, "detail": {"bullets": b}})

    if phase == "select" and aid == "strategy":
        mf = ctx["message_flow"]
        yield _run("strategy", "Selecting the four key messages and building the message flow with its non-opener branch…")
        kms = [k["topic"] for k in mf["key_messages"]]
        s = f"Message flow built — leading with **{', '.join(kms[:2])}**" + (" and more." if len(kms) > 2 else ".")
        b = [f"Key messages: {', '.join(kms)}"]
        if kit and mf.get("brand_plan_key_message_pool"):
            b.append(f"Pool sourced from the brand hub: “{mf['brand_plan_key_message_pool'][0]}”")
        return (yield {"type": "agent", "id": "strategy", "status": "done", "summary": s, "detail": {"bullets": b}})

    if phase == "select" and aid == "inspiration":
        prec = ctx.get("precedents") or []
        yield _run("inspiration", f"Pulling award-winning {ta} precedents and the brand's concept shelf…")
        s = f"Found **{len(prec)}** precedent campaign(s) to steer the creative."
        b = [f"“{p['title']}” — {p['tier']} ({p['program']} {p['year']})" for p in prec] or ["No indexed precedents"]
        if kit and kit.get("concepts"):
            b.append(f"Brand concept shelf: {len(kit['concepts'])} concepts")
        return (yield {"type": "agent", "id": "inspiration", "status": "done", "summary": s, "detail": {"bullets": b}})

    if phase == "select" and aid == "activation":
        cs = ctx.get("channel_selection") or {}
        ba = ctx.get("budget_allocation") or {}
        top = sorted(((k, v["pct"]) for k, v in ba.items()), key=lambda kv: -kv[1])[:2]
        yield _run("activation", "Scoring channels on purpose, availability and preference, and splitting the budget…")
        s = "Channel selection scored and budget split — emphasis on **" + ", ".join(f"{k} {v}%" for k, v in top) + "**."
        b = [f"{k}: {v['pct']}%" + (f" · ${int(v['amount']):,}" if v.get("amount") else "")
             for k, v in sorted(ba.items(), key=lambda kv: -kv[1]["pct"])[:4]]
        return (yield {"type": "agent", "id": "activation", "status": "done", "summary": s, "detail": {"bullets": b}})

    if phase == "create" and aid == "inspiration":
        lib = ctx.get("content_library") or {}
        cnt = lib.get("counts", {})
        yield _run("inspiration", "Mapping existing content to the message flow, designing the channel and message flows…")
        s = ("Mapped the content audit and designed the channel + message flows."
             + (f" **{cnt.get('assets', 0)}** brand assets, **{cnt.get('claims', 0)}** claims wired in." if lib.get("found") else ""))
        b = [f"{cnt.get('assets', 0)} existing assets ({cnt.get('approved_claims', 0)} MLR-approved claims)"] if lib.get("found") \
            else ["No content library indexed — audit ships as the toolkit template"]
        return (yield {"type": "agent", "id": "inspiration", "status": "done", "summary": s, "detail": {"bullets": b}})

    if phase == "create" and aid == "activation":
        kpi = ctx["kpi"]
        yield _run("activation", "Defining the CX success metrics (opt-in / non-opt-in) for the experience…")
        s = f"Metrics set — **{len(kpi['leading_indicators'])}** leading indicators to track CX success."
        b = kpi["leading_indicators"][:3]
        return (yield {"type": "agent", "id": "activation", "status": "done", "summary": s, "detail": {"bullets": b}})

    if phase == "deploy" and aid == "activation":
        ep = ctx["execution_plan"]; kpi = ctx["kpi"]
        yield _run("activation", "Laying out the execution work plan, RACI and the closed-loop test-measure-learn model…")
        s = f"**{ep['total_weeks']}-week** execution work plan + RACI and the closed-loop model drafted."
        b = [ep["mlr_delay_note"],
             f"{len(kpi['leading_indicators'])} leading / {len(kpi['lagging_indicators'])} lagging KPIs"]
        return (yield {"type": "agent", "id": "activation", "status": "done", "summary": s, "detail": {"bullets": b}})

    if phase == "deploy" and aid == "planner":
        oq = ctx.get("open_questions") or []
        n_open = sum(len(g["questions"]) for g in oq)
        yield _run("planner", "Writing the executive summary and closing the loop on the full plan…")
        s = f"Executive summary written — the plan is complete across all four phases. **{n_open}** items still need your sign-off."
        b = ["Executive summary synthesized from the whole team's output",
             f"{n_open} 'needs alignment' items across {len(oq)} groups"]
        return (yield {"type": "agent", "id": "planner", "status": "done", "final": True, "summary": s, "detail": {"bullets": b}})

    # Fallback (shouldn't happen): a bare done.
    yield {"type": "agent", "id": aid, "status": "done", "summary": "", "detail": {"bullets": []}}


# Short banter exchange to open each phase (grounded, optional).
def _phase_banter(phase: str, ctx: dict):
    inferred = ctx["inferred"]
    if phase == "align":
        yield _say("planner", "Let's build this the right way — Align first. Customer understanding and CX "
                              "objectives before anything else.", to="intel")
    elif phase == "select":
        mf = ctx["message_flow"]
        yield _say("strategy", f"Align's signed off. Now we choose what to say and where — leading with "
                               f"{mf['key_messages'][0]['topic'].lower()}.", to="activation")
    elif phase == "create":
        yield _say("inspiration", "Messages and channels are locked. Now we build the actual experience — content, "
                                  "journeys, the flows.", to="activation")
    elif phase == "deploy":
        yield _say("activation", "The CX is designed. Last step — how it ships: the work plan, ownership, and how "
                                 "we measure and learn.", to="planner")


# Grounded aside exchanged between two teammates as one hands off to the next within a phase --
# the "team talking through the problem" texture from the original single-pass run_agents(),
# reused here per consecutive pair of agents inside a phase (not just once at phase open).
def _handoff_banter(phase: str, from_id: str, to_id: str, ctx: dict):
    kit = ctx.get("brand_kit")
    comps = ctx.get("competitors") or []
    inferred = ctx["inferred"]

    if phase == "align" and from_id == "planner" and to_id == "intel":
        if kit:
            yield _say("planner", f"Structure's up. And we're not starting cold — the hub gives us "
                                  f"“{kit.get('core_claim', '')}” with a three-pillar message hierarchy already MLR-framed.", to="intel")
        else:
            yield _say("planner", "Structure's up — every section is tagged with who owns it. Market read comes first.", to="intel")
        yield _say("intel", "On it. Lifecycle says " + inferred["lifecycle_label"].lower() +
                            " — I'll pull the live landscape and hunt competitors in the trial data.", to="planner")

    elif phase == "align" and from_id == "intel" and to_id == "strategy":
        if comps:
            yield _say("strategy", f"{len(comps)} live competitor(s) in {ctx['therapy_area']} — that makes this a "
                                   f"share-of-voice fight, not a category build. The SWOT gives me my positioning openings.", to="intel")
            yield _say("intel", f"Agreed. {comps[0]} is the one to watch — it shows up across the data.", to="strategy")
        else:
            yield _say("strategy", f"No distinct competitors in the trial data — so we're building the category in "
                                   f"{ctx['therapy_area']}, not defending share. That changes the messaging job.", to="intel")

    elif phase == "select" and from_id == "strategy" and to_id == "inspiration":
        m = ctx["strategy"]["messaging_architecture"]
        yield _say("inspiration", f"“{m['current_belief']}” → “{m['desired_belief']}” is a creative brief in one line. "
                                  f"Let me find award-winning work that pulled off the same belief change.", to="strategy")
        yield _say("strategy", f"Lead with {m['messaging_type'].lower()}.", to="inspiration")

    elif phase == "select" and from_id == "inspiration" and to_id == "activation":
        active = brand_kit_mod.active_concepts(kit) if kit else []
        if active:
            yield _say("inspiration", f"The brand already has a platform on the shelf: **{active[0]['name']}**. "
                                      f"We extend it, we don't reinvent it.", to="activation")
            yield _say("activation", "Then the mix funds the platform's hero moments, not a new campaign build.", to="inspiration")
        else:
            yield _say("activation", "No close creative precedent — so the channel plan carries more of the load. "
                                     "I'll lean on sequencing rather than a single hero idea.", to="inspiration")

    elif phase == "create" and from_id == "inspiration" and to_id == "activation":
        lib = ctx.get("content_library") or {}
        if lib.get("found") and lib.get("counts", {}).get("claims"):
            yield _say("inspiration", f"The content audit is mapped — **{lib['counts'].get('claims', 0)}** claims, "
                                      f"**{lib['counts'].get('assets', 0)}** assets wired to the flow.", to="activation")
        yield _say("activation", "Good — I'll set the metrics against what's actually available to ship.", to="inspiration")

    elif phase == "deploy" and from_id == "activation" and to_id == "planner":
        ep = ctx.get("execution_plan") or {}
        if ep.get("total_weeks"):
            yield _say("activation", f"Work plan's a {ep['total_weeks']}-week build with RACI attached.", to="planner")
        yield _say("planner", "Then I'll close the loop — executive summary, and whatever still needs your sign-off.", to="activation")


def phase_open(phase: str):
    """Immediate visual feedback the instant a phase starts -- team roster + narration --
    yielded BEFORE the (possibly slow, on Align: 30-60s of live network calls) compute_plan_ctx
    call. The server yields this first so the team panel populates right away instead of
    sitting on a silent EventSource for the whole compute; run_phase() below then skips
    re-yielding it via opened=True."""
    agents = PHASE_AGENTS[phase]
    yield {"type": "agents_init", "agents": [a for a in AGENT_ROSTER if a["id"] in agents],
           "phase": phase, "phase_no": PHASE_NO[phase], "phase_label": PHASE_LABELS[phase]}
    yield {"type": "narration",
           "text": f"**Phase {PHASE_NO[phase]} · {PHASE_LABELS[phase]}** — your agent is on this step now."}


def run_phase(phase: str, ctx: dict, opened: bool = False):
    """Stream one toolkit phase's visible agent work over an already-computed ctx, revealing
    the plan up to this phase. Ends WITHOUT the human gate -- the server seeds this phase's
    validation questions and asks them, then the run stops until the user signs off.
    opened=True means the caller already streamed phase_open()'s events (used by the server
    to show the team immediately, before the ctx compute that must happen in between)."""
    reveal = _phase_reveal(phase)
    agents = PHASE_AGENTS[phase]
    done: set = set(PHASE_ORDER)  # for owner-gating we treat all agents as available; phase gating hides the rest
    if not opened:
        yield from phase_open(phase)
    yield from _phase_banter(phase, ctx)
    done_agents: set = set()
    for i, aid in enumerate(agents):
        # Every agent's turn is computed from an already-populated ctx (no real work happens
        # here), so without a deliberate pause the 'running' -> 'done' events fire back to back
        # and the working/shimmer animation never has time to actually show. AGENT_TURN_PACING_SEC
        # holds the 'running' state on screen for real, the way live network calls used to.
        turn = _agent_phase_turn(aid, phase, ctx)
        yield next(turn)  # the 'running' event
        time.sleep(AGENT_TURN_PACING_SEC)
        # Stream the 'done' event, folding in this agent's Omni OS process-grounding bullets so
        # the phased run visibly shows each agent consulting the firm's documented process.
        for ev in turn:
            if ev.get("status") == "done":
                gb = _agent_grounding_bullets(ctx, aid)
                if gb:
                    detail = ev.setdefault("detail", {})
                    detail["bullets"] = list(detail.get("bullets") or []) + gb
            yield ev
        done_agents.add(aid)
        yield _plan_partial(ctx, done | done_agents, aid, revealed=reveal)
        if i + 1 < len(agents):
            yield from _handoff_banter(phase, aid, agents[i + 1], ctx)
    # Final render for this phase (partial=False only on the last phase).
    result = _assemble_result(ctx)
    md, html_out, n_done, n_total = compose_plan_partial(ctx, None, "", revealed_phases=reveal)
    yield {"type": "plan", "html": html_out, "markdown": md, "partial": (phase != "deploy"),
           "sections_done": n_done, "sections_total": n_total, "fresh_agent": ""}
    yield {"type": "result", "result": result, "ctx": ctx}
    yield {"type": "done", "phase": phase, "phase_no": PHASE_NO[phase],
           "last_phase": (phase == PHASE_ORDER[-1])}


def _assemble_result(ctx: dict) -> dict:
    """Same shape as autorun.run_full_analysis, so it persists / renders identically."""
    strategy = ctx["strategy"]
    inferred = ctx["inferred"]
    _brief = ctx.get("brief") or {}
    # The user-supplied brief fields from the fill-in-the-blanks intake, echoed into the plan
    # so the objective/audience/KPI/reason/etc. they gave are on the record (empty ones dropped).
    campaign_brief = {k: _brief.get(k) for k in (
        "campaign_name", "molecule", "audience", "geography", "duration", "objective", "kpi",
        "existing_assets", "preferred_channels", "constraints", "notes", "reason")
        if _brief.get(k) and _brief.get(k) != "(not specified)"}
    return {
        "brand": ctx["brand"],
        "therapy_area": ctx["therapy_area"],
        "indication": ctx.get("indication", ""),
        "campaign_brief": campaign_brief,
        "inferred_inputs": {
            "persona": inferred["persona"],
            "stage_key": inferred["stage_key"],
            "stage_label": strategy["inputs"]["stage"],
            "lifecycle_label": inferred["lifecycle_label"],
            "lifecycle_rationale": inferred["rationale"],
            "discovered_competitors": ctx["competitors"],
        },
        "stage_1_market_landscape": ctx["market"],
        "stage_2_4_strategy": strategy,
        "stage_2_4_bam_chart": ctx["bam"],
        "stage_2_4_pp_npp": ctx["pp_npp"],
        "stage_2_4_micro_journeys": ctx["micro_journeys"],
        "stage_2_4_segment_profile": ctx["segment_profile"],
        "stage_2_4_tcg_template": ctx["tcg"],
        "stage_2_4_cx_questionnaire": ctx["cx_questionnaire"],
        "open_questions": ctx["open_questions"],
        "stage_2_4_feasibility": ctx["cx_maturity"]["feasibility_checklist"],
        "stage_2_4_message_flow": ctx["message_flow"],
        "cx_maturity": ctx["cx_maturity"],
        "precedent_campaigns": ctx["precedents"],
        "award_campaigns": ctx.get("award_campaigns", []),
        "stage_1b_3_competitive": ctx["swot"],
        "stage_3_positioning": ctx["positioning"],
        "stage_5_budget": {"total_budget": ctx["budget"] or None, "allocation": ctx["budget_allocation"],
                            "caveat": strategy["caveat"]},
        "stage_5_channel_selection": ctx["channel_selection"],
        "stage_3_campaign_plan": campaign_ops.build_campaign_plan(ctx),
        "content_library": ctx.get("content_library", {}),
        "audience_profile": ctx.get("audience_profile", {}),
        "engagement_baseline": ctx.get("engagement_baseline", {}),
        "brand_kit": ctx.get("brand_kit") or {},
        "stage_7_kpi": ctx["kpi"],
        "stage_9_test_measure_learn": ctx["test_measure_learn"],
        "stage_9_execution_plan": ctx["execution_plan"],
        "stage_9_execution_raci": ctx["execution_raci"],
        "stage_8_risk_governance": {"standard_risks": STANDARD_RISKS, "governance_cadence": GOVERNANCE_CADENCE},
    }


def recompose_plan(ctx: dict, revealed_phases: set | None = None) -> tuple[dict, str, str]:
    """Re-render the plan from a (possibly patched) ctx snapshot, without re-running any
    agent. Used both by the persona 'apply feedback to plan' action (which patches
    budget_allocation) and by refresh_after_clarify() below (which patches cx_maturity/
    open_questions) -- any future ctx-patching action should reuse this rather than calling
    _assemble_result/compose_plan directly, so the two always stay in sync.

    revealed_phases gates the interactive phase-by-phase build: None reveals every toolkit
    phase (persona-apply, exports); the clarify flow passes the set unlocked so far so the
    plan reveals a phase at a time as the user answers each phase's questions."""
    result = _assemble_result(ctx)
    plan_markdown, plan_html = compose_plan(ctx, revealed_phases=revealed_phases)
    return result, plan_markdown, plan_html


def refresh_after_clarify(ctx: dict, maturity_notes: str, resolved_group_ids: set[str]) -> dict:
    """Re-derive cx_maturity and the plan's own open_questions list from the latest
    maturity_notes (which grows as the user answers the post-plan clarify Q&A), then drop any
    group the user has already been asked about in THIS conversation -- keyed by the same
    stable group ids open_questions.build_open_questions() always uses ('objectives',
    'segment', 'database', ...).

    This is deliberately id-based rather than content-based: the feasibility checklist's
    auto-answer logic is a simple keyword scan (bam.has_maturity_signal) and will often still
    read a specific free-text answer as 'not yet captured'. Re-asking a question the user
    already answered -- just because the engine couldn't structurally parse the answer -- is
    the wrong trade; once a group has been asked, it is never asked again for this project.
    """
    ctx = dict(ctx)  # shallow copy -- callers keep their own reference to the original
    ctx["maturity_notes"] = maturity_notes
    new_cx_maturity = assess_cx_maturity(maturity_notes, ctx["strategy"]["channel_mix_pct"])
    raw_open = build_open_questions(new_cx_maturity["feasibility_checklist"], ctx["cx_questionnaire"], ctx["tcg"])
    ctx["cx_maturity"] = new_cx_maturity
    ctx["open_questions"] = [g for g in raw_open if g["id"] not in resolved_group_ids]
    return ctx


