import { z } from "zod";
import { DataRecordSchema } from "./dataField";
import { LocksSchema, CommentSchema } from "./node";

// Section 3.3 edge object, field names verbatim.

export const GlueModeSchema = z.enum(["static", "dynamic"]);

export const EdgeTypeSchema = z.enum([
  "sequence",
  "association",
  "optional",
  "dataflow",
  "critical",
  "message",
  "bidirectional",
  "blocked",
  "reads",
  "invisible",
]);

export const EdgeEndpointSchema = z
  .object({
    nodeId: z.string(),
    portId: z.string().optional(),
    glue: GlueModeSchema,
  })
  .passthrough();

export const EdgeLabelSchema = z
  .object({ text: z.string(), position: z.number().min(0).max(1) })
  .passthrough();

export const WaypointSchema = z.object({ x: z.number(), y: z.number() }).passthrough();

export const ArrowheadSchema = z.enum([
  "none",
  "arrow",
  "open-arrow",
  "circle",
  "circle-filled",
  "cross",
  "diamond",
  "diamond-filled",
]);

export const RoutingSchema = z.enum(["orthogonal", "straight", "curved", "step"]);
export const CurveSchema = z.enum([
  "basis",
  "bumpX",
  "bumpY",
  "cardinal",
  "catmullRom",
  "linear",
  "monotoneX",
  "monotoneY",
  "natural",
  "step",
  "stepAfter",
  "stepBefore",
]);
export const LineStyleSchema = z.enum(["solid", "dotted", "thick"]);
export const LineJumpsSchema = z.enum(["none", "arc", "gap", "square"]);

export const EdgeLineSchema = z
  .object({
    style: LineStyleSchema.default("solid"),
    weight: z.number().default(2),
    color: z.string().default("#333333"),
    arrowStart: ArrowheadSchema.default("none"),
    arrowEnd: ArrowheadSchema.default("arrow"),
    routing: RoutingSchema.default("step"),
    curve: CurveSchema.default("step"),
    lineJumps: LineJumpsSchema.default("arc"),
    waypoints: z.array(WaypointSchema).default([]),
  })
  .passthrough();

export const EdgeAnimationSchema = z
  .object({ enabled: z.boolean().default(false), speed: z.enum(["fast", "slow"]).optional() })
  .passthrough();

export const EdgeSchema = z
  .object({
    id: z.string(),
    source: EdgeEndpointSchema,
    target: EdgeEndpointSchema,
    type: EdgeTypeSchema.default("sequence"),
    label: z.string().optional(),
    labels: z.array(EdgeLabelSchema).optional(),
    line: EdgeLineSchema,
    data: DataRecordSchema.default({}),
    animation: EdgeAnimationSchema.optional(),
    layerIds: z.array(z.string()).default([]),
    locks: LocksSchema.optional(),
    comments: z.array(CommentSchema).optional(),
  })
  .passthrough();

export type GlueMode = z.infer<typeof GlueModeSchema>;
export type EdgeType = z.infer<typeof EdgeTypeSchema>;
export type EdgeEndpoint = z.infer<typeof EdgeEndpointSchema>;
export type EdgeLine = z.infer<typeof EdgeLineSchema>;
export type WorkflowEdge = z.infer<typeof EdgeSchema>;
export type Arrowhead = z.infer<typeof ArrowheadSchema>;
export type Routing = z.infer<typeof RoutingSchema>;
export type Curve = z.infer<typeof CurveSchema>;
export type LineJumps = z.infer<typeof LineJumpsSchema>;
