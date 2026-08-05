/**
 * The bottom shelf: collapsible cards instead of the long dense tables this tab used to end
 * with. Each card shows its headline number closed, and opens to the detail on demand —
 * optimisation opportunities, KPI scorecard, measurement framework, test design, learnings
 * and the UTM matrix.
 *
 * Collapse animates a 0fr/1fr grid row rather than unmounting, matching SectionCard, so the
 * height transition retargets cleanly if the user double-clicks.
 */
import type { ReactNode } from "react";
import { useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { hoverOnly, motion, tokens } from "../../../theme/tokens";
import { radius, StatusBadge, dataColor, statusColor } from "./dashboardKit";
import type { ReportingInsights } from "../../types";

function CollapsibleCard({
  icon, title, headline, sub, tone = "info", children, defaultOpen = false,
}: {
  icon: string;
  title: string;
  headline: string;
  sub?: string;
  tone?: "info" | "positive" | "warning" | "critical";
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const c = dataColor[tone];
  return (
    <Box sx={{
      background: tokens.color.surface,
      border: `1px solid ${tokens.color.outline}`,
      borderRadius: radius.md,
      overflow: "hidden",
      boxShadow: "0 1px 2px rgba(16,24,40,0.04)",
      transition: `box-shadow ${motion.duration.hover} ${motion.easeOut}`,
      [hoverOnly]: { "&:hover": { boxShadow: "0 8px 24px -16px rgba(16,24,40,0.35)" } },
    }}>
      <Box
        role="button"
        aria-expanded={open}
        tabIndex={0}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setOpen((v) => !v); } }}
        sx={{
          display: "flex", alignItems: "center", gap: 1.25, px: 2, py: 1.75, cursor: "pointer",
          "&:focus-visible": { outline: `2px solid ${c.line}`, outlineOffset: -2 },
        }}
      >
        <Box sx={{
          width: 32, height: 32, borderRadius: radius.sm, background: c.soft, color: c.ink,
          display: "grid", placeItems: "center", flex: "0 0 auto",
        }}>
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>{icon}</span>
        </Box>
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography sx={{ fontSize: 15, fontWeight: 700, lineHeight: 1.25 }}>{title}</Typography>
          <Box sx={{ display: "flex", alignItems: "baseline", gap: 0.75 }}>
            <Typography sx={{ fontSize: 20, fontWeight: 800, color: c.ink, lineHeight: 1.2 }}>{headline}</Typography>
            {sub && <Typography sx={{ fontSize: 15, color: "text.secondary" }}>{sub}</Typography>}
          </Box>
        </Box>
        <span
          className="material-symbols-outlined"
          style={{
            fontSize: 22, color: tokens.color.inkSecondary,
            transform: open ? "rotate(180deg)" : "none",
            transition: `transform ${motion.duration.hover} ${motion.easeOut}`,
          }}
        >
          expand_more
        </span>
      </Box>
      <Box sx={{
        display: "grid",
        gridTemplateRows: open ? "1fr" : "0fr",
        transition: `grid-template-rows ${motion.duration.panel} ${motion.easeOut}`,
      }}>
        <Box sx={{ minHeight: 0, overflow: "hidden" }} inert={!open} aria-hidden={!open}>
          <Box sx={{ px: 2, pb: 2, pt: 0.5, borderTop: `1px solid ${tokens.color.outline}` }}>{children}</Box>
        </Box>
      </Box>
    </Box>
  );
}

const cellSx = { fontSize: 15, padding: "8px 10px", borderBottom: `1px solid ${tokens.color.outline}`, textAlign: "left" as const };
const headSx = { ...cellSx, fontWeight: 700, color: tokens.color.inkSecondary, whiteSpace: "nowrap" as const };

function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <Box sx={{ overflowX: "auto" }}>
      <Box component="table" sx={{ width: "100%", borderCollapse: "collapse", minWidth: 420 }}>
        <thead>
          <tr>{head.map((h) => <Box component="th" key={h} sx={headSx}>{h}</Box>)}</tr>
        </thead>
        <tbody>{children}</tbody>
      </Box>
    </Box>
  );
}

export function DeepDivePanels({ insights }: { insights: ReportingInsights }) {
  const optimizations = insights.optimizations ?? [];
  const scorecard = insights.scorecard;
  const framework = insights.framework;
  const tests = insights.test_design;
  const learnings = insights.learnings ?? [];
  const tagging = insights.tagging;
  const highImpact = optimizations.filter((o) => o.impact === "High").length;

  return (
    <Box sx={{
      display: "grid",
      gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
      gap: 2,
      alignItems: "start",
    }}>
      <CollapsibleCard
        icon="rocket_launch"
        title="Optimisation opportunities"
        headline={String(optimizations.length)}
        sub={highImpact ? `${highImpact} high impact` : undefined}
        tone={highImpact ? "warning" : "info"}
      >
        <Box sx={{ display: "flex", flexDirection: "column", gap: 1.25, pt: 1 }}>
          {optimizations.map((o) => (
            <Box key={o.title} sx={{ display: "flex", gap: 1.25, alignItems: "flex-start" }}>
              <StatusBadge status={o.impact === "High" ? "warning" : "info"} label={o.impact} />
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{ fontSize: 15, fontWeight: 700 }}>{o.title}</Typography>
                <Typography sx={{ fontSize: 15, color: "text.secondary" }}>{o.detail} · {o.metric}</Typography>
              </Box>
            </Box>
          ))}
        </Box>
      </CollapsibleCard>

      {scorecard && (
        <CollapsibleCard
          icon="scoreboard"
          title="KPI scorecard"
          headline={`${scorecard.on_track} / ${scorecard.tracked}`}
          sub="on track"
          tone={scorecard.on_track === scorecard.tracked ? "positive" : "warning"}
        >
          <Table head={["KPI", "Value", "Benchmark", "Status"]}>
            {scorecard.rows.map((r) => (
              <tr key={r.key}>
                <Box component="td" sx={cellSx}>{r.label}</Box>
                <Box component="td" sx={{ ...cellSx, fontWeight: 700 }}>
                  {r.value}{r.unit === "%" ? "%" : ""}
                </Box>
                <Box component="td" sx={cellSx}>{r.benchmark ?? "—"}</Box>
                <Box component="td" sx={cellSx}>
                  <StatusBadge status={r.status} label={r.status === "good" ? "On track" : r.status === "watch" ? "Watch" : "At risk"} />
                </Box>
              </tr>
            ))}
          </Table>
        </CollapsibleCard>
      )}

      {framework && (
        <CollapsibleCard
          icon="fact_check"
          title="Measurement framework"
          headline={`${framework.coverage_pct}%`}
          sub={`${framework.live} of ${framework.total} sources live`}
          tone={framework.coverage_pct >= 80 ? "positive" : "warning"}
        >
          <Table head={["Area", "Source", "Status"]}>
            {framework.rows.map((r) => (
              <tr key={r.area}>
                <Box component="td" sx={cellSx}>
                  <Typography sx={{ fontSize: 15, fontWeight: 700 }}>{r.area}</Typography>
                  <Typography sx={{ fontSize: 15, color: "text.secondary" }}>{r.detail}</Typography>
                </Box>
                <Box component="td" sx={{ ...cellSx, fontFamily: "monospace" }}>{r.source}</Box>
                <Box component="td" sx={cellSx}>
                  <StatusBadge status={r.status === "live" ? "good" : "watch"} label={r.status === "live" ? "Live" : "Pending"} />
                </Box>
              </tr>
            ))}
          </Table>
          <Typography sx={{ fontSize: 15, color: "text.secondary", mt: 1 }}>{framework.note}</Typography>
        </CollapsibleCard>
      )}

      {tests && (
        <CollapsibleCard
          icon="science"
          title="A/B test design"
          headline={String(tests.active)}
          sub="tests defined"
          tone="info"
        >
          <Table head={["Test", "Variants", "Measure", "Cell size"]}>
            {tests.rows.map((r) => (
              <tr key={r.test}>
                <Box component="td" sx={{ ...cellSx, fontWeight: r.primary ? 700 : 400 }}>
                  {r.test}
                  {r.primary && (
                    <Box component="span" sx={{
                      ml: 1, fontSize: 15, color: dataColor.info.ink, background: dataColor.info.soft,
                      borderRadius: radius.sm, px: 0.75,
                    }}>primary</Box>
                  )}
                </Box>
                <Box component="td" sx={cellSx}>{r.variants}</Box>
                <Box component="td" sx={cellSx}>{r.measure}</Box>
                <Box component="td" sx={{ ...cellSx, fontVariantNumeric: "tabular-nums" }}>{r.cell_size.toLocaleString()}</Box>
              </tr>
            ))}
          </Table>
          <Typography sx={{ fontSize: 15, color: "text.secondary", mt: 1 }}>{tests.note}</Typography>
        </CollapsibleCard>
      )}

      <CollapsibleCard
        icon="school"
        title="Learnings"
        headline={String(learnings.length)}
        sub="from this cohort"
        tone="positive"
      >
        <Box sx={{ display: "flex", flexDirection: "column", gap: 1.25, pt: 1 }}>
          {learnings.map((l) => (
            <Box key={l.title}>
              <Typography sx={{ fontSize: 15, fontWeight: 700 }}>{l.title}</Typography>
              <Typography sx={{ fontSize: 15, color: "text.secondary" }}>{l.detail}</Typography>
            </Box>
          ))}
        </Box>
      </CollapsibleCard>

      {tagging && (
        <CollapsibleCard
          icon="link"
          title="Link & tagging matrix"
          headline={String(tagging.rows.length)}
          sub="UTM parameters enforced"
          tone="info"
        >
          <Table head={tagging.columns}>
            {tagging.rows.map((r) => (
              <tr key={r.parameter}>
                <Box component="td" sx={{ ...cellSx, fontFamily: "monospace" }}>{r.parameter}</Box>
                <Box component="td" sx={cellSx}>{r.convention}</Box>
                <Box component="td" sx={{ ...cellSx, fontFamily: "monospace", color: statusColor("info").ink }}>{r.example}</Box>
              </tr>
            ))}
          </Table>
          <Typography sx={{ fontSize: 15, color: "text.secondary", mt: 1 }}>{tagging.note}</Typography>
        </CollapsibleCard>
      )}
    </Box>
  );
}
