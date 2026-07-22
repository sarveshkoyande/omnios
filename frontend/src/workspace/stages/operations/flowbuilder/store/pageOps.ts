import type { Page } from "../schema/document";
import type { WorkflowNode } from "../schema/node";
import type { WorkflowEdge, EdgeEndpoint } from "../schema/edge";
import type { Group } from "../schema/group";
import type { Layer } from "../schema/layer";
import type { DataRecord } from "../schema/dataField";
import type { StencilMaster } from "../schema/stencil";
import { generateNodeId, generateEdgeId, generateGroupId, generateLayerId } from "../schema/ids";
import { defaultDataFor } from "../schema/nodeDefaults";

// Pure, page-scoped mutation functions. Every one takes a Page and returns a *new*
// Page (no in-place mutation) so the store's history stack can snapshot/diff cheaply
// and React Flow can rely on referential equality for change detection.

export function addNode(page: Page, node: WorkflowNode): Page {
  return { ...page, nodes: [...page.nodes, node] };
}

export function updateNode(page: Page, nodeId: string, patch: Partial<WorkflowNode>): Page {
  return { ...page, nodes: page.nodes.map((n) => (n.id === nodeId ? { ...n, ...patch } : n)) };
}

function clearConnectedEdgeWaypoints(page: Page, nodeIds: Set<string>): Page {
  let changed = false;
  const edges = page.edges.map((edge) => {
    if (!nodeIds.has(edge.source.nodeId) && !nodeIds.has(edge.target.nodeId)) return edge;
    if (edge.line.waypoints.length === 0) return edge;
    changed = true;
    return {
      ...edge,
      line: { ...edge.line, waypoints: [] },
    };
  });

  return changed ? { ...page, edges } : page;
}

export function moveNode(page: Page, nodeId: string, position: { x: number; y: number }): Page {
  return clearConnectedEdgeWaypoints(updateNode(page, nodeId, { position }), new Set([nodeId]));
}

export function resizeNode(page: Page, nodeId: string, size: WorkflowNode["size"]): Page {
  return updateNode(page, nodeId, { size });
}

export function updateNodeData(page: Page, nodeId: string, patch: DataRecord): Page {
  return {
    ...page,
    nodes: page.nodes.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, ...patch } } : n)),
  };
}

/**
 * Delete a node. With healEdges=true, if the node has exactly one inbound and one
 * outbound sequence edge, bridge them (source of inbound -> target of outbound)
 * instead of leaving a gap. Otherwise all edges touching the node are dropped.
 */
export function deleteNode(page: Page, nodeId: string, healEdges = false): Page {
  const touching = page.edges.filter((e) => e.source.nodeId === nodeId || e.target.nodeId === nodeId);
  const inbound = touching.filter((e) => e.target.nodeId === nodeId);
  const outbound = touching.filter((e) => e.source.nodeId === nodeId);

  let edges = page.edges.filter((e) => !touching.includes(e));

  if (healEdges && inbound.length === 1 && outbound.length === 1) {
    const [inE] = inbound;
    const [outE] = outbound;
    edges = [
      ...edges,
      {
        ...inE,
        id: generateEdgeId("healed"),
        target: { ...outE.target },
      },
    ];
  }

  return {
    ...page,
    nodes: page.nodes.filter((n) => n.id !== nodeId),
    edges,
    groups: page.groups, // groups keep their id list membership is derived from node.groupId, nothing to patch
  };
}

export function addEdge(page: Page, edge: WorkflowEdge): Page {
  return { ...page, edges: [...page.edges, edge] };
}

export function updateEdge(page: Page, edgeId: string, patch: Partial<WorkflowEdge>): Page {
  return { ...page, edges: page.edges.map((e) => (e.id === edgeId ? { ...e, ...patch } : e)) };
}

export function updateEdgeData(page: Page, edgeId: string, patch: DataRecord): Page {
  return {
    ...page,
    edges: page.edges.map((e) => (e.id === edgeId ? { ...e, data: { ...e.data, ...patch } } : e)),
  };
}

export function reconnectEdge(
  page: Page,
  edgeId: string,
  end: "source" | "target",
  endpoint: EdgeEndpoint
): Page {
  return updateEdge(page, edgeId, { [end]: endpoint } as Partial<WorkflowEdge>);
}

export function deleteEdge(page: Page, edgeId: string): Page {
  return { ...page, edges: page.edges.filter((e) => e.id !== edgeId) };
}

export function addWaypoint(page: Page, edgeId: string, index: number, point: { x: number; y: number }): Page {
  return {
    ...page,
    edges: page.edges.map((e) => {
      if (e.id !== edgeId) return e;
      const waypoints = [...e.line.waypoints];
      waypoints.splice(index, 0, point);
      return { ...e, line: { ...e.line, waypoints } };
    }),
  };
}

export function moveWaypoint(page: Page, edgeId: string, index: number, point: { x: number; y: number }): Page {
  return {
    ...page,
    edges: page.edges.map((e) => {
      if (e.id !== edgeId) return e;
      const waypoints = e.line.waypoints.map((w, i) => (i === index ? point : w));
      return { ...e, line: { ...e.line, waypoints } };
    }),
  };
}

export function removeWaypoint(page: Page, edgeId: string, index: number): Page {
  return {
    ...page,
    edges: page.edges.map((e) => {
      if (e.id !== edgeId) return e;
      return { ...e, line: { ...e.line, waypoints: e.line.waypoints.filter((_, i) => i !== index) } };
    }),
  };
}

/** Insert-between: split edge A->B into A->newNode->B, spaced evenly. */
export function insertNodeOnEdge(
  page: Page,
  edgeId: string,
  node: WorkflowNode,
  makeEdge: (source: string, target: string) => WorkflowEdge
): Page {
  const edge = page.edges.find((e) => e.id === edgeId);
  if (!edge) return page;
  const withoutOld = page.edges.filter((e) => e.id !== edgeId);
  const first = makeEdge(edge.source.nodeId, node.id);
  const second = makeEdge(node.id, edge.target.nodeId);
  return { ...page, nodes: [...page.nodes, node], edges: [...withoutOld, first, second] };
}

export function assignLane(page: Page, nodeId: string, groupId: string | null): Page {
  return updateNode(page, nodeId, { groupId });
}

export function createGroup(page: Page, group: Group): Page {
  return { ...page, groups: [...page.groups, group] };
}

export function updateGroup(page: Page, groupId: string, patch: Partial<Group>): Page {
  return { ...page, groups: page.groups.map((g) => (g.id === groupId ? { ...g, ...patch } : g)) };
}

export function deleteGroup(page: Page, groupId: string, alsoDeleteMembers = false): Page {
  const groups = page.groups.filter((g) => g.id !== groupId);
  if (alsoDeleteMembers) {
    return {
      ...page,
      groups,
      nodes: page.nodes.filter((n) => n.groupId !== groupId),
      edges: page.edges.filter((e) => {
        const removedIds = new Set(page.nodes.filter((n) => n.groupId === groupId).map((n) => n.id));
        return !removedIds.has(e.source.nodeId) && !removedIds.has(e.target.nodeId);
      }),
    };
  }
  return {
    ...page,
    groups,
    nodes: page.nodes.map((n) => (n.groupId === groupId ? { ...n, groupId: null } : n)),
  };
}

/** Move a lane/container and, per memberBehavior.moveWith, all its member nodes. */
export function moveGroup(page: Page, groupId: string, delta: { x: number; y: number }): Page {
  const group = page.groups.find((g) => g.id === groupId);
  if (!group) return page;
  const moveWith = group.memberBehavior?.moveWith ?? true;
  const bounds = group.bounds
    ? { ...group.bounds, x: group.bounds.x + delta.x, y: group.bounds.y + delta.y }
    : undefined;
  let nodes = page.nodes;
  const movedNodeIds = new Set<string>();
  if (moveWith) {
    nodes = nodes.map((n) =>
      n.groupId === groupId
        ? (movedNodeIds.add(n.id), { ...n, position: { x: n.position.x + delta.x, y: n.position.y + delta.y } })
        : n
    );
  }
  const nextPage = {
    ...page,
    nodes,
    groups: page.groups.map((g) => (g.id === groupId ? { ...g, bounds } : g)),
  };
  return movedNodeIds.size > 0 ? clearConnectedEdgeWaypoints(nextPage, movedNodeIds) : nextPage;
}

export function createLayer(page: Page, layer: Layer): Page {
  return { ...page, layers: [...page.layers, layer] };
}

export function updateLayer(page: Page, layerId: string, patch: Partial<Layer>): Page {
  return { ...page, layers: page.layers.map((l) => (l.id === layerId ? { ...l, ...patch } : l)) };
}

export function deleteLayer(page: Page, layerId: string): Page {
  return {
    ...page,
    layers: page.layers.filter((l) => l.id !== layerId),
    nodes: page.nodes.map((n) => ({ ...n, layerIds: n.layerIds.filter((id) => id !== layerId) })),
    edges: page.edges.map((e) => ({ ...e, layerIds: e.layerIds.filter((id) => id !== layerId) })),
  };
}

export function setElementLayers(
  page: Page,
  elementId: string,
  kind: "node" | "edge",
  layerIds: string[]
): Page {
  if (kind === "node") {
    return { ...page, nodes: page.nodes.map((n) => (n.id === elementId ? { ...n, layerIds } : n)) };
  }
  return { ...page, edges: page.edges.map((e) => (e.id === elementId ? { ...e, layerIds } : e)) };
}

export function applyStencilMaster(
  page: Page,
  master: StencilMaster,
  position: { x: number; y: number }
): Page {
  const node: WorkflowNode = {
    id: generateNodeId(master.label),
    type: master.type,
    label: master.label,
    position,
    size: master.defaultSize ?? { w: 160, h: 80, resizable: true },
    ports: master.defaultPorts ?? [],
    data: master.defaultData ?? defaultDataFor(),
    style: master.defaultStyle,
    layerIds: [],
  };
  return addNode(page, node);
}

export function batch(page: Page, ops: Array<(p: Page) => Page>): Page {
  return ops.reduce((p, op) => op(p), page);
}

export const idFactories = { generateNodeId, generateEdgeId, generateGroupId, generateLayerId };
