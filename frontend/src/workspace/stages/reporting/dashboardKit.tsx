/**
 * Shared surface, colour and motion primitives for the Reporting & Insights dashboard.
 *
 * The chrome around this dashboard is Omni blue like the rest of the product; the Reporting
 * agent's orange appears only in its marker slots (theme/stageTheme.ts). Inside a chart or a KPI
 * card the palette is deliberately *semantic*: blue carries information, green a metric at or
 * above its benchmark, amber one drifting, red only genuine breakage. Never paint a series in an
 * agent's colour — it would make an identity read as a status, which a dashboard must not do.
 */
import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { keyframes } from "@emotion/react";
import { hoverOnly, motion, tokens } from "../../../theme/tokens";
import type { MetricStatus, ReportingMetric } from "../../types";

/**
 * Corner radii as CSS strings.
 *
 * MUI's `sx` treats a *number* on `borderRadius` as a multiple of `theme.shape.borderRadius`
 * (4 here) — so `borderRadius: tokens.radius.md` silently rendered 32px, not 8px, and this
 * tab came out visibly rounder than every other screen. Always use these strings inside `sx`;
 * raw token numbers are only correct inside `styled()`, where they mean px.
 */
export const radius = {
  sm: `${tokens.radius.sm}px`,
  md: `${tokens.radius.md}px`,
  pill: `${tokens.radius.pill}px`,
} as const;

/** Semantic data palette. `ink`/`soft` pair for text-on-tint chips. */
export const dataColor = {
  info: { ink: "#034EA2", soft: "#E3EDFA", line: "#1768D1" },
  positive: { ink: "#047857", soft: "#D1FAE5", line: "#059669" },
  warning: { ink: "#9A3412", soft: "#FFEDD5", line: "#C2410C" },
  critical: { ink: "#B42318", soft: "#FEE4E2", line: "#D92D20" },
  neutral: { ink: tokens.color.inkSecondary, soft: "#F2F4F7", line: "#98A2B3" },
} as const;

export function statusColor(status: MetricStatus | string) {
  if (status === "good" || status === "positive") return dataColor.positive;
  if (status === "watch" || status === "warning") return dataColor.warning;
  if (status === "risk" || status === "critical") return dataColor.critical;
  if (status === "info") return dataColor.info;
  return dataColor.neutral;
}

/** The dashboard's one card surface: white, hairline border, one soft elevation step.
 *  Radius is `md` — the same corner every SectionCard in the product uses, so this tab does
 *  not read as a rounder island inside the app. */
export const DashCard = styled(Box)({
  background: tokens.color.surface,
  border: `1px solid ${tokens.color.outline}`,
  borderRadius: tokens.radius.md,
  boxShadow: "0 1px 2px rgba(16,24,40,0.04)",
  padding: 20,
  minWidth: 0,
  transition: `box-shadow ${motion.duration.hover} ${motion.easeOut}, transform ${motion.duration.hover} ${motion.easeOut}`,
  [hoverOnly]: {
    "&:hover": { boxShadow: "0 8px 28px -14px rgba(16,24,40,0.28)" },
  },
});

export function CardTitle({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <Box sx={{ display: "flex", alignItems: "flex-start", gap: 2, mb: 2 }}>
      <Box sx={{ minWidth: 0 }}>
        <Typography sx={{ fontSize: 17, fontWeight: 700, lineHeight: 1.3 }}>{title}</Typography>
        {hint && (
          <Typography sx={{ fontSize: 15, color: "text.secondary", mt: 0.25 }}>{hint}</Typography>
        )}
      </Box>
      <Box sx={{ flex: 1 }} />
      {action}
    </Box>
  );
}

const shimmer = keyframes`
  from { background-position: -320px 0; }
  to   { background-position: 320px 0; }
`;

/** Placeholder block used while a filter change is in flight. */
export const Shimmer = styled(Box)({
  borderRadius: tokens.radius.sm,
  background: `linear-gradient(90deg, #F2F4F7 0%, #E9EDF3 40%, #F2F4F7 80%)`,
  backgroundSize: "640px 100%",
  animation: `${shimmer} 1.1s linear infinite`,
});

/**
 * Counts a number up to its new value whenever it changes.
 *
 * Tweened with rAF rather than a CSS transition because the thing being animated is text
 * content, not a style. Interruptible: a second filter change mid-flight retargets from
 * wherever the count currently is instead of snapping back to the old value.
 */
export function useCountUp(target: number, duration = 620): number {
  const [display, setDisplay] = useState(target);
  const fromRef = useRef(target);
  const frameRef = useRef(0);

  useEffect(() => {
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const from = fromRef.current;
    if (reduce || from === target) {
      fromRef.current = target;
      setDisplay(target);
      return;
    }
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic — matches the app's enter curve
      const value = from + (target - from) * eased;
      fromRef.current = value;
      setDisplay(value);
      if (t < 1) frameRef.current = requestAnimationFrame(tick);
      else fromRef.current = target;
    };
    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [target, duration]);

  return display;
}

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-05" -> "May" (or "May 26" when the series crosses a year boundary). */
export function formatMonth(label: string, withYear = false): string {
  const [year, month] = label.split("-");
  const name = MONTH_NAMES[Number(month) - 1] ?? label;
  return withYear ? `${name} ${year.slice(2)}` : name;
}

/** True when a month series spans more than one calendar year, so labels need the year. */
export function spansYears(labels: string[]): boolean {
  return new Set(labels.map((l) => l.slice(0, 4))).size > 1;
}

export function formatMetricValue(value: number, unit: ReportingMetric["unit"]): string {
  if (unit === "count") return Math.round(value).toLocaleString();
  if (unit === "index") return value.toFixed(1);
  return `${value.toFixed(2)}%`;
}

/** Compact axis/marker form: 12.4% / 1.2k / 55. */
export function formatCompact(value: number, unit: ReportingMetric["unit"]): string {
  if (unit === "count") {
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
    if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
    return Math.round(value).toLocaleString();
  }
  if (unit === "index") return value.toFixed(0);
  return `${value.toFixed(1)}%`;
}

/** A metric's delta chip — direction arrow, coloured by whether the move was *good*. */
export function DeltaPill({ metric }: { metric: ReportingMetric }) {
  const flat = metric.direction === "flat" || metric.delta === 0;
  const good = (metric.delta > 0) === metric.higher_is_better;
  const c = flat ? dataColor.neutral : good ? dataColor.positive : dataColor.critical;
  const magnitude = metric.unit === "count"
    ? Math.abs(Math.round(metric.delta)).toLocaleString()
    : Math.abs(metric.delta).toFixed(2);
  return (
    <Box
      component="span"
      sx={{
        display: "inline-flex", alignItems: "center", gap: 0.25,
        color: c.ink, background: c.soft,
        borderRadius: tokens.radius.sm, px: 0.75, py: 0.25,
        fontSize: 15, fontWeight: 700, whiteSpace: "nowrap",
      }}
    >
      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
        {flat ? "remove" : metric.direction === "up" ? "arrow_upward" : "arrow_downward"}
      </span>
      {flat ? "0" : magnitude}
      {metric.unit === "%" ? "pp" : metric.unit === "index" ? "pts" : ""}
    </Box>
  );
}

/** Status dot + label, for legends and table badges. */
export function StatusBadge({ status, label }: { status: MetricStatus | string; label: string }) {
  const c = statusColor(status);
  return (
    <Box component="span" sx={{
      display: "inline-flex", alignItems: "center", gap: 0.75, background: c.soft, color: c.ink,
      borderRadius: tokens.radius.sm, px: 1, py: 0.25, fontSize: 15, fontWeight: 700,
    }}>
      <Box component="span" sx={{ width: 7, height: 7, borderRadius: "50%", background: c.line }} />
      {label}
    </Box>
  );
}
