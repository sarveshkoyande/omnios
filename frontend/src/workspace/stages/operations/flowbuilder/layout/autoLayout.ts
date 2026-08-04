import ELK from "elkjs/lib/elk.bundled.js";
import type { ElkNode } from "elkjs/lib/elk-api";
import type { Page } from "../schema/document";
import type { Direction } from "../schema/document";
import type { WorkflowEdge } from "../schema/edge";
import type { WorkflowNode } from "../schema/node";

const elk = new ELK();

const DIRECTION_MAP: Record<Direction, string> = {
  TB: "DOWN",
  BT: "UP",
  LR: "RIGHT",
  RL: "LEFT",
};

const GRID = 40;
const NODE_CLEARANCE = 28;
const LANE_KINDS = new Set(["lane", "pool", "container", "list", "subgraph", "phase"]);

type Pt = { x: number; y: number };
type LayoutSpacing = {
  nodeNode: number;
  layer: number;
  edgeNode: number;
  edgeEdge: number;
  lane: number;
};
type Topology = {
  incoming: Map<string, WorkflowEdge[]>;
  outgoing: Map<string, WorkflowEdge[]>;
  nodeById: Map<string, WorkflowNode>;
};

const snap = (v: number) => Math.round(v / GRID) * GRID;
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

function labelOf(edge: WorkflowEdge): string {
  return `${edge.label ?? edge.labels?.map((l) => l.text).join(" ") ?? ""}`.toLowerCase();
}

function isRecoveryBranch(edge: WorkflowEdge): boolean {
  const label = labelOf(edge);
  return /\b(no|not|unopened|unengaged|didn'?t|non-open|non-click|false)\b/.test(label);
}

function isPositiveBranch(edge: WorkflowEdge): boolean {
  const label = labelOf(edge);
  return /\b(yes|opened|clicked|engaged|true)\b/.test(label);
}

function findEntryNode(layoutable: WorkflowNode[], topology: Topology): WorkflowNode | undefined {
  return (
    layoutable.find((n) => campaignKind(n) === "entry") ??
    layoutable.find((n) => n.type === "start" || n.type.startsWith("event.start")) ??
    layoutable.find((n) => (topology.incoming.get(n.id)?.length ?? 0) === 0) ??
    layoutable[0]
  );
}

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

function assignCampaignLanes(layoutable: WorkflowNode[], topology: Topology): Map<string, number> {
  const path = primaryPath(layoutable, topology);
  const pathIndex = new Map(path.map((id, i) => [id, i]));
  const lanes = new Map<string, number>();
  const start = path[0] ?? findEntryNode(layoutable, topology)?.id;
  if (!start) return lanes;

  const visit = (nodeId: string, lane: number) => {
    const currentLane = lanes.get(nodeId);
    if (currentLane != null) {
      if (Math.abs(lane) < Math.abs(currentLane)) lanes.set(nodeId, lane);
      return;
    }
    lanes.set(nodeId, lane);

    const outgoing = [...(topology.outgoing.get(nodeId) ?? [])].filter((e) => topology.nodeById.has(e.target.nodeId));
    if (outgoing.length === 0) return;

    const nextMain = pathIndex.has(nodeId)
      ? outgoing.find((e) => pathIndex.get(e.target.nodeId) === (pathIndex.get(nodeId) ?? -1) + 1)
      : undefined;
    const sideBranches = outgoing
      .filter((e) => e !== nextMain)
      .sort((a, b) => {
        const recoveryDelta = Number(isRecoveryBranch(b)) - Number(isRecoveryBranch(a));
        if (recoveryDelta !== 0) return recoveryDelta;
        return childScore(a, topology) - childScore(b, topology);
      });

    if (nextMain) visit(nextMain.target.nodeId, lane);

    const sideCounts = new Map<number, number>();
    sideBranches.forEach((edge) => {
      const side = isRecoveryBranch(edge) ? -1 : 1;
      const offset = (sideCounts.get(side) ?? 0) + 1;
      sideCounts.set(side, offset);
      visit(edge.target.nodeId, lane + side * offset);
    });
  };

  visit(start, 0);
  for (const node of layoutable) {
    if (!lanes.has(node.id)) lanes.set(node.id, 0);
  }
  return lanes;
}

function assignCampaignRows(layoutable: WorkflowNode[], topology: Topology): Map<string, number> {
  const start = findEntryNode(layoutable, topology);
  const rows = new Map<string, number>();
  if (!start) return rows;

  rows.set(start.id, 0);
  const queue = [start.id];
  const iterations = Math.max(1, layoutable.length * Math.max(1, topology.outgoing.size));
  let guard = 0;

  while (queue.length > 0 && guard < iterations) {
    guard += 1;
    const nodeId = queue.shift()!;
    const row = rows.get(nodeId) ?? 0;
    for (const edge of topology.outgoing.get(nodeId) ?? []) {
      if (!topology.nodeById.has(edge.target.nodeId)) continue;
      const nextRow = row + 1;
      if ((rows.get(edge.target.nodeId) ?? -1) >= nextRow) continue;
      rows.set(edge.target.nodeId, nextRow);
      queue.push(edge.target.nodeId);
    }
  }

  const sortedByElkY = [...layoutable].sort((a, b) => a.position.y - b.position.y);
  for (const node of sortedByElkY) {
    if (rows.has(node.id)) continue;
    const incomingRows = (topology.incoming.get(node.id) ?? [])
      .map((edge) => rows.get(edge.source.nodeId))
      .filter((row): row is number => row != null);
    rows.set(node.id, incomingRows.length ? Math.max(...incomingRows) + 1 : rows.size);
  }

  return rows;
}

function sourceOrderScore(edge: WorkflowEdge, topology: Topology): number {
  const target = topology.nodeById.get(edge.target.nodeId);
  const kind = target ? campaignKind(target) : "";
  if (isRecoveryBranch(edge)) return -2;
  if (kind === "followup") return -1;
  if (isPositiveBranch(edge)) return 1;
  return 0;
}

const elkPortId = (nodeId: string, portId: string) => `${nodeId}::${portId}`;
const PORT_SIDE_TO_ELK: Record<string, string> = { top: "NORTH", right: "EAST", bottom: "SOUTH", left: "WEST" };

function buildElkGraph(page: Page, layoutable: WorkflowNode[], topology: Topology, direction: Direction, spacing: LayoutSpacing): ElkNode {
  const lanes = page.groups.filter((g) => LANE_KINDS.has(g.kind));
  const laneOrder = new Map(lanes.map((g, i) => [g.id, g.order ?? i]));
  const partitioningActive = lanes.length > 0;
  const laneByNode = assignCampaignLanes(layoutable, topology);

  const children = [...layoutable]
    .sort((a, b) => (laneByNode.get(a.id) ?? 0) - (laneByNode.get(b.id) ?? 0))
    .map((n) => {
      const hasPorts = n.ports.length > 0;
      return {
        id: n.id,
        width: n.size.w,
        height: n.size.h,
        ports: hasPorts
          ? n.ports.map((p) => ({
              id: elkPortId(n.id, p.id),
              layoutOptions: { "elk.port.side": PORT_SIDE_TO_ELK[p.side] },
            }))
          : undefined,
        layoutOptions: {
          ...(hasPorts ? { "elk.portConstraints": "FIXED_SIDE" } : {}),
          ...(partitioningActive ? { "elk.partitioning.partition": String(n.groupId ? (laneOrder.get(n.groupId) ?? 0) + 1 : 0) } : {}),
        },
      };
    });

  const layoutableIds = new Set(layoutable.map((n) => n.id));
  const elkInputEdges = page.edges
    .filter((e) => layoutableIds.has(e.source.nodeId) && layoutableIds.has(e.target.nodeId))
    .sort((a, b) => sourceOrderScore(a, topology) - sourceOrderScore(b, topology))
    .map((e) => {
      const sourceNode = topology.nodeById.get(e.source.nodeId);
      const targetNode = topology.nodeById.get(e.target.nodeId);
      const sourcePort =
        e.source.glue === "static" && e.source.portId && sourceNode?.ports.some((p) => p.id === e.source.portId)
          ? elkPortId(e.source.nodeId, e.source.portId)
          : undefined;
      const targetPort =
        e.target.glue === "static" && e.target.portId && targetNode?.ports.some((p) => p.id === e.target.portId)
          ? elkPortId(e.target.nodeId, e.target.portId)
          : undefined;
      const labelText = e.label ?? e.labels?.[0]?.text;
      return {
        id: e.id,
        sources: [sourcePort ?? e.source.nodeId],
        targets: [targetPort ?? e.target.nodeId],
        ...(labelText ? { labels: [{ text: labelText, width: labelText.length * 7.5 + 30, height: 28 }] } : {}),
      };
    });

  return {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": DIRECTION_MAP[direction],
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.layered.unnecessaryBendpoints": "false",
      "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
      "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
      "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
      "elk.layered.mergeEdges": "false",
      "elk.spacing.nodeNode": String(spacing.nodeNode),
      "elk.layered.spacing.nodeNodeBetweenLayers": String(spacing.layer),
      "elk.spacing.edgeNode": String(spacing.edgeNode),
      "elk.spacing.edgeEdge": String(spacing.edgeEdge),
      "elk.layered.spacing.edgeNodeBetweenLayers": String(spacing.edgeNode + 8),
      "elk.layered.spacing.edgeEdgeBetweenLayers": String(spacing.edgeEdge),
      "elk.edgeLabels.placement": "CENTER",
      ...(partitioningActive ? { "elk.partitioning.activate": "true" } : {}),
    },
    children,
    edges: elkInputEdges,
  };
}

function optimizeCampaignReadability(page: Page, nodes: WorkflowNode[], edges: WorkflowEdge[], spacing: LayoutSpacing): WorkflowNode[] {
  const layoutable = nodes.filter((n) => n.type !== "comment" && n.type !== "text");
  const movable = layoutable.filter((n) => !n.pinned);
  const topology = buildTopology({ ...page, nodes, edges });
  const lanes = assignCampaignLanes(layoutable, topology);
  const rows = assignCampaignRows(layoutable, topology);
  if (lanes.size === 0) return nodes;

  const laneValues = Array.from(lanes.values());
  const minLane = Math.min(...laneValues);
  const maxLane = Math.max(...laneValues);
  if (minLane === 0 && maxLane === 0) return nodes;

  const laneSpacing = spacing.lane;
  const laneX = new Map<number, number>();
  for (let lane = minLane; lane <= maxLane; lane++) {
    laneX.set(lane, (lane - minLane) * laneSpacing + 80);
  }

  const byY = [...movable].sort((a, b) => a.position.y - b.position.y);
  const occupied = new Map<number, WorkflowNode[]>();
  const optimized = new Map<string, WorkflowNode>();
  const maxNodeH = Math.max(...layoutable.map((node) => node.size.h), 80);
  const rowSpacing = Math.max(150, maxNodeH + spacing.layer * 0.36);
  for (const node of byY) {
    const lane = lanes.get(node.id) ?? 0;
    let x = (laneX.get(lane) ?? node.position.x) + Math.max(0, laneSpacing - node.size.w) / 2;
    let y = 80 + (rows.get(node.id) ?? 0) * rowSpacing;
    const prior = occupied.get(lane) ?? [];
    for (const other of prior) {
      if (y < other.position.y + other.size.h + spacing.layer * 0.42) {
        y = other.position.y + other.size.h + spacing.layer * 0.42;
      }
    }
    const next = { ...node, position: { x: snap(x), y: snap(y) } };
    optimized.set(node.id, next);
    occupied.set(lane, [...prior, next]);
  }

  return nodes.map((node) => optimized.get(node.id) ?? node);
}

function endpointFor(node: WorkflowNode, other: WorkflowNode, source: boolean): Pt {
  const c = centerOf(node);
  const oc = centerOf(other);
  if (Math.abs(oc.x - c.x) > Math.abs(oc.y - c.y) * 1.25) {
    return { x: oc.x > c.x ? node.position.x + node.size.w : node.position.x, y: c.y };
  }
  return { x: c.x, y: source ? node.position.y + node.size.h : node.position.y };
}

function routeEdge(source: WorkflowNode, target: WorkflowNode, spacing: LayoutSpacing): Pt[] {
  const start = endpointFor(source, target, true);
  const end = endpointFor(target, source, false);
  const laneGap = Math.abs(centerOf(source).x - centerOf(target).x);
  if (laneGap < 10) return [];
  const midY = Math.max(start.y + spacing.layer * 0.42, (start.y + end.y) / 2);
  return [
    { x: start.x, y: midY },
    { x: end.x, y: midY },
  ];
}

function applyReadableRoutes(edges: WorkflowEdge[], nodes: WorkflowNode[], _elkEdgesById: Map<string, NonNullable<ElkNode["edges"]>[number]>, spacing: LayoutSpacing): WorkflowEdge[] {
  const nodeById = new Map(nodes.map((n) => [n.id, n]));
  return edges.map((edge) => {
    const source = nodeById.get(edge.source.nodeId);
    const target = nodeById.get(edge.target.nodeId);
    if (!source || !target || edge.line.routing === "curved") return edge;
    const semanticWaypoints = routeEdge(source, target, spacing);
    const waypoints = semanticWaypoints;
    return {
      ...edge,
      source: { ...edge.source, glue: "dynamic" as const },
      target: { ...edge.target, glue: "dynamic" as const },
      line: { ...edge.line, routing: "step" as const, waypoints },
    };
  });
}

function segmentIntersectsRect(a: Pt, b: Pt, rect: ReturnType<typeof boundsOf>): boolean {
  if (Math.abs(a.x - b.x) < 0.5) {
    const x = a.x;
    const top = Math.min(a.y, b.y);
    const bottom = Math.max(a.y, b.y);
    return x > rect.left && x < rect.right && bottom > rect.top && top < rect.bottom;
  }
  if (Math.abs(a.y - b.y) < 0.5) {
    const y = a.y;
    const left = Math.min(a.x, b.x);
    const right = Math.max(a.x, b.x);
    return y > rect.top && y < rect.bottom && right > rect.left && left < rect.right;
  }
  return false;
}

function routePoints(edge: WorkflowEdge, nodes: Map<string, WorkflowNode>): Pt[] {
  const source = nodes.get(edge.source.nodeId);
  const target = nodes.get(edge.target.nodeId);
  if (!source || !target) return [];
  return [endpointFor(source, target, true), ...edge.line.waypoints, endpointFor(target, source, false)];
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
    const points = routePoints(edge, nodeById);
    for (let i = 0; i < points.length - 1; i++) {
      for (const node of layoutable) {
        if (node.id === edge.source.nodeId || node.id === edge.target.nodeId) continue;
        if (segmentIntersectsRect(points[i], points[i + 1], boundsOf(node, 10))) return true;
      }
    }
  }
  return false;
}

function spacingFor(page: Page, attempt: number): LayoutSpacing {
  const nodeCount = page.nodes.length;
  const large = nodeCount > 150;
  const multiplier = 1 + attempt * 0.22 + (large ? 0.25 : 0);
  return {
    nodeNode: Math.round(72 * multiplier),
    layer: Math.round(120 * multiplier),
    edgeNode: Math.round(38 * multiplier),
    edgeEdge: Math.round(44 * multiplier),
    lane: Math.round(240 * multiplier),
  };
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
        x: snap(minX - PAD),
        y: snap(minY - PAD - HEADER),
        w: snap(maxX - minX + PAD * 2),
        h: snap(maxY - minY + PAD * 2 + HEADER),
      },
    };
  });
}

export async function autoLayoutPage(page: Page, direction: Direction): Promise<Page> {
  const layoutable = page.nodes.filter((n) => n.type !== "comment" && n.type !== "text" && !n.pinned);
  if (layoutable.length === 0) return page;

  let best = page;
  for (let attempt = 0; attempt < 4; attempt++) {
    const spacing = spacingFor(page, attempt);
    const topology = buildTopology(page);
    const graph = buildElkGraph(page, layoutable, topology, direction, spacing);
    const result = await elk.layout(graph);
    const posById = new Map((result.children ?? []).map((c) => [c.id, { x: c.x ?? 0, y: c.y ?? 0 }]));

    const elkNodes = page.nodes.map((node) => {
      if (node.pinned) return node;
      const pos = posById.get(node.id);
      return pos ? { ...node, position: { x: pos.x, y: pos.y } } : node;
    });
    const optimizedNodes = optimizeCampaignReadability(page, elkNodes, page.edges, spacing);
    const elkEdgeById = new Map((result.edges ?? []).map((edge) => [edge.id, edge]));
    const optimizedEdges = applyReadableRoutes(page.edges, optimizedNodes, elkEdgeById, spacing);
    best = { ...page, nodes: optimizedNodes, edges: optimizedEdges, groups: resizeGroups(page, optimizedNodes) };
    if (!hasQualityIssues(optimizedNodes, optimizedEdges)) return best;
  }

  return best;
}
