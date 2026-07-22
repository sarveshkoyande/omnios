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
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import benchmarks  # noqa: E402

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


def _select_segments(ctx: dict) -> tuple[list[dict], bool]:
    """Picks up to _MAX_SEGMENTS candidates from the existing named-segment library
    (config/audience_segments.json) -- never invents a segment, only selects among
    real, authored ones. Returns (selected, is_patient_campaign)."""
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
    journeys = (ctx.get("micro_journeys") or {}).get("journeys") or []
    primary = journeys[0] if journeys else {
        "trigger": "Campaign entry", "primary_touchpoint": "Branded email", "content_readiness": "Existing stock content",
    }
    non_opener = (ctx.get("message_flow") or {}).get("non_opener_branch") or {}
    content_library = ctx.get("content_library") or {}

    nodes: list[dict] = []
    edges: list[dict] = []

    send_id = "send_primary"
    nodes.append({
        "id": send_id, "type": "send", "position": {"x": 260, "y": 0},
        "data": {"label": primary["primary_touchpoint"], "day": 1, "channel": primary["primary_touchpoint"],
                 "detail": primary["trigger"], "content_ref": _content_ref(content_library, [primary["primary_touchpoint"]])},
    })

    decision_id = "decision_engaged"
    nodes.append({
        "id": decision_id, "type": "decision", "position": {"x": 260, "y": 170},
        "data": {"label": f"Engaged with {primary['primary_touchpoint']}?", "day": wait_days},
    })
    edges.append({"id": f"e_{send_id}_{decision_id}", "source": send_id, "target": decision_id})

    exit_id = "exit_engaged"
    nodes.append({
        "id": exit_id, "type": "exit", "position": {"x": 40, "y": 350},
        "data": {"label": "Mark engaged: exit journey", "day": wait_days},
    })
    edges.append({"id": f"e_{decision_id}_{exit_id}", "source": decision_id, "target": exit_id, "label": "Yes"})

    n = max(len(segments), 1)
    span = 240
    start_x = 260 - span * (n - 1) / 2
    followup_ids: list[str] = []
    for i, seg in enumerate(segments):
        fid = f"followup_{seg['key']}"
        followup_ids.append(fid)
        nodes.append({
            "id": fid, "type": "followup", "position": {"x": start_x + i * span, "y": 350},
            "data": {"label": seg["name"], "day": wait_days + 1, "segment_key": seg["key"],
                     "channel": (seg.get("preferred_channels") or ["Email"])[0],
                     "content_ref": _content_ref(content_library, seg.get("preferred_channels") or [])},
        })
        edges.append({"id": f"e_{decision_id}_{fid}", "source": decision_id, "target": fid,
                      "label": "No" if i == 0 else ""})

    closure_id = "closure"
    nodes.append({
        "id": closure_id, "type": "closure", "position": {"x": 260, "y": 520},
        "data": {"label": "Journey closure", "day": wait_days + 2,
                 "detail": non_opener.get("node", "Engagement metrics finalized")},
    })
    for fid in followup_ids:
        edges.append({"id": f"e_{fid}_{closure_id}", "source": fid, "target": closure_id})

    return {"nodes": nodes, "edges": edges}


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
