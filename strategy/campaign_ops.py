"""Campaign Operations synthesis (Stage 3): turns the already-computed orchestration
output (micro-journeys, message flow, channel selection, execution plan, content
library) into an editable engagement-journey diagram -- start/end, touchpoints,
decision-split branches, target-segment volume, and operational specifics -- the
level of day-by-day operational detail a Salesforce-Marketing-Cloud-style journey
brief carries but nothing upstream in this app computes yet.

Two layers, the same resilience pattern as persona_review.py's _llm_narrative: a
deterministic skeleton always runs first (segment selection, flow nodes/edges with
default positions, templated operational text); an LLM enrichment pass then tries to
sharpen the wording (decision-split conditions, entry criteria, operational rules,
summary, wait-day tuning) and falls back to the deterministic text on any failure --
Stage 3 never breaks if the LLM is unavailable.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import benchmarks  # noqa: E402
import hcp_360  # noqa: E402  (real panel counts for the segments the user actually picked)
import journey_design  # noqa: E402  (journey spec -> Journey Builder-shaped flow)

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
_SEGMENTS = json.loads((BASE_DIR / "config" / "audience_segments.json").read_text(encoding="utf-8"))

# Every persona rules.PERSONAS currently defines is an HCP archetype -- there is no
# "patient" persona in the inference model, so patient/caregiver campaigns are detected
# from the free-text brief audience field instead.
_PATIENT_KEYWORDS = ("patient", "caregiver", "care partner")

_DIGITAL_BUCKET_MAP = {"High-digital": "High", "Digital": "Digital", "F2F": "F2F", "Low": "Low"}

_DEFAULT_WAIT_DAYS = 6
_MAX_SEGMENTS = 3


def _is_patient_campaign(ctx: dict) -> bool:
    audience = ((ctx.get("brief") or {}).get("audience") or "").lower()
    return any(k in audience for k in _PATIENT_KEYWORDS)


_SCOPE_WORD = {"specialty": "matched-specialty panel", "panel": "oncology panel"}


def _answered_segment_names(ctx: dict) -> list[str]:
    """The segments the user locked at the planning audience ask ('tcg'), which the
    AskCard joins with '; '. Free-text additions come through here too."""
    answer = (ctx.get("studio_answers") or {}).get("tcg") or ""
    return [p.strip() for p in re.split(r"[;\n]+", answer) if p.strip()]


def _panel_channel(ctx: dict) -> str:
    """Follow-up channel for a panel segment: the plan's own anchor channel."""
    mix = (ctx.get("strategy") or {}).get("channel_mix_pct") or {}
    return max(mix.items(), key=lambda kv: kv[1])[0] if mix else "Email"


def _selected_panel_segments(ctx: dict) -> list[dict]:
    """The user's locked segments, matched back to the HCP 360 panel's target-list segments
    so the brief names EXACTLY what was chosen and carries the panel's real headcount.

    A name the panel doesn't know (free text typed into the ask) is still returned -- the brief
    must reflect the user's call -- just without a count, flagged in its volume_note."""
    names = _answered_segment_names(ctx)
    if not names:
        return []
    try:
        sizing = hcp_360.segment_sizing(ctx.get("therapy_area", "") or "")
    except Exception:  # noqa: BLE001 — panel sizing is best-effort
        sizing = {}
    rows = {str(r.get("segment", "")).strip().lower(): r for r in (sizing.get("segments") or [])}
    scope_word = _SCOPE_WORD.get(sizing.get("scope"), "panel")
    channel = _panel_channel(ctx)
    out: list[dict] = []
    for name in names:
        row = rows.get(name.lower())
        criteria = str((row or {}).get("criteria") or "")
        head, _, tail = criteria.partition("—")
        seg = {
            "key": re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or f"segment_{len(out) + 1}",
            "name": name,
            "description": (head.strip() or criteria).rstrip(".") or "Segment selected in the planning audience call.",
            "likes": [tail.strip().rstrip(".")] if tail.strip() else [],
            "preferred_channels": [channel],
            "digital_preference": "Digital",
        }
        if row:
            count = int(row.get("count") or 0)
            pct = row.get("pct") or 0
            seg["panel_count"] = count
            seg["panel_note"] = (f"HCP 360 panel count — {count:,} HCPs, {pct:g}% of the "
                                 f"{scope_word} ({int(sizing.get('total') or 0):,} HCPs).")
            seg["likes"] = seg["likes"] + [f"{pct:g}% of the {scope_word}"]
        else:
            seg["panel_count"] = None
            seg["panel_note"] = ("Not a target-list segment on the HCP 360 panel — size this one "
                                 "off the CRM pull before build.")
        out.append(seg)
    return out


def _select_segments(ctx: dict) -> tuple[list[dict], bool]:
    """The campaign's target segments. First choice is what the user actually locked at the
    planning audience ask (sized on the HCP 360 panel); only when that ask was never answered
    does this fall back to picking up to _MAX_SEGMENTS candidates from the named-segment library
    (config/audience_segments.json) by digital posture. Returns (selected, is_patient_campaign)."""
    picked = _selected_panel_segments(ctx)
    if picked:
        return picked, False

    is_patient = _is_patient_campaign(ctx)
    if is_patient:
        candidates = _SEGMENTS.get("patient_caregiver_segments", [])
        return candidates[:_MAX_SEGMENTS], True

    candidates = _SEGMENTS.get("hcp_segments", [])
    digital_pct = ((ctx.get("segment_profile") or {}).get("digital_preference_pct")) or {}
    scored = sorted(
        candidates,
        key=lambda s: -digital_pct.get(_DIGITAL_BUCKET_MAP.get(s.get("digital_preference"), ""), 0),
    )
    return scored[:_MAX_SEGMENTS], False


def _segment_volume(seg: dict, selected: list[dict], is_patient: bool, ctx: dict) -> tuple[float | None, str | None]:
    if "panel_count" in seg:
        # A user-locked segment: exact headcount from the panel, never an apportioned estimate.
        return seg["panel_count"], seg.get("panel_note")
    if is_patient:
        return None, "No published patient-population benchmark in this tool: qualitative sizing only."
    audience = benchmarks.audience_size(ctx.get("therapy_area", ""))
    total = audience.get("total")
    if not total:
        return None, f"HCP universe not sized for {ctx.get('therapy_area', 'this therapy area')}: no matching specialty benchmark."
    bucket = _DIGITAL_BUCKET_MAP.get(seg.get("digital_preference"), "")
    digital_pct = ((ctx.get("segment_profile") or {}).get("digital_preference_pct")) or {}
    share_pct = digital_pct.get(bucket, round(100 / max(len(selected), 1), 1))
    sharers = sum(1 for s in selected if _DIGITAL_BUCKET_MAP.get(s.get("digital_preference"), "") == bucket) or 1
    volume = round(total * (share_pct / 100) / sharers)
    return volume, None


def _content_ref(content_library: dict, preferred_channels: list[str]) -> dict:
    assets = (content_library or {}).get("assets") or []
    if not assets:
        return {"label": "Content needed", "ready": False}
    asset = assets[0]
    return {"label": asset.get("title", "Untitled asset"), "ready": True, "branded": asset.get("branded", True)}


def _flow_skeleton(ctx: dict, segments: list[dict], wait_days: int) -> dict:
    """Journey Builder-shaped flow for this plan.

    The shape comes from the journey spec the planner answered (entry trigger, touchpoint
    count, cadence, non-opener rule) rather than being assumed, and the ladder decides the
    behavioural branch off the first click. `segments` is no longer the branching axis: an
    HCP's own click tells you more about what to send next than the segment they were
    bucketed into up front."""
    journeys = (ctx.get("micro_journeys") or {}).get("journeys") or []
    primary = journeys[0] if journeys else {
        "trigger": "Campaign entry", "primary_touchpoint": "Branded email",
        "content_readiness": "Existing stock content",
    }
    channel = primary["primary_touchpoint"]
    spec = dict(ctx.get("journey_spec") or journey_design.derive_spec(ctx))
    # The caller's wait window still wins when the spec has not been explicitly answered --
    # it is derived from the same operational defaults the rest of this module uses.
    if not (ctx.get("journey_spec") or {}).get("reengage_after_days"):
        spec["reengage_after_days"] = wait_days
    if not spec.get("trigger_logic"):
        spec["trigger_logic"] = primary["trigger"]

    flow = journey_design.build_flow(
        spec,
        ladder_topics=(ctx.get("message_flow") or {}).get("ladder_sequence"),
        channel=channel,
        content_ref=_content_ref(ctx.get("content_library") or {}, [channel]),
    )
    return {"nodes": flow["nodes"], "edges": flow["edges"]}


def _operational_defaults(ctx: dict, segments: list[dict], wait_days: int, primary_channel: str) -> dict:
    persona = (ctx.get("inferred") or {}).get("persona", "the target persona")
    entry_criteria = [
        "Belongs to exactly one of the selected segments",
        f"Valid, opted-in contact channel for {primary_channel}",
        "Not already active in another overlapping journey",
        f"Persona match: {persona}",
    ]
    decision_logic_summary = [
        {"condition": f"Engaged with {primary_channel} within {wait_days} days",
         "outcome": "Assign engaged status → exit journey immediately"},
        {"condition": f"Not engaged within {wait_days} days",
         "outcome": "Send segment-specific follow-up → exit journey"},
    ]
    operational_rules = [
        f"Maximum of {1 + len(segments)} sends per contact",
        "Engaged contacts never receive a follow-up send",
        "Respect channel-level frequency caps and suppression",
        "Global suppression applied for opt-outs and bounces",
    ]
    brand = ctx.get("brand", "the brand")
    therapy_area = ctx.get("therapy_area", "")
    summary = (f"A {wait_days + 2}-day journey for {brand}{f' in {therapy_area}' if therapy_area else ''}: "
              f"one primary {primary_channel} send, a {wait_days}-day engagement window, then a "
              f"segment-tailored follow-up for non-responders before the journey closes.")
    return {"entry_criteria": entry_criteria, "decision_logic_summary": decision_logic_summary,
            "operational_rules": operational_rules, "summary": summary}


def _llm_fill_operational_detail(ctx: dict, skeleton: dict, segments: list[dict], wait_days: int) -> dict | None:
    """Optional: sharper, LLM-grounded wording for the operational text + a bounded
    wait-day tune. Falls back to None (caller keeps the deterministic defaults) on any
    failure -- mirrors persona_review.py::_llm_narrative."""
    try:
        import conversation_llm
        if not conversation_llm.llm_available():
            return None
        client = conversation_llm._get_client()
        brand = ctx.get("brand", "the brand")
        therapy_area = ctx.get("therapy_area", "")
        primary_channel = skeleton["nodes"][0]["data"]["channel"]
        seg_names = ", ".join(s["name"] for s in segments) or "no named segments"
        sys_prompt = (
            "You write operational copy for a pharma omnichannel engagement-journey diagram, in the "
            "style of a Salesforce Marketing Cloud journey brief. Given the journey's real structure "
            "(brand, channel, segments), return STRICT JSON only, no markdown fences, with exactly these "
            "keys: entry_criteria (list of short strings), decision_logic_summary (list of "
            "{condition, outcome} objects, 2 items), operational_rules (list of short strings), "
            "summary (one paragraph, 2-3 sentences), wait_days (integer 3-10). Be concrete and specific "
            "to the inputs given; do not invent facts not implied by the inputs."
        )
        user = (f"Brand: {brand}. Therapy area: {therapy_area}. Primary channel: {primary_channel}. "
               f"Segments getting a tailored follow-up: {seg_names}. Current default wait window: {wait_days} days.")
        resp = client.messages.create(
            model=conversation_llm.MODEL, max_tokens=500, system=sys_prompt,
            messages=[{"role": "user", "content": user}],
        )
        text = next((b.text for b in resp.content if b.type == "text"), "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text[4:] if text.lower().startswith("json") else text
        data = json.loads(text.strip())
        wd = data.get("wait_days")
        if not (isinstance(wd, int) and 3 <= wd <= 10):
            data.pop("wait_days", None)
        return data
    except Exception:  # noqa: BLE001 -- enrichment only, deterministic skeleton always stands in
        return None


def build_campaign_plan(ctx: dict, use_llm: bool = True) -> dict:
    segments_raw, is_patient = _select_segments(ctx)
    segments = []
    for seg in segments_raw:
        volume, note = _segment_volume(seg, segments_raw, is_patient, ctx)
        segments.append({
            "key": seg["key"], "name": seg["name"],
            "profile": seg.get("description", ""),
            "key_characteristics": (seg.get("likes") or [])[:2],
            "volume": volume, "volume_note": note,
            # True => a counted headcount (HCP 360 panel), not an apportioned estimate, so the
            # brief can print it as an exact figure rather than a "~".
            "volume_exact": "panel_count" in seg and volume is not None,
        })

    wait_days = _DEFAULT_WAIT_DAYS
    flow = _flow_skeleton(ctx, segments_raw, wait_days)
    primary_channel = flow["nodes"][0]["data"]["channel"]
    op = _operational_defaults(ctx, segments_raw, wait_days, primary_channel)

    if use_llm:
        enrichment = _llm_fill_operational_detail(ctx, flow, segments_raw, wait_days)
        if enrichment:
            new_wait_days = enrichment.get("wait_days")
            if new_wait_days and new_wait_days != wait_days:
                wait_days = new_wait_days
                flow = _flow_skeleton(ctx, segments_raw, wait_days)
            for key in ("entry_criteria", "decision_logic_summary", "operational_rules", "summary"):
                val = enrichment.get(key)
                if val:
                    op[key] = val

    return {
        "overview": {
            "objective": (ctx.get("brief") or {}).get("objective") or (ctx.get("bam") or {}).get("a_to_b_shift", ""),
            "duration_days": wait_days + 2,
            "max_communications": 1 + len(segments_raw),
            "primary_channel": primary_channel,
            "secondary_automation": "Engagement badge / segment tagging",
        },
        "segments": segments,
        "entry_criteria": op["entry_criteria"],
        "flow": flow,
        "decision_logic_summary": op["decision_logic_summary"],
        "operational_rules": op["operational_rules"],
        "kpis": ctx.get("kpi", {}),
        "summary": op["summary"],
    }
