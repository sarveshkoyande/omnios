import type { NodeType } from "../../schema/nodeTypes";

// Section 5 semantic cheat sheet + Section 1.5 expanded shape table (`@{ shape: x }`
// syntax) + Section 1.4 classic bracket syntax. Export reuses nodeDefaults'
// shapeKeyFor() directly since our ShapeKey values already ARE the Section-1.5 short
// names; this file supplies the reverse (shape/alias -> NodeType) for Mermaid import,
// where the mapping is inherently many-to-one so we pick one canonical NodeType per key.

export const SHAPE_ALIAS_TO_TYPE: Record<string, NodeType> = {
  // process family
  rect: "process", proc: "process", process: "process", rectangle: "process",
  "st-rect": "process", processes: "process", procs: "process", "stacked-rectangle": "process",
  "div-rect": "process", "div-proc": "process", "divided-process": "process",
  "lin-rect": "process", "lin-proc": "process", "lined-process": "process", "shaded-process": "process",
  "tag-rect": "process", "tag-proc": "process", "tagged-process": "process",
  // event
  rounded: "event", event: "event",
  // terminal
  stadium: "terminal", pill: "terminal", terminal: "terminal",
  // start
  circle: "start", circ: "start", "sm-circ": "start", "small-circle": "start", start: "start",
  // end
  "dbl-circ": "end", "double-circle": "end", "fr-circ": "end", "framed-circle": "end", stop: "end",
  // decision
  diam: "decision", decision: "decision", diamond: "decision", question: "decision",
  // prepare
  hex: "prepare", hexagon: "prepare", prepare: "prepare",
  // subprocess
  "fr-rect": "subprocess", subproc: "subprocess", subprocess: "subprocess", subroutine: "subprocess", "framed-rectangle": "subprocess",
  // data-io
  "lean-r": "data-io", "in-out": "data-io", "lean-right": "data-io",
  "lean-l": "data-io", "out-in": "data-io", "lean-left": "data-io",
  // database
  cyl: "database", cylinder: "database", database: "database", db: "database",
  // direct-access-storage
  "h-cyl": "direct-access-storage", das: "direct-access-storage", "horizontal-cylinder": "direct-access-storage",
  // disk
  "lin-cyl": "disk", disk: "disk", "lined-cylinder": "disk",
  // data-store
  datastore: "data-store", "data-store": "data-store",
  // stored-data
  "bow-rect": "stored-data", "bow-tie-rectangle": "stored-data", "stored-data": "stored-data",
  // internal-storage
  "win-pane": "internal-storage", "internal-storage": "internal-storage", "window-pane": "internal-storage",
  // document
  doc: "document", document: "document",
  // multi-document
  docs: "multi-document", documents: "multi-document", "st-doc": "multi-document", "stacked-document": "multi-document",
  // lined-document
  "lin-doc": "lined-document", "lined-document": "lined-document",
  // tagged-document
  "tag-doc": "tagged-document", "tagged-document": "tagged-document",
  // manual-operation
  "trap-t": "manual-operation", manual: "manual-operation", "inv-trapezoid": "manual-operation", "trapezoid-top": "manual-operation",
  "flip-tri": "manual-operation", "flipped-triangle": "manual-operation", "manual-file": "manual-operation",
  // manual-input
  "sl-rect": "manual-input", "manual-input": "manual-input", "sloped-rectangle": "manual-input",
  // priority-action
  "trap-b": "priority-action", priority: "priority-action", trapezoid: "priority-action", "trapezoid-bottom": "priority-action",
  // delay
  delay: "delay", "half-rounded-rectangle": "delay",
  // display
  "curv-trap": "display", "curved-trapezoid": "display", display: "display",
  // loop-limit
  "notch-pent": "loop-limit", "loop-limit": "loop-limit", "notched-pentagon": "loop-limit",
  // extract
  tri: "extract", extract: "extract", triangle: "extract",
  // collate
  hourglass: "collate", collate: "collate",
  // fork / join
  fork: "fork", join: "join",
  // junction
  "f-circ": "junction", "filled-circle": "junction", junction: "junction",
  // summary
  "cross-circ": "summary", "crossed-circle": "summary", summary: "summary",
  // card
  "notch-rect": "card", card: "card", "notched-rectangle": "card",
  // paper-tape
  flag: "paper-tape", "paper-tape": "paper-tape",
  // com-link
  bolt: "com-link", "com-link": "com-link", "lightning-bolt": "com-link",
  // comment
  brace: "comment", "brace-l": "comment", "brace-r": "comment", braces: "comment", comment: "comment",
  // cloud / custom / text
  cloud: "cloud", bang: "custom", odd: "custom", text: "text",
};

// Section 1.4 classic bracket syntax -> NodeType, checked in this order (most specific
// multi-character delimiters first so e.g. `(((x)))` isn't mis-matched as `(x)`).
export const CLASSIC_BRACKET_PATTERNS: { regex: RegExp; type: NodeType }[] = [
  { regex: /^\(\(\((.*)\)\)\)$/, type: "end" },        // (((text)))
  { regex: /^\(\((.*)\)\)$/, type: "start" },          // ((text))
  { regex: /^\(\[(.*)\]\)$/, type: "terminal" },       // ([text])
  { regex: /^\[\[(.*)\]\]$/, type: "subprocess" },     // [[text]]
  { regex: /^\[\((.*)\)\]$/, type: "database" },       // [(text)]
  { regex: /^\{\{(.*)\}\}$/, type: "prepare" },        // {{text}}
  { regex: /^\{(.*)\}$/, type: "decision" },           // {text}
  { regex: /^\[\/(.*)\\\]$/, type: "manual-operation" }, // [/text\]
  { regex: /^\[\\(.*)\/\]$/, type: "priority-action" }, // [\text/]
  { regex: /^\[\/(.*)\/\]$/, type: "data-io" },        // [/text/]
  { regex: /^\[\\(.*)\\\]$/, type: "data-io" },        // [\text\]
  { regex: /^>(.*)\]$/, type: "paper-tape" },          // >text]
  { regex: /^\((.*)\)$/, type: "event" },              // (text)
  { regex: /^\[(.*)\]$/, type: "process" },            // [text]
];
