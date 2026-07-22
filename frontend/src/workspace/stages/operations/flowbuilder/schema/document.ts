import { z } from "zod";
import { NodeSchema } from "./node";
import { EdgeSchema } from "./edge";
import { GroupSchema } from "./group";
import { LayerSchema } from "./layer";
import { StencilMasterSchema, DataSetSchema } from "./stencil";

// Section 3.1 top-level document, field names verbatim.

export const DirectionSchema = z.enum(["TB", "BT", "LR", "RL"]);

export const ThemeSchema = z
  .object({ palette: z.string().default("default"), curve: z.string().default("step") })
  .passthrough();

export const DocMetaSchema = z
  .object({
    owner: z.string().default(""),
    status: z.enum(["draft", "published", "deprecated"]).default("draft"),
    version: z.number().default(1),
    tags: z.array(z.string()).default([]),
    createdAt: z.string().default(""),
    updatedAt: z.string().default(""),
  })
  .passthrough();

export const PageSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    nodes: z.array(NodeSchema).default([]),
    edges: z.array(EdgeSchema).default([]),
    groups: z.array(GroupSchema).default([]),
    // Layers are page-scoped (Visio convention); orthogonal to groups per Section 3.4.
    layers: z.array(LayerSchema).default([]),
  })
  .passthrough();

export const WorkflowDocumentSchema = z
  .object({
    schemaVersion: z.literal("1.0"),
    id: z.string(),
    name: z.string(),
    description: z.string().default(""),
    direction: DirectionSchema.default("TB"),
    pages: z.array(PageSchema).min(1),
    stencils: z.array(z.string()).default([]),
    dataSets: z.array(DataSetSchema).default([]),
    theme: ThemeSchema.default({ palette: "default", curve: "step" }),
    validationProfile: z.string().default("strict-flowchart"),
    meta: DocMetaSchema.default({
      owner: "",
      status: "draft",
      version: 1,
      tags: [],
      createdAt: "",
      updatedAt: "",
    }),
    // Additive: Section 3.5's "My Shapes" custom-master feature ("Save selected node
    // as custom master, adds to a My Shapes stencil kept in the document's stencils")
    // needs somewhere to actually persist the master definitions. `stencils` per the
    // 3.1 example is a flat string[] of stencil ids, so custom masters are kept here
    // and surfaced in the palette under a synthetic "My Shapes" stencil.
    customMasters: z.array(StencilMasterSchema).default([]),
  })
  .passthrough();

export type Direction = z.infer<typeof DirectionSchema>;
export type Page = z.infer<typeof PageSchema>;
export type WorkflowDocument = z.infer<typeof WorkflowDocumentSchema>;
export type DocMeta = z.infer<typeof DocMetaSchema>;
