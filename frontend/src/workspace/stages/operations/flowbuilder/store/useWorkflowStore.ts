import { create } from "zustand";
import type { WorkflowDocument, Page } from "../schema/document";
import type { WorkflowNode } from "../schema/node";
import type { WorkflowEdge, EdgeEndpoint, GlueMode, EdgeType } from "../schema/edge";
import type { Group, GroupKind } from "../schema/group";
import type { Layer } from "../schema/layer";
import type { DataRecord } from "../schema/dataField";
import type { StencilMaster } from "../schema/stencil";
import type { NodeType } from "../schema/nodeTypes";
import { createEmptyDocument, createNode, createEdge } from "../schema/factories";
import { generateGroupId, generateLayerId, generateNodeId, generateStencilId } from "../schema/ids";
import { defaultDataFor } from "../schema/nodeDefaults";
import { DEFAULT_QUICK_SHAPES } from "../palette/stencilCatalog";
import { autoLayoutPage } from "../layout/autoLayout";
import * as ops from "./pageOps";

const HISTORY_LIMIT = 100;

export interface Selection {
  nodeIds: string[];
  edgeIds: string[];
  groupIds: string[];
}

const emptySelection: Selection = { nodeIds: [], edgeIds: [], groupIds: [] };

interface WorkflowState {
  document: WorkflowDocument;
  activePageId: string;
  selection: Selection;
  clipboard: { nodes: WorkflowNode[]; edges: WorkflowEdge[] } | null;
  past: WorkflowDocument[];
  future: WorkflowDocument[];

  // --- document / page ---
  loadDocument: (doc: WorkflowDocument) => void;
  resetDocument: (name?: string) => void;
  setActivePage: (pageId: string) => void;
  getActivePage: () => Page;

  // --- history-tracked mutation entry point ---
  mutate: (fn: (page: Page) => Page) => void;
  mutateDoc: (fn: (doc: WorkflowDocument) => WorkflowDocument) => void;
  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;

  // --- node commands ---
  addNodeCmd: (type: NodeType, label: string, position: { x: number; y: number }, overrides?: Partial<WorkflowNode>) => string;
  deleteNodeCmd: (nodeId: string, healEdges?: boolean) => void;
  moveNodeCmd: (nodeId: string, position: { x: number; y: number }) => void;
  resizeNodeCmd: (nodeId: string, size: WorkflowNode["size"]) => void;
  updateNodeCmd: (nodeId: string, patch: Partial<WorkflowNode>) => void;
  updateNodeDataCmd: (nodeId: string, patch: DataRecord) => void;
  duplicateNodesCmd: (nodeIds: string[], offset?: { x: number; y: number }) => void;

  // --- edge commands ---
  addEdgeCmd: (
    sourceId: string,
    targetId: string,
    opts?: { sourcePortId?: string; targetPortId?: string; glue?: GlueMode; type?: EdgeType; label?: string }
  ) => string;
  reconnectEdgeCmd: (edgeId: string, end: "source" | "target", endpoint: EdgeEndpoint) => void;
  deleteEdgeCmd: (edgeId: string) => void;
  updateEdgeCmd: (edgeId: string, patch: Partial<WorkflowEdge>) => void;
  updateEdgeDataCmd: (edgeId: string, patch: DataRecord) => void;
  insertNodeOnEdgeCmd: (edgeId: string, type: NodeType, label: string) => void;
  addWaypointCmd: (edgeId: string, index: number, point: { x: number; y: number }) => void;
  moveWaypointCmd: (edgeId: string, index: number, point: { x: number; y: number }) => void;
  removeWaypointCmd: (edgeId: string, index: number) => void;

  // --- lane / group / layer commands ---
  assignLaneCmd: (nodeId: string, groupId: string | null) => void;
  createGroupCmd: (kind: GroupKind, label: string, bounds?: Group["bounds"]) => string;
  updateGroupCmd: (groupId: string, patch: Partial<Group>) => void;
  deleteGroupCmd: (groupId: string, alsoDeleteMembers?: boolean) => void;
  moveGroupCmd: (groupId: string, delta: { x: number; y: number }) => void;
  createLayerCmd: (name: string) => string;
  updateLayerCmd: (layerId: string, patch: Partial<Layer>) => void;
  deleteLayerCmd: (layerId: string) => void;
  setElementLayersCmd: (elementId: string, kind: "node" | "edge", layerIds: string[]) => void;

  applyStencilMasterCmd: (master: StencilMaster, position: { x: number; y: number }) => string;
  saveNodeAsMasterCmd: (nodeId: string, masterLabel: string) => string;

  // --- quick shapes (UI preference, not part of the document schema) ---
  quickShapeTypes: NodeType[];
  setQuickShapeTypes: (types: NodeType[]) => void;

  // --- selection ---
  select: (sel: Partial<Selection>, additive?: boolean) => void;
  clearSelection: () => void;
  selectAll: () => void;

  // --- clipboard ---
  copySelection: () => void;
  pasteClipboard: (offset?: { x: number; y: number }) => void;
  deleteSelection: (healEdges?: boolean) => void;

  // --- layout ---
  runAutoLayoutCmd: () => Promise<void>;

  // --- IO ---
  importPageCmd: (page: Page, direction: WorkflowDocument["direction"]) => void;
}

function getPage(doc: WorkflowDocument, pageId: string): Page {
  const page = doc.pages.find((p) => p.id === pageId);
  if (!page) throw new Error(`page not found: ${pageId}`);
  return page;
}

function setPage(doc: WorkflowDocument, pageId: string, page: Page): WorkflowDocument {
  return { ...doc, pages: doc.pages.map((p) => (p.id === pageId ? page : p)) };
}

const initialDocument = createEmptyDocument();

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  document: initialDocument,
  activePageId: initialDocument.pages[0].id,
  selection: emptySelection,
  clipboard: null,
  past: [],
  future: [],
  quickShapeTypes: DEFAULT_QUICK_SHAPES,
  setQuickShapeTypes: (types) => set({ quickShapeTypes: types.slice(0, 4) }),

  loadDocument: (doc) => set({ document: doc, activePageId: doc.pages[0]?.id ?? "", selection: emptySelection, past: [], future: [] }),
  resetDocument: (name) => {
    const doc = createEmptyDocument(name);
    set({ document: doc, activePageId: doc.pages[0].id, selection: emptySelection, past: [], future: [] });
  },
  setActivePage: (pageId) => set({ activePageId: pageId, selection: emptySelection }),
  getActivePage: () => getPage(get().document, get().activePageId),

  mutateDoc: (fn) => {
    const { document, past } = get();
    const nextPast = [...past, document].slice(-HISTORY_LIMIT);
    set({ document: fn(document), past: nextPast, future: [] });
  },
  mutate: (fn) => {
    const { activePageId } = get();
    get().mutateDoc((doc) => setPage(doc, activePageId, fn(getPage(doc, activePageId))));
  },

  undo: () => {
    const { past, document, future } = get();
    if (past.length === 0) return;
    const previous = past[past.length - 1];
    set({ document: previous, past: past.slice(0, -1), future: [document, ...future].slice(0, HISTORY_LIMIT) });
  },
  redo: () => {
    const { future, document, past } = get();
    if (future.length === 0) return;
    const next = future[0];
    set({ document: next, future: future.slice(1), past: [...past, document].slice(-HISTORY_LIMIT) });
  },
  canUndo: () => get().past.length > 0,
  canRedo: () => get().future.length > 0,

  addNodeCmd: (type, label, position, overrides) => {
    const node = createNode(type, label, position, overrides);
    get().mutate((page) => ops.addNode(page, node));
    return node.id;
  },
  deleteNodeCmd: (nodeId, healEdges = false) => {
    get().mutate((page) => ops.deleteNode(page, nodeId, healEdges));
    get().select({ nodeIds: get().selection.nodeIds.filter((id) => id !== nodeId) });
  },
  moveNodeCmd: (nodeId, position) => get().mutate((page) => ops.moveNode(page, nodeId, position)),
  resizeNodeCmd: (nodeId, size) => get().mutate((page) => ops.resizeNode(page, nodeId, size)),
  updateNodeCmd: (nodeId, patch) => get().mutate((page) => ops.updateNode(page, nodeId, patch)),
  updateNodeDataCmd: (nodeId, patch) => get().mutate((page) => ops.updateNodeData(page, nodeId, patch)),
  duplicateNodesCmd: (nodeIds, offset = { x: 24, y: 24 }) => {
    get().mutate((page) => {
      const idMap = new Map<string, string>();
      const clones = page.nodes
        .filter((n) => nodeIds.includes(n.id))
        .map((n) => {
          const id = generateNodeId(n.label);
          idMap.set(n.id, id);
          return { ...n, id, position: { x: n.position.x + offset.x, y: n.position.y + offset.y } };
        });
      const clonedEdges = page.edges
        .filter((e) => idMap.has(e.source.nodeId) && idMap.has(e.target.nodeId))
        .map((e) => ({
          ...e,
          id: generateNodeId("edge"),
          source: { ...e.source, nodeId: idMap.get(e.source.nodeId)! },
          target: { ...e.target, nodeId: idMap.get(e.target.nodeId)! },
        }));
      return { ...page, nodes: [...page.nodes, ...clones], edges: [...page.edges, ...clonedEdges] };
    });
  },

  addEdgeCmd: (sourceId, targetId, opts) => {
    const edge = createEdge(sourceId, targetId, opts);
    get().mutate((page) => ops.addEdge(page, edge));
    return edge.id;
  },
  reconnectEdgeCmd: (edgeId, end, endpoint) => get().mutate((page) => ops.reconnectEdge(page, edgeId, end, endpoint)),
  deleteEdgeCmd: (edgeId) => get().mutate((page) => ops.deleteEdge(page, edgeId)),
  updateEdgeCmd: (edgeId, patch) => get().mutate((page) => ops.updateEdge(page, edgeId, patch)),
  updateEdgeDataCmd: (edgeId, patch) => get().mutate((page) => ops.updateEdgeData(page, edgeId, patch)),
  insertNodeOnEdgeCmd: (edgeId, type, label) => {
    get().mutate((page) => {
      const edge = page.edges.find((e) => e.id === edgeId);
      if (!edge) return page;
      const source = page.nodes.find((n) => n.id === edge.source.nodeId);
      const target = page.nodes.find((n) => n.id === edge.target.nodeId);
      const position = source && target
        ? { x: (source.position.x + target.position.x) / 2, y: (source.position.y + target.position.y) / 2 }
        : { x: 0, y: 0 };
      const node = createNode(type, label, position);
      return ops.insertNodeOnEdge(page, edgeId, node, (s, t) => createEdge(s, t, { type: edge.type }));
    });
  },
  addWaypointCmd: (edgeId, index, point) => get().mutate((page) => ops.addWaypoint(page, edgeId, index, point)),
  moveWaypointCmd: (edgeId, index, point) => get().mutate((page) => ops.moveWaypoint(page, edgeId, index, point)),
  removeWaypointCmd: (edgeId, index) => get().mutate((page) => ops.removeWaypoint(page, edgeId, index)),

  assignLaneCmd: (nodeId, groupId) => get().mutate((page) => ops.assignLane(page, nodeId, groupId)),
  createGroupCmd: (kind, label, bounds) => {
    const group: Group = {
      id: generateGroupId(label),
      kind,
      label,
      collapsed: false,
      memberBehavior: { moveWith: true, deleteWith: "prompt", autoResize: true },
      bounds,
    };
    get().mutate((page) => ops.createGroup(page, group));
    return group.id;
  },
  updateGroupCmd: (groupId, patch) => get().mutate((page) => ops.updateGroup(page, groupId, patch)),
  deleteGroupCmd: (groupId, alsoDeleteMembers = false) =>
    get().mutate((page) => ops.deleteGroup(page, groupId, alsoDeleteMembers)),
  moveGroupCmd: (groupId, delta) => get().mutate((page) => ops.moveGroup(page, groupId, delta)),

  createLayerCmd: (name) => {
    const layer: Layer = { id: generateLayerId(name), name, visible: true, printable: true, locked: false, snap: true, glue: true };
    get().mutate((page) => ops.createLayer(page, layer));
    return layer.id;
  },
  updateLayerCmd: (layerId, patch) => get().mutate((page) => ops.updateLayer(page, layerId, patch)),
  deleteLayerCmd: (layerId) => get().mutate((page) => ops.deleteLayer(page, layerId)),
  setElementLayersCmd: (elementId, kind, layerIds) =>
    get().mutate((page) => ops.setElementLayers(page, elementId, kind, layerIds)),

  applyStencilMasterCmd: (master, position) => {
    const node: WorkflowNode = {
      id: generateNodeId(master.label),
      type: master.type as NodeType,
      label: master.label,
      position,
      size: master.defaultSize ?? { w: 160, h: 80, resizable: true },
      ports: master.defaultPorts ?? [],
      data: master.defaultData ?? defaultDataFor(),
      style: master.defaultStyle,
      layerIds: [],
    };
    get().mutate((page) => ops.addNode(page, node));
    return node.id;
  },
  saveNodeAsMasterCmd: (nodeId, masterLabel) => {
    const page = get().getActivePage();
    const node = page.nodes.find((n) => n.id === nodeId);
    const masterId = generateStencilId(masterLabel);
    if (!node) return masterId;
    get().mutateDoc((doc) => ({
      ...doc,
      customMasters: [
        ...doc.customMasters,
        {
          id: masterId,
          type: node.type,
          label: masterLabel,
          defaultSize: node.size,
          defaultPorts: node.ports,
          defaultData: node.data,
          defaultStyle: node.style,
        },
      ],
    }));
    return masterId;
  },

  select: (sel, additive = false) =>
    set((state) => ({
      selection: additive
        ? {
            nodeIds: Array.from(new Set([...state.selection.nodeIds, ...(sel.nodeIds ?? [])])),
            edgeIds: Array.from(new Set([...state.selection.edgeIds, ...(sel.edgeIds ?? [])])),
            groupIds: Array.from(new Set([...state.selection.groupIds, ...(sel.groupIds ?? [])])),
          }
        : { nodeIds: sel.nodeIds ?? [], edgeIds: sel.edgeIds ?? [], groupIds: sel.groupIds ?? [] },
    })),
  clearSelection: () => set({ selection: emptySelection }),
  selectAll: () => {
    const page = get().getActivePage();
    set({ selection: { nodeIds: page.nodes.map((n) => n.id), edgeIds: page.edges.map((e) => e.id), groupIds: [] } });
  },

  copySelection: () => {
    const page = get().getActivePage();
    const { nodeIds, edgeIds } = get().selection;
    set({
      clipboard: {
        nodes: page.nodes.filter((n) => nodeIds.includes(n.id)),
        edges: page.edges.filter((e) => edgeIds.includes(e.id)),
      },
    });
  },
  pasteClipboard: (offset = { x: 24, y: 24 }) => {
    const clip = get().clipboard;
    if (!clip || clip.nodes.length === 0) return;
    get().mutate((page) => {
      const idMap = new Map<string, string>();
      const nodes = clip.nodes.map((n) => {
        const id = generateNodeId(n.label);
        idMap.set(n.id, id);
        return { ...n, id, position: { x: n.position.x + offset.x, y: n.position.y + offset.y }, groupId: null };
      });
      const edges = clip.edges
        .filter((e) => idMap.has(e.source.nodeId) && idMap.has(e.target.nodeId))
        .map((e) => ({
          ...e,
          id: generateNodeId("edge"),
          source: { ...e.source, nodeId: idMap.get(e.source.nodeId)! },
          target: { ...e.target, nodeId: idMap.get(e.target.nodeId)! },
        }));
      return { ...page, nodes: [...page.nodes, ...nodes], edges: [...page.edges, ...edges] };
    });
  },
  deleteSelection: (healEdges = false) => {
    const { nodeIds } = get().selection;
    get().mutate((page) => {
      let next = page;
      for (const nodeId of nodeIds) next = ops.deleteNode(next, nodeId, healEdges);
      return next;
    });
    get().clearSelection();
  },

  runAutoLayoutCmd: async () => {
    const page = get().getActivePage();
    const laidOut = await autoLayoutPage(page, get().document.direction);
    get().mutate(() => laidOut);
  },

  importPageCmd: (importedPage, direction) => {
    const { activePageId } = get();
    get().mutateDoc((doc) => ({
      ...doc,
      direction,
      pages: doc.pages.map((p) =>
        p.id === activePageId ? { ...importedPage, id: activePageId, name: p.name } : p
      ),
    }));
    get().clearSelection();
  },
}));
