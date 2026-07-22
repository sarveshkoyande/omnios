import { z } from "zod";

// Section 3.4 groups, lanes, layers.

export const GroupKindSchema = z.enum([
  "group",
  "container",
  "list",
  "lane",
  "pool",
  "subgraph",
  "phase",
]);

export const MemberBehaviorSchema = z
  .object({
    moveWith: z.boolean().default(true),
    deleteWith: z.enum(["always", "prompt", "never"]).default("prompt"),
    autoResize: z.boolean().default(true),
  })
  .passthrough();

export const GroupStyleSchema = z
  .object({
    fill: z.string().optional(),
    stroke: z.string().optional(),
    strokeWidth: z.number().optional(),
  })
  .passthrough();

export const GroupSchema = z
  .object({
    id: z.string(),
    kind: GroupKindSchema,
    label: z.string(),
    parentId: z.string().nullable().optional(),
    order: z.number().optional(),
    direction: z.enum(["TB", "BT", "LR", "RL"]).optional(),
    memberBehavior: MemberBehaviorSchema.optional(),
    collapsed: z.boolean().default(false),
    style: GroupStyleSchema.optional(),
    // Bounding box: lanes/pools/containers render as bands and need an explicit rect
    // (not spelled out in the 3.4 snippet, but required for band rendering + resize).
    bounds: z.object({ x: z.number(), y: z.number(), w: z.number(), h: z.number() }).optional(),
  })
  .passthrough();

export type GroupKind = z.infer<typeof GroupKindSchema>;
export type Group = z.infer<typeof GroupSchema>;
export type MemberBehavior = z.infer<typeof MemberBehaviorSchema>;
