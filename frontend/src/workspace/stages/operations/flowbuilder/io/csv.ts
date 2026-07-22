import type { Page } from "../schema/document";

// Section 2.5 Data Visualizer pattern / Section 4 "CSV 'Data Visualizer' table (Step ID,
// Label, Type, Next Steps, Connector Labels, Lane, Phase, + data columns)".

function csvEscape(v: string): string {
  if (/[",\n]/.test(v)) return `"${v.replace(/"/g, '""')}"`;
  return v;
}

export function pageToCSV(page: Page): string {
  const groupById = new Map(page.groups.map((g) => [g.id, g]));
  const dataColumns = Array.from(new Set(page.nodes.flatMap((n) => Object.keys(n.data)))).sort();

  const header = ["Step ID", "Label", "Type", "Next Steps", "Connector Labels", "Lane", "Phase", ...dataColumns];
  const rows = [header];

  for (const n of page.nodes) {
    const outbound = page.edges.filter((e) => e.source.nodeId === n.id);
    const nextSteps = outbound.map((e) => e.target.nodeId).join(";");
    const connectorLabels = outbound.map((e) => e.label ?? e.labels?.[0]?.text ?? "").join(";");
    const group = n.groupId ? groupById.get(n.groupId) : undefined;
    const lane = group && (group.kind === "lane" || group.kind === "pool") ? group.label : "";
    const phase = group && group.kind === "phase" ? group.label : "";
    const dataValues = dataColumns.map((col) => {
      const field = n.data[col];
      return field?.value === null || field?.value === undefined ? "" : String(field.value);
    });
    rows.push([n.id, n.label, n.type, nextSteps, connectorLabels, lane, phase, ...dataValues]);
  }

  return rows.map((row) => row.map(csvEscape).join(",")).join("\n");
}
