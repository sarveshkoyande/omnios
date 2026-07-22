export type Severity = "error" | "warning";

export interface ValidationIssue {
  id: string;
  rule: number;
  severity: Severity;
  pageId: string;
  elementType: "node" | "edge" | "group" | "document";
  elementId?: string;
  message: string;
  fixable?: boolean;
}
