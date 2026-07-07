"""Multi-agent orchestrator for the campaign-planning workspace.

`run_agents()` is a generator that yields events as each specialist agent works --
lifecycle interpretation, market landscape, competitor discovery, segmentation/journey,
SWOT, positioning, channel mix/budget, measurement -- then a composer agent assembles a
Campaign Plan document. The FastAPI layer streams these events as Server-Sent Events so
the UI can show the agents thinking in real time. Every agent reuses the same real,
data-backed functions the rest of the tool uses -- the "agents" are genuine pipeline
stages, not theatre.
"""
from __future__ import annotations

import html
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from lifecycle import infer_persona_and_stage  # noqa: E402
from engine import generate_strategy, market_landscape  # noqa: E402
from positioning import build_positioning_statement  # noqa: E402
from kpi import build_kpi_framework  # noqa: E402
from competitive.discovery import discover_competitors  # noqa: E402
from competitive.swot import build_swot  # noqa: E402
from autorun import STANDARD_RISKS, GOVERNANCE_CADENCE  # noqa: E402

AGENT_ROSTER = [
    {"id": "lifecycle", "name": "Lifecycle Interpreter", "icon": "🧭"},
    {"id": "market", "name": "Market Landscape Agent", "icon": "🔍"},
    {"id": "competitors", "name": "Competitor Discovery Agent", "icon": "🧬"},
    {"id": "strategy", "name": "Segmentation & Journey Agent", "icon": "🎯"},
    {"id": "swot", "name": "Competitive SWOT Agent", "icon": "⚔️"},
    {"id": "positioning", "name": "Positioning Agent", "icon": "📌"},
    {"id": "budget", "name": "Channel Mix & Budget Agent", "icon": "💰"},
    {"id": "kpi", "name": "Measurement & KPI Agent", "icon": "📊"},
    {"id": "compose", "name": "Campaign Plan Composer", "icon": "📝"},
]


def _kb_count(section: dict) -> int:
    return sum(len(v) for v in section.values()) if section else 0


_ROSTER_IDS = [a["id"] for a in AGENT_ROSTER]
_ROSTER_BY_ID = {a["id"]: a for a in AGENT_ROSTER}


def _handoff(from_id: str):
    """Event marking one agent passing its findings to the next in the chain (drives the chat animation)."""
    i = _ROSTER_IDS.index(from_id)
    if i + 1 >= len(_ROSTER_IDS):
        return None
    cur, nxt = _ROSTER_BY_ID[from_id], _ROSTER_BY_ID[_ROSTER_IDS[i + 1]]
    return {"type": "handoff", "from_id": cur["id"], "from_name": cur["name"],
            "to_id": nxt["id"], "to_name": nxt["name"]}


def _run(agent_id: str, say: str):
    """Running event carrying the agent's first-person 'what I'm doing' line for the chat."""
    return {"type": "agent", "id": agent_id, "status": "running", "say": say}


def run_agents(brand: str, therapy_area: str, lifecycle_key: str, budget: float = 0):
    """Generator yielding orchestration events. The specialist agents speak in the chat
    (`say` on running, `summary` on done) and hand off to each other (`handoff`), while the
    right-hand roster/brief/plan update in parallel. Terminal events: 'plan', 'result', 'done'."""
    yield {"type": "agents_init", "agents": AGENT_ROSTER}
    ctx: dict = {"brand": brand, "therapy_area": therapy_area, "lifecycle_key": lifecycle_key, "budget": budget}

    # 1. Lifecycle
    yield _run("lifecycle", f"Reading where {brand} sits in its lifecycle…")
    inferred = infer_persona_and_stage(lifecycle_key)
    ctx["inferred"] = inferred
    yield {"type": "inferred", "persona": inferred["persona"], "lifecycle_label": inferred["lifecycle_label"]}
    yield {"type": "agent", "id": "lifecycle", "status": "done",
           "summary": f"{inferred['lifecycle_label']} → I'll target **{inferred['persona']}** HCPs. Handing the brief to the Market Landscape Agent.",
           "detail": {"bullets": [inferred["rationale"], f"Default persona: {inferred['persona']}"]}}
    yield _handoff("lifecycle")

    # 2. Market landscape
    yield _run("market", f"Scanning the market for {brand} — FDA labels, trials, PubMed and Trends…")
    market = market_landscape(brand, therapy_area)
    ctx["market"] = market
    b_n, t_n = _kb_count(market.get("brand", {})), _kb_count(market.get("therapy_area", {}))
    yield {"type": "agent", "id": "market", "status": "done",
           "summary": f"Indexed **{b_n + t_n}** live documents ({b_n} on {brand}, {t_n} on {therapy_area}). Over to Competitor Discovery.",
           "detail": {"bullets": [f"{b_n} real documents on {brand}", f"{t_n} on {therapy_area}",
                                  "Sources: FDA labels, ClinicalTrials.gov, PubMed, DailyMed, Google Trends"]}}
    yield _handoff("market")

    # 3. Competitor discovery
    yield _run("competitors", f"Hunting for competitors treating {therapy_area} in the trial data…")
    competitors = discover_competitors(therapy_area, brand, limit=5)
    ctx["competitors"] = competitors
    yield {"type": "inferred", "competitors": competitors}
    yield {"type": "agent", "id": "competitors", "status": "done",
           "summary": (f"Found **{len(competitors)}**: {', '.join(competitors)}. Passing the set to Segmentation & the SWOT Agent."
                       if competitors else "No distinct competitors in public trial data — SWOT will note that."),
           "detail": {"bullets": competitors or ["ClinicalTrials.gov returned no distinct competing interventions"]}}
    yield _handoff("competitors")

    # 4. Segmentation, journey & messaging
    yield _run("strategy", "Mapping the journey stage and the current→desired belief shift…")
    strategy = generate_strategy(brand, therapy_area, inferred["persona"], inferred["stage_key"])
    ctx["strategy"] = strategy
    yield {"type": "inferred", "stage_label": strategy["inputs"]["stage"]}
    m = strategy["messaging_architecture"]
    yield {"type": "agent", "id": "strategy", "status": "done",
           "summary": f"Journey stage: **{strategy['inputs']['stage']}**. Message: “{m['current_belief']}” → “{m['desired_belief']}”.",
           "detail": {"bullets": [f"Current → desired belief: \"{m['current_belief']}\" → \"{m['desired_belief']}\"",
                                  f"Messaging type: {m['messaging_type']}"]}}
    yield _handoff("strategy")

    # 5. Competitive SWOT
    yield _run("swot", "Running the SWOT against the discovered competitor set…")
    swot_result = build_swot(brand, competitors, therapy_area, refresh=True) if competitors else None
    ctx["swot"] = swot_result
    if swot_result:
        s = swot_result["swot"]
        yield {"type": "agent", "id": "swot", "status": "done",
               "summary": f"**{len(s['strengths'])}** strengths · **{len(s['weaknesses'])}** weaknesses · **{len(s['opportunities'])}** opportunities · **{len(s['threats'])}** threats. Feeding this to Positioning.",
               "detail": {"bullets": (s["strengths"][:1] + s["opportunities"][:1] + s["threats"][:1])}}
    else:
        yield {"type": "agent", "id": "swot", "status": "done", "summary": "Skipped — no competitors to compare against.",
               "detail": {"bullets": ["SWOT needs a competitive set; none was found for this therapy area"]}}
    yield _handoff("swot")

    # 6. Positioning
    yield _run("positioning", "Drafting the positioning statement from the SWOT + journey inputs…")
    positioning = build_positioning_statement(brand, therapy_area, inferred["persona"], inferred["stage_key"], competitors)
    ctx["positioning"] = positioning
    yield {"type": "agent", "id": "positioning", "status": "done",
           "summary": "Positioning drafted" + (" (grounded in real competitor data)" if positioning["grounded_in_competitive_data"] else "") + ". Handing budget the channel mix.",
           "detail": {"bullets": [positioning["positioning_statement"]]}}
    yield _handoff("positioning")

    # 7. Channel mix & budget
    yield _run("budget", "Modelling the channel mix and splitting the budget…")
    channel_mix = strategy["channel_mix_pct"]
    budget_allocation = {ch: {"pct": pct, "amount": round(budget * pct / 100, 2) if budget else None}
                         for ch, pct in channel_mix.items()}
    ctx["budget_allocation"] = budget_allocation
    top = sorted(channel_mix.items(), key=lambda kv: -kv[1])[:2]
    top_str = ", ".join(f"{k} {v}%" for k, v in top)
    yield {"type": "agent", "id": "budget", "status": "done",
           "summary": f"Emphasis on **{top_str}**" + (f" · ${int(budget):,} total" if budget else "") + ". Over to Measurement.",
           "detail": {"bullets": [f"{ch}: {v['pct']}%" + (f" · ${int(v['amount']):,}" if v['amount'] else "") for ch, v in
                                  sorted(budget_allocation.items(), key=lambda kv: -kv[1]['pct'])]}}
    yield _handoff("budget")

    # 8. Measurement & KPIs
    yield _run("kpi", "Building the leading / lagging / operational KPI scorecard…")
    kpi = build_kpi_framework(inferred["stage_key"], channel_mix)
    ctx["kpi"] = kpi
    yield {"type": "agent", "id": "kpi", "status": "done",
           "summary": f"**{len(kpi['leading_indicators'])}** leading · **{len(kpi['lagging_indicators'])}** lagging · **{len(kpi['operational_kpis'])}** operational KPIs. Sending everything to the Composer.",
           "detail": {"bullets": kpi["leading_indicators"][:3]}}
    yield _handoff("kpi")

    # 9. Compose
    yield _run("compose", "Assembling everyone's findings into the campaign plan document…")
    result = _assemble_result(ctx)
    plan_markdown, plan_html = _compose_plan(ctx)
    yield {"type": "agent", "id": "compose", "status": "done",
           "summary": "Campaign plan assembled — it's on the right, ready to download.",
           "detail": {"bullets": ["Full plan rendered on the right — download as Markdown or copy"]}}
    yield {"type": "plan", "html": plan_html, "markdown": plan_markdown}
    yield {"type": "result", "result": result}
    yield {"type": "narration", "text": (
        f"Done — the team has finished. Your campaign plan for **{brand}** in **{therapy_area}** is on the right. "
        "Download it as Markdown, or tell me what to adjust (persona, competitors, budget) and I'll send the agents back in."
    )}
    yield {"type": "done"}


def _assemble_result(ctx: dict) -> dict:
    """Same shape as autorun.run_full_analysis, so it persists / renders identically."""
    strategy = ctx["strategy"]
    inferred = ctx["inferred"]
    return {
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
        "stage_1b_3_competitive": ctx["swot"],
        "stage_3_positioning": ctx["positioning"],
        "stage_5_budget": {"total_budget": ctx["budget"] or None, "allocation": ctx["budget_allocation"],
                            "caveat": strategy["caveat"]},
        "stage_7_kpi": ctx["kpi"],
        "stage_8_risk_governance": {"standard_risks": STANDARD_RISKS, "governance_cadence": GOVERNANCE_CADENCE},
    }


# --------------------------------------------------------------------------- #
# Campaign Plan document composition (markdown + HTML from the same structured data)
# --------------------------------------------------------------------------- #

def _esc(s) -> str:
    return html.escape(str(s))


def _exec_summary(ctx: dict) -> str:
    brand, ta = ctx["brand"], ctx["therapy_area"]
    inferred = ctx["inferred"]
    strat = ctx["strategy"]
    m = strat["messaging_architecture"]
    comps = ctx["competitors"]
    top = sorted(strat["channel_mix_pct"].items(), key=lambda kv: -kv[1])[:2]
    top_str = " and ".join(k for k, _ in top)
    opening = ""
    if ctx["swot"]:
        opps = ctx["swot"]["swot"]["opportunities"]
        strengths = ctx["swot"]["swot"]["strengths"]
        if opps and "No competitors supplied" not in opps[0]:
            opening = opps[0]
        elif strengths and "No clear" not in strengths[0]:
            opening = strengths[0]
    comp_line = f"against {len(comps)} discovered competitor(s) ({', '.join(comps)})" if comps else "in a therapy area with no distinct competing interventions found in public trial data"
    budget_line = (f"A total budget of ${int(ctx['budget']):,} is allocated across the channel mix below."
                   if ctx["budget"] else "Channel mix is expressed as a percentage split (no total budget provided).")
    parts = [
        f"{brand} is planned for {ta} at the **{inferred['lifecycle_label']}** lifecycle stage. "
        f"The priority audience is **{inferred['persona']}** HCPs at the **{strat['inputs']['stage']}** journey stage.",
        f"The core messaging job is to move the prescriber belief from “{m['current_belief']}” to "
        f"“{m['desired_belief']}”, led with {m['messaging_type'].lower()}.",
        f"Positioned {comp_line}." + (f" The sharpest opening: {opening}" if opening else ""),
        f"Channel emphasis falls on **{top_str}**. {budget_line}",
    ]
    return " ".join(parts)


def _compose_plan(ctx: dict) -> tuple[str, str]:
    brand, ta = ctx["brand"], ctx["therapy_area"]
    inferred = ctx["inferred"]
    strat = ctx["strategy"]
    m = strat["messaging_architecture"]
    sp = strat["stage_profile"]
    pos = ctx["positioning"]
    swot = ctx["swot"]
    kpi = ctx["kpi"]
    budget_alloc = ctx["budget_allocation"]
    ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    exec_sum = _exec_summary(ctx)

    md: list[str] = []
    h: list[str] = []

    # Title
    md.append(f"# Campaign Strategy Plan — {brand} · {ta}\n")
    md.append(f"*Lifecycle stage:* {inferred['lifecycle_label']}  |  *Generated:* {ts}\n")
    h.append(f"<h1>Campaign Strategy Plan</h1><p class='plan-sub'>{_esc(brand)} · {_esc(ta)} — "
             f"{_esc(inferred['lifecycle_label'])} · generated {ts}</p>")

    # Executive summary
    md.append("## 1. Executive summary\n")
    md.append(exec_sum + "\n")
    h.append(f"<h2>1. Executive summary</h2><p>{exec_sum}</p>")

    # Brief
    md.append("## 2. Brief\n")
    md.append(f"- **Brand:** {brand}\n- **Therapy area:** {ta}\n- **Lifecycle:** {inferred['lifecycle_label']}\n"
              f"- **Priority persona:** {inferred['persona']}\n- **Journey stage:** {strat['inputs']['stage']}\n"
              f"- **Competitive set:** {', '.join(ctx['competitors']) or '—'}\n")
    h.append("<h2>2. Brief</h2><table class='plan-kv'>"
             + "".join(f"<tr><th>{k}</th><td>{_esc(v)}</td></tr>" for k, v in [
                 ("Brand", brand), ("Therapy area", ta), ("Lifecycle", inferred["lifecycle_label"]),
                 ("Priority persona", inferred["persona"]), ("Journey stage", strat["inputs"]["stage"]),
                 ("Competitive set", ", ".join(ctx["competitors"]) or "—")])
             + "</table>")

    # Market & landscape
    md.append("## 3. Market & landscape\n")
    h.append("<h2>3. Market &amp; landscape</h2>")
    src_labels = {"clinicaltrials": "ClinicalTrials.gov", "pubmed": "PubMed", "openfda": "openFDA",
                  "dailymed": "DailyMed", "google_trends": "Google Trends"}
    for scope, label in [("brand", brand), ("therapy_area", ta)]:
        section = ctx["market"].get(scope, {})
        md.append(f"**{label}**\n")
        h.append(f"<h3>{_esc(label)}</h3>")
        any_docs = False
        for src, items in section.items():
            for it in items[:3]:
                any_docs = True
                md.append(f"- [{src_labels.get(src, src)}] [{it['title']}]({it['url']})")
                h.append(f"<div class='plan-doc'><span class='plan-src'>{src_labels.get(src, src)}</span> "
                         f"<a href='{_esc(it['url'])}' target='_blank'>{_esc(it['title'])}</a></div>")
        if not any_docs:
            md.append("- (no documents indexed)")
            h.append("<div class='plan-empty'>No documents indexed.</div>")
        md.append("")

    # Competitive analysis
    md.append("## 4. Competitive analysis\n")
    h.append("<h2>4. Competitive analysis</h2>")
    if swot:
        for key, title in [("strengths", "Strengths"), ("weaknesses", "Weaknesses"),
                           ("opportunities", "Opportunities"), ("threats", "Threats")]:
            items = swot["swot"][key]
            md.append(f"**{title}**")
            for it in items:
                md.append(f"- {it}")
            md.append("")
            h.append(f"<h3>{title}</h3><ul>" + "".join(f"<li>{_esc(it)}</li>" for it in items) + "</ul>")
        # positioning table
        rows = swot["positioning_table"]
        metrics = [("FDA labels", "fda_label_count"), ("Active trials", "trials_active"),
                   ("Completed trials", "trials_completed"), ("Stopped trials", "trials_stopped"),
                   ("PubMed (2yr)", "pubmed_recent_2yr"), ("Trends interest", "trends_avg_interest")]
        header = "| Metric | " + " | ".join(f"{r['brand']}{' (target)' if i == 0 else ''}" for i, r in enumerate(rows)) + " |"
        sep = "|" + "---|" * (len(rows) + 1)
        md.append("**Positioning table**\n")
        md.append(header)
        md.append(sep)
        thead = "<tr><th>Metric</th>" + "".join(f"<th>{_esc(r['brand'])}{' (target)' if i == 0 else ''}</th>" for i, r in enumerate(rows)) + "</tr>"
        tbody = ""
        for mlabel, mkey in metrics:
            vals = [(f"{r.get(mkey):.1f}" if isinstance(r.get(mkey), float) else (r.get(mkey) if r.get(mkey) is not None else "—")) for r in rows]
            md.append(f"| {mlabel} | " + " | ".join(str(v) for v in vals) + " |")
            tbody += f"<tr><td>{mlabel}</td>" + "".join(f"<td>{_esc(v)}</td>" for v in vals) + "</tr>"
        md.append("")
        h.append(f"<table class='plan-table'>{thead}{tbody}</table>")
    else:
        md.append("_No distinct competitors were found in public trial data for this therapy area; competitive analysis skipped._\n")
        h.append("<p class='plan-empty'>No distinct competitors found in public trial data — competitive analysis skipped.</p>")

    # Positioning
    md.append("## 5. Positioning\n")
    md.append(f"> {pos['positioning_statement']}\n")
    md.append("**Alternative messaging angles**")
    for a in pos["alternative_angles"]:
        md.append(f"- {a}")
    md.append("\n**Target audience notes**")
    for a in pos["target_audience_notes"]:
        md.append(f"- {a}")
    md.append("")
    h.append("<h2>5. Positioning</h2>"
             f"<blockquote class='plan-statement'>{_esc(pos['positioning_statement'])}</blockquote>"
             "<h3>Alternative messaging angles</h3><ul>"
             + "".join(f"<li>{_esc(a)}</li>" for a in pos["alternative_angles"]) + "</ul>"
             "<h3>Target audience notes</h3><ul>"
             + "".join(f"<li>{_esc(a)}</li>" for a in pos["target_audience_notes"]) + "</ul>")

    # Segmentation, journey & messaging
    md.append("## 6. Segmentation, journey & messaging\n")
    md.append(f"- **Persona:** {inferred['persona']}\n- **Journey stage:** {strat['inputs']['stage']}\n"
              f"- **Mental state:** {sp['mental_state']}\n- **Core barrier:** {sp['core_barrier']}\n"
              f"- **Engagement goal:** {sp['engagement_goal']}\n- **Promotion signal:** {sp['promotion_signal']}\n")
    md.append(f"**Current belief → desired belief:** “{m['current_belief']}” → “{m['desired_belief']}”\n")
    md.append(f"**Proof points:** {', '.join(m['proof_points'])}\n")
    md.append(f"**Tone/format constraint:** {m['tone_constraint']}\n")
    md.append("**Recommended touchpoints**")
    for ch, tps in strat["recommended_touchpoints"].items():
        md.append(f"- {ch}: {', '.join(tps)}")
    md.append("")
    h.append("<h2>6. Segmentation, journey &amp; messaging</h2>"
             "<table class='plan-kv'>"
             + "".join(f"<tr><th>{k}</th><td>{_esc(v)}</td></tr>" for k, v in [
                 ("Persona", inferred["persona"]), ("Journey stage", strat["inputs"]["stage"]),
                 ("Mental state", sp["mental_state"]), ("Core barrier", sp["core_barrier"]),
                 ("Engagement goal", sp["engagement_goal"]), ("Promotion signal", sp["promotion_signal"])])
             + "</table>"
             f"<p><strong>Current → desired belief:</strong> “{_esc(m['current_belief'])}” → “{_esc(m['desired_belief'])}”</p>"
             f"<p><strong>Proof points:</strong> {_esc(', '.join(m['proof_points']))}</p>"
             f"<p><strong>Tone/format:</strong> {_esc(m['tone_constraint'])}</p>"
             "<h3>Recommended touchpoints</h3><ul>"
             + "".join(f"<li><strong>{_esc(ch)}:</strong> {_esc(', '.join(tps))}</li>" for ch, tps in strat["recommended_touchpoints"].items())
             + "</ul>")

    # Channel mix & budget
    md.append("## 7. Channel mix & budget\n")
    md.append("| Channel | Share | Budget |")
    md.append("|---|---|---|")
    h.append("<h2>7. Channel mix &amp; budget</h2>")
    bars = ""
    for ch, v in sorted(budget_alloc.items(), key=lambda kv: -kv[1]["pct"]):
        amt = f"${int(v['amount']):,}" if v["amount"] else "—"
        md.append(f"| {ch} | {v['pct']}% | {amt} |")
        bars += (f"<div class='plan-bar-row'><div class='plan-bar-label'>{_esc(ch)}</div>"
                 f"<div class='plan-bar-track'><div class='plan-bar-fill' style='width:{v['pct']}%'></div></div>"
                 f"<div class='plan-bar-val'>{v['pct']}% · {amt}</div></div>")
    md.append(f"\n*{strat['caveat']}*\n")
    h.append(bars + f"<p class='plan-caveat'>{_esc(strat['caveat'])}</p>")

    # Measurement & KPIs
    md.append("## 8. Measurement & KPIs\n")
    for title, items in [("Leading indicators", kpi["leading_indicators"]),
                         ("Lagging indicators", kpi["lagging_indicators"]),
                         ("Operational KPIs", kpi["operational_kpis"])]:
        md.append(f"**{title}**")
        for it in items:
            md.append(f"- {it}")
        md.append("")
    md.append(f"*Review cadence:* {kpi['cadence_note']}\n")
    h.append("<h2>8. Measurement &amp; KPIs</h2>"
             + "".join(f"<h3>{title}</h3><ul>" + "".join(f"<li>{_esc(it)}</li>" for it in items) + "</ul>"
                       for title, items in [("Leading indicators", kpi["leading_indicators"]),
                                            ("Lagging indicators", kpi["lagging_indicators"]),
                                            ("Operational KPIs", kpi["operational_kpis"])])
             + f"<p class='plan-caveat'>Review cadence: {_esc(kpi['cadence_note'])}</p>")

    # Risk & governance
    md.append("## 9. Risk & governance\n")
    md.append("**Standard risk checklist**")
    for r in STANDARD_RISKS:
        md.append(f"- {r}")
    md.append("\n**Governance cadence**")
    for k, v in GOVERNANCE_CADENCE.items():
        md.append(f"- **{k}:** {v}")
    md.append("")
    h.append("<h2>9. Risk &amp; governance</h2><h3>Standard risk checklist</h3><ul>"
             + "".join(f"<li>{_esc(r)}</li>" for r in STANDARD_RISKS) + "</ul>"
             "<h3>Governance cadence</h3><ul>"
             + "".join(f"<li><strong>{_esc(k)}:</strong> {_esc(v)}</li>" for k, v in GOVERNANCE_CADENCE.items()) + "</ul>")

    # Caveats
    caveat = ("This plan is generated from public/licensed data proxies and a rules-based framework. Channel-mix "
              "percentages are an illustrative starting allocation (not measured MMx output); SWOT/positioning derive "
              "from public-data proxies; persona and competitors were auto-inferred. Treat as a first draft for brand-team "
              "and MLR review, not a final approved plan.")
    md.append("## 10. Caveats & data provenance\n")
    md.append(caveat + "\n")
    h.append(f"<h2>10. Caveats &amp; data provenance</h2><p class='plan-caveat'>{_esc(caveat)}</p>")

    return "\n".join(md), "".join(h)
