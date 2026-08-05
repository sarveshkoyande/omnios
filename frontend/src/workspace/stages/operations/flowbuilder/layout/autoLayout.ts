import dagre from "@dagrejs/dagre";
import type { Page } from "../schema/document";
import type { Direction } from "../schema/document";
import type { WorkflowEdge } from "../schema/edge";
import type { WorkflowNode } from "../schema/node";

/**
 * Layered layout for the flow builder, on dagre.
 *
 * Why dagre and not ELK (what this file used before): the campaign brief's journey picture
 * (strategy/journey_brief.py -> mermaid.ink) is a Mermaid flowchart, and Mermaid lays its
 * flowcharts out with dagre. Running the same engine here is what makes the editable
 * diagram come out looking like the picture on the brief instead of a second, unrelated
 * drawing of the same graph. The old implementation ran ELK and then overwrote every
 * coordinate it produced with a hand-rolled lane/row grid, which is what made branches
 * pile up on top of each other.
 *
 * Three things are layered on top of plain dagre, all of them shape-preserving:
 *  1. model order — a node's outgoing edges are handed to dagre recovery-branch first,
 *     main-path second, everything else last, so dagre's initial ordering puts
 *     "didn't open / didn't click" arms on the left and the positive arms on the right.
 *  2. edge weight — the main path is weighted heavily, which is dagre's own lever for
 *     "keep this chain short and vertically aligned".
 *  3. a trunk pass — the main path is then snapped to one exact x, and each rank is
 *     repacked outwards from it. This is a local nudge on dagre's result, not a
 *     replacement for it: rank assignment and left-to-right order stay dagre's.
 *
 * Edges carry no waypoints. The renderer (edges/WorkflowEdge.tsx) already draws an
 * orthogonal stub-bridge-stub path between the glued sides, and stored waypoints only go
 * stale the moment a node moves.
 */

const LANE_KINDS = new Set(["lane", "pool", "container", "list", "subgraph", "phase"]);
/** Clearance two boxes must keep before the layout counts as unreadable and retries wider. */
const NODE_CLEARANCE = 20;
/** Must match the stub length in edges/WorkflowEdge.tsx, or the quality check tests a
 *  different path from the one the user sees. */
const EDGE_STUB = 34;
const MARGIN = 48;

type Pt = { x: number; y: number };
type Side = "top" | "right" | "bottom" | "left";
type LayoutSpacing = { nodeSep: number; rankSep: number; edgeSep: number };
type Topology = {
  incoming: Map<string, WorkflowEdge[]>;
  outgoing: Map<string, WorkflowEdge[]>;
  nodeById: Map<string, WorkflowNode>;
};

const centerOf = (n: WorkflowNode): Pt => ({ x: n.position.x + n.size.w / 2, y: n.position.y + n.size.h / 2 });

const fieldValue = (n: WorkflowNode, key: string): unknown => {
  const field = n.data?.[key];
  return field && typeof field === "object" && "value" in field ? field.value : null;
};

const campaignKind = (n: WorkflowNode): string => String(fieldValue(n, "campaignStepKind") ?? "");

function boundsOf(n: WorkflowNode, pad = 0) {
  return {
    left: n.position.x - pad,
    top: n.position.y - pad,
    right: n.position.x + n.size.w + pad,
    bottom: n.position.y + n.size.h + pad,
  };
}

function overlaps(a: WorkflowNode, b: WorkflowNode, pad = NODE_CLEARANCE): boolean {
  const ab = boundsOf(a, pad);
  const bb = boundsOf(b, pad);
  return !(ab.right <= bb.left || bb.right <= ab.left || ab.bottom <= bb.top || bb.bottom <= ab.top);
}

function buildTopology(page: Page): Topology {
  const nodeById = new Map(page.nodes.map((n) => [n.id, n]));
  const incoming = new Map<string, WorkflowEdge[]>();
  const outgoing = new Map<string, WorkflowEdge[]>();
  for (const node of page.nodes) {
    incoming.set(node.id, []);
    outgoing.set(node.id, []);
  }
  for (const edge of page.edges) {
    if (!nodeById.has(edge.source.nodeId) || !nodeById.has(edge.target.nodeId)) continue;
    incoming.get(edge.target.nodeId)?.push(edge);
    outgoing.get(edge.source.nodeId)?.push(edge);
  }
  return { incoming, outgoing, nodeById };
}

/* ------------------------------------------------------------------ main path --- */

function labelOf(edge: WorkflowEdge): string {
  return `${edge.label ?? edge.labels?.map((l) => l.text).join(" ") ?? ""}`.toLowerCase();
}

function isRecoveryBranch(edge: WorkflowEdge): boolean {
  return /\b(no|not|unopened|unengaged|didn'?t|non-open|non-click|false)\b/.test(labelOf(edge));
}

function isPositiveBranch(edge: WorkflowEdge): boolean {
  return /\b(yes|opened|clicked|engaged|true)\b/.test(labelOf(edge));
}

function findEntryNode(layoutable: WorkflowNode[], topology: Topology): WorkflowNode | undefined {
  return (
    layoutable.find((n) => campaignKind(n) === "entry") ??
    layoutable.find((n) => n.type === "start" || n.type.startsWith("event.start")) ??
    layoutable.find((n) => (topology.incoming.get(n.id)?.length ?? 0) === 0) ??
    layoutable[0]
  );
}

/** How much a branch looks like the journey's spine rather than a side arm. */
function childScore(edge: WorkflowEdge, topology: Topology): number {
  const target = topology.nodeById.get(edge.target.nodeId);
  const kind = target ? campaignKind(target) : "";
  let score = 0;
  if (isPositiveBranch(edge)) score += 80;
  if (isRecoveryBranch(edge)) score -= 60;
  if (kind === "send" || kind === "wait" || kind === "decision" || kind === "branch") score += 20;
  if (kind === "followup") score -= 10;
  if (target?.type === "end") score -= 140;
  return score;
}

/** The trunk: entry, then the highest-scoring child at every step, until it repeats or ends. */
function primaryPath(layoutable: WorkflowNode[], topology: Topology): string[] {
  const start = findEntryNode(layoutable, topology);
  if (!start) return [];
  const path: string[] = [];
  const seen = new Set<string>();
  let current: WorkflowNode | undefined = start;

  while (current && !seen.has(current.id) && path.length <= layoutable.length) {
    seen.add(current.id);
    path.push(current.id);
    const choices = [...(topology.outgoing.get(current.id) ?? [])]
      .filter((e) => topology.nodeById.has(e.target.nodeId))
      .sort((a, b) => childScore(b, topology) - childScore(a, topology));
    current = choices.length ? topology.nodeById.get(choices[0].target.nodeId) : undefined;
  }
  return path;
}

/* ---------------------------------------------------------------- dagre graph --- */

/** Left-to-right intent for a node's outgoing edges. dagre seeds its first ordering from
 *  insertion order, so this is what decides which side a fan-out lands on. */
function fanOrder(edge: WorkflowEdge, isTrunk: boolean, topology: Topology): number {
  if (isRecoveryBranch(edge)) return -2;
  if (isTrunk) return 0;
  if (isPositiveBranch(edge)) return 2;
  const target = topology.nodeById.get(edge.target.nodeId);
  return target && campaignKind(target) === "followup" ? -1 : 1;
}

/** Edges in the order dagre should see them: breadth-first from the entry node, and within
 *  each node ordered left arm -> trunk -> right arm. */
function orderedEdges(layoutable: WorkflowNode[], topology: Topology, trunkEdges: Set<string>): WorkflowEdge[] {
  const start = findEntryNode(layoutable, topology);
  const out: WorkflowEdge[] = [];
  const emitted = new Set<string>();
  const visited = new Set<string>();
  const queue = start ? [start.id] : [];

  const emitFrom = (nodeId: string) => {
    const edges = [...(topology.outgoing.get(nodeId) ?? [])]
      .filter((e) => topology.nodeById.has(e.target.nodeId))
      .sort((a, b) => fanOrder(a, trunkEdges.has(a.id), topology) - fanOrder(b, trunkEdges.has(b.id), topology));
    for (const edge of edges) {
      if (emitted.has(edge.id)) continue;
      emitted.add(edge.id);
      out.push(edge);
      if (!visited.has(edge.target.nodeId)) {
        visited.add(edge.target.nodeId);
        queue.push(edge.target.nodeId);
      }
    }
  };

  if (start) visited.add(start.id);
  while (queue.length > 0) emitFrom(queue.shift()!);
  // Anything unreachable from the entry node still has to be laid out.
  for (const node of layoutable) emitFrom(node.id);
  return out;
}

function edgeLabelBox(edge: WorkflowEdge): { width: number; height: number } | null {
  const text = edge.label ?? edge.labels?.[0]?.text ?? "";
  if (!text) return null;
  return { width: Math.min(220, text.length * 7 + 16), height: 22 };
}

type Placement = Map<string, Pt>;
type DagreResult = { placement: Placement; bends: Map<string, Pt[]> };

function runDagre(
  layoutable: WorkflowNode[],
  topology: Topology,
  direction: Direction,
  spacing: LayoutSpacing,
  trunkEdges: Set<string>,
): DagreResult {
  const graph = new dagre.graphlib.Graph({ multigraph: true });
  graph.setGraph({
    rankdir: direction,
    nodesep: spacing.nodeSep,
    ranksep: spacing.rankSep,
    edgesep: spacing.edgeSep,
    marginx: MARGIN,
    marginy: MARGIN,
    ranker: "network-simplex",
  });
  graph.setDefaultEdgeLabel(() => ({}));

  for (const node of layoutable) {
    graph.setNode(node.id, { width: node.size.w, height: node.size.h });
  }

  for (const edge of orderedEdges(layoutable, topology, trunkEdges)) {
    const box = edgeLabelBox(edge);
    const fansOut = (topology.outgoing.get(edge.source.nodeId)?.length ?? 0) > 1;
    graph.setEdge(
      edge.source.nodeId,
      edge.target.nodeId,
      {
        // dagre keeps heavy edges short and, in its x-coordinate pass, prefers to align
        // them. Heaviest on the trunk is "the trunk runs straight down"; heavy on the arms
        // of a fan-out is "the arms sit on the row directly under their gate, side by
        // side" — without it an arm whose own next step is far downstream slides down the
        // page and stops reading as one of the choices at that gate.
        weight: trunkEdges.has(edge.id) ? 16 : fansOut ? 8 : 2,
        minlen: 1,
        ...(box ? { ...box, labelpos: "c" as const, labeloffset: 8 } : {}),
      },
      edge.id,
    );
  }

  dagre.layout(graph);

  const placement: Placement = new Map();
  for (const node of layoutable) {
    const laid = graph.node(node.id) as { x?: number; y?: number } | undefined;
    if (!laid || laid.x == null || laid.y == null) continue;
    placement.set(node.id, { x: laid.x, y: laid.y });
  }

  // dagre threads an edge that skips ranks through a chain of dummy nodes, and reserves
  // the horizontal space for it. Those are the bend points that let a long connector pass
  // between the boxes on the ranks it crosses instead of straight through them; the first
  // and last are on the node borders, which the renderer computes itself.
  const bends = new Map<string, Pt[]>();
  for (const key of graph.edges()) {
    if (!key.name) continue;
    const laid = graph.edge(key) as { points?: Pt[] } | undefined;
    const points = laid?.points;
    if (!points || points.length <= 2) continue;
    bends.set(key.name, points.slice(1, -1).map((p) => ({ x: p.x, y: p.y })));
  }

  return { placement, bends };
}

/* ----------------------------------------------------------------- trunk pass --- */

const isVertical = (direction: Direction) => direction === "TB" || direction === "BT";

/** Snap the main path onto one line and repack every rank outwards from it, so side
 *  branches sit beside the trunk instead of nudging it off-centre. */
function straightenTrunk(
  placement: Placement,
  layoutable: WorkflowNode[],
  path: string[],
  direction: Direction,
  spacing: LayoutSpacing,
): Placement {
  const vertical = isVertical(direction);
  const cross = (p: Pt) => (vertical ? p.x : p.y);
  const along = (p: Pt) => (vertical ? p.y : p.x);
  const sizeCross = (n: WorkflowNode) => (vertical ? n.size.w : n.size.h);

  const onPath = path.filter((id) => placement.has(id));
  if (onPath.length < 2) return placement;

  const trunkCoords = onPath.map((id) => cross(placement.get(id)!)).sort((a, b) => a - b);
  const trunkCoord = trunkCoords[Math.floor(trunkCoords.length / 2)];
  const trunkSet = new Set(onPath);

  const ranks = new Map<number, WorkflowNode[]>();
  for (const node of layoutable) {
    const pos = placement.get(node.id);
    if (!pos) continue;
    const key = Math.round(along(pos));
    ranks.set(key, [...(ranks.get(key) ?? []), node]);
  }

  const next: Placement = new Map(placement);
  for (const members of ranks.values()) {
    const trunkMember = members.find((n) => trunkSet.has(n.id));
    if (!trunkMember) continue;

    const row = [...members].sort((a, b) => cross(placement.get(a.id)!) - cross(placement.get(b.id)!));
    const coords = row.map((n) => cross(placement.get(n.id)!));
    const pivot = row.indexOf(trunkMember);
    coords[pivot] = trunkCoord;

    for (let i = pivot - 1; i >= 0; i--) {
      const ceiling = coords[i + 1] - sizeCross(row[i + 1]) / 2 - spacing.nodeSep - sizeCross(row[i]) / 2;
      coords[i] = Math.min(coords[i], ceiling);
    }
    for (let i = pivot + 1; i < row.length; i++) {
      const floor = coords[i - 1] + sizeCross(row[i - 1]) / 2 + spacing.nodeSep + sizeCross(row[i]) / 2;
      coords[i] = Math.max(coords[i], floor);
    }

    row.forEach((node, i) => {
      const pos = next.get(node.id)!;
      next.set(node.id, vertical ? { x: coords[i], y: pos.y } : { x: pos.x, y: coords[i] });
    });
  }

  return next;
}

/** dagre centres; the document stores top-left. Also re-origins the drawing at the margin
 *  so the trunk pass can't leave the diagram sitting at negative coordinates. */
function applyPlacement(nodes: WorkflowNode[], placement: Placement): { nodes: WorkflowNode[]; shift: Pt } {
  const placed = nodes.filter((n) => placement.has(n.id));
  if (placed.length === 0) return { nodes, shift: { x: 0, y: 0 } };

  const lefts = placed.map((n) => placement.get(n.id)!.x - n.size.w / 2);
  const tops = placed.map((n) => placement.get(n.id)!.y - n.size.h / 2);
  const shift = { x: MARGIN - Math.min(...lefts), y: MARGIN - Math.min(...tops) };

  const positioned = nodes.map((node) => {
    const center = placement.get(node.id);
    if (!center) return node;
    return {
      ...node,
      position: {
        x: Math.round(center.x - node.size.w / 2 + shift.x),
        y: Math.round(center.y - node.size.h / 2 + shift.y),
      },
    };
  });
  return { nodes: positioned, shift };
}

/* -------------------------------------------------------------- quality check --- */

/** The side canvas/glue.ts will glue this end of the connector to. */
function gluedSide(node: WorkflowNode, other: WorkflowNode): Side {
  const a = boundsOf(node);
  const b = boundsOf(other);
  if (b.top >= a.bottom) return "bottom";
  if (b.bottom <= a.top) return "top";
  if (b.left >= a.right) return "right";
  if (b.right <= a.left) return "left";
  const ca = centerOf(node);
  const cb = centerOf(other);
  return Math.abs(cb.x - ca.x) > Math.abs(cb.y - ca.y) ? (cb.x > ca.x ? "right" : "left") : cb.y > ca.y ? "bottom" : "top";
}

function anchorOn(node: WorkflowNode, side: Side): Pt {
  const c = centerOf(node);
  const b = boundsOf(node);
  if (side === "top") return { x: c.x, y: b.top };
  if (side === "bottom") return { x: c.x, y: b.bottom };
  if (side === "left") return { x: b.left, y: c.y };
  return { x: b.right, y: c.y };
}

const SIDE_VECTOR: Record<Side, Pt> = {
  top: { x: 0, y: -1 },
  bottom: { x: 0, y: 1 },
  left: { x: -1, y: 0 },
  right: { x: 1, y: 0 },
};

/** Squares off a run of points the way edges/WorkflowEdge.tsx does before drawing it. */
function orthogonalize(points: Pt[]): Pt[] {
  if (points.length <= 2) return points;
  const out: Pt[] = [points[0]];
  for (let i = 1; i < points.length; i++) {
    const a = out[out.length - 1];
    const b = points[i];
    if (Math.abs(a.x - b.x) < 0.5 || Math.abs(a.y - b.y) < 0.5) {
      out.push(b);
      continue;
    }
    out.push({ x: a.x, y: b.y }, b);
  }
  return out;
}

/** The polyline edges/WorkflowEdge.tsx will draw for this edge. */
function renderedPolyline(source: WorkflowNode, target: WorkflowNode, waypoints: Pt[] = []): Pt[] {
  const sourceSide = gluedSide(source, target);
  const targetSide = gluedSide(target, source);
  const start = anchorOn(source, sourceSide);
  const end = anchorOn(target, targetSide);
  const sv = SIDE_VECTOR[sourceSide];
  const tv = SIDE_VECTOR[targetSide];
  const startStub = { x: start.x + sv.x * EDGE_STUB, y: start.y + sv.y * EDGE_STUB };
  const endStub = { x: end.x + tv.x * EDGE_STUB, y: end.y + tv.y * EDGE_STUB };

  if (waypoints.length > 0) return orthogonalize([start, startStub, ...waypoints, endStub, end]);

  const bridge: Pt[] = [];
  const aligned = Math.abs(startStub.x - endStub.x) < 0.5 || Math.abs(startStub.y - endStub.y) < 0.5;
  if (!aligned) {
    const sourceVertical = sv.y !== 0;
    const targetVertical = tv.y !== 0;
    if (sourceVertical && targetVertical) {
      const midY = (startStub.y + endStub.y) / 2;
      bridge.push({ x: startStub.x, y: midY }, { x: endStub.x, y: midY });
    } else if (!sourceVertical && !targetVertical) {
      const midX = (startStub.x + endStub.x) / 2;
      bridge.push({ x: midX, y: startStub.y }, { x: midX, y: endStub.y });
    } else if (sourceVertical) {
      bridge.push({ x: startStub.x, y: endStub.y });
    } else {
      bridge.push({ x: endStub.x, y: startStub.y });
    }
  }
  return [start, startStub, ...bridge, endStub, end];
}

function segmentIntersectsRect(a: Pt, b: Pt, rect: ReturnType<typeof boundsOf>): boolean {
  if (Math.abs(a.x - b.x) < 0.5) {
    const top = Math.min(a.y, b.y);
    const bottom = Math.max(a.y, b.y);
    return a.x > rect.left && a.x < rect.right && bottom > rect.top && top < rect.bottom;
  }
  if (Math.abs(a.y - b.y) < 0.5) {
    const left = Math.min(a.x, b.x);
    const right = Math.max(a.x, b.x);
    return a.y > rect.top && a.y < rect.bottom && right > rect.left && left < rect.right;
  }
  return false;
}

function hasQualityIssues(nodes: WorkflowNode[], edges: WorkflowEdge[]): boolean {
  const layoutable = nodes.filter((n) => n.type !== "comment" && n.type !== "text");
  for (let i = 0; i < layoutable.length; i++) {
    for (let j = i + 1; j < layoutable.length; j++) {
      if (overlaps(layoutable[i], layoutable[j])) return true;
    }
  }

  const nodeById = new Map(nodes.map((n) => [n.id, n]));
  for (const edge of edges) {
    const source = nodeById.get(edge.source.nodeId);
    const target = nodeById.get(edge.target.nodeId);
    if (!source || !target) continue;
    const points = renderedPolyline(source, target, edge.line.waypoints);
    for (let i = 0; i < points.length - 1; i++) {
      for (const node of layoutable) {
        if (node.id === edge.source.nodeId || node.id === edge.target.nodeId) continue;
        if (segmentIntersectsRect(points[i], points[i + 1], boundsOf(node, 8))) return true;
      }
    }
  }
  return false;
}

/* --------------------------------------------------------------------- output --- */

/**
 * An edge between neighbouring ranks stores no bend points at all: the renderer's own
 * stub-bridge-stub route through the empty band between the two ranks is already the right
 * line, and a stored point would only go stale as soon as a node moved. An edge that skips
 * ranks does store dagre's bend points, because the straight route would cut through
 * whatever sits on the ranks in between.
 */
function routeEdges(
  edges: WorkflowEdge[],
  bends: Map<string, Pt[]>,
  rankIndex: Map<string, number>,
  shift: Pt,
): WorkflowEdge[] {
  return edges.map((edge) => {
    if (edge.line.routing === "curved") return edge;
    const from = rankIndex.get(edge.source.nodeId);
    const to = rankIndex.get(edge.target.nodeId);
    const skipsRanks = from != null && to != null && Math.abs(to - from) > 1;
    const waypoints = skipsRanks
      ? (bends.get(edge.id) ?? []).map((p) => ({ x: Math.round(p.x + shift.x), y: Math.round(p.y + shift.y) }))
      : [];
    return {
      ...edge,
      source: { ...edge.source, glue: "dynamic" as const },
      target: { ...edge.target, glue: "dynamic" as const },
      line: { ...edge.line, routing: "step" as const, waypoints },
    };
  });
}

/** Which layer of the drawing a node landed on, counting from the entry rank. */
function rankIndexOf(placement: Placement, direction: Direction): Map<string, number> {
  const along = (p: Pt) => (isVertical(direction) ? p.y : p.x);
  const coords = [...new Set([...placement.values()].map((p) => Math.round(along(p))))].sort((a, b) => a - b);
  const order = new Map(coords.map((c, i) => [c, i]));
  const index = new Map<string, number>();
  for (const [id, point] of placement) index.set(id, order.get(Math.round(along(point))) ?? 0);
  return index;
}

function resizeGroups(page: Page, nodes: WorkflowNode[]): Page["groups"] {
  const PAD = 48;
  const HEADER = 36;
  return page.groups.map((g) => {
    if (!LANE_KINDS.has(g.kind) || g.memberBehavior?.autoResize === false) return g;
    const members = nodes.filter((n) => n.groupId === g.id);
    if (members.length === 0) return g;
    const minX = Math.min(...members.map((n) => n.position.x));
    const minY = Math.min(...members.map((n) => n.position.y));
    const maxX = Math.max(...members.map((n) => n.position.x + n.size.w));
    const maxY = Math.max(...members.map((n) => n.position.y + n.size.h));
    return {
      ...g,
      bounds: {
        x: Math.round(minX - PAD),
        y: Math.round(minY - PAD - HEADER),
        w: Math.round(maxX - minX + PAD * 2),
        h: Math.round(maxY - minY + PAD * 2 + HEADER),
      },
    };
  });
}

function spacingFor(page: Page, attempt: number): LayoutSpacing {
  const dense = page.nodes.length > 80;
  const multiplier = 1 + attempt * 0.28 + (dense ? 0.2 : 0);
  return {
    nodeSep: Math.round(72 * multiplier),
    rankSep: Math.round(104 * multiplier),
    edgeSep: Math.round(26 * multiplier),
  };
}

export async function autoLayoutPage(page: Page, direction: Direction): Promise<Page> {
  const layoutable = page.nodes.filter((n) => n.type !== "comment" && n.type !== "text" && !n.pinned);
  if (layoutable.length === 0) return page;

  const topology = buildTopology(page);
  const path = primaryPath(layoutable, topology);
  const trunkEdges = new Set(
    page.edges
      .filter((e) => {
        const from = path.indexOf(e.source.nodeId);
        return from >= 0 && path[from + 1] === e.target.nodeId;
      })
      .map((e) => e.id),
  );

  let best: Page = page;

  for (let attempt = 0; attempt < 4; attempt++) {
    const spacing = spacingFor(page, attempt);
    const { placement, bends } = runDagre(layoutable, topology, direction, spacing, trunkEdges);
    if (placement.size === 0) return page;
    const straightened = straightenTrunk(placement, layoutable, path, direction, spacing);
    const { nodes, shift } = applyPlacement(page.nodes, straightened);
    const edges = routeEdges(page.edges, bends, rankIndexOf(placement, direction), shift);
    best = { ...page, nodes, edges, groups: resizeGroups(page, nodes) };
    if (!hasQualityIssues(nodes, edges)) return best;
  }

  return best;
}
