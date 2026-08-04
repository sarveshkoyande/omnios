import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { ConsolePanel } from "../../../components/ConsolePanel";
import { tokens, indigoTint } from "../../../theme/tokens";
import { useWorkflowStore } from "./flowbuilder/store/useWorkflowStore";
import type { Page } from "./flowbuilder/schema/document";
import type { WorkflowNode } from "./flowbuilder/schema/node";
import type { CampaignPlan } from "../../types";

// The rail mirrors the *live* diagram, not the frozen plan result: the operations
// agent (and manual edits) rewrite the WorkflowDocument in the flowbuilder store,
// so trigger + steps are derived from it and only fall back to plan.flow when no
// document is loaded yet. Goal/audience/summary prose still comes from the plan â€”
// the agent doesn't rewrite those.

function fieldValue(n: WorkflowNode, key: string): string | number | boolean | null {
  const f = n.data?.[key];
  return f && typeof f === "object" && "value" in f ? f.value : null;
}

function collectNodeText(node: WorkflowNode): string[] {
  const out: string[] = [];
  if (node.label.trim()) out.push(node.label.trim());
  if (node.richLabel?.markdown?.trim()) out.push(node.richLabel.markdown.trim());
  for (const value of Object.values(node.data ?? {})) {
    const field = value as { value?: unknown } | string | null | undefined;
    if (typeof field === "string" && field.trim()) out.push(field.trim());
    else if (field && typeof field === "object" && "value" in field) {
      const v = field.value;
      if (typeof v === "string" && v.trim()) out.push(v.trim());
    }
  }
  return out;
}

function findMatchingText(page: Page | undefined, pattern: RegExp): string | null {
  if (!page) return null;
  for (const node of page.nodes) {
    const texts = collectNodeText(node);
    const match = texts.find((text) => pattern.test(text));
    if (match) {
      const content = texts.find((text) => !pattern.test(text));
      return content ?? match;
    }
  }
  return null;
}

// Journey-order the diagram's nodes (Kahn topological sort, document order as the
// tie-break) so "Expected steps" reads start-to-close even after a node is inserted
// mid-flow (which lands at the end of page.nodes' insertion order).
function journeyOrder(page: Page): WorkflowNode[] {
  const nodes = page.nodes.filter((n) => n.type !== "comment" && n.type !== "text");
  const ids = new Set(nodes.map((n) => n.id));
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const indegree = new Map(nodes.map((n) => [n.id, 0]));
  const outgoing = new Map<string, string[]>();
  for (const e of page.edges) {
    if (!ids.has(e.source.nodeId) || !ids.has(e.target.nodeId)) continue;
    indegree.set(e.target.nodeId, (indegree.get(e.target.nodeId) ?? 0) + 1);
    outgoing.set(e.source.nodeId, [...(outgoing.get(e.source.nodeId) ?? []), e.target.nodeId]);
  }
  const queue = nodes.filter((n) => (indegree.get(n.id) ?? 0) === 0).map((n) => n.id);
  const seen = new Set<string>();
  const ordered: WorkflowNode[] = [];
  while (queue.length) {
    const id = queue.shift()!;
    if (seen.has(id)) continue;
    seen.add(id);
    ordered.push(byId.get(id)!);
    for (const t of outgoing.get(id) ?? []) {
      const d = (indegree.get(t) ?? 1) - 1;
      indegree.set(t, d);
      if (d <= 0) queue.push(t);
    }
  }
  for (const n of nodes) if (!seen.has(n.id)) ordered.push(n); // cycle leftovers
  return ordered;
}

const Label = ({ children }: { children: string }) => (
  <Typography sx={{ fontSize: tokens.fontSize.xs, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: "text.secondary", mb: 0.5 }}>
    {children}
  </Typography>
);

const Panel = ({ children, sx }: { children: React.ReactNode; sx?: object }) => (
  <Box
    sx={{
      border: `1px solid ${indigoTint(0.12)}`,
      borderRadius: 2,
      background: "rgba(255,255,255,0.72)",
      p: 1.75,
      minWidth: 0,
      ...sx,
    }}
  >
    {children}
  </Box>
);

export function PlanningSummaryRail({ plan }: { plan: CampaignPlan }) {
  const document = useWorkflowStore((s) => s.document);
  const activePageId = useWorkflowStore((s) => s.activePageId);
  const page = document.pages.find((p) => p.id === activePageId) ?? document.pages[0];
  const liveNodes = page && page.nodes.length > 0 ? journeyOrder(page) : null;
  const docDescription = document.description.trim();

  const liveGoal = findMatchingText(page, /\b(goal|objective)\b/i) ?? (docDescription || plan.overview.objective);
  const liveSummary = findMatchingText(page, /\bsummary\b/i) ?? (docDescription || plan.summary);

  const audienceSegments = plan.segments.map((s) => ({
    key: s.key,
    name: s.name,
    profile: s.profile,
    key_characteristics: s.key_characteristics ?? [],
    volume: s.volume,
    volume_note: s.volume_note ?? null,
    volume_exact: s.volume_exact ?? false,
  }));

  return (
    <ConsolePanel title="Planning summary" icon="fact_check" collapsible>
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: {
            xs: "1fr",
            md: "repeat(2, minmax(0, 1fr))",
            xl: "1fr 1.35fr",
          },
          gap: 2,
          alignItems: "start",
        }}
      >
        <Panel>
          <Label>Business goal</Label>
          <Typography variant="body2" sx={{ lineHeight: 1.7, overflowWrap: "anywhere" }}>{liveGoal || "N/A"}</Typography>
        </Panel>

        <Panel>
          <Label>Target audience</Label>
          {audienceSegments.length ? (
            <Box sx={{ display: "grid", gap: 1 }}>
              {audienceSegments.map((s) => (
                <Box key={s.key} sx={{ borderLeft: `3px solid ${indigoTint(0.45)}`, pl: 1.25, minWidth: 0 }}>
                  <Typography variant="body2" sx={{ fontWeight: 700, lineHeight: 1.3, overflowWrap: "anywhere" }}>
                    {s.name}{s.volume ? ` - ${s.volume_exact ? "" : "~"}${s.volume.toLocaleString()}` : ""}
                  </Typography>
                  {s.profile && (
                    <Typography variant="caption" sx={{ color: "text.secondary", display: "block", lineHeight: 1.45, overflowWrap: "anywhere" }}>
                      {s.profile}
                    </Typography>
                  )}
                  {s.volume_note && (
                    <Typography variant="caption" sx={{ color: "text.secondary", display: "block", lineHeight: 1.45, overflowWrap: "anywhere" }}>
                      {s.volume_note}
                    </Typography>
                  )}
                  {s.key_characteristics.length > 0 && (
                    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, mt: 0.75 }}>
                      {s.key_characteristics.slice(0, 4).map((tag) => (
                        <Box
                          key={tag}
                          component="span"
                          sx={{
                            px: 0.75,
                            py: 0.25,
                            borderRadius: 999,
                            border: `1px solid ${indigoTint(0.12)}`,
                            background: "rgba(255,255,255,0.74)",
                            color: "text.secondary",
                            fontSize: tokens.fontSize.xs,
                            lineHeight: 1.35,
                          }}
                        >
                          {tag}
                        </Box>
                      ))}
                    </Box>
                  )}
                </Box>
              ))}
            </Box>
          ) : (
            <Typography variant="body2" sx={{ color: "text.secondary", fontStyle: "italic" }}>
              No segments selected.
            </Typography>
          )}
        </Panel>

        <Panel sx={{ gridColumn: "1 / -1", bgcolor: "rgba(11,61,145,0.03)" }}>
          <Label>Expected steps</Label>
          <Box
            component="ul"
            sx={{
              m: 0,
              p: 0,
              listStyle: "none",
              display: "grid",
              gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))" },
              gap: 1,
              fontSize: tokens.fontSize.sm,
            }}
          >
            {liveNodes
              ? liveNodes.map((n) => {
                  const day = fieldValue(n, "day");
                  return (
                    <Box
                      component="li"
                      key={n.id}
                      sx={{
                        display: "flex",
                        gap: 1,
                        alignItems: "flex-start",
                        p: 1,
                        borderRadius: 1.5,
                        border: `1px solid ${indigoTint(0.1)}`,
                        background: "rgba(255,255,255,0.72)",
                        minWidth: 0,
                        overflowWrap: "anywhere",
                      }}
                    >
                      <Typography variant="caption" sx={{ flex: "0 0 auto", color: "primary.main", fontWeight: 800, pt: 0.1 }}>
                        {day != null ? `Day ${day}` : "Step"}
                      </Typography>
                      <Typography variant="body2" sx={{ lineHeight: 1.45, overflowWrap: "anywhere" }}>{n.label}</Typography>
                    </Box>
                  );
                })
              : plan.flow.nodes.map((n) => (
                  <Box
                    component="li"
                    key={n.id}
                    sx={{
                      display: "flex",
                      gap: 1,
                      alignItems: "flex-start",
                      p: 1,
                      borderRadius: 1.5,
                      border: `1px solid ${indigoTint(0.1)}`,
                      background: "rgba(255,255,255,0.72)",
                      minWidth: 0,
                      overflowWrap: "anywhere",
                    }}
                  >
                    <Typography variant="caption" sx={{ flex: "0 0 auto", color: "primary.main", fontWeight: 800, pt: 0.1 }}>
                      {`Day ${n.data.day ?? "N/A"}`}
                    </Typography>
                    <Typography variant="body2" sx={{ lineHeight: 1.45, overflowWrap: "anywhere" }}>{n.data.label}</Typography>
                  </Box>
                ))}
          </Box>
        </Panel>

        <Panel sx={{ gridColumn: { xs: "1", xl: "1 / -1" }, borderLeft: { xs: `1px solid ${indigoTint(0.12)}`, xl: `4px solid ${indigoTint(0.22)}` } }}>
          <Label>Summary</Label>
          <Typography variant="body2" sx={{ color: "text.secondary", lineHeight: 1.7, overflowWrap: "anywhere" }}>{liveSummary}</Typography>
        </Panel>
      </Box>
    </ConsolePanel>
  );
}
