// ID generators. Spec (Section 6 rules, Section 3.6 rule 12) mandates unique,
// snake_case, prefixed IDs: n_ nodes, e_ edges, lane_ lanes/groups, p_ ports.
// Reserved words that break Mermaid export must never be used as bare IDs
// (rule: never emit 'end' lowercase, or an id starting with bare 'o'/'x' after link syntax).

let counter = 0;

function nextCounter(): string {
  counter += 1;
  return counter.toString(36);
}

function toSnakeCase(input: string): string {
  return input
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 40);
}

function makeId(prefix: string, hint?: string): string {
  const base = hint ? toSnakeCase(hint) : "";
  const suffix = nextCounter();
  return base ? `${prefix}${base}_${suffix}` : `${prefix}${suffix}`;
}

export const generateNodeId = (hint?: string): string => makeId("n_", hint);
export const generateEdgeId = (hint?: string): string => makeId("e_", hint);
export const generateLaneId = (hint?: string): string => makeId("lane_", hint);
export const generatePortId = (hint?: string): string => makeId("p_", hint);
export const generateGroupId = (hint?: string): string => makeId("group_", hint);
export const generateLayerId = (hint?: string): string => makeId("layer_", hint);
export const generateDocId = (hint?: string): string => makeId("wf_", hint);
export const generatePageId = (hint?: string): string => makeId("p_page_", hint);
export const generateStencilId = (hint?: string): string => makeId("stencil_", hint);
export const generateDataSetId = (hint?: string): string => makeId("dataset_", hint);

// Reserved id/label guard for Mermaid interop (Section 6 master-prompt rule).
const RESERVED_MERMAID_ID = /^end$/i;
const BARE_LINK_ARROW_START = /^[ox]$/i;

export function isReservedMermaidId(id: string): boolean {
  return RESERVED_MERMAID_ID.test(id) || BARE_LINK_ARROW_START.test(id);
}

export function sanitizeForMermaid(id: string): string {
  return isReservedMermaidId(id) ? `id_${id}` : id;
}
