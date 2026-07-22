// Section 3.2 node type catalog — full vocabulary, superset of Mermaid v11 + Visio flowchart + BPMN-lite.
// Each entry maps to default geometry / ports / data set / validation rules (see nodeDefaults.ts).

export const FLOW_CONTROL_TYPES = [
  "start",
  "end",
  "terminal",
  "process",
  "subprocess",
  "decision",
  "prepare",
  "event",
  "delay",
  "loop-limit",
  "fork",
  "join",
  "junction",
  "summary",
  "manual-operation",
  "manual-input",
  "priority-action",
  "extract",
  "collate",
] as const;

export const DATA_STORAGE_TYPES = [
  "data-io",
  "database",
  "data-store",
  "stored-data",
  "internal-storage",
  "direct-access-storage",
  "disk",
  "document",
  "multi-document",
  "lined-document",
  "tagged-document",
  "card",
  "paper-tape",
  "display",
] as const;

export const ANNOTATION_STRUCTURE_TYPES = [
  "comment",
  "text",
  "on-page-ref",
  "off-page-ref",
  "com-link",
  "cloud",
  "icon",
  "image",
  "custom",
] as const;

// BPMN-lite extension. Spec gives "event.start.message|timer" etc with an ellipsis in
// section 2.2 ("start/intermediate/end × message/timer/error/signal…") — expanded here
// as the concrete cross product so the type is a closed, machine-checkable enum.
// (Written out as literal tuples, not computed, so TS preserves the literal union —
// .map()/.flatMap() over a const tuple widens to `string` and loses that.)
export const BPMN_EVENT_TYPES = [
  "event.start.message", "event.start.timer", "event.start.error", "event.start.signal",
  "event.intermediate.message", "event.intermediate.timer", "event.intermediate.error", "event.intermediate.signal",
  "event.end.message", "event.end.timer", "event.end.error", "event.end.signal",
] as const;
export const BPMN_TASK_TYPES = ["task.user", "task.service", "task.script", "task.manual"] as const;
export const BPMN_GATEWAY_TYPES = [
  "gateway.exclusive", "gateway.parallel", "gateway.inclusive", "gateway.event",
] as const;

export const NODE_TYPES = [
  ...FLOW_CONTROL_TYPES,
  ...DATA_STORAGE_TYPES,
  ...ANNOTATION_STRUCTURE_TYPES,
  ...BPMN_EVENT_TYPES,
  ...BPMN_TASK_TYPES,
  ...BPMN_GATEWAY_TYPES,
] as const;

export type NodeType = (typeof NODE_TYPES)[number];

export const NODE_TYPE_CATEGORY: Record<NodeType, "flow-control" | "data-storage" | "annotation" | "bpmn-lite"> =
  Object.fromEntries([
    ...FLOW_CONTROL_TYPES.map((t) => [t, "flow-control"] as const),
    ...DATA_STORAGE_TYPES.map((t) => [t, "data-storage"] as const),
    ...ANNOTATION_STRUCTURE_TYPES.map((t) => [t, "annotation"] as const),
    ...BPMN_EVENT_TYPES.map((t) => [t, "bpmn-lite"] as const),
    ...BPMN_TASK_TYPES.map((t) => [t, "bpmn-lite"] as const),
    ...BPMN_GATEWAY_TYPES.map((t) => [t, "bpmn-lite"] as const),
  ]) as Record<NodeType, "flow-control" | "data-storage" | "annotation" | "bpmn-lite">;
