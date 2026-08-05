"""Renderable data blocks from HCP 360 tool calls.

The Reporting agent already answers panel questions by calling hcp_360's tools
(segment_summary / cross_tab / list_hcps) inside a bounded tool-use loop -- but only its
final prose ever reached the UI, so a breakdown arrived as a markdown pipe-table pasted
into a chat bubble. This module turns each of those tool calls into a structured block the
frontend renders as a real sortable table (plus a chart, plus drill-down) instead.

A block is deliberately self-describing: it carries the dimensions and filters that
produced it, so the frontend can build the *next* query without knowing anything about the
panel's schema -- it just posts the block's filters plus the clicked row's dimension values
back to /api/hcp360/cross-tab. `drill_dims` is the allow-listed set of dimensions still
free to group by, computed here so the UI never offers a dimension the backend would reject.

Nothing in here reads the DB; it's a pure shaping layer over values hcp_360 returned, so a
malformed tool result degrades to "no block" rather than breaking the answer.
"""
from __future__ import annotations

# Mirrors hcp_360._DIM_SQL's allow-list. Kept as its own mapping because these are UI
# labels: hcp_360 owns which dimensions are queryable, this owns what they're called.
DIM_LABELS = {
    "specialty": "Specialty",
    "state": "State",
    "preferred_channel": "Preferred channel",
    "segment": "Segment",
    "writing_persona": "Writing persona",
    "brand": "Brand",
}

# The roster columns list_hcps selects, in display order.
_HCP_COLUMNS = [
    ("npi_number__c", "NPI", "number"),
    ("first_name__c", "First name", "text"),
    ("last_name__c", "Last name", "text"),
    ("primary_specialty_description__c", "Specialty", "text"),
    ("state_code__c", "State", "text"),
    ("city__c", "City", "text"),
]

_MAX_ROWS = 400  # a chat answer never needs more; keeps the persisted payload small


def _as_list(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    return [v for v in (value or []) if isinstance(v, str)]


def _filter_caption(filters: dict) -> str:
    parts = [f"{DIM_LABELS.get(k, k).lower()}: {v}" for k, v in (filters or {}).items()]
    return ", ".join(parts)


def _dim_columns(dims: list[str]) -> list[dict]:
    return [{"key": d, "label": DIM_LABELS.get(d, d), "type": "text"} for d in dims]


def _count_column(rows: list[dict]) -> list[dict]:
    return [{"key": "count", "label": "HCPs", "type": "number"}] if rows else []


def _breakdown_block(dims: list[str], filters: dict, rows: list[dict], block_id: str) -> dict:
    """A count-by-dimension table: the shape both segment_summary and a grouped cross_tab
    reduce to once segment_summary's generic {"value": ...} is renamed to its dimension."""
    rows = rows[:_MAX_ROWS]
    caption = _filter_caption(filters)
    title = "HCPs by " + " and ".join(DIM_LABELS.get(d, d).lower() for d in dims)
    return {
        "id": block_id,
        "kind": "breakdown",
        "title": title + (f" — {caption}" if caption else ""),
        "columns": _dim_columns(dims) + _count_column(rows),
        "rows": rows,
        "group_by": dims,
        "filters": filters,
        # Grouping by a dimension already pinned as a filter would return a single row, and
        # regrouping by a dimension already in view just reproduces this table.
        "drill_dims": [d for d in DIM_LABELS if d not in dims and d not in filters],
        "total": sum(int(r.get("count") or 0) for r in rows),
        "source": "HCP 360 panel",
    }


def from_tool_call(tool: str, tool_input: dict, result, block_id: str) -> dict | None:
    """Shape one Reporting-agent tool call into a renderable block, or None when the call
    produced nothing tabular (an error, an empty result, an unrecognised tool)."""
    if not isinstance(result, list) or not result:
        return None
    if not all(isinstance(r, dict) for r in result):
        return None
    tool_input = tool_input if isinstance(tool_input, dict) else {}

    if tool == "segment_summary":
        dim = tool_input.get("group_by")
        if dim not in DIM_LABELS:
            return None
        rows = [{dim: r.get("value"), "count": int(r.get("count") or 0)} for r in result]
        return _breakdown_block([dim], {}, rows, block_id)

    if tool == "cross_tab":
        dims = [d for d in _as_list(tool_input.get("group_by")) if d in DIM_LABELS]
        filters = {k: v for k, v in (tool_input.get("filters") or {}).items() if k in DIM_LABELS}
        if not dims:
            # An un-grouped cross_tab is a single number, not a table -- the interesting
            # thing about it is the filter combination that produced it, so it renders as a
            # stat tile that can still be drilled into.
            count = int(result[0].get("count") or 0)
            caption = _filter_caption(filters)
            return {
                "id": block_id,
                "kind": "stat",
                "title": caption or "HCPs in the panel",
                "label": "HCPs",
                "value": count,
                "filters": filters,
                "drill_dims": [d for d in DIM_LABELS if d not in filters],
                "source": "HCP 360 panel",
            }
        return _breakdown_block(dims, filters, result[:_MAX_ROWS], block_id)

    if tool == "list_hcps":
        rows = result[:_MAX_ROWS]
        applied = {k: v for k, v in tool_input.items() if k in ("specialty", "state", "brand_writer") and v}
        caption = ", ".join(str(v) for v in applied.values())
        return {
            "id": block_id,
            "kind": "roster",
            "title": f"HCPs — {caption}" if caption else "HCPs",
            "columns": [{"key": k, "label": label, "type": t} for k, label, t in _HCP_COLUMNS
                        if any(k in r for r in rows)],
            "rows": rows,
            # The roster's drill-down is per-HCP (the full 360 record), not another
            # aggregate, so it advertises no grouping dimensions.
            "drill_dims": [],
            "row_key": "npi_number__c",
            "total": len(rows),
            "source": "HCP 360 panel",
        }

    return None
