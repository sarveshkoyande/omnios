"""The questions the SOP says to ask rather than guess.

Ported from the reference project's `app/flow/clarify.py`. The rule these
follow is the one the SOP repeats a dozen times: try the record, then the
stated fallback, and if neither answers it, ask - do not invent. So a question
here is raised only when a specific resolution order has actually run out. A
campaign whose brief is complete gets no questions and generates immediately;
one missing the audience gets asked about the audience and nothing else.

That is a change in kind from asking a fixed list every time. A question that
appears whether or not it is needed teaches the person answering that the
questions are decoration, and the one that mattered gets the same treatment as
the four that did not.
"""
from __future__ import annotations

import re

from strategy.flow_sop import inputs as fi
from strategy.flow_sop import llm, sop

CONFLICT, MISSING, OPEN = "conflict", "missing", "open"

# Campaign codes are 8-digit numerics (field 1.1.11 says so outright).
_CODE_IN_TEXT = re.compile(r"\b\d{8}\b")


def _q(qid: str, title: str, why: str, tag: str, options: list[str],
       recommended: str | None = None, atype: str = "choice") -> dict:
    return {"id": qid, "title": title, "why": why, "tag": tag, "type": atype,
            "options": options, "recommended": recommended}


def _questions(inp: fi.FlowInputs) -> list[dict]:
    """Every question this campaign's gaps actually warrant, in SOP order."""
    out: list[dict] = []

    # The whole SOP forks on the audience: seven suppression blocks or eight,
    # an enrollment pane or none, a source cylinder worded two different ways.
    # Nothing else is worth asking until this is settled.
    if inp.audience is None:
        out.append(_q(
            "audience", "Is this campaign DTC or HCP?",
            "The segmentation rules, the suppression list and the enrollment "
            "pane all differ by audience, and Audience (1.1.6) is not set.",
            MISSING, [sop.DTC, sop.HCP]))

    # SOP row 1: the label is shown and the content left blank in a first draft,
    # with its inclusion still to be confirmed.
    out.append(_q(
        "fulfilment_campaign_code", "What is the fulfilment campaign code?",
        "The SOP shows this label on the campaign pane and leaves it blank in a "
        "first draft, pending confirmation that it is needed at all.",
        OPEN, ["Leave blank in this draft"], "Leave blank in this draft", "text"))

    # SOP row 9: the record, then the goal and survey text, then TBD.
    declared, _ = inp.declared_segments
    if not declared:
        reason = ("Segments (1.1.13) is empty and no segment names could be read "
                  "from the campaign goal or the survey text.")
        if not llm.available():
            reason = ("Segments (1.1.13) is empty, so the journey has a single "
                      "unnamed lane.")
        out.append(_q("segment_names", "What are the segment names?", reason,
                      MISSING, [], None, "text"))

    # SOP rows 2 and 3 both build on the enrollment source. Automatrix carries a
    # segment of its own, and where the two disagree the SOP wants the source
    # confirmed rather than one of them picked.
    oms_source = inp.get(fi.F_SOURCE_NAME)
    ax_segment = inp.get(fi.F_AX_SEGMENT)
    if not inp.is_hcp:
        if not oms_source and not ax_segment:
            out.append(_q(
                "segment_source", "Which source should we use for the segment?",
                "Neither the OMS enrollment source (1.4.3) nor the Automatrix "
                "segment (1.9.7) is filled in.",
                MISSING, ["Use the Automatrix metadata segment",
                          "Use the OMS enrollment source"],
                "Use the Automatrix metadata segment"))
        elif oms_source and ax_segment and oms_source != ax_segment:
            out.append(_q(
                "segment_source", "Which source should we use for the segment?",
                f"The OMS enrollment source says {oms_source!r} and the "
                f"Automatrix segment says {ax_segment!r}.",
                CONFLICT, [f"Use the OMS enrollment source ({oms_source})",
                           f"Use the Automatrix segment ({ax_segment})"],
                f"Use the OMS enrollment source ({oms_source})"))

    # SOP row 7: historical record, then campaign goal, then TBD. There is no
    # historical record in this phase, so a goal that implies an unbranded
    # source but names no code leaves the fork unresolved.
    #
    # The test is whether the *goal* carries a campaign code, not whether the
    # campaign has one: the enrollment source codes in 1.4.5 belong to this
    # campaign's own sources, and the fork needs the code of a different,
    # unbranded campaign.
    if "unbranded" in inp.goal.lower() and not _CODE_IN_TEXT.search(inp.goal):
        out.append(_q(
            "unbranded_code", "What is the unbranded campaign source code?",
            "The campaign goal describes capturing audience from an unbranded "
            "source, but no campaign source code was found for it.",
            MISSING, [], None, "text"))

    # SOP row 7, Decision 1: which send is the last touchpoint.
    touchpoints = inp.touchpoints()
    named = [t.display_name for t in touchpoints if t.name]
    if "unbranded" in inp.goal.lower() and named:
        out.append(_q(
            "last_touch", "Which send should be shown as the last touch?",
            "The unbranded fork branches on the last touchpoint, and the brief "
            "does not say which send that is.",
            OPEN, named, named[-1]))

    # SOP rows 13 and 16: a resend decision with no rule behind it.
    if any(t.resend_needed for t in touchpoints) and not inp.get(fi.F_TP_RESEND_RULE):
        out.append(_q(
            "resend_routing", "What is the resend rule?",
            "Resend Needed (1.3.12) is Yes, but no Resend Rule (1.3.13) was "
            "given, so the resend has no day and no condition.",
            MISSING, ["Resend after 3 days to unopened",
                      "Resend after 7 days to unopened"],
            "Resend after 3 days to unopened"))

    # SOP row 10: the agent infers the legend colour from the go-live date and
    # is told to prompt for confirmation rather than assert it.
    status, date, _ = inp.golive_status()
    if date is not None:
        label = next((l["label"] for l in sop.LEGEND if l["key"] == status), status)
        out.append(_q(
            "golive_status", f"Is this campaign '{label}'?",
            f"The registered go-live date is {date.isoformat()}, which reads as "
            f"'{label}' today. Confirm the status, or amend the go-live date.",
            OPEN, [f"Yes, {label}"] + [l["label"] for l in sop.LEGEND
                                       if l["key"] != status],
            f"Yes, {label}"))
    else:
        out.append(_q(
            "golive_status", "When does this campaign go live?",
            "No go-live date is registered, so every send is shown as built but "
            "not live and no Day 1 can be anchored to a date.",
            MISSING, [], None, "text"))

    return out


def clarifications(values: dict, answers: dict, *, today=None,
                   on_hold: bool = False) -> list[dict]:
    """The open questions for one campaign, with any saved answers attached.

    Which questions are asked is decided from the record alone, deliberately
    without the answers. An answer resolves a question; it must not delete it.
    Otherwise answering one makes it disappear, and the person who answered has
    no way to see what they said or change their mind - and the endpoint that
    gates on "every question resolved" would be satisfied by a list that had
    quietly emptied itself.
    """
    inp = fi.read(values, today=today, on_hold=on_hold)
    saved = answers or {}
    out = []
    for num, question in enumerate(_questions(inp), 1):
        answer = saved.get(question["id"])
        out.append({**question, "num": num, "answer": answer,
                    "resolved": bool(answer and str(answer).strip())})
    return out
