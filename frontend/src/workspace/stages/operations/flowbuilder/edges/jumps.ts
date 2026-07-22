import type { Page } from "../schema/document";
import type { WorkflowNode as SchemaNode } from "../schema/node";
import type { WorkflowEdge as SchemaEdge, LineJumps } from "../schema/edge";
import { pickDynamicPort } from "../canvas/glue";

// "Line jumps" (Section 3.3's `line.lineJumps`, defined in the schema but never
// rendered until now): where two edges cross, the one with jumps enabled hops
// over the other with a small arc/gap/square notch, the standard Visio/drawio
// convention for showing "these lines cross but aren't connected" on a dense
// diagram. Crossings are found here, from the schema (node positions + port
// geometry) rather than React Flow's live DOM, so it can run once per page
// change independent of any single edge's own render.

export type Pt = { x: number; y: number };
export type JumpPoint = { point: Pt; orientation: "h" | "v" };

function samePoint(a: Pt, b: Pt): boolean {
  return Math.abs(a.x - b.x) < 0.01 && Math.abs(a.y - b.y) < 0.01;
}

function isAxisAligned(a: Pt, b: Pt): boolean {
  return Math.abs(a.x - b.x) < 0.01 || Math.abs(a.y - b.y) < 0.01;
}

function isCollinear(a: Pt, b: Pt, c: Pt): boolean {
  return (Math.abs(a.x - b.x) < 0.01 && Math.abs(b.x - c.x) < 0.01) || (Math.abs(a.y - b.y) < 0.01 && Math.abs(b.y - c.y) < 0.01);
}

function anchorFor(node: SchemaNode, endpoint: SchemaEdge["source"] | SchemaEdge["target"], other: SchemaNode, direction: "in" | "out"): Pt {
  let port = endpoint.portId ? node.ports.find((p) => p.id === endpoint.portId) : undefined;
  if (!port && endpoint.glue === "dynamic") port = pickDynamicPort(node, other, direction);
  if (!port) port = node.ports[0];
  const { x, y } = node.position;
  const { w, h } = node.size;
  if (!port) return { x: x + w / 2, y: y + h / 2 };
  if (port.side === "top") return { x: x + w * port.offset, y };
  if (port.side === "bottom") return { x: x + w * port.offset, y: y + h };
  if (port.side === "left") return { x, y: y + h * port.offset };
  return { x: x + w, y: y + h * port.offset }; // right
}

// When ELK provides bend points, they are already the actual route we render.
// A brand-new edge without bend points still needs a simple stepped fallback so
// jump detection sees the same style of path the renderer shows.
function expandOrthogonal(points: Pt[]): Pt[] {
  const out: Pt[] = [points[0]];
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1];
    const b = points[i];
    const midX = (a.x + b.x) / 2;
    out.push({ x: midX, y: a.y }, { x: midX, y: b.y }, b);
  }
  return out;
}

function compactPolyline(points: Pt[]): Pt[] {
  const out: Pt[] = [];
  for (const point of points) {
    if (out.length === 0) {
      out.push(point);
      continue;
    }
    if (samePoint(out[out.length - 1], point)) continue;
    out.push(point);
    while (out.length >= 3 && isCollinear(out[out.length - 3], out[out.length - 2], out[out.length - 1])) {
      out.splice(out.length - 2, 1);
    }
  }
  return out;
}

function orthogonalizePoints(points: Pt[]): Pt[] {
  const cleaned = points.filter((p, i) => i === 0 || !samePoint(p, points[i - 1]));
  if (cleaned.length <= 2) return cleaned;

  const out: Pt[] = [cleaned[0]];
  for (let i = 1; i < cleaned.length; i++) {
    const a = out[out.length - 1];
    const b = cleaned[i];
    if (isAxisAligned(a, b)) {
      out.push(b);
      continue;
    }

    const next = i < cleaned.length - 1 ? cleaned[i + 1] : null;
    const horizontalThenVertical = { x: b.x, y: a.y };
    const verticalThenHorizontal = { x: a.x, y: b.y };

    const scoreCandidate = (candidate: Pt): number => {
      let score = 0;
      const prev = out.length > 1 ? out[out.length - 2] : null;
      if (prev && !isCollinear(prev, a, candidate)) score += 1;
      if (next && !isAxisAligned(candidate, next)) score += 2;
      return score;
    };

    const useHorizontalFirst = scoreCandidate(horizontalThenVertical) <= scoreCandidate(verticalThenHorizontal);
    out.push(useHorizontalFirst ? horizontalThenVertical : verticalThenHorizontal, b);
  }

  return compactPolyline(out);
}

function routedPolyline(source: Pt, target: Pt, waypoints: Pt[]): Pt[] {
  if (waypoints.length > 0) return orthogonalizePoints([source, ...waypoints, target]);
  return expandOrthogonal([source, target]);
}

interface Seg {
  edgeId: string;
  a: Pt;
  b: Pt;
  orientation: "h" | "v";
  lineJumps: LineJumps;
}

function segsFor(edgeId: string, points: Pt[], lineJumps: LineJumps): Seg[] {
  const segs: Seg[] = [];
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1];
    const b = points[i];
    if (Math.abs(a.x - b.x) < 0.5 && Math.abs(a.y - b.y) < 0.5) continue; // zero-length
    const orientation: "h" | "v" = Math.abs(a.y - b.y) < 0.5 ? "h" : "v";
    segs.push({ edgeId, a, b, orientation, lineJumps });
  }
  return segs;
}

const EPS = 2;

/** Strictly-interior crossing of one horizontal and one vertical axis-aligned segment. */
function segIntersect(s1: Seg, s2: Seg): Pt | null {
  if (s1.orientation === s2.orientation) return null;
  const h = s1.orientation === "h" ? s1 : s2;
  const v = s1.orientation === "h" ? s2 : s1;
  const hx1 = Math.min(h.a.x, h.b.x);
  const hx2 = Math.max(h.a.x, h.b.x);
  const vy1 = Math.min(v.a.y, v.b.y);
  const vy2 = Math.max(v.a.y, v.b.y);
  const x = v.a.x;
  const y = h.a.y;
  if (x > hx1 + EPS && x < hx2 - EPS && y > vy1 + EPS && y < vy2 - EPS) return { x, y };
  return null;
}

/** Per-edge list of crossing points where that edge should draw a jump hop. */
export function computeLineJumps(page: Page): Map<string, JumpPoint[]> {
  const nodeById = new Map(page.nodes.map((n) => [n.id, n]));
  const allSegs: Seg[] = [];

  for (const e of page.edges) {
    // Bezier/straight edges aren't reliably decomposable into axis-aligned
    // segments, so they're neither jump sources nor jumped-over obstacles.
    if (e.line.routing !== "orthogonal" && e.line.routing !== "step") continue;
    const sourceNode = nodeById.get(e.source.nodeId);
    const targetNode = nodeById.get(e.target.nodeId);
    if (!sourceNode || !targetNode) continue;
    const source = anchorFor(sourceNode, e.source, targetNode, "out");
    const target = anchorFor(targetNode, e.target, sourceNode, "in");
    const points = routedPolyline(source, target, e.line.waypoints);
    allSegs.push(...segsFor(e.id, points, e.line.lineJumps));
  }

  const jumpsByEdge = new Map<string, JumpPoint[]>();
  for (let i = 0; i < allSegs.length; i++) {
    for (let j = i + 1; j < allSegs.length; j++) {
      const s1 = allSegs[i];
      const s2 = allSegs[j];
      if (s1.edgeId === s2.edgeId) continue;
      const s1Jumps = s1.lineJumps !== "none";
      const s2Jumps = s2.lineJumps !== "none";
      if (!s1Jumps && !s2Jumps) continue;
      const pt = segIntersect(s1, s2);
      if (!pt) continue;
      // If both edges want jumps, the horizontal one hops over the vertical one
      // (arbitrary but consistent convention); otherwise whichever opted in hops.
      const jumper = s1Jumps && s2Jumps ? (s1.orientation === "h" ? s1 : s2) : s1Jumps ? s1 : s2;
      const list = jumpsByEdge.get(jumper.edgeId) ?? [];
      list.push({ point: pt, orientation: jumper.orientation });
      jumpsByEdge.set(jumper.edgeId, list);
    }
  }
  return jumpsByEdge;
}
