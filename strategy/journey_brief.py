"""The campaign brief's view of the engagement journey: an ordered step list and a Mermaid
flowchart, both projected from the campaign-ops flow (`campaign_ops.build_campaign_plan`).

Why this exists as its own module: the brief used to carry a hand-collapsed summary of the
journey — one send, one gate, a flat list of follow-ups. That was written when the flow WAS
that shape. `journey_design.build_flow` now emits a real multi-touchpoint journey (per
touchpoint: send -> wait -> Opened? -> Clicked? -> re-engagement arm, plus a behavioural
branch into per-rung tracks), and the old projection silently dropped everything after the
first touchpoint: touchpoints 2..n, every wait window, every Clicked? split and the whole
branch. The brief showed three identical "Re-send to non-openers" boxes hanging off one gate
and nothing else.

So: project the WHOLE graph, and let the brief render it. Nothing here invents journey
structure — every step and every arrow comes from a node or edge the ops flow actually has.
"""
from __future__ import annotations

import base64
import json
import zlib

# Node type -> how it reads in the brief. `comms` marks the steps that actually send
# something to an HCP, which is the subset the brief's step table leads with.
_KIND_LABEL = {
    "entry": "Entry",
    "send": "Send",
    "wait": "Wait",
    "decision": "Decision",
    "branch": "Branch",
    "followup": "Follow-up",
    "exit": "Exit",
    "closure": "Closure",
}
_COMMS_TYPES = ("send", "followup")

# Mermaid shape per node type — a diamond for a decision, a hexagon for the behavioural
# branch, stadiums for the journey's two ends, plain boxes for everything that sends.
_SHAPE = {
    "entry": ("([", "])"),
    "send": ("[", "]"),
    "wait": ("(", ")"),
    "decision": ("{", "}"),
    "branch": ("{{", "}}"),
    "followup": ("[", "]"),
    "exit": ("([", "])"),
    "closure": ("([", "])"),
}
_CLASS = {
    "entry": "entry", "send": "send", "wait": "wait", "decision": "gate",
    "branch": "gate", "followup": "followup", "exit": "yes", "closure": "close",
}
_CLASSDEFS = [
    "classDef entry fill:#ffffff,stroke:#cbd5e1,stroke-width:1px,color:#0f172a;",
    "classDef send fill:#dbeafe,stroke:#2563eb,stroke-width:1.5px,color:#0f172a;",
    "classDef wait fill:#f8fafc,stroke:#94a3b8,stroke-width:1px,color:#475569;",
    "classDef gate fill:#ffedd5,stroke:#f97316,stroke-width:1.5px,color:#0f172a;",
    "classDef followup fill:#ffffff,stroke:#94a3b8,stroke-width:1px,color:#0f172a;",
    "classDef yes fill:#dcfce7,stroke:#16a34a,stroke-width:1.5px,color:#0f172a;",
    "classDef close fill:#f1f5f9,stroke:#cbd5e1,stroke-width:1px,color:#0f172a;",
]

# Node text is the diagram's whole payload and it travels in a URL (see `ink_url`), so keep
# each line short enough to stay readable in a box and short enough to keep the URL sane.
_MAX_DETAIL = 64


def _clip(text: str, limit: int = _MAX_DETAIL) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _mermaid_text(text: str) -> str:
    """Mermaid label text. Double quotes end the label and '#' opens an entity reference,
    so both have to go; the rest is plain text inside a quoted string."""
    return _clip(text, 90).replace('"', "'").replace("#", "#35;")


def steps(plan: dict) -> list[dict]:
    """Every node of the journey as an ordered step: what happens, on which day, on which
    channel. Order is the flow's own node order (already entry -> touchpoint bands ->
    branch -> ends), not a day sort — re-engagement arms legitimately run later than the
    next touchpoint's send and sorting by day would interleave the two arms into nonsense."""
    out: list[dict] = []
    for node in (plan.get("flow") or {}).get("nodes") or []:
        data = node.get("data") or {}
        node_type = node.get("type", "")
        out.append({
            "id": node.get("id", ""),
            "kind": node_type,
            "kind_label": _KIND_LABEL.get(node_type, node_type.title() or "Step"),
            "is_comms": node_type in _COMMS_TYPES,
            "day": data.get("day"),
            "label": data.get("label", ""),
            "channel": data.get("channel", ""),
            "detail": data.get("detail", ""),
        })
    return out


def _duration_days(plan: dict, step_list: list[dict]) -> int | None:
    """The journey's real span: the last day any node lands on. The plan overview's own
    duration is a single touchpoint's window (wait + 2) and understates a multi-touchpoint
    journey by weeks."""
    days = [s["day"] for s in step_list if isinstance(s.get("day"), (int, float))]
    if days:
        return int(max(days))
    return (plan.get("overview") or {}).get("duration_days")


def project(plan: dict) -> dict:
    """The journey as the brief consumes it. Empty dict when the plan has no flow, which the
    brief renders as "no journey yet" rather than a half-drawn diagram."""
    step_list = steps(plan)
    if not any(s["kind"] == "send" for s in step_list):
        return {}
    comms = [s for s in step_list if s["is_comms"]]
    gates = [s for s in step_list if s["kind"] in ("decision", "branch")]
    return {
        "summary": plan.get("summary") or "",
        "duration_days": _duration_days(plan, step_list),
        "entry": (plan.get("entry_criteria") or [])[:4],
        "touchpoint_count": sum(1 for s in step_list if s["kind"] == "send"),
        "steps": step_list,
        "comms_steps": comms,
        "gates": gates,
        "decision_logic": plan.get("decision_logic_summary") or [],
        "operational_rules": (plan.get("operational_rules") or [])[:4],
    }


def mermaid(plan: dict) -> str:
    """The whole flow as a Mermaid flowchart — one node per node, one arrow per edge."""
    flow = plan.get("flow") or {}
    nodes = flow.get("nodes") or []
    if not nodes:
        return ""

    lines = ["flowchart TD"]
    by_class: dict[str, list[str]] = {}
    for node in nodes:
        node_id = node.get("id") or ""
        node_type = node.get("type", "")
        data = node.get("data") or {}
        open_shape, close_shape = _SHAPE.get(node_type, ("[", "]"))
        head = _mermaid_text(data.get("label") or _KIND_LABEL.get(node_type, "Step"))
        sub_parts = [p for p in (data.get("channel"), data.get("detail")) if p]
        sub = _mermaid_text(" · ".join(sub_parts)) if sub_parts else ""
        day = data.get("day")
        if day is not None:
            sub = f"day {day}" + (f" · {sub}" if sub else "")
        text = head + (f"<br/><small>{sub}</small>" if sub else "")
        lines.append(f'  {node_id}{open_shape}"{text}"{close_shape}')
        by_class.setdefault(_CLASS.get(node_type, "entry"), []).append(node_id)

    lines.append("")
    known = {n.get("id") for n in nodes}
    for edge in flow.get("edges") or []:
        source, target = edge.get("source"), edge.get("target")
        if source not in known or target not in known:
            continue  # an edge to a node that isn't drawn would create a phantom box
        label = _mermaid_text(edge.get("label") or "")
        lines.append(f"  {source} -->|{label}| {target}" if label else f"  {source} --> {target}")

    lines.append("")
    lines.extend(f"  {c}" for c in _CLASSDEFS)
    for class_name, ids in by_class.items():
        lines.append(f"  class {','.join(ids)} {class_name}")
    return "\n".join(lines)


# mermaid.ink renders a diagram from the graph source base64'd into the URL path. This is a
# PUBLIC third-party service: the URL carries the journey's real labels (brand channel mix,
# message rungs, segment follow-ups) and is fetched by the viewer's browser, so the campaign
# structure leaves your infrastructure every time the brief is opened. Chosen deliberately
# over the local mermaid-cli render; swap `INK_BASE` for a self-hosted mermaid.ink (it is
# open source, `ghcr.io/jihchi/mermaid.ink`) to keep it inside the estate.
INK_BASE = "https://mermaid.ink/img/"


def ink_url(mermaid_src: str, theme: str = "default", width: int = 1400) -> str:
    """mermaid.ink image URL for a Mermaid source string, or "" when there's nothing to draw.

    Uses the `pako:` (deflate) form rather than plain base64. A full journey is a repetitive
    graph, so it compresses hard — a real 7-touchpoint brief measured 6017 URL characters
    plain against 1618 compressed. Plain base64 works today but sits close enough to common
    proxy/CDN URL ceilings that a longer journey would start failing to render, silently and
    only for some viewers."""
    if not mermaid_src.strip():
        return ""
    payload = json.dumps({"code": mermaid_src, "mermaid": {"theme": theme}}, separators=(",", ":"))
    encoded = base64.urlsafe_b64encode(zlib.compress(payload.encode("utf-8"), 9)).decode("ascii").rstrip("=")
    return f"{INK_BASE}pako:{encoded}?type=png&width={width}&bgColor=FFFFFF"


def diagram(plan: dict) -> dict:
    """Everything the brief needs to show the journey picture. `mermaid` travels with the
    payload so a client that would rather render locally (or an export that embeds its own
    image) never has to re-derive it."""
    src = mermaid(plan)
    if not src:
        return {"ok": False, "detail": "No journey flow to draw yet.", "mermaid": "", "image_url": ""}
    return {"ok": True, "detail": "Rendered by mermaid.ink from the campaign-ops flow.",
            "mermaid": src, "image_url": ink_url(src)}
