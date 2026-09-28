"""The node and edge vocabulary the Flow Planner emits.

Ported line-for-line from the reference project's `app/flow/model.py` (see this
package's `__init__.py` for the port's scope and citation).

One shape serves the two consumers this port keeps: the API returns the design
for review, and the renderer draws it (type -> shape, status -> colour, tbd ->
visible gap). The reference project's third consumer -- freezing the design as
an Approved Journey Model version with derivation-based staleness detection --
is explicitly not ported (see `__init__.py`); `derived_from`/`sop_ref`/
`rationale` are still carried on every node so that piece can be added later
without touching the generator again.

Node ids are built, never generated. Two runs over an unchanged campaign must
produce identical ids, or a content hash computed over this later would move
for nothing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Regions: the SOP's two halves.
SEGMENTATION, JOURNEY = "segmentation", "journey"

# Node types. The renderer maps these to shapes; nothing else treats them as
# more than a label.
ENTRY = "entry"
DATASOURCE = "datasource"      # the SOP's cylinder (row 3)
PROCESS = "process"            # a plain step (row 4, the QnA blocks)
DECISION = "decision"          # a diamond (suppressions, resend, the fork)
SEGMENT = "segment"            # a named segment, ending a segmentation branch
TOUCHPOINT = "touchpoint"      # an email/SMS send
RESEND = "resend"              # a resend of the touchpoint above it
WAIT = "wait"
STOP = "stop"                  # the No arm of a suppression
EXIT = "exit"
NOTE = "note"                  # the panes: drawn, not connected

# Legend states (SOP row 10).
LIVE, NEW, HOLD, BUILT_NOT_LIVE = "live", "new", "hold", "built_not_live"

_SLUG = re.compile(r"[^a-z0-9]+")


def slug(value: str, fallback: str = "x") -> str:
    """A stable id fragment from free text - segment names, mostly.

    Deterministic by construction: no hashing, no counters, no ordering
    dependence. "PsO BIO NAIVE" is always "pso-bio-naive".
    """
    out = _SLUG.sub("-", (value or "").strip().lower()).strip("-")
    return out or fallback


def field_ref(section_id: str, field_id: str) -> str:
    """An intake field reference in the "section_id/field_id" form."""
    return f"{section_id}/{field_id}"


@dataclass
class FlowNode:
    id: str
    type: str
    label: str
    region: str = SEGMENTATION
    detail: str = ""
    lane: str | None = None                    # journey region: the segment
    attrs: dict = field(default_factory=dict)  # day, fuse_id, metadata_id, ...
    status: str | None = None                  # legend colour, SOP row 10
    tbd: list[str] = field(default_factory=list)
    derived_from: list[str] = field(default_factory=list)
    rationale: str = ""
    sop_ref: str = ""

    def mark_tbd(self, key: str) -> None:
        """Record that an attribute could not be resolved.

        The SOP says TBD in a dozen places; it never says "leave it blank". A
        value the SA still owes is different from one that does not apply, and
        the renderer and the clarifications both read this list to tell them
        apart.
        """
        if key not in self.tbd:
            self.tbd.append(key)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "detail": self.detail,
            "region": self.region,
            "lane": self.lane,
            "attrs": dict(self.attrs),
            "status": self.status,
            "tbd": list(self.tbd),
            "derived_from": sorted(set(self.derived_from)),
            "rationale": self.rationale,
            "sop_ref": self.sop_ref,
        }


@dataclass
class FlowEdge:
    src: str
    dst: str
    label: str | None = None

    def to_dict(self) -> dict:
        out = {"from": self.src, "to": self.dst}
        if self.label:
            out["label"] = self.label
        return out


@dataclass
class FlowDesign:
    """A whole generated journey: both regions, plus the unconnected panes."""
    nodes: list[FlowNode] = field(default_factory=list)
    edges: list[FlowEdge] = field(default_factory=list)
    segments: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sop_version: str = ""

    def add(self, node: FlowNode) -> FlowNode:
        self.nodes.append(node)
        return node

    def link(self, src, dst, label: str | None = None) -> FlowEdge:
        edge = FlowEdge(src.id if isinstance(src, FlowNode) else src,
                        dst.id if isinstance(dst, FlowNode) else dst, label)
        self.edges.append(edge)
        return edge

    def chain(self, nodes: list[FlowNode], label: str | None = None) -> None:
        """Link a run of nodes head to tail. The SOP's spine is one of these."""
        for a, b in zip(nodes, nodes[1:]):
            self.link(a, b, label)

    def node(self, node_id: str) -> FlowNode | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    @property
    def open_items(self) -> list[str]:
        """Every unresolved attribute, as "node id.attribute"."""
        return [f"{n.id}.{key}" for n in self.nodes for key in n.tbd]

    def to_spec(self) -> dict:
        """The stored / returned document.

        `steps` is the same node list under its old name, kept for parity with
        the reference project's own API shape.
        """
        nodes = [n.to_dict() for n in self.nodes]
        return {
            "format": 1,
            "sop_version": self.sop_version,
            "nodes": nodes,
            "steps": nodes,
            "edges": [e.to_dict() for e in self.edges],
            "segments": list(self.segments),
            "open_items": self.open_items,
            "warnings": list(self.warnings),
        }
