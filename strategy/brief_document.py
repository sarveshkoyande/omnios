"""The Campaign Brief as markdown, so it can leave the browser as a .docx or .pdf.

Markdown rather than HTML for the same reason plan_export.py takes markdown: it is the one
source both converters (`plan_export.markdown_to_docx` / `markdown_to_pdf`) parse
identically, so the two downloads stay consistent with each other. The shapes used here are
exactly the ones `plan_export._parse_blocks` understands — '#'..'####' headings, '- ' bullets,
'| a | b |' tables with a separator row, '---' rules — and nothing else.

The journey travels as a TABLE of steps, not as the Mermaid picture the web brief shows: the
markdown converters have no image block, and a Word reader is better served by a sortable
list of touchpoints than by a screenshot of a flowchart they cannot edit. The Mermaid source
is appended verbatim in the appendix so anyone can regenerate the picture.
"""
from __future__ import annotations


def _esc(value) -> str:
    """Table-cell safe: a literal '|' would open a new column and shear the row."""
    return " ".join(str(value if value is not None else "").split()).replace("|", "/")


def _rows(header: list[str], rows: list[list]) -> list[str]:
    if not rows:
        return []
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    out.extend("| " + " | ".join(_esc(c) for c in row) + " |" for row in rows)
    out.append("")
    return out


def _bullets(items) -> list[str]:
    return [f"- {_esc(i)}" for i in items if str(i or "").strip()] + [""]


def _section(title: str) -> list[str]:
    return [f"## {title}", ""]


def _volume(segment: dict) -> str:
    volume = segment.get("volume")
    if not volume:
        return "Size TBD"
    return f"{int(volume):,}" if segment.get("volume_exact") else f"~{int(volume):,}"


def _journey_lines(journey: dict, diagram: dict) -> list[str]:
    if not journey:
        return ["_No journey has been designed for this campaign yet._", ""]
    lines: list[str] = []
    if journey.get("summary"):
        lines += [_esc(journey["summary"]), ""]
    facts = []
    if journey.get("touchpoint_count"):
        facts.append(f"{journey['touchpoint_count']} touchpoints")
    if journey.get("duration_days"):
        facts.append(f"{journey['duration_days']}-day span")
    if facts:
        lines += [f"**{' · '.join(facts)}**", ""]
    if journey.get("entry"):
        lines += ["### Entry criteria", ""] + _bullets(journey["entry"])
    lines += ["### Journey steps", ""]
    lines += _rows(
        ["Day", "Step", "What happens", "Channel", "Detail"],
        [[s.get("day") if s.get("day") is not None else "—", s.get("kind_label"), s.get("label"),
          s.get("channel") or "—", s.get("detail") or "—"] for s in journey.get("steps") or []],
    )
    if journey.get("decision_logic"):
        lines += ["### Decision logic", ""]
        lines += _rows(["Condition", "Outcome"],
                       [[d.get("condition"), d.get("outcome")] for d in journey["decision_logic"]])
    if journey.get("operational_rules"):
        lines += ["### Operating rules", ""] + _bullets(journey["operational_rules"])
    if diagram.get("image_url"):
        lines += [f"Journey diagram (rendered): {diagram['image_url']}", ""]
    return lines


def brief_markdown(brief: dict, project_name: str = "") -> str:
    """Render a composed brief (campaign_artifacts.compose_brief) as export markdown."""
    header = brief.get("header") or {}
    snapshot = brief.get("snapshot") or {}
    audience = brief.get("audience") or {}
    comms = brief.get("comms_strategy") or {}
    channel_journey = brief.get("channel_journey") or {}
    measurement = brief.get("measurement_plan") or {}
    scope = brief.get("scope_review") or {}
    timeline = brief.get("timeline") or {}

    title = f"Campaign Brief — {header.get('brand') or project_name or 'Campaign'}"
    lines: list[str] = [f"# {title}", ""]
    tags = [t for t in (header.get("therapy_area"), header.get("lifecycle"),
                        f"v{brief.get('version', '1.0')}", brief.get("generated_at")) if t]
    if tags:
        lines += [" · ".join(_esc(t) for t in tags), ""]
    lines += ["---", ""]

    if snapshot:
        lines += _section("Snapshot")
        lines += _rows(["Field", "Value"], [
            [label, snapshot.get(key)] for label, key in [
                ("Campaign objective", "objective"), ("Brand", "brand"),
                ("Therapy area", "therapy_area"), ("Target audience", "target_audience"),
                ("Why this campaign", "reason"),
            ] if snapshot.get(key)
        ])

    purpose = brief.get("purpose") or {}
    lines += _section("Purpose")
    lines += [f"**{_esc(purpose.get('program_context'))}**", "", _esc(purpose.get("summary")), ""]
    if purpose.get("trigger_logic"):
        lines += ["### Trigger / entry logic", ""] + _bullets(purpose["trigger_logic"])

    objective = brief.get("objective") or {}
    lines += _section("Objective")
    if objective.get("pillar"):
        lines += [f"**Pillar:** {_esc(objective['pillar'])}", ""]
    lines += [_esc(objective.get("statement")), ""]
    if objective.get("leading_indicators"):
        lines += ["### Leading indicators", ""] + _bullets(objective["leading_indicators"])

    # The audience is the part of the brief the user personally locked at the planning ask —
    # it leads with the named segments and their measured panel sizes, never a persona label.
    lines += _section("Target audience & eligibility")
    if audience.get("segment"):
        lines += [f"**Selected segments:** {_esc(audience['segment'])}", ""]
    lines += _rows(["Segment", "Size", "Profile", "Key characteristics"],
                   [[s.get("name"), _volume(s), s.get("profile"),
                     ", ".join(s.get("key_characteristics") or []) or "—"]
                    for s in audience.get("segments") or []])
    if audience.get("eligibility_rules"):
        lines += ["### Eligibility rules", ""] + _bullets(audience["eligibility_rules"])
    if audience.get("consent_note"):
        lines += [_esc(audience["consent_note"]), ""]

    lines += _section("Communication strategy")
    for label, key in [("Belief shift", "belief_shift"), ("Core claim", "core_claim")]:
        if comms.get(key):
            lines += [f"**{label}:** {_esc(comms[key])}", ""]
    ladder = comms.get("message_detail") or []
    if ladder:
        lines += ["### Message ladder", ""]
        lines += _rows(["#", "Topic", "Supporting"],
                       [[i, m.get("topic"), "; ".join(m.get("supporting") or []) or "—"]
                        for i, m in enumerate(ladder, start=1)])
    elif comms.get("message_ladder"):
        lines += ["### Message ladder", ""] + _bullets(comms["message_ladder"])
    if comms.get("tone_guardrails"):
        lines += ["### Tone guardrails", ""] + _bullets(comms["tone_guardrails"])

    lines += _section("Deliverables")
    lines += _rows(["Asset", "Variants", "Notes"],
                   [[d.get("asset"), d.get("variants"), d.get("notes")]
                    for d in brief.get("deliverables") or []])

    lines += _section("Channel & journey")
    if channel_journey.get("anchor"):
        lines += [f"**Anchor:** {_esc(channel_journey['anchor'])}", ""]
    lines += _rows(["Channel", "Share"],
                   [[m.get("channel"), f"{m.get('pct')}%"] for m in channel_journey.get("mix") or []])
    lines += _journey_lines(channel_journey.get("journey") or {}, brief.get("journey_diagram") or {})
    if channel_journey.get("cadence_note"):
        lines += [_esc(channel_journey["cadence_note"]), ""]

    lines += _section("Measurement plan")
    lines += _bullets(measurement.get("kpis") or [])
    for key in ("link_matrix_note", "test_design"):
        if measurement.get(key):
            lines += [_esc(measurement[key]), ""]

    lines += _section("Scope & review assumptions")
    lines += [f"**{_esc(scope.get('ladder'))}**", ""]
    lines += _bullets([scope.get("rounds_note"), scope.get("change_control")])

    lines += _section("Risk register")
    lines += _rows(["Severity", "Risk", "Mitigation"],
                   [[r.get("severity"), r.get("risk"), r.get("mitigation")]
                    for r in brief.get("risk_register") or []])

    lines += _section("Assumptions & mandatories")
    lines += _bullets(brief.get("assumptions") or [])

    lines += _section("Timeline & approvals")
    lines += [f"**{_esc(timeline.get('window'))}** — {_esc(timeline.get('note'))}", ""]
    lines += _rows(["Role", "Owner"],
                   [[a.get("role"), a.get("name") or "unassigned"] for a in brief.get("approvals") or []])

    appendix = brief.get("technical_appendix") or {}
    lines += _section("Technical appendix")
    if appendix.get("review_and_pv"):
        lines += _bullets(appendix["review_and_pv"])
    if appendix.get("technical_decisions"):
        lines += _rows(["Stage", "Decision"],
                       [[d.get("stage_name"), d.get("decision")] for d in appendix["technical_decisions"]])
    traceability = brief.get("traceability") or []
    if traceability:
        lines += [("Traceability: every section above projects from a named decision record — "
                   + " · ".join(_esc(t.get("stage_id")) for t in traceability) + "."), ""]
    mermaid = (brief.get("journey_diagram") or {}).get("mermaid")
    if mermaid:
        # Verbatim, so the diagram can be regenerated from the document alone.
        lines += ["### Journey diagram source (Mermaid)", ""]
        lines += [line for line in mermaid.split("\n")]
        lines += [""]

    return "\n".join(lines)
