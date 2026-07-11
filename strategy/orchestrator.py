"""Multi-agent orchestrator for the campaign-planning workspace.

`run_agents()` is a generator that yields events as each specialist agent works, then a
composer agent assembles a Campaign Plan document. The FastAPI layer streams these events
as Server-Sent Events so the UI can show the agents thinking in real time. Every agent
reuses the same real, data-backed functions the rest of the tool uses -- the "agents" are
genuine pipeline stages, not theatre.

Five broad-mandate agents (not ten narrow ones -- consolidated 2026-07-08 per feedback that
the roster was too granular): each agent owns a coherent piece of the plan rather than one
function call apiece. An agent's turn simply appears in the chat when it starts running --
there is no separate handoff animation between turns.
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
from plan_document import compose_plan  # noqa: E402
from message_flow import build_message_flow  # noqa: E402
from channel_selection import build_channel_selection  # noqa: E402
import campaign_store  # noqa: E402  (content library query for the plan's Phase-2/3 sections)
import awards_store  # noqa: E402  (award-winning campaign matches for the precedent section)
import benchmarks  # noqa: E402  (industry baselines Maya and Arjun fill plan sections from)
from execution_plan import build_execution_work_plan, build_execution_raci  # noqa: E402
from test_measure_learn import build_test_measure_learn  # noqa: E402

# Each agent is a named teammate with a role. First name only, chosen to share its first
# letter with what the agent does (Maya=Market, Sam=Strategy, Chloe=Creative, Arjun=
# Activation, Cooper=Campaign compose). The UI shows a photo avatar; `initials` seeds the
# monogram fallback. They work as a team, not a relay: summaries avoid "handing over".
AGENT_ROSTER = [
    {"id": "intel", "name": "Maya", "role": "Market & Competitive Intelligence",
     "initials": "Ma", "icon": "travel_explore"},
    {"id": "strategy", "name": "Sam", "role": "Strategy & Positioning",
     "initials": "Sa", "icon": "track_changes"},
    {"id": "inspiration", "name": "Chloe", "role": "Creative Inspiration",
     "initials": "Ch", "icon": "emoji_events"},
    {"id": "activation", "name": "Arjun", "role": "Activation Planning",
     "initials": "Ar", "icon": "payments"},
    {"id": "compose", "name": "Cooper", "role": "Brand Engagement Plan Composer",
     "initials": "Co", "icon": "description"},
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


def run_agents(brand: str, therapy_area: str, lifecycle_key: str, budget: float = 0, maturity_notes: str = "",
               indication: str = "", brief: dict | None = None):
    """Generator yielding orchestration events. The named teammates work as a group --
    each speaks in the chat (`say` on running, `summary` on done) as it picks up its
    piece; summaries describe what they found, not a hand-off, so the flow reads as a
    team collaborating rather than a linear relay. Terminal events: 'plan', 'result', 'done'."""
    yield {"type": "agents_init", "agents": AGENT_ROSTER}
    ctx: dict = {"brand": brand, "therapy_area": therapy_area, "lifecycle_key": lifecycle_key, "budget": budget,
                 "maturity_notes": maturity_notes, "indication": indication, "brief": brief or {}}

    ind_note = f" for the {indication} indication" if indication else ""

    # 1. Market & Competitive Intelligence -- lifecycle read, live market landscape, competitor discovery
    yield _run("intel", f"Reading where {brand} sits in its lifecycle{ind_note}, scanning the live market, and hunting competitors in the trial data…")
    inferred = infer_persona_and_stage(lifecycle_key)
    ctx["inferred"] = inferred
    yield {"type": "inferred", "persona": inferred["persona"], "lifecycle_label": inferred["lifecycle_label"]}
    market = market_landscape(brand, therapy_area)
    ctx["market"] = market
    b_n, t_n = _kb_count(market.get("brand", {})), _kb_count(market.get("therapy_area", {}))
    competitors = discover_competitors(therapy_area, brand, limit=5)
    ctx["competitors"] = competitors
    yield {"type": "inferred", "competitors": competitors}
    # Maya sizes the addressable HCP universe and reads its access / digital posture from
    # the researched industry benchmarks -- this fills TCG rows the state can't answer.
    audience_profile = benchmarks.maya_audience_profile(brand, therapy_area, inferred["persona"])
    ctx["audience_profile"] = audience_profile
    intel_summary = (
        f"{inferred['lifecycle_label']} → targeting **{inferred['persona']}** HCPs. Indexed **{b_n + t_n}** live documents. "
        + (f"Found **{len(competitors)}** competitor(s): {', '.join(competitors)}." if competitors
           else "No distinct competitors found in public trial data.")
    )
    if audience_profile["audience_size"]["total"]:
        intel_summary += f" Sized the audience: **{audience_profile['headline']}**."
    intel_bullets = [
        inferred["rationale"],
        f"{b_n} real documents on {brand}, {t_n} on {therapy_area} (FDA labels, ClinicalTrials.gov, PubMed, DailyMed, Google Trends)",
    ] + (competitors or ["ClinicalTrials.gov returned no distinct competing interventions"])
    if audience_profile["audience_size"]["total"]:
        intel_bullets.append(f"Audience benchmark ({audience_profile['confidence']}): {audience_profile['headline']}")
        intel_bullets.append("I filled 3 Target-Customer-Group rows from industry benchmarks — flagged as agent-recommended in the plan.")
    yield {"type": "agent", "id": "intel", "status": "done", "summary": intel_summary,
           "detail": {"bullets": intel_bullets}}

    # --- the team reacts to what Maya found ---
    if competitors:
        yield _say("strategy", f"{len(competitors)} live competitor(s) in {therapy_area} — that makes this a "
                               f"share-of-voice fight, not a category build. I'll run the SWOT against them.", to="intel")
        yield _say("intel", f"Agreed. {competitors[0]} is the one to watch — it shows up across the trial data.", to="strategy")
    else:
        yield _say("strategy", f"No distinct competitors in the trial data — so we're building the category in "
                               f"{therapy_area}, not defending share. That changes the messaging job.", to="intel")
    yield _say("activation", f"Noting the **{inferred['lifecycle_label']}** stage — it'll drive how I weight the "
                             f"channel mix later.", to="intel")
    _acc = audience_profile["rep_access"]
    if audience_profile["audience_size"]["total"]:
        yield _say("intel", f"Audience is **{audience_profile['headline']}**. I've filled the demographics, "
                            f"representative-attributes and attitude-to-industry rows from benchmarks.", to="activation")
        if _acc.get("specialty_fully_accessible_pct"):
            yield _say("activation", f"Only {_acc['specialty_fully_accessible_pct']:.0f}% of {_acc['lead_specialty']} "
                                     f"providers are fully rep-accessible — I'll cap Field and push budget to the "
                                     f"channels they'll actually open.", to="intel")

    # 2. Strategy & Positioning -- segmentation/journey/BAM/PP-NPP/micro-journeys/CX-maturity + SWOT + positioning
    yield _run("strategy", "Mapping the journey stage and BAM-chart belief shift, splitting channels, running the SWOT, and drafting positioning…")
    strategy = generate_strategy(brand, therapy_area, inferred["persona"], inferred["stage_key"])
    ctx["strategy"] = strategy
    bam = build_bam_chart(inferred["stage_key"])
    pp_npp = classify_pp_npp(strategy["channel_mix_pct"])
    micro_journeys = build_micro_journeys(inferred["stage_key"], strategy["recommended_touchpoints"])
    cx_maturity = assess_cx_maturity(maturity_notes, strategy["channel_mix_pct"])
    segment_profile = build_segment_profile(inferred["persona"], inferred["stage_key"])
    # Maya's benchmark answers fill the TCG rows the captured state cannot (t2/t7/t10).
    tcg = build_tcg_template(inferred["persona"], segment_profile, strategy, bam,
                             agent_answers=ctx["audience_profile"]["answers"], agent_name="Maya")
    message_flow = build_message_flow(inferred["stage_key"], strategy["kb_grounding"])
    ctx["tcg"] = tcg
    ctx["bam"] = bam
    ctx["pp_npp"] = pp_npp
    ctx["micro_journeys"] = micro_journeys
    ctx["cx_maturity"] = cx_maturity
    ctx["segment_profile"] = segment_profile
    ctx["message_flow"] = message_flow
    yield {"type": "inferred", "stage_label": strategy["inputs"]["stage"], "cx_maturity": cx_maturity["level"]}
    swot_result = build_swot(brand, competitors, therapy_area, refresh=True) if competitors else None
    ctx["swot"] = swot_result
    positioning = build_positioning_statement(brand, therapy_area, inferred["persona"], inferred["stage_key"], competitors)
    ctx["positioning"] = positioning
    m = strategy["messaging_architecture"]
    strat_bullets = [
        f"A→B shift: {bam['a_to_b_shift']}",
        f"Key-message topics (of the 4 default): {', '.join(bam['key_message_topics'])}",
        f"CX maturity: {cx_maturity['level']} — {cx_maturity['rationale']}",
        f"Feasibility checklist: {cx_maturity['feasibility_checklist']['auto_answered_count']}/{cx_maturity['feasibility_checklist']['total_questions']} questions auto-answered from state",
    ]
    if swot_result:
        s = swot_result["swot"]
        strat_bullets.append(f"SWOT: {len(s['strengths'])} strengths · {len(s['weaknesses'])} weaknesses · {len(s['opportunities'])} opportunities · {len(s['threats'])} threats")
    else:
        strat_bullets.append("SWOT skipped — no competitors to compare against")
    strat_bullets.append(f"Positioning: {positioning['positioning_statement']}")
    strat_summary = (
        f"Journey stage **{strategy['inputs']['stage']}**. Message: “{m['current_belief']}” → “{m['desired_belief']}”. "
        + (f"SWOT run against {len(competitors)} competitor(s); " if swot_result else "SWOT skipped (no competitors); ")
        + "positioning drafted."
    )
    yield {"type": "agent", "id": "strategy", "status": "done", "summary": strat_summary, "detail": {"bullets": strat_bullets}}

    # --- the team reacts to Sam's belief shift ---
    yield _say("inspiration", f"“{m['current_belief']}” → “{m['desired_belief']}” is a creative brief in one line. "
                              f"Let me find award-winning work that pulled off the same belief change.", to="strategy")
    yield _say("strategy", f"Lead with {m['messaging_type'].lower()} — and CX maturity reads "
                           f"**{cx_maturity['level']}**, so don't over-engineer the orchestration.", to="activation")

    # 3. Creative Inspiration -- real award-winning pharma campaigns as precedent
    yield _run("inspiration", f"Searching real award-winning pharma campaigns for {therapy_area} creative inspiration…")
    precedents = find_precedent_campaigns(therapy_area, brand, limit=3)
    ctx["precedents"] = precedents
    # Curated, festival-grounded award campaigns matched to this brand / therapy area / client
    # (why they won, the message, the hero creative) -- the awards data source.
    award_campaigns = awards_store.awards_for(brand=brand, therapy_area=therapy_area, limit=4)
    ctx["award_campaigns"] = award_campaigns
    matched_any = any(p["matched"] for p in precedents)
    insp_summary = (
        f"Found **{len(precedents)}** precedent campaign(s)"
        + (" matched to this therapy area" if matched_any else " (no therapy-area match — showing the most recent winners instead)")
        + (f" and **{len(award_campaigns)}** award-winning campaign(s) relevant to this brand/therapy area." if award_campaigns else ".")
    )
    insp_bullets = [f"“{p['title']}” — {p['tier']} in {p['category']} ({p['agency_sponsor']}), {p['program']} {p['year']}"
                    for p in precedents] or ["No award-winning campaigns indexed yet"]
    insp_bullets += [f"🏆 {a['title']} — {a['award']} ({a['festival']} {a['year']}): {a['why_awarded'][:120]}…"
                     for a in award_campaigns[:2]]
    yield {"type": "agent", "id": "inspiration", "status": "done", "summary": insp_summary, "detail": {"bullets": insp_bullets}}

    # --- the team reacts to Chloe's creative finds ---
    if award_campaigns:
        top_award = award_campaigns[0]
        yield _say("inspiration", f"The strongest reference is **{top_award['title']}** "
                                  f"({top_award['festival']} {top_award['year']}) — it won by making a hard "
                                  f"conversation easy to have.", to="activation")
        yield _say("activation", "Then the mix has to fund one hero asset, not spread thin across every channel. "
                                 "I'll protect budget for it.", to="inspiration")
    else:
        yield _say("activation", "No close creative precedent — so the channel plan carries more of the load. "
                                 "I'll lean on sequencing rather than a single hero idea.", to="inspiration")

    # 4. Activation Planning -- channel mix/budget + measurement/KPI + channel selection + execution plan
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
    # Arjun turns the funded channel mix into engagement targets against researched industry
    # baselines (baseline x lifecycle index), and the KPI priorities for this stage.
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
            _row["agent_name"] = "Arjun"
    # Pull the brand's real content library (claims + references + modules + DAM assets) so the
    # plan's "Select messages/channels" and "Create" phases render actual content, not placeholders.
    content_library = campaign_store.content_library_for(brand, indication)
    ctx["channel_selection"] = channel_selection
    ctx["execution_plan"] = execution_plan
    ctx["execution_raci"] = execution_raci
    ctx["test_measure_learn"] = test_measure_learn
    ctx["content_library"] = content_library
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
    lib_counts = content_library.get("counts", {})
    if content_library.get("found") and lib_counts.get("claims"):
        act_summary += (f" Pulled **{lib_counts.get('claims', 0)}** library claims "
                        f"({lib_counts.get('approved_claims', 0)} MLR-approved), "
                        f"**{lib_counts.get('references', 0)}** references and "
                        f"**{lib_counts.get('assets', 0)}** existing content assets into the plan.")
    act_bullets = ([f"{ch}: {v['pct']}%" + (f" · ${int(v['amount']):,}" if v['amount'] else "")
                    for ch, v in sorted(budget_allocation.items(), key=lambda kv: -kv[1]['pct'])]
                   + [f"Target — {r['channel']}: {r['what_good_looks_like']}"
                      for r in engagement_baseline["channels"][:3] if r.get("target_low_pct") is not None]
                   + kpi["leading_indicators"][:2]
                   + [execution_plan["mlr_delay_note"]])
    if content_library.get("found") and lib_counts.get("claims"):
        act_bullets.append(f"Content library: {lib_counts.get('claims',0)} claims, {lib_counts.get('modules',0)} "
                           f"reusable modules, {lib_counts.get('assets',0)} DAM assets mapped into Phase 2/3")
    yield {"type": "agent", "id": "activation", "status": "done", "summary": act_summary, "detail": {"bullets": act_bullets}}

    # --- the team converges before Cooper writes it up ---
    _eb = engagement_baseline["channels"][0] if engagement_baseline["channels"] else None
    if _eb and _eb.get("target_low_pct") is not None:
        yield _say("activation", f"Benchmark target for **{_eb['channel']}**: {_eb['what_good_looks_like']}. "
                                 f"That's the bar — I've written it into Test-Measure-Learn.", to="compose")
    if top:
        yield _say("compose", f"So the spine is **{top[0][0]}** at {top[0][1]}%. I'll build the message flow around "
                              f"that and let the rest reinforce it.", to="activation")
    if content_library.get("found") and lib_counts.get("approved_claims"):
        yield _say("compose", f"I've got **{lib_counts['approved_claims']}** MLR-approved claims with references — "
                              f"they go straight into the message flow and the content audit.", to="strategy")
        yield _say("strategy", "Good — every claim in the plan should trace to a source. Nothing unsubstantiated "
                               "goes in front of an HCP.", to="compose")
    else:
        yield _say("compose", "No approved claims library for this brand yet, so the message flow ships as a "
                              "template for the brand team to fill.", to="strategy")

    # 5. Compose -- fills the toolkit questionnaires, collects every 'needs alignment'
    # item into the open-question groups the chat agent asks after the run, and renders
    # the plan as the toolkit-replica document (plan_document.py).
    yield _run("compose", "Assembling everyone's findings into the brand engagement plan document…")
    cx_questionnaire = build_cx_questionnaire(brand, inferred["persona"], strategy, ctx["bam"], kpi)
    ctx["cx_questionnaire"] = cx_questionnaire
    open_qs = build_open_questions(cx_maturity["feasibility_checklist"], cx_questionnaire, ctx["tcg"])
    ctx["open_questions"] = open_qs
    n_open = sum(len(g["questions"]) for g in open_qs)
    result = _assemble_result(ctx)
    plan_markdown, plan_html = compose_plan(ctx)
    yield {"type": "agent", "id": "compose", "status": "done",
           "summary": (f"Brand engagement plan assembled — all four toolkit phases rendered on the right. "
                       f"**{n_open}** questions need brand-team alignment; I'll ask you them in chat."),
           "detail": {"bullets": ["Full toolkit-replica plan on the right — sections are collapsed, click to expand",
                                  f"{n_open} 'needs alignment' items highlighted across "
                                  f"{len(open_qs)} question groups"]}}
    yield {"type": "plan", "html": plan_html, "markdown": plan_markdown}
    # ctx is included so the server can snapshot it for the persona 'apply feedback to plan'
    # action (which needs to re-run compose_plan with a patched budget mix later) -- the
    # server strips it before forwarding the event to the client, so it never hits the wire.
    yield {"type": "result", "result": result, "ctx": ctx}
    yield {"type": "narration", "text": (
        f"Done — the team has finished. Your brand engagement plan for **{brand}** in **{therapy_area}** is on the right, "
        "and **Stage 1 · Planning & Strategy** is complete.\n\n"
        "The next three stages of this project are now unlocked in the stepper above the plan: "
        "**Engagement Orchestration** (triggers, next-best-channel, cadence), **Campaign Operations** "
        "(parallel execution tracks per channel), and **Reporting & Insights** (the measurement scorecard).\n\n"
        "Download the plan as Markdown, or tell me what to adjust (persona, competitors, budget) and I'll send the agents back in."
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
        "stage_7_kpi": ctx["kpi"],
        "stage_9_test_measure_learn": ctx["test_measure_learn"],
        "stage_9_execution_plan": ctx["execution_plan"],
        "stage_9_execution_raci": ctx["execution_raci"],
        "stage_8_risk_governance": {"standard_risks": STANDARD_RISKS, "governance_cadence": GOVERNANCE_CADENCE},
    }


def recompose_plan(ctx: dict) -> tuple[dict, str, str]:
    """Re-render the plan from a (possibly patched) ctx snapshot, without re-running any
    agent. Used both by the persona 'apply feedback to plan' action (which patches
    budget_allocation) and by refresh_after_clarify() below (which patches cx_maturity/
    open_questions) -- any future ctx-patching action should reuse this rather than calling
    _assemble_result/compose_plan directly, so the two always stay in sync."""
    result = _assemble_result(ctx)
    plan_markdown, plan_html = compose_plan(ctx)
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


