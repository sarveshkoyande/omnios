"""The Flow Planner itself: a brief in, a journey design out.

Ported from the reference project's `app/flow/planner.py`. This module owns
the two resolution orders the SOP states but does not resolve, because both
need to consult the record, then the model, then give up in a specific way:

  segment names (row 9)   the campaign record, then the campaign goal and
                          survey text as a *recommendation*, then TBD
  unbranded fork (row 7)  the campaign goal, then TBD

"Then TBD" is a real outcome, not a failure. A journey with TBDs and a matching
set of clarifying questions is what the SOP asks for when the inputs do not
carry the answer, and it is more useful to a Solution Architect than a confident
guess they have to catch.

Everything else is delegated: segmentation.py builds rows 1-9, journeybuild.py
builds rows 10-17, and this module decides nothing they could decide themselves.
"""
from __future__ import annotations

import datetime as dt

from strategy.flow_sop import inputs as fi
from strategy.flow_sop import journeybuild, llm, segmentation, sop
from strategy.flow_sop.model import FlowDesign

# The segment a journey gets when nothing names one. The SOP's instruction is to
# keep TBD and let the SA add the names after the discovery call, so the journey
# is still built - one unnamed lane - rather than withheld.
TBD_SEGMENT = sop.TBD


def _survey_text(inp: fi.FlowInputs) -> str:
    """The survey material row 9 says to read segment names out of."""
    return "\n".join(filter(None, [inp.get(fi.F_QNA), inp.get(fi.F_METASHEET)]))


def resolve_segments(inp: fi.FlowInputs) -> tuple[list[str], list[str], bool, llm.ModelCall]:
    """SOP row 9. Returns (names, citations, recommended, model call).

    `recommended` distinguishes names the record stated from names inferred for
    the SA to confirm. The SOP is explicit that the second kind is input "as
    Recommendation, so SA can prompt the correct segment name", and a reviewer
    cannot be expected to remember which is which by looking at them.
    """
    declared, cites = inp.declared_segments
    if declared:
        return declared, cites, False, llm.ModelCall(used=False, error="not needed")

    call = llm.ModelCall(used=False, error="disabled")
    survey = _survey_text(inp)
    # Nothing to read means nothing to infer. Asking anyway would spend a call
    # and a model's willingness to be helpful on an empty page.
    if llm.available() and (inp.goal or survey):
        call = llm.recommend_segment_names(inp.goal, survey)
        if call.value:
            return list(call.value), inp.cite(fi.F_GOAL, fi.F_QNA), True, call

    return [TBD_SEGMENT], [], True, call


def resolve_unbranded(inp: fi.FlowInputs) -> tuple[dict, llm.ModelCall]:
    """SOP row 7: does the goal require capturing from an unbranded source?

    The deterministic read is a keyword check on the campaign goal. That is
    coarse, and on its own it would over-trigger - so when the model is
    available its judgement wins in both directions, and when it is not, the
    keyword hit produces a fork whose code is TBD plus a question asking the SA
    to confirm it. Over-asking is the cheaper error here: a fork the SA deletes
    costs a click, a fork nobody noticed was missing costs a rebuild.
    """
    goal = inp.goal
    keyword = "unbranded" in goal.lower()

    call = llm.ModelCall(used=False, error="disabled")
    # An empty goal cannot describe an unbranded source, so there is nothing to
    # ask about and the keyword read below already answers it.
    if llm.available() and goal:
        call = llm.detect_unbranded_source(goal)
        if isinstance(call.value, dict):
            found = dict(call.value)
            found.setdefault("answer_codes", [])
            if found.get("present"):
                touch = llm.recommend_last_touchpoint(
                    goal, [t.display_name for t in inp.touchpoints()])
                if isinstance(touch.value, dict):
                    found["last_touchpoint_question"] = touch.value.get("question_code")
            return found, call

    return ({"present": keyword, "campaign_code": None,
             "last_touchpoint_question": None, "answer_codes": [],
             "inferred": keyword}, call)


def plan(values: dict, *, today: dt.date | None = None,
         on_hold: bool = False, answers: dict | None = None) -> tuple[FlowDesign, dict]:
    """Build the journey design for one campaign.

    Returns the design and the metadata a run record needs to explain it: which
    SOP revision, which prompts, whether the model was consulted at all.
    """
    inp = fi.read(values, today=today, on_hold=on_hold, answers=answers)
    design = FlowDesign(sop_version=sop.VERSION)

    segments, cites, recommended, segment_call = resolve_segments(inp)
    unbranded, unbranded_call = resolve_unbranded(inp)
    design.segments = list(segments)

    if inp.audience is None:
        # The entire SOP forks on this one field, and defaulting it silently
        # would produce a DTC journey for an HCP campaign - seven suppression
        # blocks instead of eight, and an enrollment pane that should not exist.
        design.warnings.append(
            "Audience is not set, so the DTC rules were applied. Set Audience "
            "(1.1.6) to HCP or DTC and regenerate.")

    segmentation.build(design, inp, segments=segments, segment_cites=cites,
                       segments_recommended=recommended, unbranded=unbranded)
    journeybuild.build(design, inp, segments)

    meta = {
        "sop_version": sop.VERSION,
        "sop_source": sop.SOURCE,
        "audience": inp.audience,
        "segments": list(segments),
        "segments_recommended": recommended,
        "unbranded_fork": bool(unbranded.get("present")),
        "llm_enabled": llm.available(),
        "model_calls": [
            {"purpose": "segment_names", **_call_meta(segment_call)},
            {"purpose": "unbranded_source", **_call_meta(unbranded_call)},
        ],
        "open_items": design.open_items,
        "answers_used": sorted(k for k, v in (answers or {}).items()
                               if v and str(v).strip()),
    }
    return design, meta


def _call_meta(call: llm.ModelCall) -> dict:
    out = {"used": call.used, "model_id": call.model_id}
    if call.error:
        out["error"] = call.error
    out.update(call.prompt)
    return out


def generate(values: dict, *, today: dt.date | None = None,
             on_hold: bool = False, answers: dict | None = None) -> dict:
    """The stored spec for one campaign."""
    design, meta = plan(values, today=today, on_hold=on_hold, answers=answers)
    spec = design.to_spec()
    spec["meta"] = meta
    return spec
