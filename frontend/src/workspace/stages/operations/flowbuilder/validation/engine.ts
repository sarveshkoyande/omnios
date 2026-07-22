import type { WorkflowDocument } from "../schema/document";
import type { Page } from "../schema/document";
import type { WorkflowEdge } from "../schema/edge";
import { isReservedMermaidId } from "../schema/ids";
import type { ValidationIssue } from "./types";

// Section 3.6 — the 12 validation rules that make up the default "strict-flowchart"
// profile. One function per numbered rule; validateDocument runs all of them per page
// (plus the whole-document id-uniqueness check) and returns a flat issue list.

const START_TYPES = (t: string) => t === "start" || t.startsWith("event.start.");
const END_TYPES = (t: string) => t === "end" || t === "terminal" || t.startsWith("event.end.");
const ANNOTATION_TYPES = new Set(["comment", "text"]);

let seq = 0;
function issue(partial: Omit<ValidationIssue, "id">): ValidationIssue {
  seq += 1;
  return { id: `iss_${seq}`, ...partial };
}

function buildAdjacency(page: Page) {
  const out = new Map<string, WorkflowEdge[]>();
  const inn = new Map<string, WorkflowEdge[]>();
  for (const n of page.nodes) { out.set(n.id, []); inn.set(n.id, []); }
  for (const e of page.edges) {
    out.get(e.source.nodeId)?.push(e);
    inn.get(e.target.nodeId)?.push(e);
  }
  return { out, inn };
}

function forwardReachable(startIds: string[], out: Map<string, WorkflowEdge[]>): Set<string> {
  const seen = new Set<string>(startIds);
  const stack = [...startIds];
  while (stack.length) {
    const id = stack.pop()!;
    for (const e of out.get(id) ?? []) {
      if (!seen.has(e.target.nodeId)) { seen.add(e.target.nodeId); stack.push(e.target.nodeId); }
    }
  }
  return seen;
}

// Rule 1: >=1 start node; every path must reach an end/terminal.
function rule1(page: Page, out: Map<string, WorkflowEdge[]>): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const starts = page.nodes.filter((n) => START_TYPES(n.type));
  if (starts.length === 0) {
    issues.push(issue({ rule: 1, severity: "error", pageId: page.id, elementType: "document", message: "No start node on this page." }));
    return issues;
  }
  const endIds = new Set(page.nodes.filter((n) => END_TYPES(n.type)).map((n) => n.id));
  for (const n of page.nodes) {
    if (ANNOTATION_TYPES.has(n.type) || END_TYPES(n.type)) continue;
    const reachable = forwardReachable([n.id], out);
    const hasPath = [...reachable].some((id) => endIds.has(id));
    if (!hasPath) {
      issues.push(issue({ rule: 1, severity: "error", pageId: page.id, elementType: "node", elementId: n.id, message: `"${n.label}" has no path to an end/terminal node.` }));
    }
  }
  return issues;
}

// Rule 2: start has no inbound; end has no outbound.
function rule2(page: Page, out: Map<string, WorkflowEdge[]>, inn: Map<string, WorkflowEdge[]>): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  for (const n of page.nodes) {
    if (START_TYPES(n.type) && (inn.get(n.id)?.length ?? 0) > 0) {
      issues.push(issue({ rule: 2, severity: "error", pageId: page.id, elementType: "node", elementId: n.id, message: `Start node "${n.label}" has inbound edges.` }));
    }
    if (END_TYPES(n.type) && (out.get(n.id)?.length ?? 0) > 0) {
      issues.push(issue({ rule: 2, severity: "error", pageId: page.id, elementType: "node", elementId: n.id, message: `End node "${n.label}" has outbound edges.` }));
    }
  }
  return issues;
}

// Rule 3: every decision has >=2 outbound labeled edges.
function rule3(page: Page, out: Map<string, WorkflowEdge[]>): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  for (const n of page.nodes) {
    if (n.type !== "decision" && !n.type.startsWith("gateway.")) continue;
    const outgoing = out.get(n.id) ?? [];
    if (outgoing.length < 2) {
      issues.push(issue({ rule: 3, severity: "error", pageId: page.id, elementType: "node", elementId: n.id, message: `"${n.label}" needs at least 2 outbound branches (has ${outgoing.length}).` }));
    }
    for (const e of outgoing) {
      const label = e.label ?? e.labels?.[0]?.text;
      if (!label) {
        issues.push(issue({ rule: 3, severity: "error", pageId: page.id, elementType: "edge", elementId: e.id, message: `Branch from decision "${n.label}" is missing a label.`, fixable: true }));
      }
    }
  }
  return issues;
}

// Rule 4: every non-terminal node has >=1 inbound and >=1 outbound edge.
function rule4(page: Page, out: Map<string, WorkflowEdge[]>, inn: Map<string, WorkflowEdge[]>): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  for (const n of page.nodes) {
    if (ANNOTATION_TYPES.has(n.type) || START_TYPES(n.type) || END_TYPES(n.type)) continue;
    if ((inn.get(n.id)?.length ?? 0) === 0) {
      issues.push(issue({ rule: 4, severity: "error", pageId: page.id, elementType: "node", elementId: n.id, message: `"${n.label}" has no inbound edge (orphan).` }));
    }
    if ((out.get(n.id)?.length ?? 0) === 0) {
      issues.push(issue({ rule: 4, severity: "error", pageId: page.id, elementType: "node", elementId: n.id, message: `"${n.label}" has no outbound edge (dead end).` }));
    }
  }
  return issues;
}

// Rule 5: fork outputs should eventually reconcile at a join (warn otherwise).
function rule5(page: Page, out: Map<string, WorkflowEdge[]>): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const joinIds = new Set(page.nodes.filter((n) => n.type === "join").map((n) => n.id));
  for (const n of page.nodes) {
    if (n.type !== "fork") continue;
    const branches = out.get(n.id) ?? [];
    const reachable = forwardReachable(branches.map((e) => e.target.nodeId), out);
    if (![...reachable].some((id) => joinIds.has(id))) {
      issues.push(issue({ rule: 5, severity: "warning", pageId: page.id, elementType: "node", elementId: n.id, message: `Fork "${n.label}" branches never reconcile at a join.` }));
    }
  }
  return issues;
}

// Rule 6: no self-loops on start/end; cycles elsewhere allowed but flagged.
function rule6(page: Page, out: Map<string, WorkflowEdge[]>): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  for (const e of page.edges) {
    if (e.source.nodeId !== e.target.nodeId) continue;
    const node = page.nodes.find((n) => n.id === e.source.nodeId);
    if (node && (START_TYPES(node.type) || END_TYPES(node.type))) {
      issues.push(issue({ rule: 6, severity: "error", pageId: page.id, elementType: "edge", elementId: e.id, message: `Self-loop not allowed on start/end node "${node.label}".` }));
    }
  }

  // DFS cycle detection (report each back-edge once).
  const color = new Map<string, 0 | 1 | 2>();
  const reported = new Set<string>();
  const dfs = (id: string) => {
    color.set(id, 1);
    for (const e of out.get(id) ?? []) {
      if (e.source.nodeId === e.target.nodeId) continue;
      const c = color.get(e.target.nodeId) ?? 0;
      if (c === 1 && !reported.has(e.id)) {
        reported.add(e.id);
        issues.push(issue({ rule: 6, severity: "warning", pageId: page.id, elementType: "edge", elementId: e.id, message: `Edge "${e.id}" closes a cycle — allowed, but review for an unintended loop.` }));
      } else if (c === 0) {
        dfs(e.target.nodeId);
      }
    }
    color.set(id, 2);
  };
  for (const n of page.nodes) if (!color.has(n.id)) dfs(n.id);
  return issues;
}

// Rule 7: port direction respected (in ports only accept targets, out ports only sources).
function rule7(page: Page): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const byId = new Map(page.nodes.map((n) => [n.id, n]));
  for (const e of page.edges) {
    const src = byId.get(e.source.nodeId);
    const tgt = byId.get(e.target.nodeId);
    if (src && e.source.portId) {
      const port = src.ports.find((p) => p.id === e.source.portId);
      if (port && port.direction !== "out") {
        issues.push(issue({ rule: 7, severity: "error", pageId: page.id, elementType: "edge", elementId: e.id, message: `Edge source port "${e.source.portId}" on "${src.label}" is not an out port.` }));
      }
    }
    if (tgt && e.target.portId) {
      const port = tgt.ports.find((p) => p.id === e.target.portId);
      if (port && port.direction !== "in") {
        issues.push(issue({ rule: 7, severity: "error", pageId: page.id, elementType: "edge", elementId: e.id, message: `Edge target port "${e.target.portId}" on "${tgt.label}" is not an in port.` }));
      }
    }
  }
  return issues;
}

// Rule 8: edge endpoints must reference existing nodes/ports; static glue requires the port to exist.
function rule8(page: Page): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const byId = new Map(page.nodes.map((n) => [n.id, n]));
  for (const e of page.edges) {
    const src = byId.get(e.source.nodeId);
    const tgt = byId.get(e.target.nodeId);
    if (!src) issues.push(issue({ rule: 8, severity: "error", pageId: page.id, elementType: "edge", elementId: e.id, message: `Edge source node "${e.source.nodeId}" does not exist.` }));
    if (!tgt) issues.push(issue({ rule: 8, severity: "error", pageId: page.id, elementType: "edge", elementId: e.id, message: `Edge target node "${e.target.nodeId}" does not exist.` }));
    if (src && e.source.glue === "static" && e.source.portId && !src.ports.some((p) => p.id === e.source.portId)) {
      issues.push(issue({ rule: 8, severity: "error", pageId: page.id, elementType: "edge", elementId: e.id, message: `Statically-glued source port "${e.source.portId}" does not exist on "${src.label}".` }));
    }
    if (tgt && e.target.glue === "static" && e.target.portId && !tgt.ports.some((p) => p.id === e.target.portId)) {
      issues.push(issue({ rule: 8, severity: "error", pageId: page.id, elementType: "edge", elementId: e.id, message: `Statically-glued target port "${e.target.portId}" does not exist on "${tgt.label}".` }));
    }
  }
  return issues;
}

// Rule 9: off-page-ref must reference a valid page + paired node.
function rule9(doc: WorkflowDocument, page: Page): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  for (const n of page.nodes) {
    if (n.type !== "off-page-ref") continue;
    const ref = n.links?.find((l) => l.kind === "page" || l.kind === "shape");
    if (!ref || !ref.pageId || !doc.pages.some((p) => p.id === ref.pageId)) {
      issues.push(issue({ rule: 9, severity: "error", pageId: page.id, elementType: "node", elementId: n.id, message: `Off-page reference "${n.label}" does not point to a valid page.` }));
      continue;
    }
    const targetPage = doc.pages.find((p) => p.id === ref.pageId)!;
    if (ref.nodeId && !targetPage.nodes.some((tn) => tn.id === ref.nodeId)) {
      issues.push(issue({ rule: 9, severity: "error", pageId: page.id, elementType: "node", elementId: n.id, message: `Off-page reference "${n.label}" points to a missing paired node.` }));
    }
  }
  return issues;
}

// Rule 10: a node belongs to at most one lane (structural, always true); sequence edges
// shouldn't cross pools (BPMN convention — warn); groupId must reference a real group.
function rule10(page: Page): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const groupById = new Map(page.groups.map((g) => [g.id, g]));
  for (const n of page.nodes) {
    if (n.groupId && !groupById.has(n.groupId)) {
      issues.push(issue({ rule: 10, severity: "error", pageId: page.id, elementType: "node", elementId: n.id, message: `"${n.label}" references a missing lane/group "${n.groupId}".` }));
    }
  }
  const poolOf = (groupId: string | null | undefined): string | null => {
    if (!groupId) return null;
    const g = groupById.get(groupId);
    if (!g) return null;
    return g.kind === "pool" ? g.id : g.parentId ?? g.id;
  };
  const byId = new Map(page.nodes.map((n) => [n.id, n]));
  for (const e of page.edges) {
    if (e.type !== "sequence") continue;
    const src = byId.get(e.source.nodeId);
    const tgt = byId.get(e.target.nodeId);
    if (!src || !tgt) continue;
    const p1 = poolOf(src.groupId);
    const p2 = poolOf(tgt.groupId);
    if (p1 && p2 && p1 !== p2) {
      issues.push(issue({ rule: 10, severity: "warning", pageId: page.id, elementType: "edge", elementId: e.id, message: `Sequence edge crosses pools — use a "message" edge type instead.` }));
    }
  }
  return issues;
}

// Rule 11: required data fields must be non-empty before status moves draft -> published.
function rule11(doc: WorkflowDocument, page: Page): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  if (doc.meta.status !== "published") return issues;
  for (const n of page.nodes) {
    for (const [name, field] of Object.entries(n.data)) {
      if (field.hidden) continue;
      const empty = field.value === null || field.value === "";
      if (empty) {
        issues.push(issue({ rule: 11, severity: "error", pageId: page.id, elementType: "node", elementId: n.id, message: `"${n.label}" has an empty "${field.label ?? name}" field but the document is published.` }));
      }
    }
  }
  return issues;
}

// Rule 12: reserved/duplicate IDs rejected.
function rule12(doc: WorkflowDocument): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const seen = new Map<string, string>(); // id -> pageId (or "doc")

  const check = (id: string, pageId: string, elementType: ValidationIssue["elementType"]) => {
    if (isReservedMermaidId(id)) {
      issues.push(issue({ rule: 12, severity: "error", pageId, elementType, elementId: id, message: `Id "${id}" is reserved (breaks Mermaid export) — rename it.` }));
    }
    if (seen.has(id)) {
      issues.push(issue({ rule: 12, severity: "error", pageId, elementType, elementId: id, message: `Duplicate id "${id}" also used on page "${seen.get(id)}".` }));
    } else {
      seen.set(id, pageId);
    }
  };

  for (const page of doc.pages) {
    for (const n of page.nodes) check(n.id, page.id, "node");
    for (const e of page.edges) check(e.id, page.id, "edge");
    for (const g of page.groups) check(g.id, page.id, "group");
  }
  return issues;
}

export function validateDocument(doc: WorkflowDocument): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  for (const page of doc.pages) {
    const { out, inn } = buildAdjacency(page);
    issues.push(
      ...rule1(page, out),
      ...rule2(page, out, inn),
      ...rule3(page, out),
      ...rule4(page, out, inn),
      ...rule5(page, out),
      ...rule6(page, out),
      ...rule7(page),
      ...rule8(page),
      ...rule9(doc, page),
      ...rule10(page),
      ...rule11(doc, page)
    );
  }
  issues.push(...rule12(doc));
  return issues;
}
