import { z } from "zod";
import { PortSchema } from "./port";
import { DataRecordSchema } from "./dataField";
import { NODE_TYPES } from "./nodeTypes";
export type { NodeType } from "./nodeTypes";

// Section 3.2 node object, field names verbatim.

export const NodeTypeSchema = z.enum(NODE_TYPES);

export const PositionSchema = z.object({ x: z.number(), y: z.number() }).passthrough();

export const SizeSchema = z
  .object({ w: z.number(), h: z.number(), resizable: z.boolean().optional() })
  .passthrough();

export const RichLabelSchema = z.object({ markdown: z.string() }).passthrough();

export const NodeStyleSchema = z
  .object({
    fill: z.string().optional(),
    stroke: z.string().optional(),
    strokeWidth: z.number().optional(),
    classNames: z.array(z.string()).optional(),
  })
  .passthrough();

export const DataGraphicRuleSchema = z
  .object({
    rule: z.string(), // expression string, evaluated against node.data at render time
    apply: z.record(z.string(), z.unknown()),
  })
  .passthrough();

export const NodeLinkSchema = z
  .object({
    kind: z.enum(["url", "page", "shape"]),
    href: z.string().optional(),
    pageId: z.string().optional(),
    nodeId: z.string().optional(),
    tooltip: z.string().optional(),
  })
  .passthrough();

export const LocksSchema = z
  .object({
    delete: z.boolean().optional(),
    move: z.boolean().optional(),
    resize: z.boolean().optional(),
    select: z.boolean().optional(),
  })
  .passthrough();

export const A11ySchema = z
  .object({ title: z.string().optional(), description: z.string().optional() })
  .passthrough();

export const CommentSchema = z
  .object({ author: z.string().optional(), text: z.string(), at: z.string().optional() })
  .passthrough();

export const NodeSchema = z
  .object({
    id: z.string(),
    type: NodeTypeSchema,
    label: z.string(),
    richLabel: RichLabelSchema.optional(),
    position: PositionSchema,
    size: SizeSchema,
    ports: z.array(PortSchema).default([]),
    data: DataRecordSchema.default({}),
    style: NodeStyleSchema.optional(),
    dataGraphics: z.array(DataGraphicRuleSchema).optional(),
    links: z.array(NodeLinkSchema).optional(),
    groupId: z.string().nullable().optional(),
    layerIds: z.array(z.string()).default([]),
    locks: LocksSchema.optional(),
    a11y: A11ySchema.optional(),
    comments: z.array(CommentSchema).optional(),
    // Additive vs. the literal 3.2 example: Section 4's auto-layout spec requires a
    // per-node "pin" flag so manual positions survive layout runs. Not in the sample
    // JSON block but explicitly demanded by prose — kept optional, defaults to false.
    pinned: z.boolean().optional(),
  })
  .passthrough();

export type WorkflowNode = z.infer<typeof NodeSchema>;
export type NodeStyle = z.infer<typeof NodeStyleSchema>;
export type NodeLink = z.infer<typeof NodeLinkSchema>;
