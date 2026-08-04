import type { Page } from "../schema/document";
import type { Layer } from "../schema/layer";
import type { WorkflowRFNode } from "../nodes/WorkflowNode";
import type { WorkflowRFEdge } from "../edges/WorkflowEdge";
import type { LaneRFNode } from "./LaneNode";
import type { Selection } from "../store/useWorkflowStore";
import { pickDynamicPort } from "./glue";

// Schema <-> React Flow adapters. React Flow owns transient view state (drag position,
// selection outline); the schema document remains the single source of truth — every
// drag/connect gesture is written back through a store command, never mutated in place.

const LANE_KINDS = new Set(["lane", "pool", "container", "list", "subgraph", "phase"]);
const DYNAMIC_BRANCH_TYPES = new Set(["decision", "fork", "gateway.parallel", "gateway.exclusive", "gateway.inclusive", "gateway.event"]);

function layerGate(layerIds: string[], layerById: Map<string, Layer>) {
  let visible = true;
  let locked = false;
  let glue = true;
  for (const id of layerIds) {
    const l = layerById.get(id);
    if (!l) continue;
    if (!l.visible) visible = false;
    if (l.locked) locked = true;
    if (!l.glue) glue = false;
  }
  return { visible, locked, glue };
}

export function pageToRFNodes(page: Page, selection: Selection): WorkflowRFNode[] {
  const layerById = new Map(page.layers.map((l) => [l.id, l]));
  return page.nodes
    .filter((n) => layerGate(n.layerIds, layerById).visible)
    .map((n) => {
      const gate = layerGate(n.layerIds, layerById);
      return {
        id: n.id,
        type: "workflow" as const,
        position: n.position,
        data: { schemaNode: n },
        selected: selection.nodeIds.includes(n.id),
        draggable: !(n.locks?.move ?? false) && !gate.locked,
        selectable: !(n.locks?.select ?? false) && !gate.locked,
        deletable: !(n.locks?.delete ?? false),
        width: n.size.w,
        height: n.size.h,
        parentId: undefined,
        zIndex: 10,
      };
    });
}

export function pageToRFEdges(page: Page, selection: Selection): WorkflowRFEdge[] {
  const layerById = new Map(page.layers.map((l) => [l.id, l]));
  const nodeById = new Map(page.nodes.map((n) => [n.id, n]));

  return page.edges
    .filter((e) => layerGate(e.layerIds, layerById).visible)
    .map((e) => {
      const sourceNode = nodeById.get(e.source.nodeId);
      const targetNode = nodeById.get(e.target.nodeId);
      const gate = layerGate(e.layerIds, layerById);

      // Static glue: always the named port. Dynamic glue: re-pick the best-facing
      // port from current node positions every render (Section 2.3 shape-to-shape glue).
      const dynamicSource = sourceNode && DYNAMIC_BRANCH_TYPES.has(sourceNode.type);
      const sourceHandle =
        (e.source.glue === "dynamic" || dynamicSource || !e.source.portId) && sourceNode && targetNode
          ? pickDynamicPort(sourceNode, targetNode, "out")?.id ?? e.source.portId
          : e.source.portId;
      const targetHandle =
        (e.target.glue === "dynamic" || !e.target.portId) && sourceNode && targetNode
          ? pickDynamicPort(targetNode, sourceNode, "in")?.id ?? e.target.portId
          : e.target.portId;

      return {
        id: e.id,
        type: "workflow" as const,
        source: e.source.nodeId,
        target: e.target.nodeId,
        sourceHandle,
        targetHandle,
        data: { schemaEdge: e, forceAutoRoute: !!dynamicSource && e.line.waypoints.length === 0 },
        selected: selection.edgeIds.includes(e.id),
        selectable: !gate.locked,
        deletable: !(e.locks?.delete ?? false),
        reconnectable: gate.glue,
        zIndex: 5,
      };
    });
}

export function pageToRFLaneNodes(page: Page, selection: Selection): LaneRFNode[] {
  return page.groups
    .filter((g) => LANE_KINDS.has(g.kind))
    .map((g) => ({
      id: g.id,
      type: "lane" as const,
      position: { x: g.bounds?.x ?? 0, y: g.bounds?.y ?? 0 },
      data: { schemaGroup: g },
      selected: selection.groupIds.includes(g.id),
      draggable: true,
      dragHandle: ".wf-lane-header",
      width: g.bounds?.w ?? 320,
      height: g.bounds?.h ?? 220,
      zIndex: -1,
    }));
}

/** True if a node's own layers block new connections to/from it. */
export function isGlueBlocked(page: Page, nodeId: string): boolean {
  const layerById = new Map(page.layers.map((l) => [l.id, l]));
  const node = page.nodes.find((n) => n.id === nodeId);
  if (!node) return false;
  return !layerGate(node.layerIds, layerById).glue;
}
