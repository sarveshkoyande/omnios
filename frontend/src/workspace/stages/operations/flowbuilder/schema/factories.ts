import type { NodeType, WorkflowNode } from "./node";
import type { WorkflowEdge, GlueMode, EdgeType } from "./edge";
import type { WorkflowDocument, Page } from "./document";
import { generateNodeId, generateEdgeId, generatePageId, generateDocId } from "./ids";
import { defaultSizeFor, defaultPortsFor, defaultDataFor } from "./nodeDefaults";

export function createNode(
  type: NodeType,
  label: string,
  position: { x: number; y: number },
  overrides: Partial<WorkflowNode> = {}
): WorkflowNode {
  return {
    id: generateNodeId(label || type),
    type,
    label: label || type,
    position,
    size: defaultSizeFor(type),
    ports: defaultPortsFor(type),
    data: defaultDataFor(),
    layerIds: [],
    ...overrides,
  };
}

export function createEdge(
  sourceNodeId: string,
  targetNodeId: string,
  opts: {
    sourcePortId?: string;
    targetPortId?: string;
    glue?: GlueMode;
    type?: EdgeType;
    label?: string;
  } = {}
): WorkflowEdge {
  return {
    id: generateEdgeId(),
    source: { nodeId: sourceNodeId, portId: opts.sourcePortId, glue: opts.glue ?? "dynamic" },
    target: { nodeId: targetNodeId, portId: opts.targetPortId, glue: opts.glue ?? "dynamic" },
    type: opts.type ?? "sequence",
    label: opts.label,
    line: {
      style: "solid",
      weight: 2,
      color: "#333333",
      arrowStart: "none",
      arrowEnd: "arrow",
      routing: "step",
      curve: "step",
      lineJumps: "arc",
      waypoints: [],
    },
    data: {},
    layerIds: [],
  };
}

export function createPage(name = "Main"): Page {
  return { id: generatePageId(name), name, nodes: [], edges: [], groups: [], layers: [] };
}

export function createEmptyDocument(name = "Untitled Workflow"): WorkflowDocument {
  const now = new Date().toISOString();
  return {
    schemaVersion: "1.0",
    id: generateDocId(name),
    name,
    description: "",
    direction: "TB",
    pages: [createPage()],
    stencils: ["core-flowchart", "bpmn-lite"],
    dataSets: [],
    theme: { palette: "default", curve: "step" },
    validationProfile: "strict-flowchart",
    meta: { owner: "", status: "draft", version: 1, tags: [], createdAt: now, updatedAt: now },
    customMasters: [],
  };
}
