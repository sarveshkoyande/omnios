"""Shape translation only -- no generation logic lives here.

`strategy.brand_journey`'s flow-editing machinery (`_assign_codes`/`_apply_ops`,
and the frontend that renders their output) was built for `journey_design.
build_flow`'s node/edge shape: `{id, type, position: {x, y}, data: {...}}`
nodes and `{id, source, target, label?}` edges, with `data["block_code"]` as
the stable per-node key an edit references. `strategy.flow_sop`'s generator
(a faithful port -- see its own `__init__.py`) emits a different, SOP-native
shape: `{id, type, region, lane, detail, attrs, status, tbd, derived_from,
rationale, sop_ref}` nodes and `{from, to, label?}` edges, because that is the
reference project's own shape and porting it exactly was the point.

This module only translates one into the other so the SOP generator's output
can be stored and edited through the existing machinery. Every SOP-specific
field survives, just moved under `data` (which is `extra="allow"` in spirit
here too -- nothing reads a closed schema on the way back out).
"""
from __future__ import annotations

from strategy.flow_sop.model import JOURNEY

# Simple auto-layout: one column per region/lane, rows in generation order.
_COL_W, _ROW_H = 340, 110
_SEGMENTATION_COL = 0


def to_journey_builder_flow(spec: dict) -> dict:
    """`strategy.flow_sop.planner.generate()`'s spec -> the `{nodes, edges}`
    shape `brand_journey.py`'s `_assign_codes`/`_apply_ops` and the frontend
    flow canvas already know how to store, edit and render."""
    lanes = list(spec.get("segments") or [])
    lane_col = {lane: i + 1 for i, lane in enumerate(lanes)}  # segmentation spine is column 0

    row_by_col: dict[int, int] = {}
    nodes = []
    for n in spec.get("nodes") or []:
        col = lane_col.get(n.get("lane"), _SEGMENTATION_COL) if n.get("region") == JOURNEY else _SEGMENTATION_COL
        row = row_by_col.get(col, 0)
        row_by_col[col] = row + 1
        nodes.append({
            "id": n["id"],
            "type": n["type"],
            "position": {"x": col * _COL_W, "y": row * _ROW_H},
            "data": {
                "label": n["label"],
                "detail": n.get("detail", ""),
                "region": n.get("region"),
                "lane": n.get("lane"),
                "attrs": n.get("attrs") or {},
                "status": n.get("status"),
                "tbd": n.get("tbd") or [],
                "derived_from": n.get("derived_from") or [],
                "rationale": n.get("rationale", ""),
                "sop_ref": n.get("sop_ref", ""),
            },
        })

    edges = [{"id": f"e_{e['from']}_{e['to']}", "source": e["from"], "target": e["to"],
             **({"label": e["label"]} if e.get("label") else {})}
            for e in spec.get("edges") or []]

    return {"nodes": nodes, "edges": edges}
