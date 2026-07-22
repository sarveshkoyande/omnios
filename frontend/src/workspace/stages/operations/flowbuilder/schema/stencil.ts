import { z } from "zod";
import { PortSchema } from "./port";
import { DataRecordSchema, DATA_FIELD_TYPES } from "./dataField";
import { NodeTypeSchema, SizeSchema, NodeStyleSchema } from "./node";

// Section 3.5 stencils and data sets.

export const StencilMasterSchema = z
  .object({
    id: z.string(),
    type: NodeTypeSchema,
    label: z.string(),
    icon: z.string().optional(),
    // "geometry as SVG path or primitive"
    geometry: z
      .union([
        z.object({ kind: z.literal("primitive"), name: z.string() }),
        z.object({ kind: z.literal("svgPath"), d: z.string(), viewBox: z.string().optional() }),
      ])
      .optional(),
    defaultSize: SizeSchema.optional(),
    defaultPorts: z.array(PortSchema).optional(),
    defaultData: DataRecordSchema.optional(),
    defaultStyle: NodeStyleSchema.optional(),
  })
  .passthrough();

export const StencilSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    masters: z.array(StencilMasterSchema),
  })
  .passthrough();

// Data set field *definitions* (no value) — applied to nodes to seed their data.value.
export const DataSetFieldDefSchema = z
  .object({
    type: z.enum(DATA_FIELD_TYPES as unknown as [string, ...string[]]),
    label: z.string().optional(),
    name: z.string().optional(),
    format: z.string().optional(),
    prompt: z.string().optional(),
    sortKey: z.number().optional(),
    hidden: z.boolean().optional(),
    askOnDrop: z.boolean().optional(),
    options: z.array(z.string()).optional(),
    currency: z.string().optional(),
    defaultValue: z.unknown().optional(),
  })
  .passthrough();

export const DataSetExternalBindingSchema = z
  .object({
    source: z.string(), // e.g. filename of the bound CSV/Excel table
    columnMap: z.record(z.string(), z.string()), // fieldName -> column header
    refreshedAt: z.string().optional(),
  })
  .passthrough();

export const DataSetSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    fields: z.record(z.string(), DataSetFieldDefSchema),
    externalBinding: DataSetExternalBindingSchema.optional(),
  })
  .passthrough();

export type StencilMaster = z.infer<typeof StencilMasterSchema>;
export type Stencil = z.infer<typeof StencilSchema>;
export type DataSet = z.infer<typeof DataSetSchema>;
export type DataSetFieldDef = z.infer<typeof DataSetFieldDefSchema>;
