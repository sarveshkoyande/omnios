import type { WorkflowNode } from "../schema/node";
import type { Port, PortSide } from "../schema/port";

// Section 2.3 glue semantics: "Dynamic (shape-to-shape) glue: the connector end is
// glued to the shape as a whole; Visio re-routes to the nearest sensible point /
// shortest path as shapes move." Static glue is trivial (always the named port);
// dynamic glue is recomputed here every render from current node positions.

function centerOf(node: WorkflowNode): { x: number; y: number } {
  return { x: node.position.x + node.size.w / 2, y: node.position.y + node.size.h / 2 };
}

function boundsOf(node: WorkflowNode): { left: number; top: number; right: number; bottom: number } {
  return {
    left: node.position.x,
    top: node.position.y,
    right: node.position.x + node.size.w,
    bottom: node.position.y + node.size.h,
  };
}

function dominantSide(from: { x: number; y: number }, to: { x: number; y: number }): PortSide {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  return Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "right" : "left") : dy > 0 ? "bottom" : "top";
}

function preferredSide(node: WorkflowNode, other: WorkflowNode): PortSide {
  const nodeBounds = boundsOf(node);
  const otherBounds = boundsOf(other);

  // Prefer a clean top/bottom entry whenever the nodes are vertically separated.
  // This keeps the connector going directly in/out of the box instead of running
  // parallel to its edge before the arrowhead.
  if (otherBounds.top >= nodeBounds.bottom) return "bottom";
  if (otherBounds.bottom <= nodeBounds.top) return "top";
  if (otherBounds.left >= nodeBounds.right) return "right";
  if (otherBounds.right <= nodeBounds.left) return "left";

  return dominantSide(centerOf(node), centerOf(other));
}

const OPPOSITE: Record<PortSide, PortSide> = { top: "bottom", bottom: "top", left: "right", right: "left" };

/** Pick the best port on `node` (of the given handle direction) facing `other`. */
export function pickDynamicPort(node: WorkflowNode, other: WorkflowNode, direction: "in" | "out"): Port | undefined {
  const candidates = node.ports.filter((p) => p.direction === direction);
  if (candidates.length === 0) return undefined;
  if (candidates.length === 1) return candidates[0];

  const side = preferredSide(node, other);
  return (
    candidates.find((p) => p.side === side) ??
    candidates.find((p) => p.side !== OPPOSITE[side]) ??
    candidates[0]
  );
}
