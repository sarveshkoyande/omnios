import {
  NODE_TYPES,
  NODE_TYPE_CATEGORY,
  type NodeType,
} from "../schema/nodeTypes";
import { shapeKeyFor } from "../schema/nodeDefaults";
import { humanizeNodeType } from "./nodeTypeLabels";
import type { StencilMaster } from "../schema/stencil";

export interface CatalogEntry {
  type: NodeType;
  label: string;
  category: string;
}

export const CATEGORY_LABELS: Record<string, string> = {
  "flow-control": "Flow Control",
  "data-storage": "Data & Storage",
  annotation: "Annotation & Structure",
  "bpmn-lite": "BPMN-lite",
};

export const CATEGORY_ORDER = ["flow-control", "data-storage", "annotation", "bpmn-lite"];

// Built-in "core-flowchart" + "bpmn-lite" stencils, generated from the full Section 3.2
// type catalog — every node type is creatable from the palette per the spec.
export const BUILT_IN_CATALOG: CatalogEntry[] = NODE_TYPES.map((type) => ({
  type,
  label: humanizeNodeType(type),
  category: NODE_TYPE_CATEGORY[type],
}));

export function catalogByCategory(entries: CatalogEntry[]): Map<string, CatalogEntry[]> {
  const map = new Map<string, CatalogEntry[]>();
  for (const entry of entries) {
    const list = map.get(entry.category) ?? [];
    list.push(entry);
    map.set(entry.category, list);
  }
  return map;
}

export const DEFAULT_QUICK_SHAPES: NodeType[] = ["process", "decision", "data-io", "database"];

export function masterFromCatalogEntry(entry: CatalogEntry): Pick<StencilMaster, "type" | "label" | "icon"> {
  return { type: entry.type, label: entry.label, icon: shapeKeyFor(entry.type) };
}
