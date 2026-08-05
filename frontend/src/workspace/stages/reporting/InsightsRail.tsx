/**
 * The Reporting agent's rail: what it found in this cohort, what looks wrong, what to do.
 *
 * Every card is derived from a named panel query (the `evidence` line), not from a model's
 * impression of the chart — so a recommendation can always be traced back to the rows that
 * produced it. Cards carrying a `metric_key` are clickable and load that metric into the
 * trend chart.
 */
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { AgentAvatar } from "../../Avatar";
import { enterWith, enterFromRight, stagger } from "../../../theme/motionPresets";
import { hoverOnly, motion, tokens } from "../../../theme/tokens";
import { Shimmer, dataColor, statusColor } from "./dashboardKit";
import type { ReportingInsight, ReportingInsights } from "../../types";

const KIND_ICON: Record<ReportingInsight["kind"], string> = {
  recommendation: "lightbulb",
  anomaly: "warning",
  win: "check_circle",
};

const KIND_LABEL: Record<ReportingInsight["kind"], string> = {
  recommendation: "Recommendation",
  anomaly: "Anomaly detected",
  win: "Working well",
};

function InsightCard({
  insight, index, onSelectMetric,
}: {
  insight: ReportingInsight;
  index: number;
  onSelectMetric: (key: string) => void;
}) {
  const c = statusColor(insight.severity);
  const clickable = Boolean(insight.metric_key);
  return (
    <Box
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      onClick={clickable ? () => onSelectMetric(insight.metric_key!) : undefined}
      onKeyDown={clickable ? (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelectMetric(insight.metric_key!); }
      } : undefined}
      sx={{
        background: tokens.color.surface,
        border: `1px solid ${tokens.color.outline}`,
        borderLeft: `3px solid ${c.line}`,
        borderRadius: tokens.radius.md,
        p: 1.75,
        cursor: clickable ? "pointer" : "default",
        animation: enterWith(enterFromRight, stagger(index, 55)),
        transition: `transform ${motion.duration.hover} ${motion.easeOut}, box-shadow ${motion.duration.hover} ${motion.easeOut}`,
        [hoverOnly]: clickable ? { "&:hover": { transform: "translateX(-2px)", boxShadow: "0 8px 22px -14px rgba(16,24,40,0.4)" } } : undefined,
        "&:focus-visible": { outline: `2px solid ${c.line}`, outlineOffset: 2 },
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, mb: 0.75 }}>
        <span className="material-symbols-outlined" style={{ fontSize: 17, color: c.line }}>
          {KIND_ICON[insight.kind]}
        </span>
        <Typography sx={{ fontSize: 15, fontWeight: 700, color: c.ink, letterSpacing: "0.3px" }}>
          {KIND_LABEL[insight.kind]}
        </Typography>
      </Box>

      <Typography sx={{ fontSize: 15, fontWeight: 700, lineHeight: 1.35, mb: 0.5 }}>{insight.title}</Typography>
      <Typography sx={{ fontSize: 15, color: "text.secondary", lineHeight: 1.45 }}>{insight.detail}</Typography>

      <Box sx={{ display: "flex", alignItems: "flex-start", gap: 0.75, mt: 1.25 }}>
        <span className="material-symbols-outlined" style={{ fontSize: 16, color: tokens.color.inkSecondary, marginTop: 2 }}>
          arrow_forward
        </span>
        <Typography sx={{ fontSize: 15, lineHeight: 1.4 }}>{insight.action}</Typography>
      </Box>

      <Typography sx={{ fontSize: 15, color: "text.disabled", mt: 1, fontFamily: "monospace" }}>
        {insight.evidence}
      </Typography>
    </Box>
  );
}

export function InsightsRail({
  insights, loading, onSelectMetric,
}: {
  insights: ReportingInsights | null;
  loading: boolean;
  onSelectMetric: (key: string) => void;
}) {
  const feed = insights?.insights ?? [];
  const grounding = insights?.grounding;
  const counts = {
    anomaly: feed.filter((i) => i.kind === "anomaly").length,
    recommendation: feed.filter((i) => i.kind === "recommendation").length,
  };

  return (
    <Box
      sx={{
        background: tokens.color.canvas,
        border: `1px solid ${tokens.color.outline}`,
        borderRadius: tokens.radius.lg,
        p: 2,
        display: "flex",
        flexDirection: "column",
        gap: 1.25,
        minWidth: 0,
        // Beside the chart the feed is capped and scrolls in place: left to run its full
        // length it would leave ~1500px of dead white space in the chart column. Stacked
        // (narrow screens) it flows normally, because there is no column to strand.
        maxHeight: { xs: "none", lg: "calc(100vh - 210px)" },
        overflowY: { xs: "visible", lg: "auto" },
        overscrollBehavior: "contain",
        "&::-webkit-scrollbar": { width: 8 },
        "&::-webkit-scrollbar-thumb": { background: tokens.color.outline, borderRadius: 4 },
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, flex: "0 0 auto" }}>
        <AgentAvatar id="reporting" size={36} />
        <Box sx={{ minWidth: 0 }}>
          <Typography sx={{ fontSize: 15, fontWeight: 800, lineHeight: 1.2 }}>Reporting & Insights Agent</Typography>
          <Typography sx={{ fontSize: 15, color: "text.secondary" }}>
            {grounding ? `Reading ${grounding.cohort_size.toLocaleString()} HCPs` : "Reading the panel…"}
          </Typography>
        </Box>
      </Box>

      <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap" }}>
        <Box sx={{
          display: "inline-flex", alignItems: "center", gap: 0.5, fontSize: 15, fontWeight: 700,
          color: dataColor.warning.ink, background: dataColor.warning.soft,
          borderRadius: tokens.radius.pill, px: 1, py: 0.25,
        }}>
          {counts.anomaly} {counts.anomaly === 1 ? "anomaly" : "anomalies"}
        </Box>
        <Box sx={{
          display: "inline-flex", alignItems: "center", gap: 0.5, fontSize: 15, fontWeight: 700,
          color: dataColor.info.ink, background: dataColor.info.soft,
          borderRadius: tokens.radius.pill, px: 1, py: 0.25,
        }}>
          {counts.recommendation} {counts.recommendation === 1 ? "recommendation" : "recommendations"}
        </Box>
      </Box>

      {loading && feed.length === 0
        ? [0, 1, 2].map((i) => <Shimmer key={i} sx={{ height: 128, borderRadius: `${tokens.radius.md}px` }} />)
        : feed.map((insight, i) => (
            <InsightCard key={insight.id} insight={insight} index={i} onSelectMetric={onSelectMetric} />
          ))}

      {insights?.caveat && (
        <Typography sx={{ fontSize: 15, color: "text.secondary", fontStyle: "italic", mt: 0.5, lineHeight: 1.45 }}>
          {insights.caveat}
        </Typography>
      )}
    </Box>
  );
}
