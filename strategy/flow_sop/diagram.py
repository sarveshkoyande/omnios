"""Render a Flow Planner journey to an SVG flowchart for the browser.

Ported from the reference project's `app/diagram.py`, unchanged. Positions,
sizes and colours all come from `strategy.flow_sop.drawing`.

The shapes are not decoration. The SOP's reference images distinguish a data
source from a decision from a stop, and a reviewer checking a generated
journey against that document is matching shapes as much as text. So a
cylinder is a cylinder and a decision is a diamond, the panes sit unconnected
where the SOP puts them, and anything still TBD is drawn dashed so an
unfinished block cannot be mistaken for a finished one at a glance.
"""
from __future__ import annotations

from strategy.flow_sop.drawing import (DECISION_CHARS, DETAIL_CHARS, DETAIL_LINE_H,
                                       LABEL_CHARS, LABEL_LINE_H, MARGIN, codes,
                                       colours, compact, extent, layout, normalise,
                                       route, wrap)


def _esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _shape(node, x, y, w, h, fill, accent, dashed):
    kind = node.get("type")
    stroke = f'stroke="{accent}" stroke-width="1.6"'
    dash = ' stroke-dasharray="6 4"' if dashed else ""

    if kind == "decision":
        cx, cy = x + w / 2, y + h / 2
        pts = f"{cx},{y} {x + w},{cy} {cx},{y + h} {x},{cy}"
        return [f'<polygon points="{pts}" fill="{fill}" {stroke}{dash}/>']

    if kind == "datasource":
        ry = 11
        return [
            f'<path d="M{x},{y + ry} a{w / 2},{ry} 0 0 1 {w},0 v{h - 2 * ry} '
            f'a{w / 2},{ry} 0 0 1 {-w},0 z" fill="{fill}" {stroke}{dash}/>',
            f'<path d="M{x},{y + ry} a{w / 2},{ry} 0 0 0 {w},0" '
            f'fill="none" {stroke}{dash}/>',
        ]

    if kind in ("stop", "exit"):
        return [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h / 2}" '
                f'fill="{fill}" {stroke}{dash}/>']

    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" '
           f'fill="{fill}" stroke="#DEDAD4"{dash}/>']
    if kind != "note":
        out.append(f'<rect x="{x}" y="{y}" width="5" height="{h}" rx="2.5" '
                   f'fill="{accent}"/>')
    return out


def _pane(node, x, y, w, h, accent):
    """A pane: titled boxes, legend swatches, no connectors."""
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" '
           f'fill="#FFFFFF" stroke="{accent}" stroke-width="1.2"/>',
           f'<text x="{x + 12}" y="{y + 21}" font-size="12.5" font-weight="700" '
           f'fill="#161616">{_esc(node.get("label"))}</text>']
    cy = y + 40
    for box in (node.get("attrs") or {}).get("boxes") or []:
        out.append(f'<text x="{x + 12}" y="{cy}" font-size="10.5" '
                   f'font-weight="700" fill="#8A8681">{_esc(box.get("title"))}</text>')
        cy += 16
        swatches = {s["label"]: s["colour"] for s in box.get("swatches") or []}
        for line in box.get("lines") or []:
            colour = swatches.get(line)
            if colour:
                out.append(f'<rect x="{x + 12}" y="{cy - 8}" width="9" height="9" '
                           f'rx="2" fill="{colour}"/>')
            tx = x + (26 if colour else 12)
            for part in wrap(line, 30):
                out.append(f'<text x="{tx}" y="{cy}" font-size="11" '
                           f'fill="#555250">{_esc(part)}</text>')
                cy += 16
        cy += 10
    return out


def _label(node, x, y, w, h):
    """Every line of a block's text. Nothing is cut - the block was sized to
    hold all of it."""
    kind = node.get("type")
    out = []

    if kind == "decision":
        lines = ([(l, True) for l in wrap(node.get("label"), DECISION_CHARS)]
                 + [(l, False) for l in wrap(node.get("detail"), DECISION_CHARS)])
        top = y + h / 2 - (len(lines) * 15) / 2 + 12
        for i, (part, bold) in enumerate(lines):
            out.append(f'<text x="{x + w / 2}" y="{top + i * 15}" '
                       f'font-size="11.5" font-weight="{700 if bold else 400}" '
                       f'text-anchor="middle" '
                       f'fill="{"#161616" if bold else "#555250"}">{_esc(part)}</text>')
        return out

    if kind == "stop":
        return [f'<text x="{x + w / 2}" y="{y + h / 2 + 4}" font-size="12" '
                f'font-weight="700" text-anchor="middle" fill="#161616">'
                f'{_esc(node.get("label"))}</text>']

    tx = x + 18
    cy = y + 24
    for part in wrap(node.get("label"), LABEL_CHARS):
        out.append(f'<text x="{tx}" y="{cy}" font-size="13.5" font-weight="700" '
                   f'fill="#161616">{_esc(part)}</text>')
        cy += LABEL_LINE_H
    cy += 2
    for part in wrap(node.get("detail"), DETAIL_CHARS):
        out.append(f'<text x="{tx}" y="{cy}" font-size="11" '
                   f'fill="#555250">{_esc(part)}</text>')
        cy += DETAIL_LINE_H
    return out


def _code_chip(code, node, x, y, w, h):
    """The block's handle, small and out of the way."""
    if node.get("type") in ("decision", "stop"):
        cx, cy = x - 6, y + 12
        anchor = "end"
    else:
        cx, cy = x + 8, y - 5
        anchor = "start"
    return [f'<text x="{cx:.1f}" y="{cy:.1f}" font-size="9.5" font-weight="700" '
            f'text-anchor="{anchor}" fill="#A9B2B8" '
            f'font-family="monospace">{_esc(code)}</text>']


def _tbd_chip(x, y, w):
    return [f'<rect x="{x + w - 44}" y="{y + 7}" width="36" height="15" rx="7.5" '
            f'fill="#FBEAE8" stroke="#C4342B" stroke-width="0.8"/>',
            f'<text x="{x + w - 26}" y="{y + 18}" font-size="9" font-weight="700" '
            f'text-anchor="middle" fill="#C4342B">TBD</text>']


def _edge(pos, edge):
    """One arrow, following the shared right-angled route."""
    src, dst = pos.get(edge.get("from")), pos.get(edge.get("to"))
    if not src or not dst:
        return []

    points = route(src, dst)
    # Stop just short of the target so the arrowhead sits on its edge rather
    # than under it.
    (lx1, ly1), (lx2, ly2) = points[-2], points[-1]
    if abs(lx2 - lx1) < 1:
        ly2 -= 2 if ly2 > ly1 else -2
    else:
        lx2 -= 2 if lx2 > lx1 else -2
    points = points[:-1] + [(lx2, ly2)]

    path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points)
    out = [f'<path d="{path}" fill="none" stroke="#B4AFA8" stroke-width="1.6" '
           f'marker-end="url(#arr)"/>']

    if edge.get("label"):
        # On the first leg, which is the one leaving the block that branches.
        (ax, ay), (bx, by) = points[0], points[1]
        out.append(f'<text x="{(ax + bx) / 2 + 7:.1f}" y="{(ay + by) / 2 - 5:.1f}" '
                   f'font-size="10" font-weight="700" fill="#8A8681">'
                   f'{_esc(edge["label"])}</text>')
    return out


def flow_svg(spec, title, *, page=False):
    """Render a design document - or a legacy bare step list - to SVG."""
    nodes, edges = normalise(spec)
    pos = layout(nodes, edges)
    handle = codes(nodes)
    if page:
        pos = compact(pos)
    width, height = extent(pos)
    width += MARGIN
    height += MARGIN

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" '
        f'height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'font-family="Arial, Helvetica, sans-serif">',
        f'<rect width="{width:.0f}" height="{height:.0f}" fill="#FCFCFC"/>',
        '<defs><marker id="arr" markerWidth="9" markerHeight="9" refX="6" refY="3" '
        'orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#B4AFA8"/></marker></defs>',
        f'<text x="{MARGIN}" y="40" font-size="17" font-weight="700" '
        f'fill="#161616">{_esc(title)}</text>',
    ]

    # Edges first, so connectors never sit on top of the blocks they join.
    for edge in edges:
        out.extend(_edge(pos, edge))

    for node in nodes:
        placed = pos.get(node["id"])
        if not placed:
            continue
        x, y, w, h = placed
        fill, accent = colours(node)
        dashed = bool(node.get("tbd"))
        if node.get("type") == "note":
            out.extend(_pane(node, x, y, w, h, accent))
            out.extend(_code_chip(handle[node["id"]], node, x, y, w, h))
            continue
        out.extend(_shape(node, x, y, w, h, fill, accent, dashed))
        out.extend(_label(node, x, y, w, h))
        out.extend(_code_chip(handle[node["id"]], node, x, y, w, h))
        if dashed and node.get("type") not in ("decision", "stop"):
            out.extend(_tbd_chip(x, y, w))

    out.append("</svg>")
    return "\n".join(out)
