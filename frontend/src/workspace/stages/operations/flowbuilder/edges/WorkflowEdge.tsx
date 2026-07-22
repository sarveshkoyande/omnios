import { memo } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getStraightPath,
  type EdgeProps,
  type Edge,
} from "@xyflow/react";
import type { WorkflowEdge as SchemaEdge } from "../schema/edge";
import type { JumpPoint } from "./jumps";
import { markerUrl } from "./markers";

export type WorkflowRFEdgeData = { schemaEdge: SchemaEdge; jumpPoints?: JumpPoint[]; forceAutoRoute?: boolean };
export type WorkflowRFEdge = Edge<WorkflowRFEdgeData, "workflow">;

type Pt = { x: number; y: number };
type PolylineSample = { point: Pt; tangent: Pt };

function samePoint(a: Pt, b: Pt): boolean {
  return Math.abs(a.x - b.x) < 0.01 && Math.abs(a.y - b.y) < 0.01;
}

function isAxisAligned(a: Pt, b: Pt): boolean {
  return Math.abs(a.x - b.x) < 0.01 || Math.abs(a.y - b.y) < 0.01;
}

function isCollinear(a: Pt, b: Pt, c: Pt): boolean {
  return (Math.abs(a.x - b.x) < 0.01 && Math.abs(b.x - c.x) < 0.01) || (Math.abs(a.y - b.y) < 0.01 && Math.abs(b.y - c.y) < 0.01);
}

function normalize(v: Pt): Pt {
  const len = Math.hypot(v.x, v.y);
  if (len === 0) return { x: 0, y: 0 };
  return { x: v.x / len, y: v.y / len };
}

function buildPolylinePath(points: Pt[]): string {
  const cleaned = compactPolyline(points);
  if (cleaned.length === 0) return "";
  let d = `M ${cleaned[0].x} ${cleaned[0].y}`;
  for (let i = 1; i < cleaned.length; i++) d += ` L ${cleaned[i].x} ${cleaned[i].y}`;
  return d;
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

function routedPolyline(routing: SchemaEdge["line"]["routing"], source: Pt, target: Pt, waypoints: Pt[]): Pt[] {
  if (waypoints.length > 0) return orthogonalizePoints([source, ...waypoints, target]);
  if (routing === "orthogonal" || routing === "step") return orthogonalPolyline(source, target, []);
  return [source, target];
}

function sideVector(position: EdgeProps["sourcePosition"] | EdgeProps["targetPosition"]): Pt {
  switch (String(position)) {
    case "top":
      return { x: 0, y: -1 };
    case "right":
      return { x: 1, y: 0 };
    case "bottom":
      return { x: 0, y: 1 };
    case "left":
      return { x: -1, y: 0 };
    default:
      return { x: 0, y: 1 };
  }
}

function directionalOrthogonalPolyline(
  source: Pt,
  target: Pt,
  sourcePosition: EdgeProps["sourcePosition"],
  targetPosition: EdgeProps["targetPosition"],
  waypoints: Pt[],
): Pt[] {
  const stub = 34;
  const sourceVec = sideVector(sourcePosition);
  const targetVec = sideVector(targetPosition);
  const sourceStub = { x: source.x + sourceVec.x * stub, y: source.y + sourceVec.y * stub };
  const targetStub = { x: target.x + targetVec.x * stub, y: target.y + targetVec.y * stub };

  if (waypoints.length > 0) {
    return orthogonalizePoints([source, sourceStub, ...waypoints, targetStub, target]);
  }

  const bridge: Pt[] = [];
  if (!isAxisAligned(sourceStub, targetStub)) {
    const sourceVertical = sourceVec.y !== 0;
    const targetVertical = targetVec.y !== 0;
    if (sourceVertical && targetVertical) {
      const midY = (sourceStub.y + targetStub.y) / 2;
      bridge.push({ x: sourceStub.x, y: midY }, { x: targetStub.x, y: midY });
    } else if (!sourceVertical && !targetVertical) {
      const midX = (sourceStub.x + targetStub.x) / 2;
      bridge.push({ x: midX, y: sourceStub.y }, { x: midX, y: targetStub.y });
    } else if (sourceVertical) {
      bridge.push({ x: sourceStub.x, y: targetStub.y });
    } else {
      bridge.push({ x: targetStub.x, y: sourceStub.y });
    }
  }

  return compactPolyline([source, sourceStub, ...bridge, targetStub, target]);
}

// Threads the edge through ELK's bend points or the schema waypoints. The path is
// rendered as a rounded polyline so orthogonal layout still reads fluidly instead of
// as a set of hard, janky elbows.
function buildPath(
  routing: SchemaEdge["line"]["routing"],
  source: Pt,
  target: Pt,
  sourcePosition: EdgeProps["sourcePosition"],
  targetPosition: EdgeProps["targetPosition"],
  waypoints: Pt[]
): [string, number, number] {
  if (routing === "straight" && waypoints.length === 0) {
    const args = { sourceX: source.x, sourceY: source.y, sourcePosition, targetX: target.x, targetY: target.y, targetPosition };
    const [path, lx, ly] = getStraightPath(args);
    return [path, lx, ly];
  }
  const points =
    routing === "orthogonal" || routing === "step"
      ? directionalOrthogonalPolyline(source, target, sourcePosition, targetPosition, waypoints)
      : routedPolyline(routing, source, target, waypoints);
  const d = buildPolylinePath(points);
  const mid = points[Math.floor(points.length / 2)];
  return [d, mid.x, mid.y];
}

// Same source->waypoints->target polyline as buildPath's orthogonal branch, but
// returned as points rather than a path string, so a jump hop can be spliced
// into whichever segment it falls on.
function orthogonalPolyline(source: Pt, target: Pt, waypoints: Pt[]): Pt[] {
  const pts = [source, ...waypoints, target];
  const out: Pt[] = [pts[0]];
  for (let i = 1; i < pts.length; i++) {
    const a = pts[i - 1];
    const b = pts[i];
    const midX = (a.x + b.x) / 2;
    out.push({ x: midX, y: a.y }, { x: midX, y: b.y }, b);
  }
  return out;
}

/** Fraction-free "is this point on this axis-aligned segment" check (with slack for
 *  rounding drift between the schema-computed jump point and RF's rendered handle). */
function onSegment(p: Pt, a: Pt, b: Pt, eps = 6): boolean {
  if (Math.abs(a.y - b.y) < 0.5) {
    if (Math.abs(p.y - a.y) > eps) return false;
    const lo = Math.min(a.x, b.x);
    const hi = Math.max(a.x, b.x);
    return p.x > lo + eps && p.x < hi - eps;
  }
  if (Math.abs(a.x - b.x) < 0.5) {
    if (Math.abs(p.x - a.x) > eps) return false;
    const lo = Math.min(a.y, b.y);
    const hi = Math.max(a.y, b.y);
    return p.y > lo + eps && p.y < hi - eps;
  }
  return false;
}

function appendSegmentWithHops(a: Pt, b: Pt, jumps: Pt[], style: "arc" | "gap" | "square", radius: number): string {
  const onThisSeg = jumps.filter((j) => onSegment(j, a, b, radius + 4));
  if (onThisSeg.length === 0) return ` L ${b.x} ${b.y}`;

  const horizontal = Math.abs(a.y - b.y) < 0.5;
  const sorted = [...onThisSeg].sort((p, q) =>
    horizontal ? (a.x < b.x ? p.x - q.x : q.x - p.x) : a.y < b.y ? p.y - q.y : q.y - p.y
  );

  let d = "";
  let cursor = a;
  for (const j of sorted) {
    const hopStyle = style === "arc" ? "square" : style;
    if (horizontal) {
      const before = { x: j.x - radius, y: a.y };
      const after = { x: j.x + radius, y: a.y };
      if (!samePoint(cursor, before)) d += ` L ${before.x} ${before.y}`;
      if (hopStyle === "square") d += ` L ${before.x} ${a.y - radius} L ${after.x} ${a.y - radius} L ${after.x} ${after.y}`;
      else d += ` M ${after.x} ${after.y}`;
      cursor = after;
    } else {
      const before = { x: a.x, y: j.y - radius };
      const after = { x: a.x, y: j.y + radius };
      if (!samePoint(cursor, before)) d += ` L ${before.x} ${before.y}`;
      if (hopStyle === "square") d += ` L ${a.x + radius} ${before.y} L ${a.x + radius} ${after.y} L ${after.x} ${after.y}`;
      else d += ` M ${after.x} ${after.y}`;
      cursor = after;
    }
  }

  if (!samePoint(cursor, b)) d += ` L ${b.x} ${b.y}`;
  return d;
}

// Draw the same stepped polyline with both rounded corners and optional jump hops
// so overlap handling stays consistent without reintroducing diagonal curve segments.
function buildPathWithHops(points: Pt[], jumps: Pt[], style: "arc" | "gap" | "square", jumpRadius = 8): string {
  const cleaned = points.filter((p, i) => i === 0 || !samePoint(p, points[i - 1]));
  if (cleaned.length <= 1) return cleaned.length === 0 ? "" : `M ${cleaned[0].x} ${cleaned[0].y}`;

  let d = `M ${cleaned[0].x} ${cleaned[0].y}`;
  for (let i = 0; i < cleaned.length - 1; i++) {
    d += appendSegmentWithHops(cleaned[i], cleaned[i + 1], jumps, style, jumpRadius);
  }

  return d;
}

// Interpolates along the source->waypoints->target polyline by cumulative Euclidean
// distance. Used for label placement instead of SVG textPath, whose glyphs flip upside
// down whenever the underlying path segment runs right-to-left or bottom-to-top.
function samplePolylineAtFraction(points: Pt[], fraction: number): PolylineSample {
  const lengths: number[] = [];
  let total = 0;
  for (let i = 1; i < points.length; i++) {
    const d = Math.hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y);
    lengths.push(d);
    total += d;
  }
  if (total === 0) return { point: points[0], tangent: { x: 1, y: 0 } };
  let target = fraction * total;
  for (let i = 0; i < lengths.length; i++) {
    if (target <= lengths[i] || i === lengths.length - 1) {
      const t = lengths[i] === 0 ? 0 : target / lengths[i];
      return {
        point: {
          x: points[i].x + (points[i + 1].x - points[i].x) * t,
          y: points[i].y + (points[i + 1].y - points[i].y) * t,
        },
        tangent: normalize({
          x: points[i + 1].x - points[i].x,
          y: points[i + 1].y - points[i].y,
        }),
      };
    }
    target -= lengths[i];
  }
  return { point: points[points.length - 1], tangent: { x: 1, y: 0 } };
}

function labelNormalFor(tangent: Pt): Pt {
  const raw = normalize({ x: -tangent.y, y: tangent.x });
  if (samePoint(raw, { x: 0, y: 0 })) return { x: 0, y: -1 };
  if (Math.abs(raw.y) >= Math.abs(raw.x)) return raw.y > 0 ? { x: -raw.x, y: -raw.y } : raw;
  return raw.x < 0 ? { x: -raw.x, y: -raw.y } : raw;
}

function WorkflowEdgeImpl({
  id,
  data,
  sourceX,
  sourceY,
  sourcePosition,
  targetX,
  targetY,
  targetPosition,
  selected,
}: EdgeProps<WorkflowRFEdge>) {
  const edge = data!.schemaEdge;
  const line = edge.line;

  const source: Pt = { x: sourceX, y: sourceY };
  const target: Pt = { x: targetX, y: targetY };
  const waypoints: Pt[] = data?.forceAutoRoute ? [] : line.waypoints;
  const labelTrack =
    line.routing === "orthogonal" || line.routing === "step"
      ? directionalOrthogonalPolyline(source, target, sourcePosition, targetPosition, waypoints)
      : routedPolyline(line.routing, source, target, waypoints);

  const canJump = !data?.forceAutoRoute && line.lineJumps !== "none" && (line.routing === "orthogonal" || line.routing === "step");
  const jumpPoints = canJump ? (data!.jumpPoints ?? []).map((j) => j.point) : [];
  const [path] =
    jumpPoints.length > 0
      ? [buildPathWithHops(labelTrack, jumpPoints, line.lineJumps as "arc" | "gap" | "square")]
      : buildPath(line.routing, source, target, sourcePosition, targetPosition, waypoints);

  const dashArray = line.style === "dotted" ? "6,5" : undefined;
  const weight = line.style === "thick" ? Math.max(line.weight, 4) : line.weight;
  const animated = edge.animation?.enabled;
  const speed = edge.animation?.speed === "fast" ? "0.6s" : edge.animation?.speed === "slow" ? "2.4s" : "1.2s";
  const labels = edge.labels ?? (edge.label ? [{ text: edge.label, position: 0.5 }] : []);

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        style={{
          stroke: selected ? "#2563EB" : line.color,
          strokeWidth: weight,
          strokeDasharray: dashArray,
          animation: animated ? `wf-dash ${speed} linear infinite` : undefined,
          strokeLinecap: "round",
          strokeLinejoin: "round",
        }}
        markerStart={markerUrl(line.arrowStart)}
        markerEnd={markerUrl(line.arrowEnd)}
        interactionWidth={20}
      />

      {labels.length > 0 && (
        <EdgeLabelRenderer>
          {labels.map((l, i) => {
            const sample = samplePolylineAtFraction(labelTrack, l.position);
            const normal = labelNormalFor(sample.tangent);
            const offset = 26;
            const p = {
              x: sample.point.x + normal.x * offset,
              y: sample.point.y + normal.y * offset,
            };
            return (
              <div
                key={i}
                className="wf-edge-label"
                style={{ transform: `translate(-50%, -50%) translate(${p.x}px, ${p.y}px)` }}
              >
                {l.text}
              </div>
            );
          })}
        </EdgeLabelRenderer>
      )}
    </>
  );
}

export const WorkflowEdge = memo(WorkflowEdgeImpl);
export const edgeTypes = { workflow: WorkflowEdge };
