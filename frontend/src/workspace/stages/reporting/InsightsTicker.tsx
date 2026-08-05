/**
 * The Reporting agent's findings as a single horizontal ticker rather than a sidebar.
 *
 * A vertical rail cost the whole right-hand column of the dashboard and stranded the chart
 * beside 1500px of cards. As a ticker the same feed runs on one line under the filter bar,
 * scrolling continuously, and never takes width from the data.
 *
 * Behaviour: hover (or focus) pauses the marquee so a headline can actually be read; an item
 * carrying a `metric_key` loads that metric into the trend chart; the full detail and action
 * stay in the item's tooltip. Reduced-motion users get a static, horizontally scrollable
 * strip instead of a marquee.
 */
import { useMemo } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { keyframes } from "@emotion/react";
import { AgentAvatar } from "../../Avatar";
import { hoverOnly, motion, tokens } from "../../../theme/tokens";
import { radius, dataColor, statusColor } from "./dashboardKit";
import type { ReportingInsight, ReportingInsights } from "../../types";

const KIND_ICON: Record<ReportingInsight["kind"], string> = {
  recommendation: "lightbulb",
  anomaly: "warning",
  win: "check_circle",
};

const marquee = keyframes`
  from { transform: translateX(0); }
  to   { transform: translateX(-50%); }
`;

function TickerItem({ insight, onSelectMetric }: { insight: ReportingInsight; onSelectMetric: (key: string) => void }) {
  const c = statusColor(insight.severity);
  const clickable = Boolean(insight.metric_key);
  return (
    <Box
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      title={`${insight.title} — ${insight.detail} Action: ${insight.action} (${insight.evidence})`}
      onClick={clickable ? () => onSelectMetric(insight.metric_key!) : undefined}
      onKeyDown={clickable ? (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelectMetric(insight.metric_key!); }
      } : undefined}
      sx={{
        display: "inline-flex", alignItems: "center", gap: 0.75, flex: "0 0 auto",
        px: 1.5, py: 0.5, mr: 1,
        borderRadius: radius.sm,
        border: `1px solid ${tokens.color.outline}`,
        borderLeft: `3px solid ${c.line}`,
        background: tokens.color.surface,
        cursor: clickable ? "pointer" : "default",
        whiteSpace: "nowrap",
        transition: `background ${motion.duration.hover} ${motion.easeOut}`,
        [hoverOnly]: clickable ? { "&:hover": { background: c.soft } } : undefined,
        "&:focus-visible": { outline: `2px solid ${c.line}`, outlineOffset: 2 },
      }}
    >
      <span className="material-symbols-outlined" style={{ fontSize: 16, color: c.line }}>
        {KIND_ICON[insight.kind]}
      </span>
      <Typography component="span" sx={{ fontSize: 15, fontWeight: 700 }}>{insight.title}</Typography>
      <Typography component="span" sx={{ fontSize: 15, color: "text.secondary" }}>
        {insight.detail}
      </Typography>
    </Box>
  );
}

export function InsightsTicker({
  insights, onSelectMetric,
}: {
  insights: ReportingInsights | null;
  onSelectMetric: (key: string) => void;
}) {
  const feed = insights?.insights ?? [];
  const grounding = insights?.grounding;
  const anomalies = feed.filter((i) => i.kind === "anomaly").length;

  // The track is rendered twice and translated by exactly -50%, so the loop is seamless.
  const track = useMemo(() => [...feed, ...feed], [feed]);
  if (!feed.length) return null;

  const speed = Math.max(28, feed.length * 9); // seconds — longer feeds scroll proportionally

  return (
    <Box
      sx={{
        display: "flex", alignItems: "center", gap: 1.5,
        border: `1px solid ${tokens.color.outline}`,
        borderRadius: radius.md,
        background: tokens.color.surface,
        px: 1.5, py: 1, mb: 2,
        overflow: "hidden",
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, flex: "0 0 auto" }}>
        <AgentAvatar id="reporting" size={28} />
        <Box sx={{ lineHeight: 1.15 }}>
          <Typography sx={{ fontSize: 15, fontWeight: 800, whiteSpace: "nowrap" }}>Reporting agent</Typography>
          <Typography sx={{ fontSize: 15, color: "text.secondary", whiteSpace: "nowrap" }}>
            {grounding ? `${grounding.cohort_size.toLocaleString()} HCPs` : "reading panel"}
            {anomalies > 0 && (
              <Box component="span" sx={{ color: dataColor.warning.ink, fontWeight: 700, ml: 0.75 }}>
                · {anomalies} {anomalies === 1 ? "anomaly" : "anomalies"}
              </Box>
            )}
          </Typography>
        </Box>
      </Box>

      {/* "1px", not 1: MUI's sx reads a bare 0-1 number as a *fraction* of the parent, so
          `width: 1` would paint a full-width grey block over the ticker. */}
      <Box sx={{ width: "1px", alignSelf: "stretch", background: tokens.color.outline, flex: "0 0 auto" }} />

      <Box
        sx={{
          flex: 1, minWidth: 0, overflow: "hidden",
          "@media (prefers-reduced-motion: reduce)": { overflowX: "auto" },
        }}
      >
        <Box
          sx={{
            display: "flex", alignItems: "center", width: "max-content",
            animation: `${marquee} ${speed}s linear infinite`,
            "&:hover, &:focus-within": { animationPlayState: "paused" },
            "@media (prefers-reduced-motion: reduce)": { animation: "none", width: "auto" },
          }}
        >
          {track.map((insight, i) => (
            <TickerItem key={`${insight.id}-${i}`} insight={insight} onSelectMetric={onSelectMetric} />
          ))}
        </Box>
      </Box>
    </Box>
  );
}
