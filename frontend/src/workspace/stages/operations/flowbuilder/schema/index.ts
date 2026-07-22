import { WorkflowDocumentSchema } from "./document";
import type { WorkflowDocument } from "./document";

export * from "./ids";
export * from "./nodeTypes";
export * from "./nodeDefaults";
export * from "./dataField";
export * from "./port";
export * from "./node";
export * from "./edge";
export * from "./group";
export * from "./layer";
export * from "./stencil";
export * from "./document";
export * from "./factories";

export type ParseResult =
  | { ok: true; document: WorkflowDocument }
  | { ok: false; errors: string[] };

// Round-trip contract: parseDocument(serializeDocument(doc)) is structurally identical
// to doc for every field the schema knows about (Section: "quality bar" — lossless
// serialization). .passthrough() on every object schema preserves unknown/future keys.
export function parseDocument(input: unknown): ParseResult {
  const result = WorkflowDocumentSchema.safeParse(input);
  if (!result.success) {
    const errors = result.error.issues.map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`);
    return { ok: false, errors };
  }
  return { ok: true, document: result.data };
}

export function serializeDocument(document: WorkflowDocument): string {
  return JSON.stringify(document, null, 2);
}
