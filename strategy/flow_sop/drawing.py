"""Where the journey's blocks sit on the page, and what colour they are.

Ported from the reference project's `app/drawing.py`, unchanged. One layout,
shared by both renderers there (`diagram.py` for SVG, `visio.py` for .vsdx --
only `diagram.py`/SVG is ported here, per this port's scope). Positions come
from here so the drawing is deterministic: the same design must place the
same way twice, or a regenerated journey looks like a changed one.

Layout is deliberately simple: the segmentation spine runs down a centre
column with its Stop arms to the right, the segments fan out at the foot of
it, and each segment's journey gets its own column below. No force-directed
anything.
"""
from __future__ import annotations

MARGIN, TOP = 40, 74
NW, NH = 264, 66          # a standard block
DW, DH = 240, 92          # a decision diamond
SW, SH = 130, 40          # a stop pill
PANE_W = 250
ROW_GAP = 46
COL_W = 330
STOP_DX = 60
RESEND_DX = 40

# Fill and accent by node type, used when a block carries no legend status.
PALETTE = {
    "entry":      ("#E7F1F5", "#14607A"),
    "objective":  ("#EEEAF6", "#5B4B8A"),
    "datasource": ("#FBF3DA", "#8A6508"),
    "process":    ("#F2F2F2", "#8A8681"),
    "decision":   ("#FBF3DA", "#C8A302"),
    "segment":    ("#EEEAF6", "#5B4B8A"),
    "touchpoint": ("#FFF0EA", "#FF4E00"),
    "resend":     ("#FFF6F2", "#FF8A5B"),
    "optimize":   ("#E7F1F5", "#14607A"),
    "wait":       ("#F2F2F2", "#8A8681"),
    "split":      ("#FBF3DA", "#8A6508"),
    "stop":       ("#FBEAE8", "#C4342B"),
    "exit":       ("#E7F2EC", "#1B7F51"),
    "note":       ("#FFFFFF", "#B4AFA8"),
}
DEFAULT = ("#F6F8FA", "#8A8681")

# The SOP row 10 legend overrides the type palette wherever a status is set.
STATUS = {
    "live":           ("#E7F2EC", "#1B7F51"),
    "new":            ("#FBF3DA", "#C8A302"),
    "hold":           ("#FBEAE8", "#C4342B"),
    "built_not_live": ("#F2F2F2", "#8A8681"),
}


def normalise(spec) -> tuple[list[dict], list[dict]]:
    """Blocks and edges out of a design document, or out of a legacy list."""
    if isinstance(spec, list):
        nodes, edges = list(spec), []
    else:
        nodes = spec.get("nodes") or spec.get("steps") or []
        edges = spec.get("edges") or []

    if nodes and not any(n.get("id") for n in nodes):
        nodes = [{**n, "id": f"n{i}"} for i, n in enumerate(nodes)]
        edges = [{"from": f"n{i}", "to": f"n{i + 1}"}
                 for i in range(len(nodes) - 1)]
    return nodes, edges


# How many characters fit on a line, per place text is drawn. Approximate -
# these are proportional fonts - but consistent between the two renderers.
LABEL_CHARS = 32
DETAIL_CHARS = 40
DECISION_CHARS = 26
LABEL_LINE_H = 17
DETAIL_LINE_H = 14


def colours(node) -> tuple[str, str]:
    status = node.get("status")
    if status in STATUS:
        return STATUS[status]
    return PALETTE.get(node.get("type"), DEFAULT)


def wrap(text, width: int) -> list[str]:
    """Break text onto as many lines as it needs. Nothing is cut.

    A word longer than the line is split rather than allowed to overflow: Fuse
    and Metadata IDs run to twenty characters with no spaces in them.
    """
    out: list[str] = []
    for paragraph in str(text or "").split("\n"):
        current = ""
        for word in paragraph.split():
            while len(word) > width:
                if current:
                    out.append(current)
                    current = ""
                out.append(word[:width])
                word = word[width:]
            candidate = f"{current} {word}".strip()
            if len(candidate) <= width:
                current = candidate
            else:
                out.append(current)
                current = word
        if current:
            out.append(current)
    return out


def size(node) -> tuple[float, float]:
    """A block's width and height, grown to fit whatever text it carries."""
    kind = node.get("type")
    label = node.get("label") or ""
    detail = node.get("detail") or ""

    if kind == "decision":
        lines = len(wrap(label, DECISION_CHARS)) + len(wrap(detail, DECISION_CHARS))
        # A diamond wastes most of its box on the corners, so it needs more
        # slack per line than a rectangle does.
        return DW, max(DH, 46 + lines * 15)
    if kind == "stop":
        return SW, SH
    if kind == "note":
        boxes = (node.get("attrs") or {}).get("boxes") or []
        lines = sum(len(b.get("lines") or []) for b in boxes)
        return PANE_W, 34 + len(boxes) * 26 + lines * 16

    height = (14                                        # top padding
              + len(wrap(label, LABEL_CHARS)) * LABEL_LINE_H
              + len(wrap(detail, DETAIL_CHARS)) * DETAIL_LINE_H
              + 12)                                     # bottom padding
    # +20%: the exact-fit height above reads as cramped in the browser (first reported on
    # B2/"Dedupe") -- deliberate headroom on top of the reference project's own sizing, not
    # a port of it.
    return NW, max(NH, height * 1.2)


def layout(nodes, edges) -> dict[str, tuple[float, float, float, float]]:
    """Every block's (x, y, width, height), in pixels from the top-left."""
    pos: dict[str, tuple[float, float, float, float]] = {}

    seg = [n for n in nodes if n.get("region", "segmentation") == "segmentation"]
    jny = [n for n in nodes if n.get("region") == "journey"]

    panes = [n for n in seg if n["type"] == "note"]
    stops = [n for n in seg if n["type"] == "stop"]
    segments = [n for n in seg if n["type"] == "segment"]
    spine = [n for n in seg if n["type"] not in ("note", "stop", "segment")]

    spine_x = MARGIN + PANE_W + MARGIN
    y = TOP

    # The left pane is a caption beside the spine, not a step in it.
    left = next((p for p in panes if p["id"] == "pane.left"), None)
    if left is not None:
        w, h = size(left)
        pos[left["id"]] = (MARGIN, TOP, w, h)

    stop_source = {}
    for edge in edges:
        if edge.get("to") in {s["id"] for s in stops}:
            stop_source[edge["to"]] = edge.get("from")

    for node in spine:
        w, h = size(node)
        pos[node["id"]] = (spine_x + (NW - w) / 2, y, w, h)
        y += h + ROW_GAP

    # Stops sit level with the suppression that rejects to them.
    for stop in stops:
        w, h = size(stop)
        src = stop_source.get(stop["id"])
        sy = pos[src][1] + (pos[src][3] - h) / 2 if src in pos else TOP
        pos[stop["id"]] = (spine_x + NW + STOP_DX, sy, w, h)

    # The enrollment pane is drawn clear of the stop arms, unconnected.
    right = next((p for p in panes if p["id"] == "pane.right"), None)
    if right is not None:
        w, h = size(right)
        pos[right["id"]] = (spine_x + NW + STOP_DX + SW + MARGIN, TOP, w, h)

    for i, node in enumerate(segments):
        w, h = size(node)
        pos[node["id"]] = (spine_x + (i * COL_W) - (NW - w) / 2, y, w, h)
    if segments:
        y += NH + ROW_GAP

    # The journey region starts below everything the segmentation drew.
    y += ROW_GAP
    legend = next((n for n in jny if n["id"] == "pane.legend"), None)
    if legend is not None:
        w, h = size(legend)
        pos[legend["id"]] = (MARGIN, y, w, h)

    lanes: dict[str, list] = {}
    for node in jny:
        if node["id"] == "pane.legend":
            continue
        lanes.setdefault(node.get("lane") or "", []).append(node)

    # A resend hangs off its decision rather than sitting under it.
    has_resend = any(n["type"] == "resend" for n in jny)
    lane_w = (NW + RESEND_DX + NW + MARGIN) if has_resend else COL_W

    for i, (_lane, members) in enumerate(lanes.items()):
        ly = y
        lx = spine_x + i * lane_w
        by_id_lane = {n["id"]: n for n in members}
        for node in members:
            if node["type"] == "resend":
                continue                      # placed beside its decision below
            w, h = size(node)
            pos[node["id"]] = (lx + (NW - w) / 2, ly, w, h)

            # "jny.<segment>.tp3.q" is answered by "jny.<segment>.tp3.resend".
            if node["id"].endswith(".q"):
                resend = by_id_lane.get(node["id"][:-2] + ".resend")
                if resend is not None:
                    rw, rh = size(resend)
                    pos[resend["id"]] = (lx + NW + RESEND_DX,
                                         ly + (h - rh) / 2, rw, rh)
            ly += h + ROW_GAP

    return pos


def route(src, dst) -> list[tuple[float, float]]:
    """The waypoints an arrow follows, in layout pixels. Right-angled throughout."""
    sx, sy, sw, sh = src
    dx, dy, dw, dh = dst
    overlap = sy < dy + dh and dy < sy + sh

    if overlap and dx >= sx + sw:                    # side by side, target right
        start = (sx + sw, sy + sh / 2)
        end = (dx, dy + dh / 2)
    elif overlap and dx + dw <= sx:                  # side by side, target left
        start = (sx, sy + sh / 2)
        end = (dx + dw, dy + dh / 2)
    else:                                            # the usual case: downward
        start = (sx + sw / 2, sy + sh)
        end = (dx + dw / 2, dy)

    if abs(start[0] - end[0]) < 1 or abs(start[1] - end[1]) < 1:
        return [start, end]                          # already straight

    if start[1] == end[1] or overlap:
        # Sideways: out, along, in. The turn is halfway across.
        mid = (start[0] + end[0]) / 2
        return [start, (mid, start[1]), (mid, end[1]), end]

    # Downward: down, across, down. The turn is halfway between the two rows.
    mid = (start[1] + end[1]) / 2
    return [start, (start[0], mid), (end[0], mid), end]


def codes(nodes) -> dict[str, str]:
    """A short handle for every block, in reading order: B1, B2, B3..."""
    return {n["id"]: f"B{i}" for i, n in enumerate(nodes, start=1)}


def compact(pos) -> dict:
    """Shift a drawing to the top-left of its own canvas."""
    if not pos:
        return pos
    dx = MARGIN - min(x for x, _y, _w, _h in pos.values())
    dy = TOP - min(y for _x, y, _w, _h in pos.values())
    return {k: (x + dx, y + dy, w, h) for k, (x, y, w, h) in pos.items()}


def extent(pos) -> tuple[float, float]:
    """How much page the drawing needs, before any margin is added."""
    width = max([x + w for x, _y, w, _h in pos.values()] or [600])
    height = max([y + h for _x, y, _w, h in pos.values()] or [400])
    return width, height
