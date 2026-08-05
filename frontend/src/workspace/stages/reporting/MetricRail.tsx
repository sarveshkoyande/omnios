/**
 * The KPI rail: one card per headline metric.
 *
 * A card is also the chart's selector — clicking it loads that metric into the trend chart
 * below, which is why the whole rail is a radiogroup rather than decoration. The value
 * counts up on every filter change so the user can see which numbers actually moved.
 */
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { enterWith, enterRise, stagger } from "../../../theme/motionPresets";
import { hoverOnly, motion, tokens } from "../../../theme/tokens";
import { DeltaPill, Shimmer, formatMetricValue, statusColor, useCountUp } from "./dashboardKit";
import type { ReportingMetric } from "../../types";

const STATUS_LABEL: Record<string, string> = {
  good: "At or above benchmark",
  watch: "Drifting below benchmark",
  risk: "Below working band",
  neutral: "Volume — no benchmark band",
};

function MetricCard({
  metric, selected, index, onSelect,
}: {
  metric: ReportingMetric;
  selected: boolean;
  index: number;
  onSelect: () => void;
}) {
  const value = useCountUp(metric.value);
  const c = statusColor(metric.status);
  const prior = metric.monthly.length > 1 ? metric.monthly[metric.monthly.length - 2].month : null;

  return (
    <Box
      role="radio"
      aria-checked={selected}
      aria-label={`${metric.label}: ${formatMetricValue(metric.value, metric.unit)}`}
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(); }
      }}
      title={metric.description}
      sx={{
        cursor: "pointer", position: "relative", overflow: "hidden", minWidth: 0,
        background: tokens.color.surface,
        border: `1px solid ${selected ? c.line : tokens.color.outline}`,
        boxShadow: selected ? `0 0 0 3px ${c.soft}` : "0 1px 2px rgba(16,24,40,0.04)",
        borderRadius: tokens.radius.lg,
        p: 2,
        animation: enterWith(enterRise, stagger(index)),
        transition: `box-shadow ${motion.duration.hover} ${motion.easeOut}, border-color ${motion.duration.hover} ${motion.easeOut}, transform ${motion.duration.hover} ${motion.easeOut}`,
        [hoverOnly]: { "&:hover": { transform: "translateY(-2px)", boxShadow: "0 10px 26px -16px rgba(16,24,40,0.4)" } },
        "&:active": { transform: "translateY(0)" },
        "&:focus-visible": { outline: `2px solid ${c.line}`, outlineOffset: 2 },
      }}
    >
      {/* Status rail — the only place colour is allowed to mean "how is this doing". */}
      <Box sx={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: c.line }} />

      <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, mb: 1 }}>
        <Typography sx={{ fontSize: 15, fontWeight: 700, color: "text.secondary", lineHeight: 1.2 }}>
          {metric.label}
        </Typography>
      </Box>

      <Typography sx={{ fontSize: 30, fontWeight: 800, lineHeight: 1.05, letterSpacing: "-0.5px", fontVariantNumeric: "tabular-nums" }}>
        {formatMetricValue(value, metric.unit)}
      </Typography>

      <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, mt: 0.75, minHeight: 24 }}>
        <DeltaPill metric={metric} />
        <Typography sx={{ fontSize: 15, color: "text.secondary", whiteSpace: "nowrap" }}>
          {prior ? "vs prior" : "1 period"}
        </Typography>
      </Box>

      <Typography
        sx={{ fontSize: 15, color: c.ink, mt: 0.5, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}
        title={STATUS_LABEL[metric.status]}
      >
        {metric.benchmark != null ? `Benchmark ${metric.benchmark}${metric.unit === "%" ? "%" : ""}` : "Cohort volume"}
      </Typography>
    </Box>
  );
}

export function MetricRail({
  metrics, selectedKey, loading, onSelect,
}: {
  metrics: ReportingMetric[];
  selectedKey: string;
  loading: boolean;
  onSelect: (key: string) => void;
}) {
  // Grid, not flex-wrap: a flex row leaves the last card on its own row stretched to full
  // width, which reads as "this KPI is more important" for no reason.
  const gridSx = {
    display: "grid",
    // auto-fit tracks the *container*, not the viewport — the workspace column is much
    // narrower than the window, so viewport breakpoints would size these wrong.
    gridTemplateColumns: "repeat(auto-fit, minmax(168px, 1fr))",
    gap: 1.5,
    mb: 2.5,
  } as const;

  if (loading && metrics.length === 0) {
    return (
      <Box sx={gridSx}>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <Shimmer key={i} sx={{ height: 132, borderRadius: `${tokens.radius.lg}px` }} />
        ))}
      </Box>
    );
  }
  return (
    <Box role="radiogroup" aria-label="Headline metrics" sx={gridSx}>
      {metrics.map((m, i) => (
        <MetricCard
          key={m.key}
          metric={m}
          index={i}
          selected={m.key === selectedKey}
          onSelect={() => onSelect(m.key)}
        />
      ))}
    </Box>
  );
}
