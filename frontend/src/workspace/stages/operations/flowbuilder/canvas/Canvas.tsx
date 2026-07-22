import { useCallback, useEffect, useRef, useState } from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  MiniMap,
  Controls,
  applyNodeChanges,
  applyEdgeChanges,
  useReactFlow,
  ConnectionMode,
  type OnConnect,
  type OnConnectEnd,
  type OnSelectionChangeFunc,
  type NodeChange,
  type EdgeChange,
} from "@xyflow/react";
import { useWorkflowStore } from "../store/useWorkflowStore";
import { nodeTypes as workflowNodeTypes, type WorkflowRFNode } from "../nodes/WorkflowNode";
import { edgeTypes, type WorkflowRFEdge } from "../edges/WorkflowEdge";
import { EdgeMarkerDefs } from "../edges/markers";
import { LaneNode, type LaneRFNode } from "./LaneNode";
import { pageToRFNodes, pageToRFEdges, pageToRFLaneNodes, isGlueBlocked } from "./adapters";
import { computeLineJumps } from "../edges/jumps";
import { BUILT_IN_CATALOG } from "../palette/stencilCatalog";
import { DRAG_NODE_TYPE, DRAG_MASTER_ID, DRAG_AUTOCONNECT_SOURCE } from "../interactions/dragTypes";
import type { NodeType } from "../schema/nodeTypes";

const GRID = 40;
const nodeTypes = { ...workflowNodeTypes, lane: LaneNode };
type AnyRFNode = WorkflowRFNode | LaneRFNode;

function laneContaining(
  groups: import("../schema/document").Page["groups"],
  point: { x: number; y: number }
): string | null {
  for (const g of groups) {
    if (!g.bounds) continue;
    const { x, y, w, h } = g.bounds;
    if (point.x >= x && point.x <= x + w && point.y >= y && point.y <= y + h) return g.id;
  }
  return null;
}

function clearTransientEdgeRouting(edges: WorkflowRFEdge[], movedNodeIds: Set<string>): WorkflowRFEdge[] {
  let changed = false;
  const nextEdges = edges.map((edge) => {
    if (!movedNodeIds.has(edge.source) && !movedNodeIds.has(edge.target)) return edge;
    const schemaEdge = edge.data?.schemaEdge;
    if (!schemaEdge || schemaEdge.line.waypoints.length === 0) return edge;
    changed = true;
    return {
      ...edge,
      data: {
        ...edge.data,
        schemaEdge: {
          ...schemaEdge,
          line: { ...schemaEdge.line, waypoints: [] },
        },
        jumpPoints: [],
      },
    };
  });

  return changed ? nextEdges : edges;
}

function CanvasInner() {
  const document = useWorkflowStore((s) => s.document);
  const activePageId = useWorkflowStore((s) => s.activePageId);
  const selection = useWorkflowStore((s) => s.selection);
  const moveNodeCmd = useWorkflowStore((s) => s.moveNodeCmd);
  const addEdgeCmd = useWorkflowStore((s) => s.addEdgeCmd);
  const addNodeCmd = useWorkflowStore((s) => s.addNodeCmd);
  const applyStencilMasterCmd = useWorkflowStore((s) => s.applyStencilMasterCmd);
  const insertNodeOnEdgeCmd = useWorkflowStore((s) => s.insertNodeOnEdgeCmd);
  const assignLaneCmd = useWorkflowStore((s) => s.assignLaneCmd);
  const moveGroupCmd = useWorkflowStore((s) => s.moveGroupCmd);
  const select = useWorkflowStore((s) => s.select);
  const deleteSelection = useWorkflowStore((s) => s.deleteSelection);
  const undo = useWorkflowStore((s) => s.undo);
  const redo = useWorkflowStore((s) => s.redo);
  const copySelection = useWorkflowStore((s) => s.copySelection);
  const pasteClipboard = useWorkflowStore((s) => s.pasteClipboard);
  const duplicateNodesCmd = useWorkflowStore((s) => s.duplicateNodesCmd);
  const selectAll = useWorkflowStore((s) => s.selectAll);
  const clearSelection = useWorkflowStore((s) => s.clearSelection);
  const { screenToFlowPosition, fitView } = useReactFlow();

  const page = document.pages.find((p) => p.id === activePageId) ?? document.pages[0];

  const [rfNodes, setRfNodes] = useState<AnyRFNode[]>([]);
  const [rfEdges, setRfEdges] = useState<WorkflowRFEdge[]>([]);
  const hasFitRef = useRef(false);

  // React Flow's `fitView` prop only fits whatever nodes were present at its own first
  // measured render. A consumer that seeds nodes synchronously right at mount (e.g. an
  // embedding that loads a document before first paint) can end up with nodes present
  // from the very first frame RF measures, without ever producing the 0->N transition
  // fitView normally reacts to — so the viewport can settle on an empty/arbitrary frame.
  // Make the first real population always explicitly fit, once.
  useEffect(() => {
    if (!hasFitRef.current && rfNodes.length > 0) {
      hasFitRef.current = true;
      requestAnimationFrame(() => fitView({ duration: 200 }));
    }
  }, [rfNodes, fitView]);

  // Resync from the store whenever the underlying document changes (undo/redo, data
  // edits, remote load). During an active drag React Flow's own onNodesChange keeps
  // local state smooth; the store is only written to on drag-stop.
  useEffect(() => {
    setRfNodes([...pageToRFLaneNodes(page, selection), ...pageToRFNodes(page, selection)]);
    const jumps = computeLineJumps(page);
    setRfEdges(
      pageToRFEdges(page, selection).map((e) => ({
        ...e,
        data: { ...e.data!, jumpPoints: jumps.get(e.id) ?? [] },
      }))
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, selection]);

  const onNodesChange = useCallback((changes: NodeChange<AnyRFNode>[]) => {
    setRfNodes((nds) => applyNodeChanges(changes, nds));

    const movedNodeIds = new Set(
      changes
        .filter((change) => change.type === "position")
        .map((change) => change.id)
    );
    if (movedNodeIds.size === 0) return;

    setRfEdges((edges) => clearTransientEdgeRouting(edges, movedNodeIds));
  }, []);

  const onEdgesChange = useCallback((changes: EdgeChange<WorkflowRFEdge>[]) => {
    setRfEdges((eds) => applyEdgeChanges(changes, eds));
  }, []);

  const onNodeDragStop = useCallback(
    (_: unknown, node: AnyRFNode) => {
      const snapped = { x: Math.round(node.position.x / GRID) * GRID, y: Math.round(node.position.y / GRID) * GRID };

      if (node.type === "lane") {
        const group = page.groups.find((g) => g.id === node.id);
        const prev = group?.bounds ?? { x: 0, y: 0, w: 320, h: 220 };
        moveGroupCmd(node.id, { x: snapped.x - prev.x, y: snapped.y - prev.y });
        return;
      }

      moveNodeCmd(node.id, snapped);

      // Dropping a node inside a lane's bounds sets lane membership (Section 4:
      // "dragging a node into a lane sets membership"); dragging it back out clears it.
      const schemaNode = page.nodes.find((n) => n.id === node.id);
      if (!schemaNode) return;
      const center = { x: snapped.x + schemaNode.size.w / 2, y: snapped.y + schemaNode.size.h / 2 };
      const laneId = laneContaining(page.groups, center);
      if (laneId !== (schemaNode.groupId ?? null)) assignLaneCmd(node.id, laneId);
    },
    [moveNodeCmd, moveGroupCmd, assignLaneCmd, page]
  );

  const onConnect: OnConnect = useCallback(
    (params) => {
      if (!params.source || !params.target) return;
      if (isGlueBlocked(page, params.source) || isGlueBlocked(page, params.target)) return;
      // Dragging from a specific port handle is a Visio "point glue" gesture -> static.
      addEdgeCmd(params.source, params.target, {
        sourcePortId: params.sourceHandle ?? undefined,
        targetPortId: params.targetHandle ?? undefined,
        glue: "static",
      });
    },
    [addEdgeCmd, page]
  );

  // A connection drag that ends on a node's *body* (not on a handle) still connects:
  // create the edge with dynamic glue so the best-facing ports get picked per render.
  // Without this, releasing anywhere but exactly on a port dot silently does nothing.
  const onConnectEnd: OnConnectEnd = useCallback(
    (event, connectionState) => {
      if (connectionState.isValid) return; // landed on a handle; onConnect already handled it
      const fromId = connectionState.fromNode?.id;
      if (!fromId) return;
      const { clientX, clientY } = "changedTouches" in event ? event.changedTouches[0] : event;
      const targetEl = window.document.elementFromPoint(clientX, clientY);
      const targetId = targetEl?.closest<HTMLElement>(".react-flow__node")?.getAttribute("data-id");
      if (!targetId || targetId === fromId) return;
      if (isGlueBlocked(page, fromId) || isGlueBlocked(page, targetId)) return;
      addEdgeCmd(fromId, targetId, { glue: "dynamic" });
    },
    [addEdgeCmd, page]
  );

  const onSelectionChange: OnSelectionChangeFunc = useCallback(
    ({ nodes, edges }) => {
      const nodeIds = nodes.filter((n) => n.type !== "lane").map((n) => n.id);
      const groupIds = nodes.filter((n) => n.type === "lane").map((n) => n.id);
      select({ nodeIds, edgeIds: edges.map((e) => e.id), groupIds });
    },
    [select]
  );

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = e.dataTransfer.types.includes(DRAG_AUTOCONNECT_SOURCE) ? "link" : "copy";
  }, []);

  // Palette drag-drop (creates a node, or Insert-between if dropped on an edge) and
  // AutoConnect-arrow drag-drop (connects to an existing node, no new node created).
  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const autoconnectSourceId = e.dataTransfer.getData(DRAG_AUTOCONNECT_SOURCE);
      const targetEl = window.document.elementFromPoint(e.clientX, e.clientY);

      if (autoconnectSourceId) {
        const targetNodeEl = targetEl?.closest<HTMLElement>(".react-flow__node");
        const targetNodeId = targetNodeEl?.getAttribute("data-id");
        if (targetNodeId && targetNodeId !== autoconnectSourceId) {
          addEdgeCmd(autoconnectSourceId, targetNodeId, { glue: "dynamic" });
        }
        return;
      }

      const nodeType = e.dataTransfer.getData(DRAG_NODE_TYPE) as NodeType | "";
      const masterId = e.dataTransfer.getData(DRAG_MASTER_ID);
      if (!nodeType && !masterId) return;

      const flowPos = screenToFlowPosition({ x: e.clientX, y: e.clientY });
      const snapped = { x: Math.round(flowPos.x / GRID) * GRID, y: Math.round(flowPos.y / GRID) * GRID };

      const edgeEl = targetEl?.closest<HTMLElement>(".react-flow__edge");
      const edgeId = edgeEl?.getAttribute("data-id");

      if (edgeId) {
        const type = nodeType || document.customMasters.find((m) => m.id === masterId)?.type;
        const label = nodeType
          ? BUILT_IN_CATALOG.find((c) => c.type === nodeType)?.label ?? nodeType
          : document.customMasters.find((m) => m.id === masterId)?.label ?? "Step";
        if (type) insertNodeOnEdgeCmd(edgeId, type, label);
        return;
      }

      if (masterId) {
        const master = document.customMasters.find((m) => m.id === masterId);
        if (master) applyStencilMasterCmd(master, snapped);
        return;
      }
      if (!nodeType) return;
      const label = BUILT_IN_CATALOG.find((c) => c.type === nodeType)?.label ?? nodeType;
      addNodeCmd(nodeType, label, snapped);
    },
    [addEdgeCmd, addNodeCmd, applyStencilMasterCmd, insertNodeOnEdgeCmd, screenToFlowPosition, document.customMasters]
  );

  // Section 4 keyboard shortcuts: Del, Ctrl+Z/Y, Ctrl+C/V/D, Ctrl+A, Esc, and arrow-key
  // nudging (1 grid unit, 5 with Shift) for every currently-selected node.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) return;
      const mod = e.ctrlKey || e.metaKey;

      if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        deleteSelection(true);
      } else if (mod && e.key.toLowerCase() === "z" && !e.shiftKey) {
        e.preventDefault();
        undo();
      } else if (mod && (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey))) {
        e.preventDefault();
        redo();
      } else if (mod && e.key.toLowerCase() === "c") {
        e.preventDefault();
        copySelection();
      } else if (mod && e.key.toLowerCase() === "v") {
        e.preventDefault();
        pasteClipboard();
      } else if (mod && e.key.toLowerCase() === "d") {
        e.preventDefault();
        if (selection.nodeIds.length > 0) duplicateNodesCmd(selection.nodeIds);
      } else if (mod && e.key.toLowerCase() === "a") {
        e.preventDefault();
        selectAll();
      } else if (e.key === "Escape") {
        clearSelection();
      } else if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key) && selection.nodeIds.length > 0) {
        e.preventDefault();
        const step = e.shiftKey ? GRID * 5 : GRID;
        const dx = e.key === "ArrowLeft" ? -step : e.key === "ArrowRight" ? step : 0;
        const dy = e.key === "ArrowUp" ? -step : e.key === "ArrowDown" ? step : 0;
        for (const nodeId of selection.nodeIds) {
          const n = page.nodes.find((x) => x.id === nodeId);
          if (n) moveNodeCmd(nodeId, { x: n.position.x + dx, y: n.position.y + dy });
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [deleteSelection, undo, redo, copySelection, pasteClipboard, duplicateNodesCmd, selectAll, clearSelection, selection.nodeIds, page.nodes, moveNodeCmd]);

  return (
    <div className="wf-canvas" onDragOver={onDragOver} onDrop={onDrop}>
      <EdgeMarkerDefs />
      <ReactFlow<AnyRFNode, WorkflowRFEdge>
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDragStop={onNodeDragStop}
        onConnect={onConnect}
        onConnectEnd={onConnectEnd}
        connectionMode={ConnectionMode.Loose}
        connectionRadius={32}
        onSelectionChange={onSelectionChange}
        deleteKeyCode={null}
        snapToGrid
        snapGrid={[GRID, GRID]}
        selectionOnDrag
        panOnDrag={[1, 2]}
        selectionKeyCode={null}
        multiSelectionKeyCode="Shift"
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={GRID} size={1.5} />
        <MiniMap pannable zoomable />
        <Controls />
      </ReactFlow>
      {page.nodes.length === 0 && (
        <div className="wf-empty-state">
          <p>This page is empty.</p>
          <p>Drag a shape from the palette, or paste a Mermaid flowchart via Import Mermaid, to get started.</p>
        </div>
      )}
    </div>
  );
}

// ReactFlowProvider lives at the App level (see App.tsx) so panels like the Validation
// tab can also call useReactFlow() (e.g. to center the viewport on a flagged element).
export { CanvasInner as Canvas };
