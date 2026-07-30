"""Journey design: the spec a planner answers, and the SFMC-shaped flow built from it.

Two problems this fixes.

First, the agent used to draw a journey without ever asking how the journey runs. Entry
mode, touchpoint count, cadence and the non-opener rule were all assumed, so every campaign
got the same shape regardless of whether it was a one-off blast or an API-triggered program.
`JourneySpec` is the small set of answers that actually determine the shape, and
`derive_spec()` fills what the brief already implies so only the genuinely unknown is asked.

Second, the drawn journey was a generic flowchart -- send, "Engaged?", follow-up, closure.
A campaign team reads journeys in Journey Builder terms: a send, a wait, an Opened? split,
a Clicked? split, and behavioural branches off what the HCP actually clicked. `build_flow()`
emits that shape, including the message-ladder branch (clicked MOA -> MOA track, clicked
efficacy -> efficacy track) instead of one undifferentiated follow-up.

Node types stay within the vocabulary campaign_artifacts._journey and the frontend campaign
adapter already understand (send / wait / decision / branch / followup / exit / closure), so
the existing brief projection keeps working: re-engagement steps are typed `followup`, which
is what that projection means by the non-opener path.
"""
from __future__ import annotations

# How an HCP enters the journey. This is the question that was never asked, and it changes
# everything downstream -- eligibility, consent basis, and whether a "send date" exists.
ENTRY_MODES = [
    {"key": "adhoc", "label": "Ad-hoc batch send",
     "detail": "One-off audience list, sent on a fixed date",
     "trigger_hint": "Audience uploaded and scheduled; no upstream event"},
    {"key": "api", "label": "API-triggered",
     "detail": "An upstream system fires an entry event per HCP",
     "trigger_hint": "Entry event posted by the calling system; needs a documented payload contract"},
    {"key": "website", "label": "Website sign-up",
     "detail": "HCP enters after submitting a form on the brand site",
     "trigger_hint": "Form submit writes consent + entry event; double opt-in where required"},
]
_ENTRY_BY_KEY = {mode["key"]: mode for mode in ENTRY_MODES}

# Defaults are deliberately ordinary: a 3-touch nurture over six weeks, a fortnight apart,
# re-engaging non-openers after a week. They exist so the ask has a concrete recommendation
# to accept, not so the plan can skip asking.
DEFAULT_SPEC: dict = {
    "entry_mode": "adhoc",
    "trigger_logic": "",
    "touchpoints": 3,
    "duration_days": 42,
    "email_frequency_days": 14,
    "reengage_after_days": 7,
    "signup_flow": "",
}

_MAX_TOUCHPOINTS = 6  # beyond this the canvas stops being readable and the plan stops being real


def _int_in(value, low: int, high: int, fallback: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return fallback


def derive_spec(ctx: dict, answers: dict | None = None) -> dict:
    """The journey spec for this plan: defaults, overlaid with anything the brief already
    implies, overlaid with the planner's explicit answers."""
    spec = dict(DEFAULT_SPEC)
    brief = ctx.get("brief") or ctx.get("slots") or {}

    duration_text = str(brief.get("duration") or "")
    weeks = _weeks_in(duration_text)
    if weeks:
        spec["duration_days"] = weeks * 7

    for key, value in (answers or {}).items():
        if key in spec and value not in (None, ""):
            spec[key] = value

    spec["touchpoints"] = _int_in(spec["touchpoints"], 1, _MAX_TOUCHPOINTS, DEFAULT_SPEC["touchpoints"])
    spec["duration_days"] = _int_in(spec["duration_days"], 7, 365, DEFAULT_SPEC["duration_days"])
    spec["email_frequency_days"] = _int_in(spec["email_frequency_days"], 1, 90,
                                           DEFAULT_SPEC["email_frequency_days"])
    spec["reengage_after_days"] = _int_in(spec["reengage_after_days"], 1, 60,
                                          DEFAULT_SPEC["reengage_after_days"])
    if spec["entry_mode"] not in _ENTRY_BY_KEY:
        spec["entry_mode"] = DEFAULT_SPEC["entry_mode"]
    return spec


def _weeks_in(text: str) -> int | None:
    """Week count from a free-text duration ("13-week wave", "6 weeks"). None when absent."""
    import re

    match = re.search(r"(\d{1,2})\s*[-\s]?\s*week", text, re.I)
    if match:
        return _int_in(match.group(1), 1, 52, 6)
    match = re.search(r"(\d{1,2})\s*[-\s]?\s*month", text, re.I)
    if match:
        return _int_in(match.group(1), 1, 12, 2) * 4
    return None


def spec_summary(spec: dict) -> str:
    """One line a planner can accept or correct, used as the ask's recommendation label."""
    mode = _ENTRY_BY_KEY.get(spec["entry_mode"], ENTRY_MODES[0])
    weeks = round(spec["duration_days"] / 7)
    return (f"{mode['label']}, {spec['touchpoints']} touchpoints over {weeks} weeks, "
            f"email every {spec['email_frequency_days']} days, "
            f"re-engage non-openers after {spec['reengage_after_days']}")


def entry_mode(spec: dict) -> dict:
    return _ENTRY_BY_KEY.get(spec.get("entry_mode"), ENTRY_MODES[0])


# What the planner may override in free text, and the words they use for it. Sneha's nine
# journey questions are all here -- asked as one decision rather than nine gates, because a
# planner states a journey shape in a sentence ("6 emails, fortnightly, API-triggered") and
# nine separate confirmations is the interrogation the feedback objected to elsewhere.
_NUMERIC_PATTERNS = {
    "touchpoints": r"(\d{1,2})\s*(?:touch\s?points?|touches|emails?|sends?|steps?)",
    "duration_days": r"(?:over|across|for)\s*(\d{1,3})\s*(?:day|week|month)",
    "email_frequency_days": r"(?:every|each)\s*(\d{1,3})\s*(?:day|week)",
    "reengage_after_days": r"re-?engage[^.\d]{0,24}(\d{1,3})",
}


def parse_answer(text: str, spec: dict) -> dict:
    """Fold a free-text or option answer into the spec.

    Accepts an entry-mode label, and pulls any journey numbers the planner stated in
    passing. Anything not mentioned keeps its derived value."""
    import re

    answer = str(text or "").strip()
    if not answer:
        return dict(spec)
    out = dict(spec)
    lowered = answer.lower()

    for key, mode in _ENTRY_BY_KEY.items():
        if mode["label"].lower() in lowered or key in lowered:
            out["entry_mode"] = key
            break
    if "website" in lowered and "sign" in lowered:
        out["entry_mode"] = "website"

    for field, pattern in _NUMERIC_PATTERNS.items():
        match = re.search(pattern, lowered)
        if not match:
            continue
        value = int(match.group(1))
        unit = match.group(0)
        if field != "touchpoints":
            if "week" in unit:
                value *= 7
            elif "month" in unit:
                value *= 30
        out[field] = value

    # Free text that describes the trigger is worth keeping verbatim -- it is the trigger
    # logic the journey has to be built against, and no parser should be trusted to
    # summarise someone's integration contract.
    if out["entry_mode"] != "adhoc" or len(answer.split()) > 6:
        out["trigger_logic"] = answer
    return derive_spec({}, out)


# --------------------------------------------------------------------------- #
# Flow construction. Journey Builder shape: send -> wait -> Opened? -> Clicked?
# with a behavioural branch off what was actually clicked.
# --------------------------------------------------------------------------- #

_BAND_HEIGHT = 460          # vertical space one touchpoint occupies
_CENTRE_X = 300


def _node(node_id: str, node_type: str, x: int, y: int, **data) -> dict:
    return {"id": node_id, "type": node_type, "position": {"x": x, "y": y}, "data": data}


def _edge(source: str, target: str, label: str = "") -> dict:
    edge = {"id": f"e_{source}_{target}", "source": source, "target": target}
    if label:
        edge["label"] = label
    return edge


def _touchpoint_band(index: int, topic: str, spec: dict, channel: str,
                     content_ref: dict | None) -> tuple[list[dict], list[dict], dict]:
    """One touchpoint: send, wait, Opened? split, Clicked? split, re-engagement arm.

    Returns (nodes, edges, exits) where `exits` names the nodes a following touchpoint or
    the journey closure should be wired from."""
    base = 140 + index * _BAND_HEIGHT
    day = 1 + index * spec["email_frequency_days"]
    tag = index + 1
    send_id, wait_id = f"send_{tag}", f"wait_{tag}"
    open_id, click_id, reengage_id = f"open_{tag}", f"click_{tag}", f"reengage_{tag}"

    nodes = [
        _node(send_id, "send", _CENTRE_X, base, label=f"Email {tag} - {topic}", day=day,
              channel=channel, detail=f"Message rung: {topic}",
              **({"content_ref": content_ref} if content_ref else {})),
        _node(wait_id, "wait", _CENTRE_X, base + 110,
              label=f"Wait {spec['reengage_after_days']} days", day=day + spec["reengage_after_days"],
              detail="Engagement window before the split is evaluated"),
        _node(open_id, "decision", _CENTRE_X, base + 220, label="Opened?",
              day=day + spec["reengage_after_days"]),
        _node(click_id, "decision", _CENTRE_X + 260, base + 330, label="Clicked?",
              day=day + spec["reengage_after_days"]),
        _node(reengage_id, "followup", _CENTRE_X - 280, base + 330,
              label=f"Re-send to non-openers - new subject line", channel=channel,
              day=day + spec["reengage_after_days"] + 1,
              detail="No open in the engagement window; resend with a different subject line"),
    ]
    edges = [
        _edge(send_id, wait_id),
        _edge(wait_id, open_id),
        _edge(open_id, click_id, "Opened"),
        _edge(open_id, reengage_id, "No open"),
    ]
    return nodes, edges, {"entry": send_id, "clicked": click_id, "not_clicked": click_id,
                          "reengaged": reengage_id}


def _behavioural_branch(topics: list[str], spec: dict, channel: str) -> tuple[list[dict], list[dict], str]:
    """The branch Sneha asked for: what the HCP clicked decides which track they continue on,
    instead of every engaged HCP dropping into one generic follow-up."""
    base = 140 + _BAND_HEIGHT
    branch_id = "branch_clicked_content"
    nodes = [_node(branch_id, "branch", _CENTRE_X + 260, base - 40,
                   label="Which rung did they click?",
                   detail="Behavioural split on the clicked content, not a fixed next send")]
    edges: list[dict] = []
    span = 260
    start_x = _CENTRE_X + 260 - span * (len(topics) - 1) / 2
    for position, topic in enumerate(topics):
        track_id = f"track_{position}"
        nodes.append(_node(track_id, "send", int(start_x + position * span), base + 90,
                           label=f"{topic} track", channel=channel,
                           day=1 + spec["email_frequency_days"],
                           detail=f"Continue on {topic}: next asset deepens the rung they engaged with"))
        edges.append(_edge(branch_id, track_id, topic))
    return nodes, edges, branch_id


def build_flow(spec: dict, ladder_topics: list[str] | None = None,
               channel: str = "Branded email", content_ref: dict | None = None) -> dict:
    """SFMC-shaped journey for this spec. Entry -> per-touchpoint send/wait/Opened?/Clicked?
    -> behavioural branch on the first click -> exit, with non-openers on a re-engagement arm
    that rejoins the next touchpoint."""
    topics = [t for t in (ladder_topics or []) if t] or ["Core message"]
    mode = entry_mode(spec)
    nodes: list[dict] = [
        _node("entry", "entry", _CENTRE_X, 0, label=mode["label"], day=0,
              detail=spec.get("trigger_logic") or mode["trigger_hint"]),
    ]
    edges: list[dict] = []

    bands = []
    for index in range(spec["touchpoints"]):
        topic = topics[index % len(topics)]
        band_nodes, band_edges, exits = _touchpoint_band(index, topic, spec, channel, content_ref)
        nodes.extend(band_nodes)
        edges.extend(band_edges)
        bands.append(exits)
    edges.append(_edge("entry", bands[0]["entry"]))

    branch_nodes, branch_edges, branch_id = _behavioural_branch(topics, spec, channel)
    nodes.extend(branch_nodes)
    edges.extend(branch_edges)
    edges.append(_edge(bands[0]["clicked"], branch_id, "Clicked"))

    end_y = 140 + spec["touchpoints"] * _BAND_HEIGHT + 120
    nodes.append(_node("exit_engaged", "exit", _CENTRE_X - 280, end_y,
                       label="Mark engaged: exit journey", day=spec["duration_days"]))
    nodes.append(_node("closure", "closure", _CENTRE_X, end_y,
                       label="Campaign summary for non-openers", day=spec["duration_days"],
                       detail="Non-openers receive the campaign summary and the journey closes"))
    edges.extend(_edge(node["id"], "exit_engaged", "Engaged")
                 for node in branch_nodes if node["type"] == "send")

    # Wire each touchpoint's unengaged arms into the next touchpoint, and the last band into
    # closure -- so no path dead-ends on the canvas.
    for index, exits in enumerate(bands):
        nxt = bands[index + 1]["entry"] if index + 1 < len(bands) else "closure"
        edges.append(_edge(exits["reengaged"], nxt, "Still no open" if index + 1 < len(bands) else ""))
        if index > 0:
            edges.append(_edge(exits["clicked"], "exit_engaged", "Clicked"))
        edges.append(_edge(exits["not_clicked"], nxt, "No click"))

    return {"nodes": nodes, "edges": edges, "spec": spec,
            "legend": [mode["label"], f"{spec['touchpoints']} touchpoints",
                       f"every {spec['email_frequency_days']} days",
                       f"re-engage after {spec['reengage_after_days']} days"]}
