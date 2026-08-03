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
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import benchmarks  # noqa: E402  (addressable HCP universe sizing for segment evidence)
import brief_summary  # noqa: E402  (≤14-word gists so asks never echo the deck verbatim)
import channel_selection  # noqa: E402  (go-to-market postures + their MMx channel splits)
import decision_spine  # noqa: E402  (SME-grounded stage registry + extra asks + decision records)
import external_evidence  # noqa: E402  (live public-source datapoints, pulled per-section on demand)
import hcp_360  # noqa: E402  (dummy HCP 360 panel -- real segment sizing for the audience ask + brief)
import journey_design  # noqa: E402  (journey spec + SFMC-shaped flow built from the planner's answers)
import llm_decisioning  # noqa: E402  (Foundry + Cognee question/brief synthesis)
import plan_document  # noqa: E402  (renders one section via its _SECTION_TABLE entry)
import process_knowledge  # noqa: E402  (Cognee-backed SME process grounding, pulled per-section)
import message_flow as message_flow_mod  # noqa: E402  (brand-kit claim grounding for a rebuilt ladder)
from message_flow import build_message_flow  # noqa: E402  (rebuilds the ladder from the user's rung picks)
from orchestrator import AGENT_ROSTER, compute_plan_ctx  # noqa: E402
from segment_profile import build_segment_profile, build_tcg_template  # noqa: E402

# ------------------------------------------------------------------ #
# The build sequence: the 11 toolkit sections, in document order.
# ask=None => a 0-ask section (grounding -> draft directly): the rhythm
# should breathe, not interrogate. topics = process-graph topics whose
# grounding renders as provenance chips when the phase opens.
# ------------------------------------------------------------------ #
# `render: False` steps still run: they pose their ask, fold the answer into ctx and emit
# their decision record -- they just contribute no section to the plan document or the Plan
# sections list. That keeps the segmentation, objective and program-placement questions
# exactly where they belong while dropping the toolkit-template write-ups nobody reads.
SEQUENCE = [
    {"num": 4,  "id": "tcg",       "owner": "strategy",    "topics": ["segmentation_targeting"], "ask": "audience", "render": False},
    {"num": 5,  "id": "cxq",       "owner": "planner",     "topics": ["intake_context"],         "ask": "objective", "render": False},
    {"num": 6,  "id": "feas",      "owner": "strategy",    "topics": ["journey_messaging"],      "ask": None, "render": False},
    {"num": 7,  "id": "msgflow",   "owner": "strategy",    "topics": ["journey_messaging", "competitive_positioning"], "ask": "message"},
    {"num": 8,  "id": "channels",  "owner": "activation",  "topics": ["channel_budget"],         "ask": "channel"},
    {"num": 9,  "id": "content",   "owner": "inspiration", "topics": ["creative_content"],       "ask": None},
    {"num": 10, "id": "chflow",    "owner": "inspiration", "topics": ["journey_messaging"],      "ask": "journey"},
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
    {"num": 29, "id": "tacsci",      "owner": "intel",     "topics": ["market_landscape", "competitive_positioning"], "ask": None, "render": False},
    {"num": 30, "id": "tacaccount",  "owner": "strategy",  "topics": ["segmentation_targeting"],  "ask": None, "render": False},
    {"num": 31, "id": "tacpatient",  "owner": "planner",   "topics": ["risk_governance"],          "ask": None, "render": False},
    {"num": 32, "id": "tacmeasure",  "owner": "activation", "topics": ["measurement_kpi", "risk_governance"], "ask": None, "render": False},
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


# ------------------------------------------------------------------ #
# Lazy per-section grounding (+ prefetch during ask pauses).
#
# compute_plan_ctx(lazy_grounding=True) leaves process_grounding/external_evidence
# empty; each section's slice is pulled here the moment it opens, and the NEXT
# section's slice is warmed in a background thread while the user answers an ask.
# These module caches are keyed by (brand, therapy_area[, topic]) so they survive
# across the separate resume requests (ctx is reloaded from disk each resume, but
# this process-local cache is not) — no re-pull, no DB write race.
# ------------------------------------------------------------------ #
_GROUND_CACHE: dict[tuple, dict] = {}
_EXT_CACHE: dict[tuple, list] = {}


def _ground_topics(brand: str, therapy_area: str, topics: list[str]) -> dict:
    """Ground `topics` cache-first. Returns {topic: grounding-or-{}} for every requested topic
    (an empty {} marks 'grounded, nothing found' so it is never re-attempted)."""
    out: dict[str, dict] = {}
    missing: list[str] = []
    for t in topics:
        key = (brand, therapy_area, t)
        if key in _GROUND_CACHE:
            out[t] = _GROUND_CACHE[key]
        else:
            missing.append(t)
    if missing:
        try:
            got = process_knowledge.ground_all(brand, therapy_area, topics=missing)
        except Exception as exc:  # noqa: BLE001 - grounding must never break the run
            print(f"[studio] section grounding failed: {exc!r}")
            got = {}
        for t in missing:
            val = got.get(t) or {}
            _GROUND_CACHE[(brand, therapy_area, t)] = val
            out[t] = val
    return out


def _ground_external(brand: str, therapy_area: str) -> list:
    key = (brand, therapy_area)
    if key not in _EXT_CACHE:
        try:
            _EXT_CACHE[key] = external_evidence.datapoints(therapy_area, brand)
        except Exception as exc:  # noqa: BLE001
            print(f"[studio] external evidence pull failed: {exc!r}")
            _EXT_CACHE[key] = []
    return _EXT_CACHE[key]


def ensure_grounding(ctx: dict, step: dict) -> None:
    """Populate ctx grounding for THIS section only (cache-first) — the deferred slice of what
    compute_plan_ctx used to pull all at once."""
    if ctx.get("_core_only"):
        # First ask is posed from the fast core ctx — do NO grounding pulls here so it lands in
        # seconds; grounding fills once fill_plan_ctx completes and the section re-grounds on resume.
        return
    brand = ctx.get("brand", "") or ""
    ta = ctx.get("therapy_area", "") or ""
    pg = ctx.setdefault("process_grounding", {})
    needed = [t for t in step.get("topics", []) if t not in pg]
    if needed:
        pg.update(_ground_topics(brand, ta, needed))
    # Only the customer-group section surfaces live external evidence today; pull it there.
    if step["id"] == "tcg" and not ctx.get("external_evidence"):
        ctx["external_evidence"] = _ground_external(brand, ta)


def prefetch_grounding(brand: str, therapy_area: str, from_idx: int) -> None:
    """Warm the cache for `from_idx` (the section that drafts right after the answer) through the
    NEXT ask-bearing section — run in a background thread during an ask pause so the resume drafts
    and re-asks straight from cache instead of grounding on the critical path. Best-effort; writes
    only the process-local cache."""
    idx = from_idx
    while idx < len(SEQUENCE):
        step = SEQUENCE[idx]
        try:
            _ground_topics(brand, therapy_area, list(step.get("topics", [])))
            if step["id"] == "tcg":
                _ground_external(brand, therapy_area)
        except Exception as exc:  # noqa: BLE001 - prefetch is best-effort
            print(f"[studio] prefetch failed at idx {idx}: {exc!r}")
        # Ground the starting section even if it has an ask, then stop at the FOLLOWING ask.
        if idx > from_idx and step.get("ask"):
            break
        idx += 1


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
    # The step's SME process grounding already exists (grounding_items) but never reached
    # the ask, which is why recommendations read as generic AI suggestions: the documented
    # pharma workflow behind them was computed and then dropped. Lead the basis with it so
    # the question rests on how campaign teams actually work.
    items = grounding_items(ctx, step)
    if not items:
        return ask
    ask["grounding"] = items
    sme = next((item for item in items if item["source"] == "Omni OS process graph"), None)
    if sme:
        ask["sme_basis"] = sme["snippet"]
        basis = (ask.get("evidence_basis") or "").strip()
        ask["evidence_basis"] = f"SME process knowledge ({sme['label']}): {sme['snippet']} {basis}".strip()
    return ask


# ------------------------------------------------------------------ #
# Segment evidence: size each behavioural segment against the addressable HCP
# universe so the lead-segment ask reads as an analysis ("≈ X HCPs, these are the
# criteria, this is why we recommend it"), not a bare pick-one.
# ------------------------------------------------------------------ #
# Illustrative behavioural shares of the addressable universe (sum to 100). Real total
# comes from benchmarks.audience_size(); the split is a heuristic read, same
# illustrative-on-real-inputs pattern as segment_profile.py — flagged in evidence_basis.
_SEGMENT_LIBRARY = [
    {"label": "Evidence-driven skeptics", "share": 22,
     "criteria": "High scientific-ladder position · demand RCT-grade OS/PFS data · move on peer, KOL and congress proof."},
    {"label": "Guideline followers", "share": 34,
     "criteria": "Anchor to NCCN/ESMO updates · reflex-testing adopters · switch when guidelines and labels shift."},
    {"label": "Digital-first early adopters", "share": 18,
     "criteria": "High owned-digital affinity · self-serve e-detailing · responsive to webinar and EHR point-of-care."},
    {"label": "Relationship-led traditionalists", "share": 26,
     "criteria": "Rep-access dependent · F2F-led · value continuity of care · slower to switch treatment."},
]


_SCOPE_WORD = {"specialty": "matched-specialty", "panel": "oncology panel"}


_LIFECYCLE_KEYS = ("launch", "growth", "mature", "loe")


def _lifecycle_key(ctx: dict) -> str:
    """Benchmark lifecycle key for this plan. Defaults to growth -- the middle index -- so a
    brand with no lifecycle captured is not scored against launch or LOE expectations."""
    inferred = ctx.get("inferred") or {}
    for candidate in (inferred.get("lifecycle_key"), inferred.get("lifecycle_label")):
        text = str(candidate or "").lower()
        for key in _LIFECYCLE_KEYS:
            if key in text:
                return key
    return "growth"


def _objective_default(ctx: dict) -> str:
    """Brand-specific north star for when the brief states none.

    "Boost HCP engagement above 35%" is unusable as an objective: it names no brand, no
    audience and no behaviour change, so nothing downstream can trace back to it and every
    plan gets the same one. Compose from what the plan actually knows instead."""
    inferred = ctx.get("inferred") or {}
    brand = (inferred.get("brand") or _brief_field(ctx, "brand") or "").strip()
    therapy = (ctx.get("therapy_area") or "").strip()
    chosen = ctx.get("chosen_segments") or []
    segment = (chosen[0].get("segment") if chosen else "") or inferred.get("persona") or "the target segment"
    where = f" in {therapy}" if therapy else ""
    if _lifecycle_key(ctx) == "launch":
        subject = brand or "this brand"
        return f"Establish {subject} as a considered option for {segment}{where}"
    # Without a brand name the possessive reads as nonsense ("routine the brand use"), so
    # drop the brand clause entirely rather than papering over it with a placeholder.
    what = f"routine {brand} use" if brand else "routine use"
    return f"Move {segment}{where} from trial to {what}"


def _objective_kpi(ctx: dict) -> str:
    """Success measure tied to this campaign's anchor channel and lifecycle stage, rather
    than a flat engagement percentage that means nothing without a baseline."""
    mix = (ctx.get("strategy") or {}).get("channel_mix_pct") or {}
    if not mix:
        return ""
    anchor = max(mix.items(), key=lambda kv: kv[1])[0]
    try:
        target = benchmarks.channel_targets(anchor, _lifecycle_key(ctx))
    except Exception:  # noqa: BLE001 -- a missing benchmark must not block the ask
        return ""
    if not target or target.get("target_pct") is None:
        return ""
    return (f"{target['kpi']} {target['target_low_pct']}-{target['target_high_pct']}% on {anchor} "
            f"(industry baseline {target['baseline_pct']}%, {_lifecycle_key(ctx)} index {target['index']}x)")


def _segment_evidence(ctx: dict) -> tuple[list[dict], str, int]:
    """Per-segment sizing from the HCP 360 dummy panel -- the segments the user picks (and the
    numbers the final brief quotes) are the panel's real target-list segments, counted on the
    plan's therapy-area specialties (panel fallback). Returns (segments, note, total). Falls back
    to the benchmark-library sizing only if the panel is empty/unavailable."""
    try:
        # `segment_filters` is set when the user narrows the panel (state/specialty) from the
        # segmentation ask or by revising the decision later. Absent on a first run.
        sizing = hcp_360.segment_sizing(ctx.get("therapy_area", "") or "", ctx.get("segment_filters"))
    except Exception:  # noqa: BLE001 — sizing is best-effort
        sizing = {}
    seg_rows = (sizing or {}).get("segments") or []
    if not seg_rows:
        return _segment_evidence_fallback(ctx)
    total = int(sizing.get("total") or sum(s["count"] for s in seg_rows))
    scope_word = _SCOPE_WORD.get(sizing.get("scope"), "panel")
    segs = [{"label": s["segment"], "share": s["pct"], "criteria": s["criteria"], "size": s["count"],
             "size_str": f"{s['count']:,} HCPs ({s['pct']:.0f}% of the {scope_word})"} for s in seg_rows]
    spec_note = ""
    if sizing.get("scope") == "specialty" and sizing.get("specialties"):
        spec_note = " (" + ", ".join(sizing["specialties"][:3]) + ")"
    # The sourcing line is not decoration: without it a reader assumes a launch brand's
    # segments came from its own script performance, which is the objection this answers.
    note = (f"Measured on the HCP 360 dummy panel -- {total:,} {scope_word} HCPs{spec_note} "
            f"across {len(segs)} therapy-area segments. "
            + (sizing.get("sourcing") or ""))
    return segs, note, total


def _segment_facets(ctx: dict) -> dict:
    """Filter dimensions offered alongside the segmentation ask. Best-effort: the ask must
    still pose without them."""
    try:
        return hcp_360.segment_filter_facets(ctx.get("therapy_area", "") or "")
    except Exception:  # noqa: BLE001
        return {"states": [], "specialties": []}


def _segment_evidence_fallback(ctx: dict) -> tuple[list[dict], str, int]:
    """Benchmark-library sizing (illustrative behavioural archetypes) -- used only when the HCP
    360 panel returns no segments. Returns (segments, note, total)."""
    ta = ctx.get("therapy_area", "") or ""
    total = 0
    try:
        total = int((benchmarks.audience_size(ta) or {}).get("total") or 0)
    except Exception:  # noqa: BLE001 — sizing is best-effort; fall back to a neutral universe
        total = 0
    if total <= 0:
        total = 5000  # neutral fallback when this therapy area isn't in the universe table
    segs = []
    for s in _SEGMENT_LIBRARY:
        size = round(total * s["share"] / 100)
        segs.append({**s, "size": size,
                     "size_str": f"≈ {size:,} HCPs ({s['share']}% of universe)"})
    note = (f"Sized against ≈ {total:,} addressable US HCPs, split across four behavioural segments "
            f"(ABCD tier × scientific-ladder position × digital posture).")
    return segs, note, total


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
        # The brief's audience is the BROAD group, shown as ≤20-word context in the question —
        # not offered back as a verbatim option. The ask is: which segment(s) within it to lead
        # with. Multi-select: the plan can lead with more than one segment.
        broad_full = _brief_field(ctx, "audience") or inferred.get("persona", "")
        broad = brief_summary.summarize_value(broad_full, 14) if broad_full else "the lifecycle-stage default audience"
        segs, evidence_note, _total = _segment_evidence(ctx)
        rec, alts = segs[0], segs[1:]

        def _seg_opt(s: dict, source: str) -> dict:
            return {"label": s["label"], "source": source, "size": s["size_str"], "criteria": s["criteria"]}

        return _attach_grounding_to_ask(ctx, step, {"ask_id": f"ask-{step['num']}", "section": step["num"],
                "question_focus": f"Broad audience is {broad}. Ask which segment(s) within it to prioritise.",
                "broad_group": broad,
                "text": f"Your broad target is **{broad}**. Within that, which segment(s) should the plan lead with? "
                        "You can pick more than one.",
                "multi_select": True,
                "select_noun": "segment",
                "evidence_note": evidence_note,
                # Facets the user can narrow the panel by. Sizes above recompute against the
                # filtered population rather than being scaled client-side, so a filtered share
                # is a real count and still sums to 100%.
                "filters": {"available": _segment_facets(ctx), "active": ctx.get("segment_filters") or {}},
                "evidence_basis": _basis(ctx,
                    "Segment sizes counted on the HCP 360 dummy panel, filtered to the plan's therapy-area "
                    "specialties with a whole-panel fallback. Segments describe therapy-area prescribing "
                    "behaviour (syndicated scripts data), not this brand's performance.",
                    "audience", ("csfs", "positioning")),
                "why": "The segment lock drives eligibility, message ladder, channel weighting and flow defaults.",
                "recommendation": {**_seg_opt(rec, "HCP 360 panel — largest addressable segment")},
                "recommendation_reason": f"{rec['label']} is the largest addressable group in the panel "
                                         f"({rec['size_str']}); leading with it anchors the ladder for every other segment.",
                "options": [_seg_opt(s, "HCP 360 panel segment") for s in alts],
                "free_text": True})
    if kind == "objective":
        bam = ctx.get("bam") or {}
        positioning = _strategic_source(ctx).get("positioning")
        if isinstance(positioning, list):
            positioning = next((str(v).strip() for v in positioning if str(v or "").strip()), "")
        rec = (_brief_field(ctx, "objective") or positioning
               or bam.get("a_to_b_shift") or _objective_default(ctx)).strip()
        rec = brief_summary.summarize_value(rec, 14)  # never the whole two-part deck paragraph
        kpi = _objective_kpi(ctx)
        options = []
        if bam.get("a_to_b_shift") and bam.get("a_to_b_shift") != rec:
            options.append({"label": brief_summary.summarize_value(bam["a_to_b_shift"], 14), "source": "BAM framework default"})
        for c in _strategic_items(ctx, "csfs", limit=2):
            if c.lower() != rec.lower():
                options.append({"label": brief_summary.summarize_value(c, 14), "source": f"CSF from {_source_name(ctx)}"})
        return _attach_grounding_to_ask(ctx, step, {"ask_id": f"ask-{step['num']}", "section": step["num"],
                "question_focus": "Choose the CX objective / north star that every KPI and tactic should trace back to.",
                "text": f"North-star objective reads as **{rec}**."
                        + (f" Measured as {kpi}." if kpi else "")
                        + " Lock this, or steer it another way?",
                "objective_kpi": kpi,
                "evidence_basis": _basis(ctx,
                    "Objective composed from this brand, its lifecycle stage and the locked segment; the success "
                    "measure is the anchor channel's benchmark band, not a flat engagement percentage.",
                    "objective", ("positioning", "csfs")),
                "why": "The CX Planning Questionnaire locks the objective; every KPI and downstream tactic traces back to it.",
                "recommendation": {"label": rec, "source": "brief objective or strategic source; "
                                                           "fallback = brand + segment + lifecycle composition"},
                "options": options[:3],
                "free_text": True})
    if kind == "message":
        mf = ctx.get("message_flow") or {}
        sequence = mf.get("ladder_sequence") or [k["topic"] for k in (mf.get("key_messages") or [])]
        if not sequence:
            return None
        ladder = mf.get("message_ladder") or list(sequence)
        optional = mf.get("optional_topics") or []
        # One rung per option, never the ladder as a single take-it-or-leave-it chip: the
        # decision is which rungs are in scope, so each has to be tickable on its own. The
        # order is not up for selection -- the plan always tells it in clinical sequence.
        kit_source = "message-flow model" + (" + brand-kit claim library" if ctx.get("brand_kit") else "")
        rungs = [{"label": topic,
                  "source": kit_source if topic in sequence else "ladder rung outside this stage's default set"}
                 for topic in ladder]
        rungs += [{"label": topic,
                   "source": "access message -- sits outside the clinical ladder, off by default"}
                  for topic in optional]
        return _attach_grounding_to_ask(ctx, step, {"ask_id": f"ask-{step['num']}", "section": step["num"],
                "question_focus": "Choose which rungs the message ladder covers; the sequence itself is fixed.",
                "text": "Which rungs should the message ladder cover? They are always told in clinical "
                        "order -- mechanism, then efficacy, then safety, then dosing.",
                "multi_select": True,
                "select_noun": "rung",
                # The clinical rungs start ticked; pricing does not.
                "preselected": [topic for topic in ladder if topic in sequence],
                "evidence_basis": _basis(ctx,
                    "Ladder rungs default from the journey stage; brand-kit claims are used where available. "
                    "Sequence follows the clinical order a reviewer expects (mechanism before outcome).",
                    None, ("evidence", "positioning", "csfs")),
                "why": "The rungs in scope set what every asset can say; the ladder order fixes how it is told.",
                "recommendation": {"label": rungs[0]["label"], "source": rungs[0]["source"]},
                "recommendation_reason": f"{sequence[0]} opens the ladder because the stage's belief gap is "
                                         f"closed by mechanism-first framing before outcome claims land.",
                "options": rungs[1:],
                "free_text": True})
    if kind == "channel":
        mix = (ctx.get("strategy") or {}).get("channel_mix_pct") or {}
        if not mix:
            return None
        # Postures, not buckets: a planner picks how the campaign goes to market, and each
        # option carries the MMx split underneath it so the trade-off is visible up front.
        postures = channel_selection.build_posture_options(mix)
        preferred_full = _brief_field(ctx, "preferred_channels")
        preferred = brief_summary.summarize_value(preferred_full, 14) if preferred_full else ""
        broad = preferred or "the channel-affinity default mix"
        lead, alts = postures[0], postures[1:]

        def _posture_opt(posture: dict, source: str) -> dict:
            # `distribution` renders as the per-channel split under the option; the headline
            # is deliberately not also put in `size`, or the same numbers appear twice.
            return {"label": posture["label"], "source": source,
                    "criteria": posture["rationale"], "distribution": posture["distribution"]}

        text = (f"Your brief leans to **{preferred}**. Which way should this campaign go to market?"
                if preferred else "Which way should this campaign go to market?")
        return _attach_grounding_to_ask(ctx, step, {"ask_id": f"ask-{step['num']}", "section": step["num"],
                "question_focus": f"Broad channel intent: {broad}. Ask which go-to-market posture anchors the plan.",
                "broad_group": broad,
                "text": text,
                "evidence_basis": _basis(ctx,
                    "Channel-affinity mix for this segment and lifecycle stage, tilted to each posture's anchor. "
                    "Directional -- replace with the brand's own MMx or media plan when one exists.",
                    "preferred_channels", ("csfs", "guardrails")),
                "why": "The posture sets the anchor channel, the budget split and the cadence guardrails.",
                "recommendation": _posture_opt(lead, "channel-affinity model -- best-supported anchor"),
                "recommendation_reason": f"{lead['label']} splits to {lead['headline']}; "
                                         f"{lead['rationale'].lower()}",
                "options": [_posture_opt(p, "alternative posture") for p in alts],
                "free_text": True})
    if kind == "journey":
        return _attach_grounding_to_ask(ctx, step, _journey_ask(ctx, step))
    if kind == "timeline":
        duration = _brief_field(ctx, "duration")
        rec = brief_summary.summarize_value(duration, 14) if duration else "13-week standard wave"
        options = [] if duration else [{"label": "Compressed 9-week wave", "source": "execution model trade-off"}]
        return _attach_grounding_to_ask(ctx, step, {"ask_id": f"ask-{step['num']}", "section": step["num"],
                "question_focus": "Confirm the execution window and whether there is a hard launch date.",
                "text": f"Plan to a **{rec}**? Confirm the window, or set a hard launch date.",
                "evidence_basis": _basis(ctx,
                    "Default execution wave from the work-plan model; confirm against launch date and MLR capacity.",
                    "duration", ("guardrails", "csfs")),
                "why": "The work plan's bands and the MLR buffer are laid out against this window.",
                "recommendation": {"label": rec, "source": "brief timing if provided; otherwise execution work-plan model"},
                "options": options, "free_text": True})
    return None


def journey_answer_key(question_key: str) -> str:
    return f"chflow:{question_key}"


def journey_pending(ctx: dict) -> str | None:
    """The next journey question still to be asked, or None when the shape is settled.

    The journey is settled one short question at a time rather than as a form: a planner
    reasons about cadence and touchpoint count separately, and a single card asking for all
    of it at once is answered by accepting the default."""
    answered = ctx.get("journey_answers") or {}
    for question in journey_design.JOURNEY_QUESTIONS:
        if question["key"] not in answered:
            return question["key"]
    return None if "entry" in answered else "entry"


def _journey_numeric_ask(ctx: dict, step: dict, question: dict) -> dict:
    spec = ctx.get("journey_spec") or journey_design.derive_spec(ctx)
    current = spec.get(question["field"], question["recommended"])
    recommended = current if current in question["choices"] else question["recommended"]
    notes = question["notes"]

    def _option(value: int) -> dict:
        return {"label": journey_design.option_label(question, value),
                "source": "best practice" if value == recommended else "alternative cadence",
                "criteria": notes.get(value, "")}

    alternatives = [_option(v) for v in question["choices"] if v != recommended]
    return {"ask_id": f"ask-{step['num']}-{question['key']}", "section": step["num"],
            "answer_key": journey_answer_key(question["key"]),
            "question_focus": question["question"],
            "text": question["question"],
            # Options here are an enumerated range, not competing arguments, so the usual
            # two-alternative ceiling would hide most of the scale.
            "keep_options": True,
            "evidence_basis": _basis(ctx,
                "Recommended value is the common HCP nurture default; the range around it is what "
                "real campaigns use. Confirm against the brand's own engagement history.",
                "duration", ("csfs", "guardrails")),
            "why": question["why"],
            "recommendation": _option(recommended),
            "recommendation_reason": notes.get(recommended, ""),
            "options": alternatives,
            "free_text": True}


def _journey_entry_ask(ctx: dict, step: dict) -> dict:
    spec = ctx.get("journey_spec") or journey_design.derive_spec(ctx)
    current = journey_design.entry_mode(spec)
    return {"ask_id": f"ask-{step['num']}-entry", "section": step["num"],
            "answer_key": journey_answer_key("entry"),
            "question_focus": "Confirm how an HCP enters this journey.",
            "text": "Last one on the journey: how does an HCP enter it?",
            "keep_options": True,
            "journey_spec": spec,
            "evidence_basis": _basis(ctx,
                "Entry trigger is an assumption until confirmed; it decides eligibility, the consent "
                "basis, and whether a fixed send date exists at all.",
                "duration", ("csfs", "guardrails")),
            "why": "The trigger decides eligibility and consent basis, and whether the journey has a "
                   "send date or waits on an event.",
            "recommendation": {"label": current["label"], "source": current["trigger_hint"],
                               "criteria": current["detail"]},
            "recommendation_reason": f"{current['detail']}.",
            "options": [{"label": mode["label"], "source": mode["trigger_hint"], "criteria": mode["detail"]}
                        for mode in journey_design.ENTRY_MODES if mode["key"] != current["key"]],
            "free_text": True}


def _journey_ask(ctx: dict, step: dict) -> dict | None:
    pending = journey_pending(ctx)
    if pending is None:
        return None
    if pending == "entry":
        return _journey_entry_ask(ctx, step)
    return _journey_numeric_ask(ctx, step, journey_design.question_for(pending))


def apply_journey_answers(ctx: dict, answers: dict) -> None:
    """Fold every recorded journey sub-answer into ctx. Idempotent: the spec is rebuilt from
    the answers each time, so a resumed stream lands on the same shape."""
    collected: dict[str, str] = {}
    for question in journey_design.JOURNEY_QUESTIONS + [{"key": "entry"}]:
        value = answers.get(journey_answer_key(question["key"]))
        if value not in (None, ""):
            collected[question["key"]] = value
    ctx["journey_answers"] = collected
    if not collected:
        return
    spec = journey_design.derive_spec(ctx)
    for question in journey_design.JOURNEY_QUESTIONS:
        raw = collected.get(question["key"])
        if raw is None:
            continue
        value = journey_design.value_from_label(question, raw)
        if value is not None:
            spec[question["field"]] = value
    if collected.get("entry"):
        spec = journey_design.parse_answer(collected["entry"], spec)
    ctx["journey_spec"] = journey_design.derive_spec({}, spec)


def _step_answered(step: dict, studio: dict) -> bool:
    """Whether a step has everything it needs to draft. Most steps carry one ask keyed by
    section id; the journey step asks a short series, each with its own key."""
    answers = studio.get("answers") or {}
    if step["id"] != "chflow":
        return step["id"] in answers
    keys = [q["key"] for q in journey_design.JOURNEY_QUESTIONS] + ["entry"]
    return all(journey_answer_key(key) in answers for key in keys)


def _safe_build_ask(ctx: dict, step: dict) -> dict | None:
    """build_ask, degraded to the deterministic draft on failure -- an LLM hiccup must never
    strand a run mid-sequence."""
    try:
        return build_ask(ctx, step)
    except Exception as exc:  # noqa: BLE001
        print(f"[studio] build_ask failed for {step['id']}: {exc!r}")
        try:
            return _build_ask_draft(ctx, step)
        except Exception:  # noqa: BLE001
            return None


def _build_ask_llm_first(ctx: dict, step: dict) -> dict | None:
    draft = _build_ask_draft(ctx, step)
    if not draft:
        return None
    if ctx.get("_core_only"):
        # Racing to pose the first ask from the core ctx — skip the ~10s LLM refine and ship the
        # grounded deterministic draft; later asks (full ctx) get the LLM polish as normal.
        draft.setdefault("source", "fast-draft")
        return draft
    return llm_decisioning.refine_studio_ask(ctx, step, draft)


def auto_answer_value(ask: dict | None) -> str:
    """The value auto-assume takes on the user's behalf: the agent's own recommendation,
    falling back to the first offered option. Empty string => nothing safe to assume, so
    the ask must still be posed."""
    if not ask:
        return ""
    # A multi-select's recommendation is only its first row; taking that alone would silently
    # drop the rest of the pre-ticked set (the whole ladder becomes one rung).
    preselected = [str(x).strip() for x in (ask.get("preselected") or []) if str(x).strip()]
    if preselected and ask.get("multi_select"):
        return "; ".join(preselected)
    label = ((ask.get("recommendation") or {}).get("label") or "").strip()
    if label:
        return label
    for opt in ask.get("options") or []:
        label = (opt.get("label") or "").strip()
        if label:
            return label
    return ""


def _auto_assume_on(auto_assume) -> bool:
    """auto_assume is a live callable (so a mid-run toggle is honoured at the NEXT ask
    rather than being frozen at stream open) or a plain bool."""
    if callable(auto_assume):
        try:
            return bool(auto_assume())
        except Exception:  # noqa: BLE001 — a broken probe must never stall the run
            return False
    return bool(auto_assume)


def apply_answer(ctx: dict, step: dict, value: str) -> str:

    """Fold an answer into ctx before the section drafts. Returns a short note describing
    what changed (used in the drafting event). Deep recompute only where it is safe."""
    note = f"using your call — “{value}”"
    ctx.setdefault("studio_answers", {})[step["id"]] = value
    if step["id"] == "tcg":
        rec = (ctx.get("inferred") or {}).get("persona", "")
        # Multi-select answers arrive as a "; "-joined list; the FIRST is the lead segment the
        # profile re-aims at, the rest are recorded alongside it.
        segments = [s.strip() for s in value.split(";") if s.strip()]
        lead = segments[0] if segments else value.strip()
        # Record the picked segments with their real dummy-panel sizing, and re-point the HCP 360
        # grounding at them so the final brief's segmentation section leads with exactly what the
        # user chose, sized on the panel population -- not the lifecycle-default persona.
        _apply_chosen_segments(ctx, segments)
        if lead and rec and lead.lower() != rec.strip().lower():
            try:  # re-aim the segment profile + TCG at the lead group
                ctx["inferred"]["persona"] = lead
                sp = build_segment_profile(lead, ctx["inferred"]["stage_key"])
                ctx["segment_profile"] = sp
                ctx["tcg"] = build_tcg_template(lead, sp, ctx.get("strategy") or {}, ctx.get("bam") or {},
                                                agent_answers=(ctx.get("audience_profile") or {}).get("answers"),
                                                agent_name="Market & Competitive Intelligence")
                extra = f" (+{len(segments) - 1} more segment{'s' if len(segments) > 2 else ''})" if len(segments) > 1 else ""
                note = f"re-aimed the customer group at “{lead}”{extra} and rebuilt the profile"
            except Exception:  # noqa: BLE001 — fall back to recording the preference
                pass
    elif step["id"] == "chflow":
        spec = journey_design.parse_answer(value, ctx.get("journey_spec") or journey_design.derive_spec(ctx))
        ctx["journey_spec"] = spec
        note = "journey shape set to " + journey_design.spec_summary(spec)
    elif step["id"] == "msgflow":
        # Multi-select arrives "; "-joined. The auto-assume path instead records the whole
        # recommendation label, which is the ladder joined by "->" -- accept both shapes.
        topics = [t.strip() for t in value.replace("->", ";").split(";") if t.strip()]
        try:
            flow = build_message_flow(ctx["inferred"]["stage_key"],
                                      (ctx.get("strategy") or {}).get("kb_grounding") or {},
                                      selected_topics=topics)
            ctx["message_flow"] = message_flow_mod.ground_in_brand_kit(flow, ctx.get("brand_kit"))
            note = "message ladder set to " + " -> ".join(flow.get("ladder_sequence") or topics)
        except Exception:  # noqa: BLE001 — fall back to recording the preference
            pass
    return note


def _apply_chosen_segments(ctx: dict, segments: list[str]) -> None:
    """Match the user's picked segment label(s) back to the HCP 360 panel sizing and stash the
    result on ctx (`chosen_segments`) plus refresh `hcp_360_grounding` so every downstream brief
    section that renders that grounding leads with the chosen segment and its measured size. Best
    effort: any failure (LLM/db/label mismatch) leaves ctx unchanged."""
    if not segments:
        return
    try:
        sizing = hcp_360.segment_sizing(ctx.get("therapy_area", "") or "", ctx.get("segment_filters"))
    except Exception:  # noqa: BLE001
        return
    by_label = {s["segment"].lower(): s for s in (sizing.get("segments") or [])}
    chosen = [by_label[s.lower()] for s in segments if s.lower() in by_label]
    if not chosen:
        return
    ctx["chosen_segments"] = chosen
    scope_word = _SCOPE_WORD.get(sizing.get("scope"), "panel")
    total = int(sizing.get("total") or 0)
    lead = chosen[0]
    headline = f"Leading with {lead['segment']} — {lead['count']:,} HCPs ({lead['pct']:.0f}% of the {scope_word})"
    if len(chosen) > 1:
        headline += f"; +{len(chosen) - 1} more segment{'s' if len(chosen) > 2 else ''}"
    g = dict(ctx.get("hcp_360_grounding") or {})
    g.update({
        "agent": "strategy",
        "confidence": g.get("confidence") or f"measured (n={total} synthetic HCPs)",
        "headline": headline,
        "segment_breakdown": {s["segment"]: s["pct"] for s in (sizing.get("segments") or [])},
        "chosen_segments": [s["segment"] for s in chosen],
        "caveat": g.get("caveat") or "Synthetic HCP 360 panel — directional only, not real prescriber data.",
        "sources": g.get("sources") or ["hcp_360.db"],
    })
    ctx["hcp_360_grounding"] = g


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
def stream(ctx: dict, studio: dict, auto_assume=None):
    """Yields v2 events from the current cursor. Mutates `studio` (the caller persists it).
    studio = {"idx": int, "answers": {section_id: str}, "await_ask": dict | None}

    `auto_assume` (bool or callable-returning-bool, re-read at EVERY ask): when on, the ask
    is emitted already decided with the agent's recommendation and the stream keeps going
    instead of ending — the run drafts straight through with no human gate."""
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
        try:
            ensure_grounding(ctx, step)  # lazy: pull only THIS section's grounding, now
            grounding = grounding_items(ctx, step)
        except Exception as exc:  # noqa: BLE001 — a grounding hiccup must not kill the run
            print(f"[studio] grounding_items failed for {step['id']}: {exc!r}")
            grounding = []
        yield {"type": "grounding", "section_id": step["id"], "items": grounding}
        # A flaky grounding/LLM failure in one section must degrade to the deterministic
        # draft (or no ask) — never crash the whole run and strand the user mid-build.
        # Fold any sub-answers recorded on a previous stream back into ctx before deciding
        # what to ask next -- a multi-question step resumes mid-sequence.
        if step["id"] == "chflow":
            apply_journey_answers(ctx, studio["answers"])
        if _step_answered(step, studio):
            ask = None  # already answered on a prior pass — don't rebuild (saves a wasted LLM refine on resume)
        else:
            try:
                ask = build_ask(ctx, step)
            except Exception as exc:  # noqa: BLE001
                print(f"[studio] build_ask failed for {step['id']}: {exc!r}")
                try:
                    ask = _build_ask_draft(ctx, step)
                except Exception:  # noqa: BLE001
                    ask = None
        if ask:  # every ask names its spine framework + what it unblocks (why-chip data)
            stage = decision_spine.stage_for(step["id"])
            if stage:
                ask.setdefault("framework", stage["framework"]["name"])
                ask.setdefault("blocked", " · ".join(stage["feeds"]))
            # Keep the posed ask on ctx: the decision record is built on a LATER pass of this
            # loop (and after a reconnect, in a different process), so the options and the
            # agent's recommendation are long out of scope by then. Without this the record
            # cannot say what was actually set aside -- decision_spine._ask_for reads it here.
            ctx.setdefault("studio_asks", {})[step["id"]] = ask
        auto_value = ""
        # Auto-assume has to keep going on a step that asks more than one question, or it
        # would answer the first and draft with the rest still unset.
        while ask and _auto_assume_on(auto_assume):
            taken = auto_answer_value(ask)
            if not taken:
                break
            key = ask.get("answer_key") or step["id"]
            studio["answers"][key] = taken
            auto_value = taken
            studio["await_ask"] = None
            studio.setdefault("auto_answered", [])
            if key not in studio["auto_answered"]:
                studio["auto_answered"].append(key)
            yield {"type": "ask", **ask, "auto_assumed": True, "auto_answer": taken}
            if step["id"] == "chflow":
                apply_journey_answers(ctx, studio["answers"])
            ask = None if _step_answered(step, studio) else _safe_build_ask(ctx, step)
        if ask:
            # The very first (segmentation) ask is posed from the fast core ctx, so without this it
            # would appear almost the instant the budget is entered — reading as unconsidered. Pace
            # it: show the agent visibly sizing the segments, then reveal the analysed ask a few
            # seconds later. Guarded so a reconnect/refresh doesn't pace it again.
            if step["id"] == "tcg" and ctx.get("_core_only") and not studio.get("tcg_paced"):
                studio["tcg_paced"] = True
                yield {"type": "chat", "author": step["owner"], "kind": "turn", "reply_to": "",
                       "text": "Sizing each segment against the addressable HCP universe before we choose…"}
                time.sleep(4.5)
            # Unanswered ask: (re-)pose it and end the stream. A reconnect lands
            # right back here, so a refresh can never skip a gate.
            studio["await_ask"] = ask
            yield {"type": "ask", **ask}
            return
        # Answered (or no ask): draft and emit.
        note = ""
        if step["id"] == "chflow":
            apply_journey_answers(ctx, studio["answers"])
            if ctx.get("journey_spec"):
                note = "journey shape set to " + journey_design.spec_summary(ctx["journey_spec"])
        elif step["id"] in studio["answers"]:
            note = apply_answer(ctx, step, studio["answers"][step["id"]])
            if auto_value:
                note = f"auto-assuming the recommendation — “{auto_value}”"
        studio["await_ask"] = None
        renders = step.get("render", True)
        if renders:
            yield {"type": "drafting", "section_id": step["id"],
                   "note": (f"Drafting {title} — {note}." if note else f"Drafting {title} from the graph pull.")}
            md, html = compose_section(ctx, step["num"])
            yield {"type": "section_html", "section_id": step["id"], "num": step["num"], "title": title,
                   "owner": step["owner"], "html": html}
        # Decision record: the landed step explains itself — inputs, framework, decision,
        # rationale, what it feeds. Accumulated in ctx (campaign_artifacts re-derives them
        # deterministically if this list is ever lost, so persistence is a bonus not a need).
        # A step that is ALREADY answered never builds its ask -- true on every resume,
        # reconnect and post-revision replay. Without the ask the record cannot name what was
        # set aside, so it falls back to "no alternatives were put to the user" on exactly the
        # runs where the alternatives matter most. Rebuild the deterministic draft (no LLM) to
        # recover them; historical plans with neither stashed ask nor rebuildable draft still
        # degrade to the fallback rather than failing.
        if step["id"] not in (ctx.get("studio_asks") or {}):
            recovered = _safe_build_ask(ctx, step)
            if recovered:
                ctx.setdefault("studio_asks", {})[step["id"]] = recovered
        record = decision_spine.build_decision_record(
            ctx, step, studio["answers"].get(step["id"]),
            answered_by_user=None if not auto_value else False)
        if record:
            ctx.setdefault("decision_records", [])
            # Replace, don't skip. A revision replays this step, and skipping the re-emitted
            # record would leave campaign_artifacts and the persisted brief quoting the
            # PRE-revision decision while the live trail showed the new one.
            existing = next((i for i, r in enumerate(ctx["decision_records"])
                             if r.get("stage_id") == record["stage_id"]), None)
            if existing is None:
                ctx["decision_records"].append(record)
            else:
                ctx["decision_records"][existing] = record
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

