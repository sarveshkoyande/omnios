import type { Page } from "../../schema/document";
import type { Direction } from "../../schema/document";
import type { WorkflowEdge } from "../../schema/edge";
import { shapeKeyFor } from "../../schema/nodeDefaults";
import { sanitizeForMermaid } from "../../schema/ids";

// Section 6 CONVERT rules + Appendix A. Lossy items (positions, ports, data types
// beyond simple key=value, glue mode, waypoints, validation profile, etc.) are
// collected and returned alongside the text rather than silently dropped.

const FALLBACK_SHAPE: Record<string, string> = {
  "pentagon-tab": "notch-pent",
  icon: "text",
  image: "text",
};

function escapeLabel(s: string): string {
  return s.replace(/"/g, "#quot;");
}

function edgeOperator(edge: WorkflowEdge): { op: string; labeled: (l: string) => string } {
  const thick = edge.line.style === "thick" || edge.type === "critical";
  const dotted = edge.line.style === "dotted" || edge.type === "optional" || edge.type === "dataflow" || edge.type === "message";

  if (edge.type === "invisible") return { op: "~~~", labeled: () => "~~~" };
  if (edge.type === "association") return { op: "---", labeled: (l) => `-- ${l} ---` };
  if (edge.type === "bidirectional") return { op: "<-->", labeled: (l) => `<-- ${l} -->` };
  if (edge.type === "blocked") return { op: "--x", labeled: (l) => `-- ${l} --x` };
  if (edge.type === "reads") return { op: "--o", labeled: (l) => `-- ${l} --o` };
  if (thick) return { op: "==>", labeled: (l) => `== ${l} ==>` };
  if (dotted) return { op: "-.->", labeled: (l) => `-. ${l} .->` };
  return { op: "-->", labeled: (l) => `-->|${l}|` };
}

export function pageToMermaid(page: Page, direction: Direction): { text: string; lossy: string[] } {
  const lossy: string[] = [];
  const lines: string[] = [`flowchart ${direction}`];
  const idOf = new Map(page.nodes.map((n) => [n.id, sanitizeForMermaid(n.id)]));
  for (const [orig, safe] of idOf) if (orig !== safe) lossy.push(`Node id "${orig}" renamed to "${safe}" (reserved in Mermaid).`);

  const laneKinds = new Set(["lane", "pool", "subgraph"]);
  const lanes = page.groups.filter((g) => laneKinds.has(g.kind) && page.nodes.some((n) => n.groupId === g.id));
  const unlaned = page.nodes.filter((n) => !lanes.some((g) => g.id === n.groupId));

  const emitNode = (n: (typeof page.nodes)[number], indent: string) => {
    const id = idOf.get(n.id)!;
    const shape = FALLBACK_SHAPE[shapeKeyFor(n.type)] ?? shapeKeyFor(n.type);
    if (FALLBACK_SHAPE[shapeKeyFor(n.type)]) {
      lossy.push(`Node "${n.label}" (${n.type}) has no direct Mermaid shape; approximated as "${shape}".`);
    }
    lines.push(`${indent}${id}@{ shape: ${shape}, label: "${escapeLabel(n.label)}" }`);
    const dataEntries = Object.entries(n.data).filter(([, f]) => f.value !== null && f.value !== "");
    if (dataEntries.length > 0) {
      const kv = dataEntries.map(([k, f]) => `${id}.${k}=${f.value}`).join("; ");
      lines.push(`${indent}%% metadata: ${kv}`);
    }
    const urlLink = n.links?.find((l) => l.kind === "url" && l.href);
    if (urlLink) lines.push(`${indent}click ${id} "${urlLink.href}"${urlLink.tooltip ? ` "${urlLink.tooltip}"` : ""} _blank`);
    if (n.style?.fill || n.style?.stroke) {
      const parts = [n.style.fill && `fill:${n.style.fill}`, n.style.stroke && `stroke:${n.style.stroke}`, n.style.strokeWidth && `stroke-width:${n.style.strokeWidth}px`].filter(Boolean);
      lines.push(`${indent}style ${id} ${parts.join(",")}`);
    }
    if (n.style?.classNames?.length) {
      lines.push(`${indent}class ${id} ${n.style.classNames.join(",")}`);
      lossy.push(`Class names on "${n.label}" exported as a class assignment; no classDef body is emitted (styling not roundtripped).`);
    }
  };

  for (const g of lanes) {
    lines.push(`  subgraph ${idOf.get(g.id) ?? sanitizeForMermaid(g.id)} [${escapeLabel(g.label)}]`);
    for (const n of page.nodes.filter((n) => n.groupId === g.id)) emitNode(n, "    ");
    lines.push("  end");
  }
  for (const n of unlaned) emitNode(n, "  ");

  let edgeCounter = 0;
  for (const e of page.edges) {
    const s = idOf.get(e.source.nodeId);
    const t = idOf.get(e.target.nodeId);
    if (!s || !t) continue;
    const { op, labeled } = edgeOperator(e);
    const label = e.label ?? e.labels?.[0]?.text;
    const eid = `e${++edgeCounter}`;
    lines.push(`  ${eid}@${s} ${label ? labeled(escapeLabel(label)) : op} ${t}`);
    if (e.animation?.enabled) lines.push(`  ${eid}@{ animate: true }`);
    if (e.source.glue === "static" || e.target.glue === "static") {
      lossy.push(`Edge ${e.id}: static glue (port binding) has no Mermaid equivalent — exported as a plain connection.`);
    }
    if (e.line.waypoints.length > 0) lossy.push(`Edge ${e.id}: manual waypoints are not representable in Mermaid and were dropped.`);
  }

  if (page.layers.length > 0) lossy.push(`${page.layers.length} layer(s) (visibility/lock/glue) have no Mermaid equivalent and were dropped.`);
  lossy.push("Node/edge positions, sizes, and ports are not roundtripped — Mermaid always computes its own layout.");

  return { text: lines.join("\n"), lossy };
}
