import { z } from "zod";

// Section 2.4 "Shape Data" — the eight typed data fields Visio ships, adopted verbatim
// as the Section 3.2 node.data / edge.data value types. Every field additionally carries
// label/name/format/prompt/sortKey/hidden/askOnDrop per the spec's field-attribute list.

const fieldCommon = {
  label: z.string().optional(),
  name: z.string().optional(),
  format: z.string().optional(),
  prompt: z.string().optional(),
  sortKey: z.number().optional(),
  hidden: z.boolean().optional(),
  askOnDrop: z.boolean().optional(),
};

export const StringFieldSchema = z
  .object({ type: z.literal("string"), value: z.string().nullable(), ...fieldCommon })
  .passthrough();

export const NumberFieldSchema = z
  .object({ type: z.literal("number"), value: z.number().nullable(), ...fieldCommon })
  .passthrough();

export const FixedListFieldSchema = z
  .object({
    type: z.literal("fixedList"),
    value: z.string().nullable(),
    options: z.array(z.string()),
    ...fieldCommon,
  })
  .passthrough();

export const VariableListFieldSchema = z
  .object({
    type: z.literal("variableList"),
    value: z.string().nullable(),
    options: z.array(z.string()).optional(),
    ...fieldCommon,
  })
  .passthrough();

// ISO 8601 duration string, e.g. PT4H, P1D. Unit-aware editor decomposes this in the UI.
export const DurationFieldSchema = z
  .object({ type: z.literal("duration"), value: z.string().nullable(), ...fieldCommon })
  .passthrough();

export const DateFieldSchema = z
  .object({ type: z.literal("date"), value: z.string().nullable(), ...fieldCommon })
  .passthrough();

export const CurrencyFieldSchema = z
  .object({
    type: z.literal("currency"),
    value: z.number().nullable(),
    currency: z.string().default("USD"),
    ...fieldCommon,
  })
  .passthrough();

export const BooleanFieldSchema = z
  .object({ type: z.literal("boolean"), value: z.boolean().nullable(), ...fieldCommon })
  .passthrough();

export const DataFieldSchema = z.discriminatedUnion("type", [
  StringFieldSchema,
  NumberFieldSchema,
  FixedListFieldSchema,
  VariableListFieldSchema,
  DurationFieldSchema,
  DateFieldSchema,
  CurrencyFieldSchema,
  BooleanFieldSchema,
]);

export type DataField = z.infer<typeof DataFieldSchema>;
export type DataFieldType = DataField["type"];

export const DataRecordSchema = z.record(z.string(), DataFieldSchema);
export type DataRecord = z.infer<typeof DataRecordSchema>;

export const DATA_FIELD_TYPES: DataFieldType[] = [
  "string",
  "number",
  "fixedList",
  "variableList",
  "duration",
  "date",
  "currency",
  "boolean",
];

export function emptyDataField(type: DataFieldType): DataField {
  switch (type) {
    case "string":
      return { type, value: null };
    case "number":
      return { type, value: null };
    case "fixedList":
      return { type, value: null, options: [] };
    case "variableList":
      return { type, value: null, options: [] };
    case "duration":
      return { type, value: null };
    case "date":
      return { type, value: null };
    case "currency":
      return { type, value: null, currency: "USD" };
    case "boolean":
      return { type, value: null };
  }
}
