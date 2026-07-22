"""Sequential Plan Studio — the section-by-section run engine (SSE protocol v2).

The plan is assembled ONE section at a time (docs/SEQUENTIAL_STUDIO_DESIGN.md):
each section phase opens with its owner agent, shows what it pulled from the
knowledge graph, asks at most one GROUNDED question (recommendation + options,
never a blank box), and only then drafts and emits that section's HTML. The
stream ENDS at every ask — `record_answer` + a fresh stream resume the phase —
so a refresh or reconnect always resumes mid-run, never restarts it.

Section names never leak ahead of their phase: `run_open` carries a count only.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import decision_spine  # noqa: E402  (SME-grounded stage registry + extra asks + decision records)
import llm_decisioning  # noqa: E402  (Foundry + Cognee question/brief synthesis)
import plan_document  # noqa: E402  (renders one section via its _SECTION_TABLE entry)
from orchestrator import AGENT_ROSTER, compute_plan_ctx  # noqa: E402
from segment_profile import build_segment_profile, build_tcg_template  # noqa: E402

# ------------------------------------------------------------------ #
# The build sequence: the 11 toolkit sections, in document order.
# ask=None => a 0-ask section (grounding -> draft directly): the rhythm
# should breathe, not interrogate. topics = process-graph topics whose
# grounding renders as provenance chips when the phase opens.
# ------------------------------------------------------------------ #
SEQUENCE = [
    {"num": 4,  "id": "tcg",       "owner": "strategy",    "topics": ["segmentation_targeting"], "ask": "audience"},
    {"num": 5,  "id": "cxq",       "owner": "planner",     "topics": ["intake_context"],         "ask": "objective"},
    {"num": 6,  "id": "feas",      "owner": "strategy",    "topics": ["journey_messaging"],      "ask": None},
    {"num": 7,  "id": "msgflow",   "owner": "strategy",    "topics": ["journey_messaging", "competitive_positioning"], "ask": "message"},
    {"num": 8,  "id": "channels",  "owner": "activation",  "topics": ["channel_budget"],         "ask": "channel"},
    {"num": 9,  "id": "content",   "owner": "inspiration", "topics": ["creative_content"],       "ask": None},
    {"num": 10, "id": "chflow",    "owner": "inspiration", "topics": ["journey_messaging"],      "ask": None},
    {"num": 11, "id": "dmf",       "owner": "inspiration", "topics": ["creative_content"],       "ask": None},
    {"num": 12, "id": "metrics",   "owner": "activation",  "topics": ["measurement_kpi"],        "ask": None},
    {"num": 13, "id": "workplan",  "owner": "activation",  "topics": ["channel_budget"],         "ask": "timeline"},
    {"num": 14, "id": "tml",       "owner": "activation",  "topics": ["measurement_kpi"],        "ask": None},
    # §26-33: Tactical Plan + Campaign Brief -- turns the strategy above into field, channel,
    # scientific, account and measurement tactics, optionally grounded in an uploaded
    # strategic-plan document (ctx["strategic_source"]). All 0-ask for this first pass.
    {"num": 26, "id": "tacoverview", "owner": "planner",   "topics": ["intake_context"],          "ask": None},
    {"num": 27, "id": "tacfield",    "owner": "strategy",  "topics": ["segmentation_targeting"],  "ask": None},
    {"num": 28, "id": "tacomni",     "owner": "activation", "topics": ["channel_budget"],          "ask": None},
    {"num": 29, "id": "tacsci",      "owner": "intel",     "topics": ["market_landscape", "competitive_positioning"], "ask": None},
    {"num": 30, "id": "tacaccount",  "owner": "strategy",  "topics": ["segmentation_targeting"],  "ask": None},
    {"num": 31, "id": "tacpatient",  "owner": "planner",   "topics": ["risk_governance"],          "ask": None},
    {"num": 32, "id": "tacmeasure",  "owner": "activation", "topics": ["measurement_kpi", "risk_governance"], "ask": None},
    {"num": 33, "id": "tacbrief",    "owner": "planner",   "topics": ["intake_context"],           "ask": None},
]

_SECTION_BY_NUM = {e[1]: e for e in plan_document._SECTION_TABLE if e[0] == "sec"}
_AGENT_NAME = {a["id"]: a["name"] for a in AGENT_ROSTER}


def section_title(num: int) -> str:
    return _SECTION_BY_NUM[num][2]


# ------------------------------------------------------------------ #
# Grounding chips: what the owner agent visibly pulled before speaking.
# ------------------------------------------------------------------ #
_TOPIC_LABEL = {
    "intake_context": "intake & context",
    "risk_governance": "risk & governance",
    "market_landscape": "market landscape",
    "segmentation_targeting": "segmentation & targeting",
    "journey_messaging": "journey & messaging",
    "competitive_positioning": "competitive positioning",
    "creative_content": "creative & content",
    "channel_budget": "channel & budget",
    "measurement_kpi": "measurement & KPI",
}


def _clip(value: str, limit: int = 140) -> str:
    value = " ".join(str(value or "").split())
    return value[: limit - 1].rstrip() + "..." if len(value) > limit else value


def _brief(ctx: dict) -> dict:
    return ctx.get("brief") or ctx.get("slots") or {}


def _strategic_source(ctx: dict) -> dict:
    return ctx.get("strategic_source") or {}


def _source_name(ctx: dict) -> str:
    src = _strategic_source(ctx)
    return src.get("source_name") or "provided strategic brief"


def _brief_field(ctx: dict, key: str) -> str:
    return str((_brief(ctx).get(key) or "")).strip()


def _strategic_items(ctx: dict, *keys: str, limit: int = 2) -> list[str]:
    src = _strategic_source(ctx)
    out: list[str] = []
    for key in keys:
        value = src.get(key)
        if isinstance(value, list):
            out.extend(str(v).strip() for v in value if str(v or "").strip())
        elif value:
            out.append(str(value).strip())
    return [_clip(v, 120) for v in out[:limit]]


def _brief_context_line(ctx: dict) -> str:
    captured = []
    for key, label in (
        ("audience", "audience"),
        ("objective", "objective"),
        ("kpi", "KPI"),
        ("preferred_channels", "channels"),
        ("duration", "timing"),
        ("constraints", "constraints"),
        ("reason", "why now"),
    ):
        value = _brief_field(ctx, key)
        if value:
            captured.append(f"{label}: {_clip(value, 70)}")
    src = _strategic_source(ctx)
    if src.get("has_content"):
        strategic = _strategic_items(ctx, "positioning", "csfs", "guardrails", "evidence", limit=2)
        if strategic:
            captured.append(f"{_source_name(ctx)}: {' | '.join(strategic)}")
    return "Captured brief context: " + " | ".join(captured[:4]) if captured else ""


def _basis(ctx: dict, fallback: str, direct_key: str | None = None,
           strategic_keys: tuple[str, ...] = ()) -> str:
    direct = _brief_field(ctx, direct_key) if direct_key else ""
    if direct:
        return f"Brief-provided: {direct_key} = {_clip(direct, 110)}."
    strategic = _strategic_items(ctx, *strategic_keys, limit=2) if strategic_keys else []
    if strategic:
        return f"Strategic-source supported from {_source_name(ctx)}: {' | '.join(strategic)}."
    return fallback


def grounding_items(ctx: dict, step: dict) -> list[dict]:
    items = []
    pg = ctx.get("process_grounding") or {}
    for topic in step["topics"]:
        g = pg.get(topic)
        if g:
            snippet = g["guidance"].replace("\n", " ").strip()
            items.append({"source": "Omni OS process graph", "label": _TOPIC_LABEL.get(topic, topic),
                          "snippet": snippet[:240] + ("…" if len(snippet) > 240 else "")})
    if step["id"] == "tcg" and (ctx.get("audience_profile") or {}).get("audience_size", {}).get("total"):
        items.append({"source": "industry benchmark", "label": "audience sizing",
                      "snippet": ctx["audience_profile"]["headline"]})
    if step["id"] == "tcg" and ctx.get("hcp_360_grounding"):
        g = ctx["hcp_360_grounding"]
        items.append({"source": "HCP 360 panel", "label": "measured segmentation",
                      "snippet": f"{g['headline']} ({g['confidence']})"})
    if step["id"] == "channels" and ctx.get("strategy"):
        mix = ctx["strategy"].get("channel_mix_pct") or {}
        if mix:
            top = sorted(mix.items(), key=lambda kv: -kv[1])[:3]
            items.append({"source": "engagement benchmarks", "label": "channel affinity",
                          "snippet": " · ".join(f"{k} {v}%" for k, v in top)})
    if ctx.get("brand_kit"):
        kit = ctx["brand_kit"]
        if step["id"] in ("msgflow", "content", "dmf"):
            items.append({"source": kit.get("source_label", "brand intelligence hub"), "label": "brand kit",
                          "snippet": f"core claim — “{kit.get('core_claim', '')}”"})
    src = ctx.get("strategic_source") or {}
    if src.get("has_content"):
        snippets = (src.get("csfs") or [])[:1] + (src.get("evidence") or [])[:1] + (src.get("guardrails") or [])[:1]
        if snippets:
            items.append({"source": src.get("source_name") or "uploaded strategic plan",
                          "label": "uploaded strategic plan",
                          "snippet": " · ".join(snippets)[:240]})
    if step["id"] == "tcg":
        for d in (ctx.get("external_evidence") or [])[:1]:
            items.append({"source": d["source"], "label": d["label"], "snippet": f"{d['value']} (as of {d['as_of']})"})
    # Tactical Plan steps: surface what was pulled from an uploaded strategic-plan document,
    # when one was attached. Absent (or empty) when no document was uploaded -- those steps
    # ground purely in the process-graph topics above instead.
    return items


def _grounded_question_prefix(ctx: dict, step: dict, max_items: int = 2) -> str:
    """Short SME grounding lead-in for a question prompt."""
    brief_line = _brief_context_line(ctx)
    items = grounding_items(ctx, step)
    if not items:
        return f"{brief_line} " if brief_line else ""
    parts = []
    for item in items[:max_items]:
        label = item["label"]
        snippet = item["snippet"].strip()
        if len(snippet) > 120:
            snippet = snippet[:119].rstrip() + "..."
        parts.append(f"{label}: {snippet}")
    prefix = "SME grounding: " + " | ".join(parts)
    if brief_line:
        prefix = f"{brief_line} {prefix}"
    return prefix + " "


def _attach_grounding_to_ask(ctx: dict, step: dict, ask: dict | None) -> dict | None:
    if not ask:
        return None
    # Draft asks are only a grounded scaffold for the LLM. Final status/source is set by
    # llm_decisioning.refine_studio_ask(): source=ai on success, deterministic-fallback
    # with exact diagnostics on failure.
    ask.setdefault("source", "draft")
    return ask


# ------------------------------------------------------------------ #
# Grounded asks: recommendation-first, options from real ctx data.
# ------------------------------------------------------------------ #
def build_ask(ctx: dict, step: dict) -> dict | None:
    return _build_ask_llm_first(ctx, step)


def _build_ask_draft(ctx: dict, step: dict) -> dict | None:
    kind = step["ask"]
    if not kind:
        # Spine-added asks (program placement / compliance envelope / deliverables spec) ???
        # derive-first: returns None whenever ctx already answers it (decision_spine).
        return _attach_grounding_to_ask(ctx, step, decision_spine.spine_ask_extras(ctx, step))
    inferred = ctx.get("inferred") or {}
    if kind == "audience":
        rec = _brief_field(ctx, "audience") or inferred.get("persona", "")
        alts = [s for s in ("Evidence-driven skeptics", "Guideline followers", "Digital-first early adopters",
                            "Relationship-led traditionalists") if s.lower() != rec.lower()][:2]
        return _attach_grounding_to_ask(ctx, step, {"ask_id": f"ask-{step['num']}", "section": step["num"],
                "question_focus": "Confirm the target audience and eligibility rules for the plan.",
                "text": "",
                "evidence_basis": _basis(ctx,
                    "Directional default from lifecycle-stage segment map, audience benchmark, and SME process grounding.",
                    "audience", ("csfs", "positioning")),
                "why": "This is the audience lock: it drives eligibility, message ladder, channel weighting and flow defaults.",
                "recommendation": {"label": rec, "source": "brief audience if provided; otherwise lifecycle-stage segment map"},
                "options": [{"label": a, "source": "segment-library alternative; not brief-provided"} for a in alts],
                "free_text": True})
    if kind == "objective":
        bam = ctx.get("bam") or {}
        positioning = _strategic_source(ctx).get("positioning")
        if isinstance(positioning, list):
            positioning = next((str(v).strip() for v in positioning if str(v or "").strip()), "")
        rec = (_brief_field(ctx, "objective") or positioning
               or bam.get("a_to_b_shift") or "Shift awareness into confident first use").strip()
        options = []
        if bam.get("a_to_b_shift") and bam.get("a_to_b_shift") != rec:
            options.append({"label": bam["a_to_b_shift"], "source": "BAM framework default"})
        for c in _strategic_items(ctx, "csfs", limit=2):
            if c.lower() != rec.lower():
                options.append({"label": c, "source": f"CSF from {_source_name(ctx)}"})
        return _attach_grounding_to_ask(ctx, step, {"ask_id": f"ask-{step['num']}", "section": step["num"],
                "question_focus": "Choose the CX objective / north star that every KPI and tactic should trace back to.",
                "text": "",
                "evidence_basis": _basis(ctx,
                    "Directional BAM objective from lifecycle-stage rules and SME process grounding; validate with brand strategy.",
                    "objective", ("positioning", "csfs")),
                "why": "The CX Planning Questionnaire locks the objective; every KPI and downstream tactic traces back to it.",
                "recommendation": {"label": rec, "source": "brief objective or strategic source; fallback = BAM framework default"},
                "options": options[:3],
                "free_text": True})
    if kind == "message":
        kms = (ctx.get("message_flow") or {}).get("key_messages") or []
        if not kms:
            return None
        rec = kms[0]["topic"]
        alts = [k["topic"] for k in kms[1:3]]
        return _attach_grounding_to_ask(ctx, step, {"ask_id": f"ask-{step['num']}", "section": step["num"],
                "question_focus": "Pick the lead message rung for the ladder.",
                "text": "",
                "evidence_basis": _basis(ctx,
                    "Directional message-flow default from journey stage; brand-kit claims are used when available.",
                    None, ("evidence", "positioning", "csfs")),
                "why": "The first rung sets the tone of every asset; the rest of the ladder sequences behind it.",
                "recommendation": {"label": rec, "source": "message-flow model" +
                                   (" + brand-kit claim library" if ctx.get("brand_kit") else "")},
                "options": [{"label": a, "source": "next available message-flow topic"} for a in alts],
                "free_text": True})
    if kind == "channel":
        mix = (ctx.get("strategy") or {}).get("channel_mix_pct") or {}
        if not mix:
            return None
        ranked = sorted(mix.items(), key=lambda kv: -kv[1])
        preferred = _brief_field(ctx, "preferred_channels")
        rec = preferred if preferred else f"{ranked[0][0]}-led mix ({ranked[0][1]}%)"
        alts = [f"{k}-led mix ({v}%)" for k, v in ranked[1:3]]
        return _attach_grounding_to_ask(ctx, step, {"ask_id": f"ask-{step['num']}", "section": step["num"],
                "question_focus": "Set the anchor channel and budget split for the journey.",
                "text": "",
                "evidence_basis": _basis(ctx,
                    "Directional channel-affinity mix from lifecycle/persona framework; replace with brand media plan if available.",
                    "preferred_channels", ("csfs", "guardrails")),
                "why": "The anchor channel takes the largest budget share and sets the cadence guardrails.",
                "recommendation": {"label": rec, "source": "brief channel preference if provided; otherwise channel-affinity model"},
                "options": [{"label": a, "source": "channel-affinity model alternative"} for a in alts],
                "free_text": True})
    if kind == "timeline":
        duration = _brief_field(ctx, "duration")
        rec = duration if duration else "13-week standard wave"
        options = [] if duration else [{"label": "Compressed 9-week wave", "source": "execution model trade-off"}]
        return _attach_grounding_to_ask(ctx, step, {"ask_id": f"ask-{step['num']}", "section": step["num"],
                "question_focus": "Confirm the execution window and whether there is a hard launch date.",
                "text": "",
                "evidence_basis": _basis(ctx,
                    "Default execution wave from the work-plan model; confirm against launch date and MLR capacity.",
                    "duration", ("guardrails", "csfs")),
                "why": "The work plan's bands and the MLR buffer are laid out against this window.",
                "recommendation": {"label": rec, "source": "brief timing if provided; otherwise execution work-plan model"},
                "options": options, "free_text": True})
    return None


def _build_ask_llm_first(ctx: dict, step: dict) -> dict | None:
    draft = _build_ask_draft(ctx, step)
    if not draft:
        return None
    return llm_decisioning.refine_studio_ask(ctx, step, draft)


def apply_answer(ctx: dict, step: dict, value: str) -> str:

    """Fold an answer into ctx before the section drafts. Returns a short note describing
    what changed (used in the drafting event). Deep recompute only where it is safe."""
    note = f"using your call — “{value}”"
    ctx.setdefault("studio_answers", {})[step["id"]] = value
    if step["id"] == "tcg":
        rec = (ctx.get("inferred") or {}).get("persona", "")
        if value and rec and value.strip().lower() != rec.strip().lower():
            try:  # re-aim the segment profile + TCG at the chosen group
                ctx["inferred"]["persona"] = value.strip()
                sp = build_segment_profile(value.strip(), ctx["inferred"]["stage_key"])
                ctx["segment_profile"] = sp
                ctx["tcg"] = build_tcg_template(value.strip(), sp, ctx.get("strategy") or {}, ctx.get("bam") or {},
                                                agent_answers=(ctx.get("audience_profile") or {}).get("answers"),
                                                agent_name="Market & Competitive Intelligence")
                note = f"re-aimed the customer group at “{value.strip()}” and rebuilt the profile"
            except Exception:  # noqa: BLE001 — fall back to recording the preference
                pass
    return note


# ------------------------------------------------------------------ #
# Per-section chat lines (handoff + landed banter), grounded in ctx.
# ------------------------------------------------------------------ #
def handoff_chat(ctx: dict, step: dict, idx: int) -> dict:
    # No hand-off to a named sub-agent: one agent, addressing the human directly.
    title = section_title(step["num"])
    return {"type": "chat", "author": "planner", "kind": "turn", "reply_to": "",
            "text": f"Section {idx + 1} — **{title}**."}


def landed_banter(ctx: dict, step: dict) -> dict | None:
    inferred = ctx.get("inferred") or {}
    lines = {
        "tcg": ("intel", f"That group sizes at {ctx.get('audience_profile', {}).get('headline', 'a defined audience')} — "
                         "worth every downstream dollar being aimed at it."),
        "channels": ("strategy", "With that anchor set I'll keep the message ladder's first rung native to it."),
        "msgflow": ("activation", "Ladder locked — I'll sequence the channel cadence to hit rung one first."),
        "workplan": ("planner", "Bands are on the timeline with the MLR buffer honoured — reporting lands after wave one."),
    }
    pair = lines.get(step["id"])
    if not pair:
        return None
    return {"type": "chat", "author": pair[0], "kind": "banter", "reply_to": step["owner"], "text": pair[1]}


# ------------------------------------------------------------------ #
# Single-section render: one _SECTION_TABLE entry -> html fragment.
# ------------------------------------------------------------------ #
def compose_section(ctx: dict, num: int) -> tuple[str, str]:
    entry = _SECTION_BY_NUM[num]
    _, _, title, icon, phase, owner, ready, fn, skip = entry
    md: list[str] = []
    h: list[str] = []
    if not ready(ctx):
        return "", ""
    fn(ctx, md, h, plan_document._R(fresh=True))
    return "\n".join(md), "".join(h)


# ------------------------------------------------------------------ #
# The stream: continues from state["studio"]["idx"], ends at every ask.
# ------------------------------------------------------------------ #
def stream(ctx: dict, studio: dict):
    """Yields v2 events from the current cursor. Mutates `studio` (the caller persists it).
    studio = {"idx": int, "answers": {section_id: str}, "await_ask": dict | None}"""
    total = len(SEQUENCE)
    yield {"type": "run_open", "total_sections": total}

    while studio["idx"] < total:
        idx = studio["idx"]
        step = SEQUENCE[idx]
        title = section_title(step["num"])

        # phase_open + grounding are idempotent (a reconnected client rebuilds its
        # canvas slot from them); the handoff chat line is emitted exactly once.
        yield {"type": "phase_open", "idx": idx, "section_id": step["id"], "num": step["num"],
               "title": title, "owner": step["owner"], "owner_name": _AGENT_NAME[step["owner"]]}
        if studio.get("opened_num") != step["num"]:
            studio["opened_num"] = step["num"]
            yield handoff_chat(ctx, step, idx)
        yield {"type": "grounding", "section_id": step["id"], "items": grounding_items(ctx, step)}
        ask = build_ask(ctx, step)
        if ask:  # every ask names its spine framework + what it unblocks (why-chip data)
            stage = decision_spine.stage_for(step["id"])
            if stage:
                ask.setdefault("framework", stage["framework"]["name"])
                ask.setdefault("blocked", " · ".join(stage["feeds"]))
        if ask and step["id"] not in studio["answers"]:
            # Unanswered ask: (re-)pose it and end the stream. A reconnect lands
            # right back here, so a refresh can never skip a gate.
            studio["await_ask"] = ask
            yield {"type": "ask", **ask}
            return
        # Answered (or no ask): draft and emit.
        note = ""
        if step["id"] in studio["answers"]:
            note = apply_answer(ctx, step, studio["answers"][step["id"]])
        studio["await_ask"] = None
        yield {"type": "drafting", "section_id": step["id"],
               "note": (f"Drafting {title} — {note}." if note else f"Drafting {title} from the graph pull.")}
        md, html = compose_section(ctx, step["num"])
        yield {"type": "section_html", "section_id": step["id"], "num": step["num"], "title": title,
               "owner": step["owner"], "html": html}
        # Decision record: the landed step explains itself — inputs, framework, decision,
        # rationale, what it feeds. Accumulated in ctx (campaign_artifacts re-derives them
        # deterministically if this list is ever lost, so persistence is a bonus not a need).
        record = decision_spine.build_decision_record(ctx, step, studio["answers"].get(step["id"]))
        if record:
            ctx.setdefault("decision_records", [])
            if not any(r.get("stage_id") == record["stage_id"] for r in ctx["decision_records"]):
                ctx["decision_records"].append(record)
            yield record
        banter = landed_banter(ctx, step)
        if banter:
            yield banter
        yield {"type": "phase_done", "section_id": step["id"], "idx": idx}
        studio["idx"] = idx + 1

    # All sections landed: the full document (incl. supporting analysis) exists now.
    md, html_out = plan_document.compose_plan(ctx)
    yield {"type": "chat", "author": "planner", "kind": "turn", "reply_to": "",
           "text": "That's every section — the full Brand Engagement Plan is assembled, including the "
                   "supporting analysis. Exports are live; persona pressure-testing is available whenever you want it."}
    yield {"type": "plan", "html": html_out, "markdown": md, "partial": False}
    yield {"type": "run_done"}
