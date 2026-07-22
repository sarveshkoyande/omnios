import type { WorkflowDocument } from "../schema/document";
import { parseDocument, serializeDocument } from "../schema";
import { downloadText } from "./download";

export function downloadDocumentJSON(doc: WorkflowDocument): void {
  downloadText(`${doc.name.replace(/[^\w-]+/g, "_")}.json`, serializeDocument(doc), "application/json");
}

export function readDocumentFile(file: File): Promise<{ ok: true; document: WorkflowDocument } | { ok: false; errors: string[] }> {
  return file.text().then((text) => {
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch (e) {
      return { ok: false, errors: [`Invalid JSON: ${(e as Error).message}`] };
    }
    return parseDocument(parsed);
  });
}
