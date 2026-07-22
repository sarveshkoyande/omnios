import type { NodeType } from "../schema/nodeTypes";
import { NODE_TYPE_CATEGORY } from "../schema/nodeTypes";

// Default fill/stroke per Section 3.2 category, used when node.style doesn't override.
export const CATEGORY_COLORS: Record<string, { fill: string; stroke: string }> = {
  "flow-control": { fill: "#EFF0FB", stroke: "#3833AB" },
  "data-storage": { fill: "#ECFEFF", stroke: "#0891B2" },
  annotation: { fill: "#F8FAFC", stroke: "#64748B" },
  "bpmn-lite": { fill: "#FDF4FF", stroke: "#A21CAF" },
};

export function defaultColorsFor(type: NodeType): { fill: string; stroke: string } {
  return CATEGORY_COLORS[NODE_TYPE_CATEGORY[type]] ?? CATEGORY_COLORS["flow-control"];
}
