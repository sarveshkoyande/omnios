"""Brand Engagement Plan document composer -- a ground-up rewrite (2026-07-09) that renders the
plan as an exact HTML/CSS replica of the Customer Engagement Planning Toolkit workbook:
the Sheet-2 home navigator with its four phase ribbons (Align = magenta, Select = cyan,
Create = navy, Deploy = grey), the Sheet-3/4 question tables with blue band rows, the
Sheet-5 feasibility checklist with its cyan/magenta/green answer tiers and legend, the
Sheet-6/9 message-flow boxes, the Sheet-10 metrics pyramid, and the Sheet-12/14 work
plan + RACI. Every section is a <details> element, collapsed by default (executive
summary and open questions start open); items no synthesis can answer are highlighted
as "Needs alignment" and mirrored into the chat agent's post-plan clarify questions.

Emits (markdown, html) from the same structured ctx dict orchestrator.run_agents builds.
The markdown mirror keeps plain tables/lists (it is the download artifact, not the replica).
"""
from __future__ import annotations

import html
import time

from autorun import STANDARD_RISKS, GOVERNANCE_CADENCE  # noqa: E402


def _esc(s) -> str:
    return html.escape(str(s))


def _icon(name: str) -> str:
    return f"<span class='material-symbols-outlined'>{name}</span>"


def _badge(icon: str, text) -> str:
    return f"<span class='plan-badge'>{_icon(icon)}{_esc(text)}</span>"


_NEEDS_CHIP = "<span class='plan-open-chip'>Needs alignment</span>"


def _is_open_answer(answer: str) -> bool:
    return answer.startswith("Needs alignment") or answer.startswith("Not yet captured")


# --------------------------------------------------------------------------- #
# Section registry (phase-grouped; drives the home navigator + <details> ids)
# --------------------------------------------------------------------------- #

_PHASES = [
    ("align", "Align on customer understanding and CX objectives",
     [(4, "Target Customer Group Template"), (5, "CX Planning Questionnaire"),
      (6, "Omnichannel CX Feasibility Analysis")]),
    ("select", "Select relevant messages and channels",
     [(7, "Message Flow Template"), (8, "Channel Selection Template")]),
    ("create", "Create omnichannel CX",
     [(9, "Map Existing Content & Identify"), (10, "Design Channel Flow"),
      (11, "Design Message Flow"), (12, "Metrics to Track CX Success")]),
    ("deploy", "Deploy campaign",
     [(13, "CX Execution Work Plan"), (14, "Develop Closed Loop Model")]),
]

_SUPPORTING = [
    (15, "travel_explore", "Market & landscape"),
    (16, "balance", "Competitive analysis"),
    (17, "track_changes", "Positioning"),
    (18, "route", "Journey & messaging (BAM)"),
    (19, "emoji_events", "Precedent campaigns"),
    (20, "payments", "Channel mix & budget"),
    (21, "query_stats", "KPI framework"),
    (22, "gpp_maybe", "Risk & governance"),
    (23, "fact_check", "Caveats & data provenance"),
]

_PHASE_ICONS = {"align": "handshake", "select": "checklist", "create": "design_services", "deploy": "rocket_launch"}

_CHANNEL_ICONS = {
    "Field": "groups", "Events": "event", "Owned digital": "language", "Reach": "campaign",
    "Patient-adjacent": "favorite", "Peer": "diversity_3",
}

_TIER_CLASS = {"Gold": "tier-gold", "Silver": "tier-silver", "Bronze": "tier-bronze"}

_FEAS_LEGEND = [
    ("tk-t0", "Simple Omnichannel CX", "Limited CX personalization, leveraging existing channels, systems and content"),
    ("tk-t1", "Medium Omnichannel CX", "Some personalization of CX, leveraging limited new content, channels & orchestration tools"),
    ("tk-t2", "Complex Omnichannel CX", "Highly personalized CX, leveraging new content, channels & orchestration tools"),
]

_LEVEL_TO_TIER_CLASS = {"Simple": "tk-t0", "Medium": "tk-t1", "Complex": "tk-t2"}


def _det_open(num: int, title: str, icon: str, phase: str = "", start_open: bool = False,
              open_count: int = 0) -> str:
    chip = f"<span class='plan-open-chip'>{open_count} need alignment</span>" if open_count else ""
    cls = f"plan-sec{' tk-sec-' + phase if phase else ''}"
    return (f"<details class='{cls}' id='sec-{num}'{' open' if start_open else ''}>"
            f"<summary class='plan-sec-head'>{_icon(icon)}<h2>{num}. {_esc(title)}</h2>{chip}"
            f"<span class='plan-sec-chev material-symbols-outlined'>expand_more</span></summary>"
            f"<div class='plan-sec-body'>")


_DET_CLOSE = "</div></details>"


def _phase_banner(phase: str, label: str, phase_no: int) -> str:
    return (f"<div class='tk-phase-banner tk-{phase}'><span class='tk-phase-no'>Phase {phase_no}</span>"
            f"{_esc(label)}</div>")


def _home_navigator() -> str:
    cols = []
    for phase, label, items in _PHASES:
        pills = "".join(
            f"<a class='tk-item tk-{phase}' href='#sec-{num}'><span class='tk-num'>{i + 1}</span>"
            f"<span class='tk-item-label'>{_esc(title)}</span></a>"
            for i, (num, title) in enumerate(items)
        )
        cols.append(f"<div class='tk-col'><div class='tk-ribbon tk-{phase}'>{_esc(label)}</div>{pills}</div>")
    chips = "".join(f"<a href='#sec-{n}'>{_icon(ic)}{_esc(t)}</a>" for n, ic, t in _SUPPORTING)
    return ("<div class='tk-home'>" + "".join(cols) + "</div>"
            f"<nav class='plan-toc'><a href='#sec-1'>{_icon('insights')}Executive summary</a>"
            f"<a href='#sec-2'>{_icon('help')}Open questions</a>"
            f"<a href='#sec-3'>{_icon('assignment')}Brief</a>{chips}</nav>")


def _dist_boxes(dist: dict, prefix: str = "") -> str:
    cells = "".join(f"<div class='tk-dist-cell'><div class='tk-dist-k'>{_esc(prefix)}{_esc(k)}</div>"
                    f"<div class='tk-dist-v'>{v}%</div></div>" for k, v in dist.items())
    return f"<div class='tk-dist'>{cells}</div>"


def _gantt_row_html(band: dict) -> str:
    tooltip = _esc(", ".join(band["tasks"]))
    return (
        f"<div class='plan-gantt-row'><div class='plan-gantt-label'>{_esc(band['category'])}</div>"
        f"<div class='plan-gantt-track'><div class='plan-gantt-bar' "
        f"style='grid-column: {band['start_week']} / {band['end_week'] + 1}' title='{tooltip}'>"
        f"W{band['start_week']}–W{band['end_week']}</div></div></div>"
    )


# --------------------------------------------------------------------------- #
# Executive summary prose
# --------------------------------------------------------------------------- #

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
    comp_line = (f"against {len(comps)} discovered competitor(s) ({', '.join(comps)})" if comps
                 else "in a therapy area with no distinct competing interventions found in public trial data")
    budget_line = (f"A total budget of ${int(ctx['budget']):,} is allocated across the channel mix."
                   if ctx["budget"] else "Channel mix is expressed as a percentage split (no total budget provided).")
    n_open = sum(len(g["questions"]) for g in ctx.get("open_questions", []))
    indication = ctx.get("indication", "")
    ind_clause = f" for the **{indication}** indication" if indication else ""
    parts = [
        f"{brand} is planned for {ta}{ind_clause} at the **{inferred['lifecycle_label']}** lifecycle stage. "
        f"The priority audience is **{inferred['persona']}** HCPs at the **{strat['inputs']['stage']}** journey stage.",
        f"The core messaging job is to move the prescriber belief from “{m['current_belief']}” to "
        f"“{m['desired_belief']}”, led with {m['messaging_type'].lower()}.",
        f"Positioned {comp_line}." + (f" The sharpest opening: {opening}" if opening else ""),
        f"Channel emphasis falls on **{top_str}**. {budget_line}",
    ]
    if n_open:
        parts.append(f"**{n_open}** toolkit questions could not be answered from state and are flagged "
                     "“Needs alignment” throughout — I'll ask you them in chat.")
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# Replica section renderers (HTML)
# --------------------------------------------------------------------------- #

def _render_open_questions(groups: list[dict]) -> str:
    body = ""
    for g in groups:
        qs = "".join(f"<li>{_esc(q)}</li>" for q in g["questions"])
        body += (f"<div class='plan-openq-group'><div class='plan-openq-title'>{_esc(g['title'])} "
                 f"<span class='plan-openq-src'>{_esc(g['source'])}</span></div><ul>{qs}</ul></div>")
    return (
        "<p>These are the toolkit questions only your brand team can answer — the agent asks them "
        "one group at a time in the chat after this plan is generated. Answer there (or say <em>skip</em>) "
        "and regenerate to fold them in. Until then they stay highlighted like this: "
        + _NEEDS_CHIP + "</p>" + body
    )


def _render_tcg(tcg: dict, profile: dict) -> str:
    rows_html = ""
    last_band = None
    for i, r in enumerate(tcg["rows"], start=1):
        if r["band"] != last_band:
            rows_html += f"<tr class='tk-band'><td colspan='3'>{_esc(r['band'])}</td></tr>"
            last_band = r["band"]
        open_row = not r["auto_answered"]
        ans = (_NEEDS_CHIP if open_row else _esc(r["answer"]))
        if r["id"] == "t13":
            ans += _dist_boxes(profile["abcd_segmentation_pct"])
        elif r["id"] == "t14":
            ans += _dist_boxes(profile["adoption_ladder_pct"])
        elif r["id"] == "t15":
            ans += _dist_boxes(profile["digital_preference_pct"])
        rows_html += (f"<tr{' class=plan-open-row' if open_row else ''}><td class='tk-srno'>{i}</td>"
                      f"<td>{_esc(r['text'])}</td><td>{ans}</td></tr>")
    return ("<table class='tk-qtable'><tr class='tk-qhead'><th>Sr.No.</th><th>Questions</th><th>Responses</th></tr>"
            + rows_html + "</table>"
            + f"<p class='plan-caveat'>{_esc(tcg['caveat'])}</p>")


def _render_questionnaire(cq: dict, one_idea: dict) -> str:
    rows_html = ""
    last_sec = None
    for i, r in enumerate(cq["rows"], start=1):
        if r["section"] != last_sec:
            rows_html += f"<tr class='tk-band'><td colspan='3'>{_esc(r['section'])}</td></tr>"
            last_sec = r["section"]
        open_row = not r["auto_answered"]
        if r["id"] == "cq5":
            ans = ("<div class='tk-oneidea'>"
                   + "".join(f"<div>{_esc(v)}</div>" for v in one_idea.values()) + "</div>")
        else:
            ans = _NEEDS_CHIP if open_row else _esc(r["answer"])
        rows_html += (f"<tr{' class=plan-open-row' if open_row else ''}><td class='tk-srno'>{i}</td>"
                      f"<td>{_esc(r['text'])}</td><td>{ans}</td></tr>")
    return ("<table class='tk-qtable'><tr class='tk-qhead'><th>Sr.No.</th><th>Questions</th><th>Responses</th></tr>"
            + rows_html + "</table>"
            + f"<p class='plan-caveat'>{_esc(cq['caveat'])}</p>")


def _render_feasibility(feas: dict) -> str:
    # Category rowspans (questions arrive grouped by category, toolkit order).
    rows = feas["questions"]
    span: dict[str, int] = {}
    for q in rows:
        span[q["category"]] = span.get(q["category"], 0) + 1
    seen: set[str] = set()
    body = ""
    for i, q in enumerate(rows, start=1):
        cat_cell = ""
        if q["category"] not in seen:
            seen.add(q["category"])
            cat_cell = f"<td class='tk-cat' rowspan='{span[q['category']]}'>{_esc(q['category'])}</td>"
        sel_idx = {"Simple": 0, "Medium": 1, "Complex": 2}.get(q.get("answer_tier") or "", None)
        tier_cells = ""
        for t_i, t_label in enumerate(q["tiers"]):
            sel = " sel" if (q["auto_answered"] and sel_idx == t_i) else ""
            tier_cells += f"<td class='tk-t{t_i}{sel}'>{_esc(t_label)}</td>"
        qtext = f"{i}. {_esc(q['text'])}" + ("" if q["auto_answered"] else " " + _NEEDS_CHIP)
        note = (f"<div class='tk-feas-note'>{_esc(q['answer'])}</div>"
                if q["auto_answered"] and q["answer"] not in q["tiers"] else "")
        body += f"<tr>{cat_cell}<td class='tk-q'>{qtext}{note}</td>{tier_cells}</tr>"
    legend = "".join(
        f"<div class='tk-legend-box {cls}'><strong>{_esc(t)}</strong><span>{_esc(d)}</span></div>"
        for cls, t, d in _FEAS_LEGEND)
    cat_rows = "".join(
        f"<tr><td>{_esc(cat)}</td><td><span class='tk-level {_LEVEL_TO_TIER_CLASS[v['level']]}'>{_esc(v['level'])}</span></td></tr>"
        for cat, v in feas["by_category"].items())
    overall = (f"<div class='tk-feas-overall'>Overall read: "
               f"<span class='tk-level {_LEVEL_TO_TIER_CLASS[feas['overall_level']]}'>{_esc(feas['overall_level'])} Omnichannel CX</span>"
               f" — {feas['auto_answered_count']}/{feas['total_questions']} questions auto-answered from state</div>")
    return (overall
            + "<div class='tk-feas-wrap'><table class='tk-feas'>"
              "<tr class='tk-qhead'><th>Categories</th><th>Checklist</th><th>Answer 1</th><th>Answer 1</th><th>Answer 1</th></tr>"
            + body + "</table><div class='tk-legend'>" + legend + "</div></div>"
            + "<table class='plan-table' style='max-width:340px'><tr><th>Category</th><th>Level</th></tr>" + cat_rows + "</table>"
            + f"<p class='plan-caveat'>{_esc(feas['caveat'])}</p>")


# --------------------------------------------------------------------------- #
# Content-library helpers (claims / references / assets that fill Phase 2 & 3)
# --------------------------------------------------------------------------- #

_CLAIM_STATUS_CLASS = {"approved": "tk-claim-approved", "in_review": "tk-claim-review",
                       "draft": "tk-claim-draft", "expired": "tk-claim-draft", "retired": "tk-claim-draft"}

# Which claim types are most relevant to each toolkit key-message topic (keyword-matched).
_TOPIC_CLAIM_TYPES = {
    "efficacy": ["efficacy", "moa"], "outcome": ["efficacy"], "survival": ["efficacy"],
    "clinical": ["efficacy", "moa"], "safety": ["safety", "isi"], "tolerab": ["safety"],
    "mechanism": ["moa"], "moa": ["moa"], "dosing": ["access"], "administration": ["access"],
    "access": ["access"], "cost": ["access"], "value": ["rtb", "access"], "burden": ["rtb", "access"],
    "quality": ["efficacy", "rtb"], "differenti": ["rtb", "efficacy"], "awareness": ["rtb"],
}

_ASSET_CHANNEL = {  # asset format -> the channel/touchpoint it flows through
    "email": ("Owned digital", "language"), "banner": ("Reach (programmatic/display)", "campaign"),
    "detail_aid": ("Field / peer detailing", "groups"), "social": ("Patient-adjacent / social", "favorite"),
    "video": ("Owned digital", "smart_display"), "webpage": ("Owned digital", "language"),
}


def _match_claims_for_topic(topic: str, claims: list[dict]) -> list[dict]:
    """Claims from the library most relevant to a key-message topic (by type keyword),
    approved first. Falls back to all approved claims when nothing matches by type."""
    tl = topic.lower()
    wanted: set[str] = set()
    for kw, types in _TOPIC_CLAIM_TYPES.items():
        if kw in tl:
            wanted.update(types)
    matched = [c for c in claims if c["claim_type"] in wanted] if wanted else []
    if not matched:
        matched = [c for c in claims if c["status"] == "approved" and c["claim_type"] in ("efficacy", "moa")]
    matched.sort(key=lambda c: 0 if c["status"] == "approved" else 1)
    return matched[:3]


def _claim_ref_chip(c: dict) -> str:
    if not c.get("references"):
        return ""
    r = c["references"][0]
    src = {"dailymed": "DailyMed label", "clinicaltrials": "ClinicalTrials.gov", "pubmed": "PubMed",
           "openfda": "openFDA"}.get(r.get("source_type"), r.get("source_type", "ref"))
    ext = f" {r['external_id']}" if r.get("external_id") else ""
    label = f"{src}{ext}"
    return (f"<a class='tk-ref-chip' href='{_esc(r.get('url') or '#')}' target='_blank' "
            f"title='{_esc(r.get('locator') or '')}'>{_icon('link')}{_esc(label)}</a>")


def _claim_line(c: dict) -> str:
    status = c.get("status", "draft")
    scls = _CLAIM_STATUS_CLASS.get(status, "tk-claim-draft")
    mat = f"<span class='tk-claim-mat'>{_esc(c['material_number'])}</span>" if c.get("material_number") else ""
    badge = f"<span class='tk-claim-badge {scls}'>{_esc(status.replace('_', ' '))}</span>"
    return (f"<div class='tk-claim'><div class='tk-claim-txt'>{_esc(c['text'])}</div>"
            f"<div class='tk-claim-meta'>{badge}{mat}{_claim_ref_chip(c)}</div></div>")


def _render_message_flow_template(mf: dict, persona: str, stage_label: str, engagement_goal: str,
                                  content_library: dict | None = None) -> str:
    pool = "".join(f"<div class='tk-msg tk-msg-green'>{_esc(t)}</div>" for t in mf["brand_plan_key_message_pool"])
    depri = ("".join(f"<div class='tk-msg tk-msg-plain'>{_esc(t)}</div>" for t in mf["de_prioritized_messages"])
             or "<div class='tk-msg tk-msg-empty'>(none — all pool messages selected)</div>")
    new_km = "".join(f"<div class='tk-msg tk-msg-orange'>{_esc(km['topic'])}</div>" for km in mf["key_messages"])
    km_cols = ""
    for km in mf["key_messages"]:
        supports = "".join(f"<div class='tk-msg tk-msg-blue'>{_esc(s)}</div>" for s in km["supporting_messages"])
        km_cols += (f"<div class='tk-mf-col'><div class='tk-msg tk-msg-green tk-msg-km'>{_esc(km['topic'])}</div>"
                    f"{supports}</div>")
    return (
        "<div class='tk-mf-side'>"
        f"<div class='tk-chip tk-chip-blue'>Segment name<span>{_esc(persona)}</span></div>"
        f"<div class='tk-chip tk-chip-navy'>Campaign Objective<span>{_esc(engagement_goal)}</span></div>"
        f"<div class='tk-chip tk-chip-cyan'>Leverage Point<span>{_esc(stage_label)}</span></div></div>"
        "<div class='tk-mf-pools'>"
        f"<div class='tk-mf-pool'><h4>Brand plan key messages</h4><div class='tk-pool'>{pool}</div></div>"
        f"<div class='tk-mf-pool'><h4>De-prioritized messages</h4><div class='tk-depri'>{depri}</div></div>"
        f"<div class='tk-mf-pool'><h4>New key messages</h4><div class='tk-pool-col'>{new_km}</div></div></div>"
        "<div class='tk-mf-bar'>Behavioral objective / adoption/scientific ladder step-up to be achieved</div>"
        f"<div class='tk-mf-grid'><div class='tk-mf-rail'>Key<br>messages<br><br>Supporting<br>messages</div>{km_cols}</div>"
        + _render_message_claims_block(mf, content_library)
        + f"<p class='plan-caveat'>{_esc(mf['caveat'])}</p>"
    )


def _render_message_claims_block(mf: dict, content_library: dict | None) -> str:
    """The real substantiated claims from the content library, matched to each key message --
    this is what fills Q7 with actual claims + references instead of only synthesized text."""
    lib = content_library or {}
    claims = lib.get("claims", [])
    if not lib.get("found") or not claims:
        return ("<div class='tk-lib-empty'>No approved claims library is indexed for this brand yet — "
                "run <code>scripts/build_content_library.py</code> to populate it, or the brand team supplies it. "
                + _NEEDS_CHIP + "</div>")
    cols = ""
    for km in mf["key_messages"]:
        matched = _match_claims_for_topic(km["topic"], claims)
        chips = "".join(_claim_line(c) for c in matched) or "<div class='tk-claim tk-claim-none'>No library claim matched — brand team to supply.</div>"
        cols += (f"<div class='tk-lib-col'><div class='tk-lib-col-head'>{_esc(km['topic'])}</div>{chips}</div>")
    approved = sum(1 for c in claims if c["status"] == "approved")
    return (
        "<div class='tk-lib-block'><h4 class='tk-lib-h'>"
        + _icon("verified") + "Substantiated claims from the content library</h4>"
        f"<p class='tk-lib-sub'>{len(claims)} claims ({approved} MLR-approved) for this brand/indication, each "
        "traceable to a reference. Matched to the key messages above.</p>"
        f"<div class='tk-lib-grid'>{cols}</div></div>"
    )


def _render_channel_selection(chsel: dict) -> str:
    purposes = ["Frequency", "Impact", "Reach", "Relation building", "Reach patients"]
    head = ("<tr class='tk-qhead'><th rowspan='2'>Channels</th>"
            f"<th colspan='{len(purposes)}'>Channel purpose</th><th colspan='2'>Availability</th>"
            "<th rowspan='2'>Preference / affinity</th><th colspan='3'>Brand priority</th></tr>"
            "<tr class='tk-qhead'>" + "".join(f"<th>{p}</th>" for p in purposes)
            + "<th>Current</th><th>Future</th><th>High</th><th>Medium</th><th>Low</th></tr>")
    body = ""
    for r in chsel["channels"]:
        p_cells = "".join(f"<td class='tk-tick'>{'✓' if p in r['purpose'] else ''}</td>" for p in purposes)
        avail = (f"<td class='tk-tick'>{'✓' if r['availability'] == 'Current' else ''}</td>"
                 f"<td class='tk-tick'>{'✓' if r['availability'] == 'Future' else ''}</td>")
        pri_cells = ""
        for band, cls in [("High", "tk-t2"), ("Medium", "tk-t1"), ("Low", "tk-t0")]:
            pri_cells += f"<td class='tk-tick {cls if r['brand_priority'] == band else ''}'>{'✓' if r['brand_priority'] == band else ''}</td>"
        body += (f"<tr><td class='tk-ch'>{_esc(r['channel'])}</td>{p_cells}{avail}"
                 f"<td class='tk-tick'>{r['preference_affinity']}</td>{pri_cells}</tr>")
    return (f"<p class='plan-caveat'>{_esc(chsel['guidance'])}</p>"
            f"<table class='tk-qtable tk-chsel'>{head}{body}</table>"
            f"<p class='plan-caveat'>{_esc(chsel['caveat'])}</p>")


_CONTENT_AUDIT_COLS = ["File Name", "Asset Title", "Target Group", "Branded/Unbranded", "Asset format",
                       "Key Messages", "Description", "Where to find it: URL", "ID_code"]


def _render_content_audit(mf: dict, persona: str, micro_journeys: dict,
                          content_library: dict | None = None) -> str:
    head = "".join(f"<th>{_esc(c)}</th>" for c in _CONTENT_AUDIT_COLS)
    lib = content_library or {}
    assets = lib.get("assets", [])
    if lib.get("found") and assets:
        body = ""
        for a in assets:
            key_msgs = ", ".join(m for m in a.get("modules", []) if "claim block" in m.lower()) \
                or ", ".join(a.get("modules", [])[:2]) or "—"
            branded = "Branded" if a.get("branded") else "Unbranded"
            url = a.get("url") or (f"blob:{a['blob_key'][:12]}…" if a.get("blob_key") else "—")
            cells = [_esc(a.get("file_name") or "—"), _esc(a.get("title") or "—"), _esc(a.get("target_group") or persona),
                     _esc(branded), _esc(a.get("asset_format") or "—"), _esc(key_msgs),
                     _esc(a.get("description") or "—"), _esc(url), _esc(a.get("id_code") or "—")]
            body += "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
        counts = lib.get("counts", {})
        intro = (f"<p>Content inventory for this brand/indication — <strong>{counts.get('assets', len(assets))}</strong> "
                 f"existing assets assembled from <strong>{counts.get('modules', 0)}</strong> reusable modules, each "
                 f"carrying its key-message claim block and traceable references. This is the real 'Map Existing "
                 f"Content' audit, populated from the content library.</p>")
        return (intro + f"<div class='tk-scroll'><table class='tk-qtable tk-audit'><tr class='tk-qhead'>{head}</tr>{body}</table></div>")
    # Fallback: no library indexed -> the toolkit template with seeded rows.
    body = ""
    journeys = micro_journeys["journeys"]
    for i, km in enumerate(mf["key_messages"]):
        fmt = journeys[i % len(journeys)]["primary_touchpoint"] if journeys else "—"
        cells = [_NEEDS_CHIP, _NEEDS_CHIP, _esc(persona), _NEEDS_CHIP, _esc(fmt),
                 _esc(km["topic"]), _esc(km["supporting_messages"][0]), _NEEDS_CHIP, _NEEDS_CHIP]
        body += "<tr class='plan-open-row'>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
    return ("<p>No content library is indexed for this brand yet, so this audit ships as the toolkit's template with "
            "one seeded row per key message — the highlighted cells are what the brand team's content inventory needs "
            "to fill in. " + _NEEDS_CHIP + "</p>"
            f"<div class='tk-scroll'><table class='tk-qtable tk-audit'><tr class='tk-qhead'>{head}</tr>{body}</table></div>")


def _render_channel_flow(micro_journeys: dict, pp_npp: list[dict], content_library: dict | None = None) -> str:
    mj = "".join(f"<li><strong>{_esc(j['name'])}</strong> — trigger: {_esc(j['trigger'])}; "
                 f"primary touchpoint: {_esc(j['primary_touchpoint'])}; {_esc(j['content_readiness'])}</li>"
                 for j in micro_journeys["journeys"])
    pp = "".join(f"<tr><td>{_esc(r['channel'])}</td><td>{r['pct']}%</td><td>{_esc(r['bucket'])}</td></tr>" for r in pp_npp)
    return ("<h3 class='plan-sec-sub'>Micro-journeys</h3><ul>" + mj + "</ul>"
            f"<p class='plan-caveat'>Governance: {_esc(micro_journeys['interim_check'])}</p>"
            + _render_content_to_channel(content_library)
            + "<h3 class='plan-sec-sub'>PP / NPP channel split</h3>"
            "<table class='plan-table'><tr><th>Channel</th><th>Share</th><th>PP / NPP</th></tr>" + pp + "</table>")


def _render_content_to_channel(content_library: dict | None) -> str:
    """Maps the brand's real DAM assets onto the channels they flow through -- so Design
    Channel Flow shows which existing content lands in which channel, not an empty diagram."""
    lib = content_library or {}
    assets = lib.get("assets", [])
    if not lib.get("found") or not assets:
        return ""
    buckets: dict[str, list[dict]] = {}
    for a in assets:
        channel, icon = _ASSET_CHANNEL.get(a.get("asset_format", ""), ("Owned digital", "language"))
        buckets.setdefault(channel, []).append(a)
    cards = ""
    for channel, items in buckets.items():
        icon = next((ic for ch, ic in _ASSET_CHANNEL.values() if ch == channel), "language")
        rows = "".join(
            f"<div class='tk-cf-asset'><span class='tk-cf-fmt'>{_esc(a.get('asset_format',''))}</span>"
            f"<span class='tk-cf-title'>{_esc(a.get('title',''))}</span>"
            f"<span class='tk-cf-badge'>{'Branded' if a.get('branded') else 'Unbranded'}</span></div>"
            for a in items)
        cards += (f"<div class='tk-cf-col'><div class='tk-cf-head'>{_icon(icon)}{_esc(channel)}"
                  f"<span class='tk-cf-count'>{len(items)}</span></div>{rows}</div>")
    return ("<h3 class='plan-sec-sub'>" + _icon("dashboard") + "Content-to-channel mapping</h3>"
            "<p class='tk-lib-sub'>Existing content assets routed to the channels they flow through — "
            "the raw material for the channel flow, drawn from the content library.</p>"
            f"<div class='tk-cf-grid'>{cards}</div>")


def _render_design_message_flow(mf: dict) -> str:
    cols = ""
    for i, km in enumerate(mf["key_messages"], start=1):
        supports = "".join(f"<div class='tk-imp-box'>{_esc(s)}</div>" for s in km["supporting_messages"])
        cols += (f"<div class='tk-imp-col'><div class='tk-msg tk-msg-green tk-msg-km'>Key Message #{i}: {_esc(km['topic'])}</div>"
                 f"<div class='tk-imp-head'><span class='tk-circ'>{i}</span>Impact {i}</div>{supports}</div>")
    nob = mf["non_opener_branch"]
    cs_items = "".join(f"<div class='tk-imp-box'>{_esc(s)}</div>" for s in nob["campaign_summary"])
    cs = (f"<div class='tk-imp-col tk-cs-col'><div class='tk-cs-head'><span class='tk-cs-badge'>CS</span>"
          f"{_esc(nob['node'])}</div><div class='tk-cs-trigger'>{_esc(nob['trigger'])}</div>{cs_items}</div>")
    return f"<div class='tk-impacts'>{cols}{cs}</div><p class='plan-caveat'>{_esc(mf['caveat'])}</p>"


_AWARD_TIER_CLASS = {"Grand Prix": "aw-grand", "Grand": "aw-grand", "Gold": "aw-gold",
                     "Silver": "aw-silver", "Bronze": "aw-bronze", "Finalist": "aw-finalist"}
_MATCH_LABEL = {"brand": "Same brand", "therapy_area": "Same therapy area", "client": "Same client",
                "industry": "Industry benchmark"}


def _render_award_campaigns(awards: list[dict]) -> str:
    cards = ""
    for a in awards:
        tier_cls = _AWARD_TIER_CLASS.get(a.get("tier", ""), "aw-finalist")
        srcs = "".join(f"<a href='{_esc(u)}' target='_blank' class='aw-src'>{_icon('link')}source {i + 1}</a>"
                       for i, u in enumerate(a.get("source_urls", [])[:4]))
        match = _MATCH_LABEL.get(a.get("match", ""), a.get("match", ""))
        cards += (
            f"<div class='aw-card'>"
            f"<div class='aw-top'><span class='aw-badge {tier_cls}'>{_icon('emoji_events')}{_esc(a.get('award', ''))}</span>"
            f"<span class='aw-match'>{_esc(match)}</span></div>"
            f"<div class='aw-title'>{_esc(a.get('title', ''))}</div>"
            f"<div class='aw-meta'>{_esc(a.get('festival', ''))} {a.get('year', '')} · {_esc(a.get('agency', ''))}"
            + (f" · {_esc(a.get('client', ''))}" if a.get('client') else "") + "</div>"
            f"<div class='aw-row'><span class='aw-k'>Why it won</span><span>{_esc(a.get('why_awarded', ''))}</span></div>"
            f"<div class='aw-row'><span class='aw-k'>Message</span><span>{_esc(a.get('key_message', ''))}</span></div>"
            f"<div class='aw-row'><span class='aw-k'>Creative</span><span>{_esc(a.get('creative_summary', ''))}</span></div>"
            f"<div class='aw-row'><span class='aw-k'>Imagery</span><span>{_esc(a.get('images_description', ''))}</span></div>"
            f"<div class='aw-srcs'>{srcs}</div></div>"
        )
    return ("<h3 class='plan-sec-sub'>" + _icon("military_tech") + "Award-winning campaigns to learn from</h3>"
            "<p class='tk-lib-sub'>Real festival winners matched to this brand, therapy area or client — why each "
            "won, its core message, and the hero creative. Creative-direction inspiration, grounded in cited sources.</p>"
            f"<div class='aw-grid'>{cards}</div>")


_PYRAMID_LAYERS = [("tk-pyr-navy", "Business Objective"), ("tk-pyr-mag", "Marketing Objective"),
                   ("tk-pyr-cyan", "Campaign Objective"), ("tk-pyr-green", "Campaign KPI / Metrics")]

_PYR_NUM_CLASSES = ["n-navy", "n-mag", "n-cyan", "n-green", "n-green", "n-green", "n-green"]


def _render_metrics_pyramid(tk: dict) -> str:
    layers = "".join(f"<div class='tk-pyr-layer {cls}'>{_esc(label)}</div>" for cls, label in _PYRAMID_LAYERS)
    rows = ""
    all_measures = [("OPTIN", m) for m in tk["optin"]] + [("NON-OPTIN", m) for m in tk["non_optin"]]
    for i, (bucket, m) in enumerate(all_measures):
        ncls = _PYR_NUM_CLASSES[i] if i < len(_PYR_NUM_CLASSES) else "n-green"
        rows += (f"<div class='tk-pyr-row'><span class='tk-circ {ncls}'>{i + 1}</span>"
                 f"<div class='tk-pyr-obj'><strong>{_esc(m['objective'])}</strong>"
                 f"<span class='tk-pyr-bucket'>{bucket}</span><div class='tk-pyr-measure'>{_esc(m['measure'])}</div></div></div>")
    return (f"<div class='tk-pyr'><div class='tk-pyr-left'>{layers}</div>"
            f"<div class='tk-pyr-right'>{rows}</div></div>")


def _render_work_plan(exec_plan: dict, exec_raci: dict) -> str:
    gantt = (f"<div class='plan-gantt' style='--total-weeks:{exec_plan['total_weeks']}'>"
             + "".join(_gantt_row_html(b) for b in exec_plan["bands"]) + "</div>")
    tasks = "".join(f"<tr><td>{_esc(b['category'])}</td><td>W{b['start_week']}–W{b['end_week']}</td>"
                    f"<td>{_esc(', '.join(b['tasks']))}</td></tr>" for b in exec_plan["bands"])
    raci_head = "".join(f"<th>{_esc(w)}</th>" for w in exec_raci["workstreams"])
    raci_rows = ""
    for row in exec_raci["rows"]:
        cells = "".join(f"<td class='tk-raci tk-raci-{row['assignments'][w].lower()}'>{_esc(row['assignments'][w])}</td>"
                        for w in exec_raci["workstreams"])
        raci_rows += f"<tr><td>{_esc(row['stakeholder'])}</td>{cells}</tr>"
    legend = " · ".join(f"<strong>{k}</strong> {v}" for k, v in exec_raci["legend"].items())
    return (f"<p class='plan-caveat'>{_esc(exec_plan['mlr_delay_note'])}</p>" + gantt
            + "<table class='plan-table'><tr><th>Task category</th><th>Weeks</th><th>Representative tasks</th></tr>"
            + tasks + "</table>"
            + "<h3 class='plan-sec-sub'>RACI (Sheet 14) " + _NEEDS_CHIP + "</h3>"
            + f"<div class='tk-scroll'><table class='tk-qtable tk-raci-table'><tr class='tk-qhead'><th>Stakeholder</th>{raci_head}</tr>"
            + raci_rows + "</table></div>"
            + f"<p class='plan-caveat'>{legend}. {_esc(exec_raci['caveat'])}</p>")


def _render_tml(tml: dict) -> str:
    head = ("<tr class='tk-qhead'><th rowspan='2'>Test</th><th rowspan='2'>Objective</th><th rowspan='2'>Channels</th>"
            "<th colspan='4'>What &amp; how do we measure?</th><th colspan='2'>What we will learn?</th></tr>"
            "<tr class='tk-qhead'><th>Measure</th><th>Definition</th><th>Measure Type, Frequency</th><th>Data Source</th>"
            "<th>What does good look like?</th><th>What will we Learn?</th></tr>")
    body = ""
    for r in tml["rows"]:
        cells = [r["test"], r["objective"], r["channels"], r["measure"], r["definition"],
                 r["frequency"], r["data_source"], r["what_good_looks_like"], r["what_we_will_learn"]]
        body += "<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in cells) + "</tr>"
    return (f"<div class='tk-scroll'><table class='tk-qtable tk-tml'>{head}{body}</table></div>"
            f"<p class='plan-caveat'>{_esc(tml['caveat'])}</p>")


# --------------------------------------------------------------------------- #
# Main composer
# --------------------------------------------------------------------------- #

def compose_plan(ctx: dict) -> tuple[str, str]:
    brand, ta = ctx["brand"], ctx["therapy_area"]
    inferred = ctx["inferred"]
    strat = ctx["strategy"]
    m = strat["messaging_architecture"]
    sp = strat["stage_profile"]
    pos = ctx["positioning"]
    swot = ctx["swot"]
    kpi = ctx["kpi"]
    budget_alloc = ctx["budget_allocation"]
    bam = ctx["bam"]
    cx_maturity = ctx["cx_maturity"]
    feas = cx_maturity["feasibility_checklist"]
    precedents = ctx["precedents"]
    profile = ctx["segment_profile"]
    tcg = ctx["tcg"]
    cq = ctx["cx_questionnaire"]
    mf = ctx["message_flow"]
    chsel = ctx["channel_selection"]
    open_groups = ctx.get("open_questions", [])
    indication = ctx.get("indication", "")
    ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    exec_sum = _exec_summary(ctx)
    stage_label = strat["inputs"]["stage"]

    md: list[str] = []
    h: list[str] = []

    # ---- Title + badges + home navigator -------------------------------------- #
    md.append(f"# Brand Engagement Plan — {brand} · {ta}\n")
    md.append(f"*Lifecycle stage:* {inferred['lifecycle_label']}  |  *Generated:* {ts}\n")
    h.append(f"<h1>Brand Engagement Plan</h1><p class='plan-sub'>{_esc(brand)} · {_esc(ta)} — "
             f"{_esc(inferred['lifecycle_label'])} · generated {ts}</p>")
    h.append("<div class='plan-badges'>"
             + _badge("science", brand) + _badge("biotech", ta)
             + (_badge("vaccines", indication) if indication else "")
             + _badge("trending_up", inferred["lifecycle_label"])
             + _badge("groups", inferred["persona"]) + _badge("route", stage_label)
             + _badge("military_tech", f"{cx_maturity['level']} CX maturity")
             + (_badge("swords", f"{len(ctx['competitors'])} competitor(s)") if ctx["competitors"] else "")
             + "</div>")
    h.append(_home_navigator())

    # ---- 1. Executive summary (open) ------------------------------------------ #
    md.append("## 1. Executive summary\n\n" + exec_sum + "\n")
    h.append(_det_open(1, "Executive summary", "insights", start_open=True)
             + f"<div class='plan-hero'>{_icon('auto_awesome')}<p>{exec_sum}</p></div>" + _DET_CLOSE)

    # ---- 2. Open questions (open, highlighted) --------------------------------- #
    n_open = sum(len(g["questions"]) for g in open_groups)
    md.append("## 2. Open questions — needs brand-team alignment\n")
    for g in open_groups:
        md.append(f"**{g['title']}** *({g['source']})*")
        for q in g["questions"]:
            md.append(f"- {q}")
        md.append("")
    h.append(_det_open(2, "Open questions — needs brand-team alignment", "help", start_open=True,
                       open_count=n_open)
             + _render_open_questions(open_groups) + _DET_CLOSE)

    # ---- 3. Brief --------------------------------------------------------------- #
    md.append("## 3. Brief\n")
    md.append(f"- **Brand:** {brand}\n- **Therapy area:** {ta}\n"
              + (f"- **Indication:** {indication}\n" if indication else "")
              + f"- **Lifecycle:** {inferred['lifecycle_label']}\n"
              f"- **Priority persona:** {inferred['persona']}\n- **Journey stage:** {stage_label}\n"
              f"- **Competitive set:** {', '.join(ctx['competitors']) or '—'}\n")
    brief_rows = [("Brand", brand), ("Therapy area", ta)]
    if indication:
        brief_rows.append(("Indication", indication))
    brief_rows += [("Lifecycle", inferred["lifecycle_label"]), ("Priority persona", inferred["persona"]),
                   ("Journey stage", stage_label), ("Competitive set", ", ".join(ctx["competitors"]) or "—")]
    h.append(_det_open(3, "Brief", "assignment")
             + "<table class='plan-kv'>"
             + "".join(f"<tr><th>{k}</th><td>{_esc(v)}</td></tr>" for k, v in brief_rows)
             + "</table>" + _DET_CLOSE)

    # =========================== PHASE 1 · ALIGN ================================ #
    h.append(_phase_banner("align", "Align on customer understanding and CX objectives", 1))
    md.append("---\n\n# Phase 1 · Align on customer understanding and CX objectives\n")

    # 4. Target Customer Group Template
    md.append("## 4. Target Customer Group Template (Sheet 3)\n")
    md.append("| # | Question | Response |")
    md.append("|---|---|---|")
    for i, r in enumerate(tcg["rows"], start=1):
        md.append(f"| {i} | {r['text']} | {r['answer']} |")
    md.append("")
    h.append(_det_open(4, "Target Customer Group Template", _PHASE_ICONS["align"], phase="align",
                       open_count=len(tcg["open_questions"]))
             + _render_tcg(tcg, profile) + _DET_CLOSE)

    # 5. CX Planning Questionnaire
    md.append("## 5. CX Planning Questionnaire (Sheet 4)\n")
    md.append("| # | Question | Response |")
    md.append("|---|---|---|")
    for i, r in enumerate(cq["rows"], start=1):
        md.append(f"| {i} | {r['text']} | {r['answer']} |")
    md.append("")
    h.append(_det_open(5, "CX Planning Questionnaire", _PHASE_ICONS["align"], phase="align",
                       open_count=len(cq["open_questions"]))
             + _render_questionnaire(cq, cq["one_idea"]) + _DET_CLOSE)

    # 6. Omnichannel CX Feasibility Analysis
    md.append("## 6. Omnichannel CX Feasibility Analysis (Sheet 5)\n")
    md.append(f"**Overall read: {feas['overall_level']} Omnichannel CX** "
              f"({feas['auto_answered_count']}/{feas['total_questions']} auto-answered)\n")
    md.append("| # | Question | Category | Answer |")
    md.append("|---|---|---|---|")
    for i, q in enumerate(feas["questions"], start=1):
        md.append(f"| {i} | {q['text']} | {q['category']} | {q['answer']} |")
    md.append("")
    feas_open = sum(1 for q in feas["questions"] if not q["auto_answered"])
    h.append(_det_open(6, "Omnichannel CX Feasibility Analysis", _PHASE_ICONS["align"], phase="align",
                       open_count=feas_open)
             + _render_feasibility(feas) + _DET_CLOSE)

    # =========================== PHASE 2 · SELECT =============================== #
    h.append(_phase_banner("select", "Select relevant messages and channels", 2))
    md.append("---\n\n# Phase 2 · Select relevant messages and channels\n")

    # 7. Message Flow Template
    md.append("## 7. Message Flow Template (Sheet 6)\n")
    md.append(f"- **Segment name:** {inferred['persona']}\n- **Campaign objective:** {sp['engagement_goal']}\n"
              f"- **Leverage point:** {stage_label}\n")
    md.append("**Brand plan key messages:** " + ", ".join(mf["brand_plan_key_message_pool"]))
    md.append("**De-prioritized:** " + (", ".join(mf["de_prioritized_messages"]) or "(none)"))
    for km in mf["key_messages"]:
        md.append(f"- **{km['topic']}** — " + "; ".join(km["supporting_messages"]))
    md.append("")
    h.append(_det_open(7, "Message Flow Template", _PHASE_ICONS["select"], phase="select")
             + _render_message_flow_template(mf, inferred["persona"], stage_label, sp["engagement_goal"],
                                             ctx.get("content_library"))
             + _DET_CLOSE)

    # 8. Channel Selection Template
    md.append("## 8. Channel Selection Template (Sheet 7)\n")
    md.append("| Channel | Purpose | Availability | Preference/affinity | Brand priority |")
    md.append("|---|---|---|---|---|")
    for r in chsel["channels"]:
        md.append(f"| {r['channel']} | {', '.join(r['purpose'])} | {r['availability']} | {r['preference_affinity']} | {r['brand_priority']} |")
    md.append("")
    h.append(_det_open(8, "Channel Selection Template", _PHASE_ICONS["select"], phase="select")
             + _render_channel_selection(chsel) + _DET_CLOSE)

    # =========================== PHASE 3 · CREATE =============================== #
    h.append(_phase_banner("create", "Create omnichannel CX", 3))
    md.append("---\n\n# Phase 3 · Create omnichannel CX\n")

    # 9. Map Existing Content
    lib = ctx.get("content_library") or {}
    lib_assets = lib.get("assets", []) if lib.get("found") else []
    md.append("## 9. Map Existing Content & Identify (Sheet 8)\n")
    if lib_assets:
        md.append(f"_Content inventory for this brand/indication — {len(lib_assets)} existing assets from the content "
                  "library, each assembled from reusable modules with traceable claims._\n")
        md.append("| File | Title | Target | Branded | Format | Key messages | ID code |")
        md.append("|---|---|---|---|---|---|---|")
        for a in lib_assets:
            km = ", ".join(m for m in a.get("modules", []) if "claim block" in m.lower()) or "—"
            md.append(f"| {a.get('file_name','—')} | {a.get('title','—')} | {a.get('target_group','—')} | "
                      f"{'Branded' if a.get('branded') else 'Unbranded'} | {a.get('asset_format','—')} | {km} | {a.get('id_code','—')} |")
        md.append("")
    else:
        md.append("_No content library is indexed — the audit ships as the toolkit template with one seeded row per key "
                  "message; the brand team's content inventory fills the rest._\n")
    h.append(_det_open(9, "Map Existing Content & Identify", _PHASE_ICONS["create"], phase="create",
                       open_count=0 if lib_assets else len(mf["key_messages"]))
             + _render_content_audit(mf, inferred["persona"], ctx["micro_journeys"], ctx.get("content_library"))
             + _DET_CLOSE)

    # 10. Design Channel Flow
    md.append("## 10. Design Channel Flow\n")
    for j in ctx["micro_journeys"]["journeys"]:
        md.append(f"- **{j['name']}** — trigger: {j['trigger']}; primary touchpoint: {j['primary_touchpoint']}; {j['content_readiness']}")
    md.append("\n| Channel | Share | PP / NPP |")
    md.append("|---|---|---|")
    for r in ctx["pp_npp"]:
        md.append(f"| {r['channel']} | {r['pct']}% | {r['bucket']} |")
    md.append("")
    h.append(_det_open(10, "Design Channel Flow", _PHASE_ICONS["create"], phase="create")
             + _render_channel_flow(ctx["micro_journeys"], ctx["pp_npp"], ctx.get("content_library")) + _DET_CLOSE)

    # 11. Design Message Flow
    md.append("## 11. Design Message Flow (Sheet 9)\n")
    for i, km in enumerate(mf["key_messages"], start=1):
        md.append(f"**Impact {i} — {km['topic']}**")
        for s in km["supporting_messages"]:
            md.append(f"- {s}")
    md.append(f"\n**{mf['non_opener_branch']['node']}** ({mf['non_opener_branch']['trigger']}):")
    for s in mf["non_opener_branch"]["campaign_summary"]:
        md.append(f"- {s}")
    md.append("")
    h.append(_det_open(11, "Design Message Flow", _PHASE_ICONS["create"], phase="create")
             + _render_design_message_flow(mf) + _DET_CLOSE)

    # 12. Metrics to Track CX Success
    tk = kpi["toolkit_measures"]
    md.append("## 12. Metrics to Track CX Success (Sheet 10)\n")
    for bucket, items in [("Optin", tk["optin"]), ("Non-optin", tk["non_optin"])]:
        md.append(f"**{bucket}**")
        for m2 in items:
            md.append(f"- **{m2['objective']}:** {m2['measure']}")
        md.append("")
    h.append(_det_open(12, "Metrics to Track CX Success", _PHASE_ICONS["create"], phase="create")
             + _render_metrics_pyramid(tk) + _DET_CLOSE)

    # =========================== PHASE 4 · DEPLOY =============================== #
    h.append(_phase_banner("deploy", "Deploy campaign", 4))
    md.append("---\n\n# Phase 4 · Deploy campaign\n")

    # 13. CX Execution Work Plan (+ RACI)
    exec_plan, exec_raci = ctx["execution_plan"], ctx["execution_raci"]
    md.append("## 13. CX Execution Work Plan (Sheets 12 & 14)\n")
    md.append(f"*{exec_plan['mlr_delay_note']}*\n")
    md.append("| Task category | Weeks | Representative tasks |")
    md.append("|---|---|---|")
    for b in exec_plan["bands"]:
        md.append(f"| {b['category']} | W{b['start_week']}–W{b['end_week']} | {', '.join(b['tasks'])} |")
    md.append("\n**RACI**\n")
    md.append("| Stakeholder | " + " | ".join(exec_raci["workstreams"]) + " |")
    md.append("|---|" + "---|" * len(exec_raci["workstreams"]))
    for row in exec_raci["rows"]:
        md.append(f"| {row['stakeholder']} | " + " | ".join(row["assignments"][w] for w in exec_raci["workstreams"]) + " |")
    md.append("")
    h.append(_det_open(13, "CX Execution Work Plan", _PHASE_ICONS["deploy"], phase="deploy", open_count=1)
             + _render_work_plan(exec_plan, exec_raci) + _DET_CLOSE)

    # 14. Develop Closed Loop Model (Test-Measure-Learn)
    tml = ctx["test_measure_learn"]
    md.append("## 14. Develop Closed Loop Model — Test-Measure-Learn (Sheets 11 & 13)\n")
    md.append("| Test | Objective | Channels | Measure | What good looks like | What we'll learn |")
    md.append("|---|---|---|---|---|---|")
    for r in tml["rows"]:
        md.append(f"| {r['test']} | {r['objective']} | {r['channels']} | {r['measure']} | {r['what_good_looks_like']} | {r['what_we_will_learn']} |")
    md.append("")
    h.append(_det_open(14, "Develop Closed Loop Model", _PHASE_ICONS["deploy"], phase="deploy")
             + _render_tml(tml) + _DET_CLOSE)

    # =========================== SUPPORTING ANALYSIS ============================ #
    h.append("<div class='tk-phase-banner tk-support'>Supporting analysis</div>")
    md.append("---\n\n# Supporting analysis\n")

    # 15. Market & landscape
    md.append("## 15. Market & landscape\n")
    h.append(_det_open(15, "Market & landscape", "travel_explore"))
    src_labels = {"clinicaltrials": "ClinicalTrials.gov", "pubmed": "PubMed", "openfda": "openFDA",
                  "dailymed": "DailyMed", "google_trends": "Google Trends"}
    for scope, label in [("brand", brand), ("therapy_area", ta)]:
        section = ctx["market"].get(scope, {})
        md.append(f"**{label}**\n")
        h.append(f"<h3 class='plan-sec-sub'>{_esc(label)}</h3>")
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
    h.append(_DET_CLOSE)

    # 16. Competitive analysis
    md.append("## 16. Competitive analysis\n")
    h.append(_det_open(16, "Competitive analysis", "balance"))
    if swot:
        quadrants = [("strengths", "Strengths", "s-strength", "trending_up"),
                     ("weaknesses", "Weaknesses", "s-weak", "trending_down"),
                     ("opportunities", "Opportunities", "s-opp", "emoji_objects"),
                     ("threats", "Threats", "s-threat", "warning")]
        for key, title in [(k, t) for k, t, _, _ in quadrants]:
            md.append(f"**{title}**")
            for it in swot["swot"][key]:
                md.append(f"- {it}")
            md.append("")
        h.append("<div class='plan-swot-grid'>" + "".join(
            f"<div class='plan-swot-cell {cls}'><h3>{_icon(ic)}{_esc(title)}</h3><ul>"
            + "".join(f"<li>{_esc(it)}</li>" for it in swot["swot"][key]) + "</ul></div>"
            for key, title, cls, ic in quadrants
        ) + "</div>")
        rows = swot["positioning_table"]
        metrics = [("FDA labels", "fda_label_count"), ("Active trials", "trials_active"),
                   ("Completed trials", "trials_completed"), ("Stopped trials", "trials_stopped"),
                   ("PubMed (2yr)", "pubmed_recent_2yr"), ("Trends interest", "trends_avg_interest")]
        header = "| Metric | " + " | ".join(f"{r['brand']}{' (target)' if i == 0 else ''}" for i, r in enumerate(rows)) + " |"
        md.append("**Positioning table**\n")
        md.append(header)
        md.append("|" + "---|" * (len(rows) + 1))
        thead = "<tr><th>Metric</th>" + "".join(f"<th>{_esc(r['brand'])}{' (target)' if i == 0 else ''}</th>" for i, r in enumerate(rows)) + "</tr>"
        tbody = ""
        for mlabel, mkey in metrics:
            vals = [(f"{r.get(mkey):.1f}" if isinstance(r.get(mkey), float) else (r.get(mkey) if r.get(mkey) is not None else "—")) for r in rows]
            md.append(f"| {mlabel} | " + " | ".join(str(v) for v in vals) + " |")
            tbody += f"<tr><td>{mlabel}</td>" + "".join(f"<td>{_esc(v)}</td>" for v in vals) + "</tr>"
        md.append("")
        h.append(f"<h3 class='plan-sec-sub'>Positioning table</h3><table class='plan-table'>{thead}{tbody}</table>")
    else:
        md.append("_No distinct competitors were found in public trial data; competitive analysis skipped._\n")
        h.append("<p class='plan-empty'>No distinct competitors found in public trial data — competitive analysis skipped.</p>")
    h.append(_DET_CLOSE)

    # 17. Positioning
    md.append("## 17. Positioning\n")
    md.append(f"> {pos['positioning_statement']}\n")
    md.append("**Alternative messaging angles**")
    for a in pos["alternative_angles"]:
        md.append(f"- {a}")
    md.append("\n**Target audience notes**")
    for a in pos["target_audience_notes"]:
        md.append(f"- {a}")
    md.append("")
    h.append(_det_open(17, "Positioning", "track_changes")
             + f"<blockquote class='plan-statement'>{_esc(pos['positioning_statement'])}</blockquote>"
             "<h3 class='plan-sec-sub'>Alternative messaging angles</h3><ul>"
             + "".join(f"<li>{_esc(a)}</li>" for a in pos["alternative_angles"]) + "</ul>"
             "<h3 class='plan-sec-sub'>Target audience notes</h3><ul>"
             + "".join(f"<li>{_esc(a)}</li>" for a in pos["target_audience_notes"]) + "</ul>" + _DET_CLOSE)

    # 18. Journey & messaging (BAM)
    md.append("## 18. Journey & messaging (BAM)\n")
    md.append(f"- **Mental state:** {sp['mental_state']}\n- **Core barrier:** {sp['core_barrier']}\n"
              f"- **Engagement goal:** {sp['engagement_goal']}\n- **Promotion signal:** {sp['promotion_signal']}\n")
    md.append(f"**A→B shift:** {bam['a_to_b_shift']}\n")
    md.append(f"**Current → desired belief:** “{m['current_belief']}” → “{m['desired_belief']}”\n")
    md.append(f"**Proof points:** {', '.join(m['proof_points'])}\n")
    md.append(f"**Tone/format constraint:** {m['tone_constraint']}\n")
    md.append("**Recommended touchpoints**")
    for ch, tps in strat["recommended_touchpoints"].items():
        md.append(f"- {ch}: {', '.join(tps)}")
    md.append("")
    h.append(_det_open(18, "Journey & messaging (BAM)", "route")
             + "<table class='plan-kv'>"
             + "".join(f"<tr><th>{k}</th><td>{_esc(v)}</td></tr>" for k, v in [
                 ("Mental state", sp["mental_state"]), ("Core barrier", sp["core_barrier"]),
                 ("Engagement goal", sp["engagement_goal"]), ("Promotion signal", sp["promotion_signal"])])
             + "</table>"
             f"<p><strong>A→B shift:</strong> {_esc(bam['a_to_b_shift'])}</p>"
             f"<p><strong>Current → desired belief:</strong> “{_esc(m['current_belief'])}” → “{_esc(m['desired_belief'])}”</p>"
             f"<p><strong>Proof points:</strong> {_esc(', '.join(m['proof_points']))}</p>"
             f"<p><strong>Tone/format:</strong> {_esc(m['tone_constraint'])}</p>"
             "<h3 class='plan-sec-sub'>Recommended touchpoints</h3><ul>"
             + "".join(f"<li><strong>{_esc(ch)}:</strong> {_esc(', '.join(tps))}</li>"
                       for ch, tps in strat["recommended_touchpoints"].items())
             + "</ul>" + _DET_CLOSE)

    # 19. Precedent campaigns
    md.append("## 19. Precedent campaigns (inspiration)\n")
    h.append(_det_open(19, "Precedent campaigns (inspiration)", "emoji_events"))
    if precedents:
        note = ("" if any(p["matched"] for p in precedents) else
                "_No award-winning campaign in the archive matched this therapy area — showing the most recent winners instead._\n")
        md.append(note)
        for p in precedents:
            md.append(f"- **\"{p['title']}\"** — {p['tier']} · {p['category']} · {p['agency_sponsor']} "
                      f"([{p['program']} {p['year']}]({p['url']}))")
        h.append((f"<p class='plan-caveat'>{_esc(note.strip('_').strip())}</p>" if note else "")
                 + "".join(
                     f"<div class='plan-precedent-card'>"
                     f"<div class='pc-title'>&ldquo;{_esc(p['title'])}&rdquo; "
                     f"<span class='tier-badge {_TIER_CLASS.get(p['tier'], 'tier-bronze')}'>{_esc(p['tier'])}</span></div>"
                     f"<div class='pc-meta'>{_esc(p['category'])} · {_esc(p['agency_sponsor'])} · "
                     f"<a href='{_esc(p['url'])}' target='_blank'>{_esc(p['program'])} {p['year']}</a></div>"
                     f"</div>"
                     for p in precedents))
        md.append("\n_Real award-winning campaign entries (PM360 Pharma Choice / Trailblazer) — creative-direction "
                  "inspiration, not a competitive benchmark. Visual creative assets are not included (source pages "
                  "block automated access)._\n")
        h.append("<p class='plan-caveat'>Real award-winning campaign entries — creative-direction inspiration, not a "
                 "competitive benchmark. Visual creative assets are not included (source pages block automated access).</p>")
    else:
        md.append("_No award-winning campaigns indexed yet — run scrapers/awards.py to seed the archive._\n")
        h.append("<p class='plan-empty'>No award-winning campaigns indexed yet.</p>")
    # Curated, festival-grounded award campaigns matched to this brand/therapy area/client.
    awards = ctx.get("award_campaigns") or []
    if awards:
        md.append("\n**Award-winning campaigns to learn from** (why they won · the message · the creative)\n")
        for a in awards:
            md.append(f"- **{a['title']}** — {a['award']} ({a['festival']} {a['year']}, {a['agency']}) · "
                      f"match: {a['match']}. *Why:* {a['why_awarded']} *Message:* {a['key_message']} "
                      f"*Creative:* {a['creative_summary']}")
        h.append(_render_award_campaigns(awards))
    h.append(_DET_CLOSE)

    # 20. Channel mix & budget
    md.append("## 20. Channel mix & budget\n")
    md.append("| Channel | Share | Budget |")
    md.append("|---|---|---|")
    h.append(_det_open(20, "Channel mix & budget", "payments"))
    bars = ""
    for ch, v in sorted(budget_alloc.items(), key=lambda kv: -kv[1]["pct"]):
        amt = f"${int(v['amount']):,}" if v["amount"] else "—"
        md.append(f"| {ch} | {v['pct']}% | {amt} |")
        bars += (f"<div class='plan-bar-row'>{_icon(_CHANNEL_ICONS.get(ch, 'donut_small'))}"
                 f"<div class='plan-bar-label'>{_esc(ch)}</div>"
                 f"<div class='plan-bar-track'><div class='plan-bar-fill' style='width:{v['pct']}%'></div></div>"
                 f"<div class='plan-bar-val'>{v['pct']}% · {amt}</div></div>")
    md.append(f"\n*{strat['caveat']}*\n")
    h.append(bars + f"<p class='plan-caveat'>{_esc(strat['caveat'])}</p>" + _DET_CLOSE)

    # 21. KPI framework
    md.append("## 21. KPI framework\n")
    kpi_icons = {"Leading indicators": "trending_up", "Lagging indicators": "flag", "Operational KPIs": "settings"}
    h.append(_det_open(21, "KPI framework", "query_stats"))
    for title, items in [("Leading indicators", kpi["leading_indicators"]),
                         ("Lagging indicators", kpi["lagging_indicators"]),
                         ("Operational KPIs", kpi["operational_kpis"])]:
        md.append(f"**{title}**")
        for it in items:
            md.append(f"- {it}")
        md.append("")
        h.append(f"<h3 class='plan-sec-sub'>{_icon(kpi_icons[title])}{_esc(title)}</h3><ul>"
                 + "".join(f"<li>{_esc(it)}</li>" for it in items) + "</ul>")
    md.append(f"*Review cadence:* {kpi['cadence_note']}\n")
    h.append(f"<p class='plan-caveat'>Review cadence: {_esc(kpi['cadence_note'])}</p>" + _DET_CLOSE)

    # 22. Risk & governance
    md.append("## 22. Risk & governance\n")
    md.append("**Standard risk checklist**")
    for r in STANDARD_RISKS:
        md.append(f"- {r}")
    md.append("\n**Governance cadence**")
    for k, v in GOVERNANCE_CADENCE.items():
        md.append(f"- **{k}:** {v}")
    md.append("")
    h.append(_det_open(22, "Risk & governance", "gpp_maybe")
             + "<h3 class='plan-sec-sub'>Standard risk checklist</h3><ul>"
             + "".join(f"<li>{_esc(r)}</li>" for r in STANDARD_RISKS) + "</ul>"
             "<h3 class='plan-sec-sub'>Governance cadence</h3><ul>"
             + "".join(f"<li><strong>{_esc(k)}:</strong> {_esc(v)}</li>" for k, v in GOVERNANCE_CADENCE.items())
             + "</ul>" + _DET_CLOSE)

    # 23. Caveats
    caveat = ("This plan is generated from public/licensed data proxies and a rules-based framework. Channel-mix "
              "percentages are an illustrative starting allocation (not measured MMx output); SWOT/positioning derive "
              "from public-data proxies; persona and competitors were auto-inferred. Toolkit templates are rendered "
              "with every unanswerable cell flagged 'Needs alignment' rather than guessed. Treat as a first draft "
              "for brand-team and MLR review, not a final approved plan.")
    md.append("## 23. Caveats & data provenance\n\n" + caveat + "\n")
    h.append(_det_open(23, "Caveats & data provenance", "fact_check")
             + f"<p class='plan-caveat'>{_esc(caveat)}</p>" + _DET_CLOSE)

    return "\n".join(md), "".join(h)
