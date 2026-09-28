"""SOP rows 1-9: the segmentation region.

Ported from the reference project's `app/flow/segmentation.py`. Read this next
to the SOP table. Each builder below carries the row number it implements, and
the order they run in is the order the document lists them. The audience fork
is the one structural difference between DTC and HCP, and it is isolated to
three places - the right pane (row 2), the data source block (row 3) and the
suppression list (row 5) - rather than being threaded through every function
as a flag.

What this module does not decide: segment names, and whether the campaign
captures from an unbranded source. Both are judgement calls the SOP defers
(row 7, row 9), so the planner resolves them - from the record, then from the
model, then TBD - and passes the answer in.
"""
from __future__ import annotations

from strategy.flow_sop import inputs as fi
from strategy.flow_sop import sop
from strategy.flow_sop.model import (DATASOURCE, DECISION, NOTE, PROCESS, SEGMENT,
                                     FlowDesign, FlowNode, field_ref, slug)


def _note(node_id: str, label: str, boxes: list[dict], sop_ref: str,
          derived_from: list[str], rationale: str) -> FlowNode:
    """A pane: drawn, never connected.

    SOP row 2 is explicit that the enrollment box is "not connected to the flow
    by arrows", and the left pane is a caption rather than a step. Giving them
    real nodes keeps them inside the approved artifact - they carry campaign
    identity and the legend, which a reviewer needs - without pretending they
    are part of the path.
    """
    return FlowNode(
        id=node_id, type=NOTE, label=label,
        detail=" · ".join(b["title"] for b in boxes),
        attrs={"boxes": boxes}, derived_from=derived_from,
        rationale=rationale, sop_ref=sop_ref)


# --- row 1 -----------------------------------------------------------------

def left_pane(inp: fi.FlowInputs) -> FlowNode:
    """Row 1: campaign identity, task responsibilities, legend, campaign type."""
    name = inp.get(fi.F_NAME)
    code = inp.get(fi.F_CODE)
    ctype = inp.campaign_type

    box1 = [f"Campaign Name: {name or sop.TBD}",
            f"Campaign Code: {code or sop.TBD}",
            # The SOP wants the label present and the content blank in a first
            # draft, with its inclusion still to be confirmed. So it is rendered
            # as an empty labelled line rather than a TBD: nobody owes a value
            # yet, which is a different state from owing one.
            f"{sop.text('fulfilment_code_label')}:"]

    boxes = [
        {"title": "Campaign", "lines": box1},
        {"title": "Task Responsibility", "lines": list(sop.TASK_RESPONSIBILITIES)},
        {"title": "Legend", "lines": [l["label"] for l in sop.LEGEND],
         "swatches": [{"label": l["label"], "colour": l["colour"]} for l in sop.LEGEND]},
        {"title": "Campaign Type", "lines": [ctype or sop.TBD]},
    ]
    node = _note("pane.left", "Campaign", boxes, "seg.1",
                 inp.cite(fi.F_NAME, fi.F_CODE, fi.F_TYPE),
                 "Campaign identity, responsibilities and legend — SOP row 1")
    if not name:
        node.mark_tbd("campaign_name")
    if not code:
        node.mark_tbd("campaign_code")
    if not ctype:
        node.mark_tbd("campaign_type")
    return node


# --- row 2 -----------------------------------------------------------------

def right_pane(inp: fi.FlowInputs) -> FlowNode | None:
    """Row 2: the enrollment sources box. Empty for HCP, so not drawn at all.

    Returns None rather than an empty box: "leave empty" in the SOP means the
    pane is absent from an HCP diagram, and an empty titled box would read as a
    missing answer instead of an inapplicable one.
    """
    if inp.is_hcp:
        return None

    sources = inp.enrollment_sources
    lines: list[str] = []
    for i, src in enumerate(sources, 1):
        lines.append(f"Source {i}: {src['name'] or sop.TBD}")
        lines.append(f"  Campaign Source Code: {src['code'] or sop.TBD}")
        # Segment-specific QnA pairs in full text. Hidden pairs and the MDS
        # suppression pairs are deliberately excluded here (row 2); the hidden
        # ones get their own block at row 6.
        lines.append(f"  QnA: {src['qna'] or sop.TBD}")

    node = _note("pane.right", sop.text("enrollment_sources_title"),
                 [{"title": sop.text("enrollment_sources_title"),
                   "lines": lines or [sop.TBD]}],
                 "seg.2",
                 inp.cite(fi.F_SOURCE_NAME, fi.F_SOURCE_CODE, fi.F_QNA),
                 "Enrollment sources with their codes and segment QnA pairs — SOP row 2")
    if not sources:
        node.mark_tbd("enrollment_sources")
    return node


# --- row 3 -----------------------------------------------------------------

def data_source(inp: fi.FlowInputs) -> FlowNode:
    """Row 3: the qualification cylinder. Wholly different text per audience."""
    if inp.is_hcp:
        ctype = inp.campaign_type
        cadence = sop.cadence(ctype)
        lines = [sop.text("hcp_qualification", campaign_type=ctype or sop.TBD),
                 sop.text("hcp_target_list", cadence=cadence or sop.TBD)]
        node = FlowNode(
            id="seg.source", type=DATASOURCE, label="Qualification for Campaign",
            detail=" / ".join(lines), attrs={"lines": lines},
            derived_from=inp.cite(fi.F_TYPE), sop_ref="seg.3",
            rationale="HCP target list qualified by campaign type — SOP row 3, HCP column")
        if not cadence:
            # Model based and Real-time say nothing about cadence, and the SOP
            # only defines the Adhoc and Cadenced cases.
            node.mark_tbd("cadence")
        return node

    name = inp.get(fi.F_NAME)
    code = inp.get(fi.F_CODE)
    ctype = inp.campaign_type
    lines = [", ".join(x for x in (name, ctype, code) if x) or sop.TBD]

    sources = inp.enrollment_sources
    if sources:
        join = sop.text("source_pair_join")
        for i, src in enumerate(sources):
            if i:
                lines.append(join)
            lines.append(f"{src['name'] or sop.TBD}, {src['code'] or sop.TBD}")
    else:
        lines.append(sop.TBD)
    lines.append(sop.text("disposition"))

    node = FlowNode(
        id="seg.source", type=DATASOURCE, label="Campaign Source",
        detail=" / ".join(lines), attrs={"lines": lines},
        derived_from=inp.cite(fi.F_NAME, fi.F_TYPE, fi.F_CODE,
                              fi.F_SOURCE_NAME, fi.F_SOURCE_CODE),
        sop_ref="seg.3",
        rationale="Campaign identity and enrollment source codes — SOP row 3, DTC column")
    if not sources:
        node.mark_tbd("enrollment_sources")
    return node


# --- row 4 -----------------------------------------------------------------

def dedupe() -> FlowNode:
    """Row 4: fixed on every campaign, both audiences."""
    return FlowNode(
        id="seg.dedupe", type=PROCESS, label="Dedupe",
        detail=sop.text("dedupe"), sop_ref="seg.4",
        rationale="Fixed SOP step — row 4")


# --- row 5 -----------------------------------------------------------------

def suppressions(design: FlowDesign, inp: fi.FlowInputs) -> list[FlowNode]:
    """Row 5: seven MDS blocks for DTC, eight for HCP, chained in order.

    The count is part of the specification, so it comes from the seed list
    rather than from whatever the campaign happens to have filled in. Where a
    block corresponds to a real intake field - specialty inclusion, opt-out -
    the rule names it and the node cites it, which is what lets an edit to that
    field later invalidate a journey approval that depended on it.

    The checks run one after another with no Stop block drawn beside each and no
    Yes/No on the arrows between them. Failing a suppression always means the
    same thing and the SA reads the column as a sequence of checks; a Stop pill
    and a label on every one of seven or eight rows was noise that crowded the
    page without telling anyone anything they did not already know.
    """
    audience = inp.audience or sop.DTC
    built: list[FlowNode] = []
    for rule in sop.suppressions(audience):
        ref = rule.get("field_ref")
        value = None
        cites: list[str] = []
        if ref:
            section_id, field_id = ref.split("/", 1)
            value = inp.get((section_id, field_id))
            if value:
                cites = [field_ref(section_id, field_id)]

        node = design.add(FlowNode(
            id=f"seg.supp.{rule['slug']}", type=DECISION, label=rule["label"],
            # The block name is already the label on most of these; only show it
            # again when the record supplied something different.
            detail=value if value and value != rule["label"] else "",
            attrs={"block": rule["block"]},
            derived_from=cites, sop_ref="seg.5",
            rationale=f"MDS suppression '{rule['block']}' — SOP row 5, {audience} column"))
        built.append(node)

    design.chain(built)
    return built


# --- rows 6 and 8 ----------------------------------------------------------

def qna_block(inp: fi.FlowInputs, which: str) -> FlowNode:
    """Rows 6 and 8: the hidden and the segment QnA pairs.

    Both are extracted from the survey metadata sheet; the SOP distinguishes
    them by which field of that sheet they come from. The intake schema has one
    Q&A field and one metadata sheet, so the two blocks cite the same sources
    and are told apart by their label until the sheet is parsed into its parts.
    """
    hidden = which == "hidden"
    return FlowNode(
        id=f"seg.qna.{which}", type=PROCESS,
        label=sop.text("hidden_qna" if hidden else "segment_qna"),
        detail=inp.get(fi.F_QNA) or sop.TBD,
        derived_from=inp.cite(fi.F_QNA, fi.F_METASHEET),
        sop_ref="seg.6" if hidden else "seg.8",
        rationale=("Hidden survey QnA pairs from the metadata sheet — SOP row 6"
                   if hidden else
                   "Segment survey QnA pairs from the metadata sheet — SOP row 8"))


# --- row 7 -----------------------------------------------------------------

def unbranded_fork(design: FlowDesign, inp: fi.FlowInputs,
                   unbranded: dict) -> FlowNode:
    """Row 7: the branded / unbranded fork, when the goal calls for one.

    Three decisions in sequence: is this the unbranded source code, which
    question code was the last touchpoint in the unbranded flow, and which
    answer codes hang off it. The SOP's resolution order for the second is
    historical record, then campaign goal, then TBD - and with no history
    available in this phase, the first step is simply unavailable rather than
    silently skipped.
    """
    code = unbranded.get("campaign_code")
    head = design.add(FlowNode(
        id="seg.fork.decision", type=DECISION,
        label=sop.text("unbranded_fork_label"),
        detail=f"Campaign source code = {code or sop.TBD}",
        attrs={"campaign_code": code},
        derived_from=inp.cite(fi.F_GOAL, fi.F_BRANDED, fi.F_SOURCE_CODE),
        sop_ref="seg.7",
        rationale="Campaign goal requires capture from an unbranded source — SOP row 7"))
    if not code:
        head.mark_tbd("campaign_code")

    question = unbranded.get("last_touchpoint_question")
    metadata, meta_cite = inp.first(fi.F_AX_METADATA, fi.F_EMAIL_METADATA)
    q_node = design.add(FlowNode(
        id="seg.fork.question", type=DECISION,
        label=sop.text("last_touchpoint_label"),
        detail=f"{question or sop.TBD} · Metadata ID: {metadata or sop.TBD}",
        attrs={"question_code": question, "metadata_id": metadata},
        derived_from=meta_cite + inp.cite(fi.F_GOAL),
        sop_ref="seg.7",
        rationale="Last touchpoint question code and Metadata ID in the unbranded flow — SOP row 7, Decision 1"))
    if not question:
        q_node.mark_tbd("question_code")
    if not metadata:
        q_node.mark_tbd("metadata_id")

    answers = unbranded.get("answer_codes") or []
    a_node = design.add(FlowNode(
        id="seg.fork.answer", type=DECISION,
        label=sop.text("last_touchpoint_answer_label"),
        detail=", ".join(answers) if answers else sop.TBD,
        attrs={"answer_codes": answers},
        derived_from=inp.cite(fi.F_QNA), sop_ref="seg.7",
        rationale="Answer codes linked to the last touchpoint question — SOP row 7, Decision 2"))
    if not answers:
        a_node.mark_tbd("answer_codes")

    design.link(head, q_node, "Yes")
    design.link(q_node, a_node)
    return a_node


# --- row 9 -----------------------------------------------------------------

def segment_nodes(design: FlowDesign, names: list[str], cites: list[str],
                  recommended: bool) -> list[FlowNode]:
    """Row 9: one terminal node per segment, ending the segmentation region.

    `recommended` marks names the planner inferred rather than read. The SOP
    wants those surfaced as a recommendation for the SA to confirm, not
    presented as settled, so they are flagged on the node and raised as a
    clarification.
    """
    out = []
    for i, name in enumerate(names, 1):
        node = design.add(FlowNode(
            id=f"seg.name.{slug(name, str(i))}", type=SEGMENT,
            # The name is in the label; repeating it as the detail printed it
            # twice in the same box.
            label=f"Segment Name: {name}", detail="",
            attrs={"segment": name, "recommended": recommended},
            derived_from=list(cites), sop_ref="seg.9",
            rationale=("Segment name recommended from the campaign goal and survey text "
                       "for the SA to confirm — SOP row 9"
                       if recommended else
                       "Segment name taken from the campaign record — SOP row 9")))
        if recommended or name == sop.TBD:
            node.mark_tbd("segment_name")
        out.append(node)
    return out


# --- the region ------------------------------------------------------------

def build(design: FlowDesign, inp: fi.FlowInputs, *, segments: list[str],
          segment_cites: list[str], segments_recommended: bool,
          unbranded: dict | None) -> list[FlowNode]:
    """Assemble rows 1-9 and return the segment nodes the journeys hang off."""
    design.add(left_pane(inp))
    pane = right_pane(inp)
    if pane is not None:
        design.add(pane)

    spine: list[FlowNode] = [design.add(data_source(inp)),
                             design.add(dedupe())]
    design.chain(spine)

    supps = suppressions(design, inp)
    if supps:
        design.link(spine[-1], supps[0])
        tail = supps[-1]
    else:
        tail = spine[-1]

    hidden = design.add(qna_block(inp, "hidden"))
    design.link(tail, hidden)
    tail = hidden

    if unbranded and unbranded.get("present"):
        tail = unbranded_fork(design, inp, unbranded)
        design.link(hidden, "seg.fork.decision")

    segment_qna = design.add(qna_block(inp, "segment"))
    design.link(tail, segment_qna)

    nodes = segment_nodes(design, segments, segment_cites, segments_recommended)
    for node in nodes:
        design.link(segment_qna, node)
    return nodes
