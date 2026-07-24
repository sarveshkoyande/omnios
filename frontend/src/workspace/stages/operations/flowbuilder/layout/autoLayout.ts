import ELK from "elkjs/lib/elk.bundled.js";
import type { ElkNode } from "elkjs/lib/elk-api";
import type { Page } from "../schema/document";
import type { Direction } from "../schema/document";

// Section 4: "Auto-layout button (layered/Dagre-style for TB/LR...) that respects lanes;
// manual positions preserved otherwise (hybrid: 'pin' flag per node)." Implemented with
// elkjs's layered algorithm. Lanes become ELK partitions: activating
// elk.partitioning.activate constrains nodes to ranks in ascending partition order along
// the main layout axis, which for a TB document renders as horizontal bands stacked in
// lane.order — i.e. exactly a lane arrangement — and for LR renders as side-by-side pools.

const elk = new ELK();

const DIRECTION_MAP: Record<Direction, string> = {
  TB: "DOWN",
  BT: "UP",
  LR: "RIGHT",
  RL: "LEFT",
};

const GRID = 40;
const snap = (v: number) => Math.round(v / GRID) * GRID;

// ELK port ids must be globally unique across the whole graph, so each schema
// port id (stable but only unique per-node, e.g. "yes"/"no") is namespaced
// under its owning node.
const elkPortId = (nodeId: string, portId: string) => `${nodeId}::${portId}`;

const PORT_SIDE_TO_ELK: Record<string, string> = { top: "NORTH", right: "EAST", bottom: "SOUTH", left: "WEST" };
const MIN_NODE_GAP = 36;

type PageNode = Page["nodes"][number];

function overlapsWithPadding(a: PageNode, b: PageNode): boolean {
  return !(
    a.position.x + a.size.w + MIN_NODE_GAP <= b.position.x ||
    b.position.x + b.size.w + MIN_NODE_GAP <= a.position.x ||
    a.position.y + a.size.h + MIN_NODE_GAP <= b.position.y ||
    b.position.y + b.size.h + MIN_NODE_GAP <= a.position.y
  );
}

function separateOverlappingNodes(nodes: Page["nodes"]): { nodes: Page["nodes"]; movedIds: Set<string> } {
  const placed: PageNode[] = [];
  const movedIds = new Set<string>();

  for (const node of nodes) {
    let current = node;
    if (!node.pinned && node.type !== "comment" && node.type !== "text") {
      let guard = 0;
      let shifted = true;
      while (shifted && guard < 200) {
        shifted = false;
        for (const other of placed) {
          if (other.type === "comment" || other.type === "text") continue;
          if (!overlapsWithPadding(current, other)) continue;
          current = {
            ...current,
            position: {
              ...current.position,
              y: Math.max(current.position.y, other.position.y + other.size.h + MIN_NODE_GAP),
            },
          };
          movedIds.add(current.id);
          shifted = true;
        }
        guard += 1;
      }
    }
    placed.push(current);
  }

  return { nodes: placed, movedIds };
}

export async function autoLayoutPage(page: Page, direction: Direction): Promise<Page> {
  const laneKinds = new Set(["lane", "pool", "container", "list", "subgraph", "phase"]);
  const lanes = page.groups.filter((g) => laneKinds.has(g.kind));
  const laneOrder = new Map(lanes.map((g, i) => [g.id, g.order ?? i]));
  const partitioningActive = lanes.length > 0;

  const layoutable = page.nodes.filter((n) => n.type !== "comment" && n.type !== "text");

  // A "static"-glued edge is hard-pinned to a specific side of its node (e.g. a
  // decision's "yes" port always exits its right side) -- if ELK is left free to
  // place the target anywhere, that fixed exit side combined with orthogonal edge
  // routing produces long loop-around paths. Telling ELK about each node's real
  // ports (elk.portConstraints: FIXED_SIDE) makes it rank/order nodes consistent
  // with the side they must actually connect through. Dynamic-glue edges legitimately
  // re-pick their best-facing port after layout (glue.ts's pickDynamicPort), so they
  // aren't given a fixed port here.
  const children = layoutable.map((n) => {
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
  const nodeById = new Map(layoutable.map((n) => [n.id, n]));
  const elkInputEdges = page.edges
    .filter((e) => layoutableIds.has(e.source.nodeId) && layoutableIds.has(e.target.nodeId))
    .map((e) => {
      const sourceNode = nodeById.get(e.source.nodeId);
      const targetNode = nodeById.get(e.target.nodeId);
      const sourcePort =
        e.source.glue === "static" && e.source.portId && sourceNode?.ports.some((p) => p.id === e.source.portId)
          ? elkPortId(e.source.nodeId, e.source.portId)
          : undefined;
      const targetPort =
        e.target.glue === "static" && e.target.portId && targetNode?.ports.some((p) => p.id === e.target.portId)
          ? elkPortId(e.target.nodeId, e.target.portId)
          : undefined;
      // Tell ELK about the edge's own label geometry (it has no idea otherwise --
      // WorkflowEdge.tsx renders labels independently at render time). Without
      // this, ELK only keeps bare lines from touching, which isn't enough
      // clearance for a full pill label sitting just off the edge midpoint --
      // several edges fanning out of the same node then get close enough that
      // their labels stack and overlap even though the lines themselves don't.
      const labelText = e.label ?? e.labels?.[0]?.text;
      return {
        id: e.id,
        sources: [sourcePort ?? e.source.nodeId],
        targets: [targetPort ?? e.target.nodeId],
        ...(labelText ? { labels: [{ text: labelText, width: labelText.length * 7.5 + 24, height: 24 }] } : {}),
      };
    });

  const graph: ElkNode = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": DIRECTION_MAP[direction],
      // Route edges as orthogonal polylines during layout itself (not left to each
      // edge to guess independently at render time) -- this is what actually keeps
      // lines from criss-crossing through boxes and each other; see the bend-point
      // capture below.
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.layered.unnecessaryBendpoints": "false",
      "elk.spacing.nodeNode": "72",
      "elk.layered.spacing.nodeNodeBetweenLayers": "120",
      // elk.spacing.edgeEdge/edgeEdgeBetweenLayers is how far apart two
      // near-parallel edge tracks sit -- it needs to clear a full label's
      // height (our labels render as 24px-ish pills offset off the midpoint), not just
      // enough to keep the lines themselves from touching. The bunched-up
      // fan-out + overlapping label text was this being too tight, not the
      // earlier (now-fixed) grid-snap mismatch, which was a separate bug.
      "elk.spacing.edgeNode": "34",
      "elk.spacing.edgeEdge": "42",
      "elk.layered.spacing.edgeNodeBetweenLayers": "38",
      "elk.layered.spacing.edgeEdgeBetweenLayers": "42",
      "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
      "elk.edgeLabels.placement": "CENTER",
      ...(partitioningActive ? { "elk.partitioning.activate": "true" } : {}),
    },
    children,
    edges: elkInputEdges,
  };

  const result = await elk.layout(graph);
  const posById = new Map((result.children ?? []).map((c) => [c.id, { x: c.x ?? 0, y: c.y ?? 0 }]));

  // Not grid-snapped, for the same reason the waypoints above aren't: ELK's
  // node positions and its edge routing were computed together as one
  // consistent layout. Snapping only the node afterward -- independent of the
  // edges already routed against its real position -- shifts it by up to
  // half a grid cell away from where its own edges assume it sits, which is
  // exactly what produced the little jogs right at the box boundary. Manual
  // drags still snap to grid (Canvas.tsx's own snapGrid); this is layout-only.
  const laidOutNodes = page.nodes.map((n) => {
    if (n.pinned) return n; // manual positions preserved for pinned nodes
    const pos = posById.get(n.id);
    if (!pos) return n;
    return { ...n, position: { x: pos.x, y: pos.y } };
  });
  const { nodes, movedIds } = separateOverlappingNodes(laidOutNodes);

  // ELK already worked out a clean bend-point route per edge that keeps clear of
  // node bodies and (as much as the layered algorithm can) other edges. Previously
  // this route was thrown away and every edge re-routed itself independently at
  // render time -- exactly what produced the criss-crossed, label-hiding tangle.
  // Thread ELK's interior bend points through as the edge's waypoints so the
  // rendered path follows the same route the layout engine actually computed.
  //
  // Deliberately NOT grid-snapped: ELK computed these against the node's
  // pre-snap position, and snapping each point independently could round two
  // points that were meant to share an X or Y (a clean straight run) onto
  // different grid cells -- reintroducing a tiny diagonal jog that then forced
  // an extra dogleg right where the edge meets its node. Waypoints are a
  // rendering hint, not something the user drags square to the grid, so they
  // don't need it.
  const elkEdgeById = new Map((result.edges ?? []).map((e) => [e.id, e]));
  const edges = page.edges.map((e) => {
    const elkEdge = elkEdgeById.get(e.id);
    const section = elkEdge?.sections?.[0];
    const bendPoints = section?.bendPoints ?? [];
    if (movedIds.has(e.source.nodeId) || movedIds.has(e.target.nodeId)) {
      return { ...e, line: { ...e.line, routing: "step" as const, waypoints: [] } };
    }
    if (bendPoints.length === 0 || e.line.routing === "curved") return e;
    return {
      ...e,
      line: {
        ...e.line,
        routing: "step" as const,
        waypoints: bendPoints.map((p) => ({ x: p.x, y: p.y })),
      },
    };
  });

  // Auto-resize each lane's bounds to encompass its (now repositioned) members.
  const PAD = 40;
  const HEADER = 32;
  const groups = page.groups.map((g) => {
    if (!laneKinds.has(g.kind) || g.memberBehavior?.autoResize === false) return g;
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

  return { ...page, nodes, edges, groups };
}
