"""SOP rows 10-17: the email journey, built once per segment.

Ported from the reference project's `app/flow/journeybuild.py`. The shape the
SOP describes is a spine of sends with a resend decision hanging off each one:
email, "opened / clicked?", resend on the No arm, next email. Rows 12-14
specify the first send and rows 15-17 repeat the pattern, and the only
substantive difference between them is the Go-Live value - the first send
inherits the campaign's go-live date, every later one is TBD. So this builds
one loop and varies that single attribute, rather than duplicating the block
twice.

Every node in this region carries a legend status (row 10), which is why the
go-live comparison is resolved once in inputs.py and applied here uniformly.
"""
from __future__ import annotations

from strategy.flow_sop import inputs as fi
from strategy.flow_sop import sop
from strategy.flow_sop.inputs import FlowInputs, Touchpoint
from strategy.flow_sop.model import (DECISION, EXIT, JOURNEY, NOTE, RESEND, SEGMENT,
                                     TOUCHPOINT, FlowDesign, FlowNode, slug)


def legend_pane(inp: FlowInputs) -> FlowNode:
    """Row 10: the legend, and the go-live comparison behind the colours."""
    status, date, cites = inp.golive_status()
    label = next((l["label"] for l in sop.LEGEND if l["key"] == status), status)
    node = FlowNode(
        id="pane.legend", type=NOTE, label="Legend", region=JOURNEY,
        detail=f"Go-live {date.isoformat() if date else sop.TBD} · {label}",
        attrs={"boxes": [{"title": "Legend",
                          "lines": [l["label"] for l in sop.LEGEND],
                          "swatches": [{"label": l["label"], "colour": l["colour"]}
                                       for l in sop.LEGEND]}],
               "golive": date.isoformat() if date else None,
               "status": status},
        status=status, derived_from=cites, sop_ref="jny.10",
        rationale="Email status inferred by comparing today against the registered "
                  "go-live date; the SA confirms the status or amends the date — SOP row 10")
    if date is None:
        node.mark_tbd("golive")
    return node


def _touchpoint_node(design: FlowDesign, inp: FlowInputs, segment: str,
                     tp: Touchpoint, status: str, golive: str | None,
                     cites: list[str]) -> FlowNode:
    """Rows 12 and 15: one send.

    Go-Live is passed in rather than read: the SOP gives the first send the
    campaign go-live date and leaves every later one TBD, because the wait times
    between sends are themselves often unconfirmed at this stage.
    """
    detail = " · ".join(filter(None, [
        f"Day {tp.day}" if tp.day is not None else f"Day {sop.TBD}",
        tp.type or sop.TBD,
        f"Fuse ID: {tp.fuse_id or sop.TBD}",
        f"Metadata ID: {tp.metadata_id or sop.TBD}",
        f"Go-Live: {golive or sop.TBD}",
    ]))
    node = design.add(FlowNode(
        id=f"jny.{slug(segment)}.tp{tp.index}", type=TOUCHPOINT,
        label=tp.display_name, detail=detail, region=JOURNEY, lane=segment,
        attrs={"day": tp.day, "touchpoint_type": tp.type,
               "fuse_id": tp.fuse_id, "metadata_id": tp.metadata_id,
               "golive": golive},
        status=status, derived_from=list(cites), sop_ref="jny.12" if tp.index == 1 else "jny.15",
        rationale=("First send: day, touchpoint name and type, Fuse ID, Metadata ID, "
                   "and the campaign go-live date — SOP row 12"
                   if tp.index == 1 else
                   "Subsequent send: day derived from the wait time before it and the "
                   "preceding touchpoint; go-live TBD — SOP row 15")))
    for key in tp.missing:
        node.mark_tbd(key)
    if golive is None:
        node.mark_tbd("golive")
    return node


def _resend_pair(design: FlowDesign, segment: str, tp: Touchpoint,
                 status: str, cites: list[str]) -> tuple[FlowNode, FlowNode]:
    """Rows 13/16 and 14/17: the resend decision and the resend itself.

    Built only when Resend Needed is Yes. The SOP is unambiguous that the resend
    carries Go-Live TBD regardless of the campaign date, so that is asserted
    here rather than inherited.
    """
    question = design.add(FlowNode(
        id=f"jny.{slug(segment)}.tp{tp.index}.q", type=DECISION,
        label=sop.text("resend_decision"),
        detail=tp.resend_rule or sop.TBD, region=JOURNEY, lane=segment,
        attrs={"resend_rule": tp.resend_rule},
        status=status, derived_from=list(cites),
        sop_ref="jny.13" if tp.index == 1 else "jny.16",
        rationale="Resend decision on the engagement rule — SOP row 13"))
    if not tp.resend_rule:
        question.mark_tbd("resend_rule")

    resend = design.add(FlowNode(
        id=f"jny.{slug(segment)}.tp{tp.index}.resend", type=RESEND,
        label=tp.display_name + sop.text("resend_suffix"),
        detail=" · ".join([
            f"Day {tp.resend_day}" if tp.resend_day is not None else f"Day {sop.TBD}",
            tp.type or sop.TBD,
            f"Fuse ID: {tp.fuse_id or sop.TBD}",
            f"Metadata ID: {tp.metadata_id or sop.TBD}",
            f"Go-Live: {sop.TBD}",
        ]),
        region=JOURNEY, lane=segment,
        attrs={"day": tp.resend_day, "touchpoint_type": tp.type,
               "fuse_id": tp.fuse_id, "metadata_id": tp.metadata_id,
               "golive": None},
        status=status, derived_from=list(cites),
        sop_ref="jny.14" if tp.index == 1 else "jny.17",
        rationale="Resend of the preceding touchpoint, day derived from it and the "
                  "resend rule; go-live always TBD — SOP row 14"))
    # Go-Live: TBD is the rule, not a gap in the record.
    resend.mark_tbd("golive")
    if tp.resend_day is None:
        resend.mark_tbd("day")

    design.link(question, resend, "No")
    return question, resend


def build_segment(design: FlowDesign, inp: FlowInputs, segment: str,
                  touchpoints: list[Touchpoint], status: str,
                  golive: str | None, cites: list[str]) -> None:
    """Rows 11-17 for one segment."""
    start = design.add(FlowNode(
        id=f"jny.{slug(segment)}.start", type=SEGMENT,
        label=f"Segment Name: {segment}", detail="",
        region=JOURNEY, lane=segment, attrs={"segment": segment},
        status=status, sop_ref="jny.11",
        rationale="Segment carried through from the segmentation region — SOP row 11"))

    # The segmentation branch and its journey are the same audience; linking
    # them is what makes the two regions one traversable design rather than two
    # drawings that happen to share a name.
    seg_node = design.node(f"seg.name.{slug(segment)}")
    if seg_node is not None:
        design.link(seg_node, start)

    previous: FlowNode = start
    for tp in touchpoints:
        node = _touchpoint_node(design, inp, segment, tp, status,
                                golive if tp.index == 1 else None, cites)
        # Coming out of a resend decision, this is its Yes arm: the recipient
        # engaged, so they skip the resend and go straight to the next send.
        # Both arms of a diamond are labelled or neither is readable.
        design.link(previous, node, "Yes" if previous.type == DECISION else None)

        if tp.resend_needed:
            question, resend = _resend_pair(design, segment, tp, status, cites)
            design.link(node, question)
            # Both arms rejoin: an engaged recipient skips the resend, an
            # unengaged one gets it, and the journey continues either way.
            previous = question
            design.link(resend, f"jny.{slug(segment)}.exit"
                        if tp is touchpoints[-1] else
                        f"jny.{slug(segment)}.tp{tp.index + 1}")
        else:
            previous = node

    exit_rule = inp.get(fi.F_TP_EXIT)
    exit_node = design.add(FlowNode(
        id=f"jny.{slug(segment)}.exit", type=EXIT, label="Exit",
        detail=exit_rule or "Goal met or journey complete",
        region=JOURNEY, lane=segment, status=status,
        derived_from=inp.cite(fi.F_TP_EXIT), sop_ref="jny.exit",
        rationale="Exit rule after send"))
    design.link(previous, exit_node, "Yes" if previous.type == DECISION else None)


def build(design: FlowDesign, inp: FlowInputs, segments: list[str]) -> None:
    """Rows 10-17, once per segment."""
    design.add(legend_pane(inp))

    status, date, _ = inp.golive_status()
    golive = date.isoformat() if date else None
    touchpoints = inp.touchpoints()
    cites = inp.touchpoint_citations()

    for segment in segments:
        build_segment(design, inp, segment, touchpoints, status, golive, cites)
