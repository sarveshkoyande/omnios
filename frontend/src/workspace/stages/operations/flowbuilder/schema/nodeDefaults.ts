import type { NodeType } from "./nodeTypes";
import type { Port } from "./port";
import type { DataRecord } from "./dataField";

// Default geometry (Section 5 semantic cheat sheet + Section 1.5 expanded shape table),
// default ports, and default data set (Section 6 master-prompt rule: "every node gets
// at minimum owner, sla, and status data fields, use null values if unknown") per
// Section 3.2 node type. This is what the palette instantiates and what nodeDefaults
// falls back to for stencil masters that don't override a field.

export type ShapeKey =
  | "rect" | "rounded" | "stadium" | "circle" | "sm-circ" | "dbl-circ" | "fr-circ"
  | "diam" | "hex" | "fr-rect" | "lean-r" | "lean-l" | "cyl" | "h-cyl" | "lin-cyl"
  | "datastore" | "bow-rect" | "win-pane" | "doc" | "docs" | "lin-doc" | "tag-doc"
  | "st-rect" | "div-rect" | "lin-rect" | "tag-rect" | "trap-t" | "sl-rect" | "flip-tri"
  | "trap-b" | "delay" | "curv-trap" | "notch-pent" | "tri" | "hourglass" | "fork"
  | "f-circ" | "cross-circ" | "notch-rect" | "flag" | "bolt" | "brace" | "cloud"
  | "bang" | "odd" | "text" | "icon" | "image" | "pentagon-tab";

const SHAPE_KEY: Record<NodeType, ShapeKey> = {
  start: "sm-circ",
  end: "dbl-circ",
  terminal: "stadium",
  process: "rect",
  subprocess: "fr-rect",
  decision: "diam",
  prepare: "hex",
  event: "rounded",
  delay: "delay",
  "loop-limit": "notch-pent",
  fork: "fork",
  join: "fork",
  junction: "f-circ",
  summary: "cross-circ",
  "manual-operation": "trap-t",
  "manual-input": "sl-rect",
  "priority-action": "trap-b",
  extract: "tri",
  collate: "hourglass",

  "data-io": "lean-r",
  database: "cyl",
  "data-store": "datastore",
  "stored-data": "bow-rect",
  "internal-storage": "win-pane",
  "direct-access-storage": "h-cyl",
  disk: "lin-cyl",
  document: "doc",
  "multi-document": "docs",
  "lined-document": "lin-doc",
  "tagged-document": "tag-doc",
  card: "notch-rect",
  "paper-tape": "flag",
  display: "curv-trap",

  comment: "brace",
  text: "text",
  "on-page-ref": "f-circ",
  "off-page-ref": "pentagon-tab",
  "com-link": "bolt",
  cloud: "cloud",
  icon: "icon",
  image: "image",
  custom: "odd",

  "event.start.message": "circle",
  "event.start.timer": "circle",
  "event.start.error": "circle",
  "event.start.signal": "circle",
  "event.intermediate.message": "circle",
  "event.intermediate.timer": "circle",
  "event.intermediate.error": "circle",
  "event.intermediate.signal": "circle",
  "event.end.message": "dbl-circ",
  "event.end.timer": "dbl-circ",
  "event.end.error": "dbl-circ",
  "event.end.signal": "dbl-circ",

  "task.user": "rounded",
  "task.service": "rounded",
  "task.script": "rounded",
  "task.manual": "rounded",

  "gateway.exclusive": "diam",
  "gateway.parallel": "diam",
  "gateway.inclusive": "diam",
  "gateway.event": "diam",
};

const ROUND_TYPES = new Set<NodeType>([
  "start", "end", "terminal", "junction", "summary",
  "event.start.message", "event.start.timer", "event.start.error", "event.start.signal",
  "event.intermediate.message", "event.intermediate.timer", "event.intermediate.error", "event.intermediate.signal",
  "event.end.message", "event.end.timer", "event.end.error", "event.end.signal",
]);

export function defaultSizeFor(type: NodeType): { w: number; h: number; resizable?: boolean } {
  if (ROUND_TYPES.has(type)) return { w: 60, h: 60, resizable: true };
  if (type === "decision" || type.startsWith("gateway.")) return { w: 140, h: 90, resizable: true };
  if (type === "comment" || type === "text") return { w: 160, h: 50, resizable: true };
  return { w: 160, h: 80, resizable: true };
}

const START_ONLY: NodeType[] = ["start", "event.start.message", "event.start.timer", "event.start.error", "event.start.signal"];
const END_ONLY: NodeType[] = ["end", "event.end.message", "event.end.timer", "event.end.error", "event.end.signal"];
const NO_PORTS: NodeType[] = ["comment", "text"];

// Port ids are stable, human-readable names ("in", "out", "yes", "no"...) — not
// counter-suffixed generated ids — because they're the handle a connector glues to
// (static glue stores this id permanently) and the thing a Mermaid/CSV export or a
// hand-edited JSON file needs to reference predictably. Matches the Section 3.2
// example's own port ids ("in"/"yes"/"no"). generatePortId() is reserved for ports a
// user adds interactively via the Connection Point tool, where uniqueness matters more
// than readability.
export function defaultPortsFor(type: NodeType): Port[] {
  if (NO_PORTS.includes(type)) return [];

  if (START_ONLY.includes(type)) {
    return [{ id: "out", side: "bottom", offset: 0.5, direction: "out", name: "out" }];
  }
  if (END_ONLY.includes(type)) {
    return [{ id: "in", side: "top", offset: 0.5, direction: "in", name: "in" }];
  }
  if (type === "decision") {
    return [
      { id: "in", side: "top", offset: 0.5, direction: "in", name: "input" },
      { id: "yes", side: "right", offset: 0.5, direction: "out", name: "yes" },
      { id: "no", side: "bottom", offset: 0.5, direction: "out", name: "no" },
      { id: "alt", side: "left", offset: 0.5, direction: "out", name: "alt" },
    ];
  }
  if (type.startsWith("gateway.")) {
    return [
      { id: "in", side: "top", offset: 0.5, direction: "in", name: "in" },
      { id: "out1", side: "right", offset: 0.5, direction: "out", name: "out1" },
      { id: "out2", side: "bottom", offset: 0.5, direction: "out", name: "out2" },
    ];
  }
  if (type === "fork") {
    return [
      { id: "in", side: "top", offset: 0.5, direction: "in", name: "in" },
      { id: "out1", side: "right", offset: 0.3, direction: "out", name: "out1" },
      { id: "out2", side: "bottom", offset: 0.5, direction: "out", name: "out2" },
    ];
  }
  if (type === "join") {
    return [
      { id: "in1", side: "left", offset: 0.3, direction: "in", name: "in1" },
      { id: "in2", side: "top", offset: 0.5, direction: "in", name: "in2" },
      { id: "out", side: "bottom", offset: 0.5, direction: "out", name: "out" },
    ];
  }
  // Every ordinary node also gets a left/right pair, on top of the top/bottom
  // "in"/"out" pair above -- four connection points per node instead of two, so
  // side-by-side boxes (a common layout in wide flows) can connect directly
  // instead of routing all the way up over the top or down under the bottom.
  // Ids "in"/"out" are preserved unchanged for backward compatibility with
  // existing saved diagrams' static port references.
  return [
    { id: "in", side: "top", offset: 0.5, direction: "in", name: "in" },
    { id: "out", side: "bottom", offset: 0.5, direction: "out", name: "out" },
    { id: "in-left", side: "left", offset: 0.5, direction: "in", name: "in" },
    { id: "out-right", side: "right", offset: 0.5, direction: "out", name: "out" },
  ];
}

export function defaultDataFor(): DataRecord {
  return {
    owner: { type: "string", value: null, label: "Owner" },
    sla: { type: "duration", value: null, label: "SLA" },
    status: {
      type: "fixedList",
      value: "Draft",
      options: ["Draft", "Active", "Deprecated"],
      label: "Status",
    },
  };
}

export function shapeKeyFor(type: NodeType): ShapeKey {
  return SHAPE_KEY[type];
}
