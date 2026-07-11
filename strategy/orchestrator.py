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
import sys

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

# Each agent is named by its function. The Engagement Planner Agent is the one exception
# with a human name in its title (Cooper's successor): it opens the run by framing the
# document structure and closes it by writing the executive summary -- the plan's author.
# Pipeline order == the order sections fill into the live document: planner scaffolds,
# then intel -> strategy -> inspiration -> activation each complete their own sections,
# then the planner returns to finalize. The UI shows a photo avatar (purely decorative)
# with `initials` as the monogram fallback if it fails to load.
AGENT_ROSTER = [
    {"id": "planner", "name": "Engagement Planner Agent", "role": "",
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


# The interactive build reveals the plan phase by phase: the run itself only ever reveals
# Phase 1 (Align) + the always-on base/supporting sections; the later phases unlock as the
# user answers each phase's clarify questions in chat (see open_questions.revealed_phases_for).
_RUN_REVEAL = {"align"}


def _plan_partial(ctx: dict, done: set, fresh: str):
    """A progressive render of the plan document: sections owned by completed agents are
    real, the rest are owner-labelled placeholders. The UI swaps the plan pane in place, so
    the document visibly fills in as each agent finishes. Gated to the Align phase so the
    plan stitches together one toolkit phase at a time."""
    md, html_out, n_done, n_total = compose_plan_partial(ctx, done, fresh, revealed_phases=_RUN_REVEAL)
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
    done_agents.add("planner")
    _, _, n_done0, n_total0 = compose_plan_partial(ctx, done_agents, "")
    planner_summary = (f"Plan structure framed — **{n_total0}** sections scaffolded across the four toolkit phases. "
                       f"Brief, governance and caveats are locked; the team fills the rest in live on the right.")
    planner_bullets = [inferred["rationale"],
                       f"{n_done0} of {n_total0} sections filled at kickoff; each remaining section is labelled with the agent that owns it"]
    if kit:
        planner_summary += (f" This brand ships its own intelligence hub — **{kit.get('tagline', '')}** platform, "
                            f"message hierarchy, guardrails and {len(kit.get('concepts', []))} campaign concepts are "
                            f"loaded into the Brand foundation section.")
        planner_bullets += [f"Brand kit: {kit.get('source_label', '')} — core claim “{kit.get('core_claim', '')}”",
                            f"{len((kit.get('guardrails') or {}).get('dos', []))} brand dos / "
                            f"{len((kit.get('guardrails') or {}).get('donts', []))} don'ts folded into Risk & governance"]
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
    strategy = generate_strategy(brand, therapy_area, inferred["persona"], inferred["stage_key"])
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
    content_library = campaign_store.content_library_for(brand, indication)
    # Fictional kit brands (e.g. Oncomyra) have no scraped KB -- source the Create-phase
    # content library from the brand kit's own claims + creative components instead.
    if not content_library.get("found") and kit:
        content_library = brand_kit_mod.content_library_from_kit(kit, indication)
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


