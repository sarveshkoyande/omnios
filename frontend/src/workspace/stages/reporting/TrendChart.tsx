/**
 * Campaign performance trend — one metric at a time.
 *
 * Deliberately single-series: the metric is chosen from the drop-down (or by clicking a KPI
 * card) and only that series is drawn, so the y-axis is honest and a 0.18% unsubscribe rate
 * is never squashed flat under a 98.7% delivery rate. The x-axis is the calendar month of
 * each wave; the shaded band is the metric's working band around its benchmark.
 *
 * The line redraws on every metric or filter change — the draw is keyed on the series
 * identity, so switching metric is a visible redraw rather than a silent value swap.
 */
import { useMemo, useState } from "react";
import Box from "@mui/material/Box";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Typography from "@mui/material/Typography";
import { keyframes } from "@emotion/react";
import { motion, tokens } from "../../../theme/tokens";
import { CardTitle, DashCard, dataColor, formatCompact, formatMetricValue, formatMonth, spansYears, statusColor } from "./dashboardKit";
import type { ReportingMetric } from "../../types";

const W = 900;
const H = 300;
const PAD = { left: 54, right: 20, top: 16, bottom: 34 };
const innerW = W - PAD.left - PAD.right;
const innerH = H - PAD.top - PAD.bottom;

const drawLine = keyframes`
  from { stroke-dashoffset: 1; }
  to   { stroke-dashoffset: 0; }
`;
const fadeUp = keyframes`
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: none; }
`;

function niceTicks(min: number, max: number, count = 4): number[] {
  if (max <= min) return [min];
  const step = (max - min) / count;
  return Array.from({ length: count + 1 }, (_, i) => min + step * i);
}

export function TrendChart({
  metrics, selectedKey, onSelect, busy,
}: {
  metrics: ReportingMetric[];
  selectedKey: string;
  onSelect: (key: string) => void;
  busy: boolean;
}) {
  const metric = metrics.find((m) => m.key === selectedKey) ?? metrics[0];
  const [hover, setHover] = useState<number | null>(null);

  const geometry = useMemo(() => {
    if (!metric) return null;
    const values = metric.monthly.map((p) => p.value);
    const bandValues = metric.band ?? [];
    const rawMin = Math.min(...values, ...bandValues);
    const rawMax = Math.max(...values, ...bandValues);
    const pad = Math.max((rawMax - rawMin) * 0.35, rawMax * 0.04, 0.01);
    const min = Math.max(0, rawMin - pad);
    const max = rawMax + pad;
    const n = metric.monthly.length;
    const x = (i: number) => PAD.left + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW);
    const y = (v: number) => PAD.top + innerH - ((v - min) / (max - min || 1)) * innerH;
    const points = metric.monthly.map((p, i) => ({ ...p, cx: x(i), cy: y(p.value) }));
    const line = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.cx.toFixed(2)} ${p.cy.toFixed(2)}`).join(" ");
    const area = `${line} L ${points[points.length - 1].cx.toFixed(2)} ${PAD.top + innerH} L ${points[0].cx.toFixed(2)} ${PAD.top + innerH} Z`;
    return { min, max, x, y, points, line, area, ticks: niceTicks(min, max) };
  }, [metric]);

  if (!metric || !geometry) return null;

  // Volume metrics have no benchmark and so no status — they draw in information blue rather
  // than the grey a "neutral" status would give them.
  const c = metric.status === "neutral" ? dataColor.info : statusColor(metric.status);
  const withYear = spansYears(metric.monthly.map((p) => p.month));
  // Axis ticks: a count series spanning ~70 units reads as five identical "1.3k" labels under
  // the compact formatter, so short-range counts stay unabbreviated.
  const tickRange = geometry.max - geometry.min;
  const formatTick = (v: number) =>
    metric.unit === "count" && tickRange < 5000
      ? Math.round(v).toLocaleString()
      : formatCompact(v, metric.unit);
  const seriesKey = `${metric.key}:${metric.monthly.map((p) => p.value).join(",")}`;
  const active = hover != null ? geometry.points[hover] : null;

  const handleMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const vx = ((e.clientX - rect.left) / rect.width) * W;
    let best = 0;
    geometry.points.forEach((p, i) => {
      if (Math.abs(p.cx - vx) < Math.abs(geometry.points[best].cx - vx)) best = i;
    });
    setHover(best);
  };

  return (
    <DashCard sx={{ opacity: busy ? 0.55 : 1, transition: `opacity ${motion.duration.hover} ${motion.easeOut}` }}>
      <CardTitle
        title="Campaign performance over time"
        hint={metric.description}
        action={
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Typography sx={{ fontSize: 15, color: "text.secondary", fontWeight: 700 }}>Metric</Typography>
            <Select
              size="small"
              value={metric.key}
              onChange={(e) => onSelect(String(e.target.value))}
              sx={{ fontSize: 15, minWidth: 220, background: tokens.color.surface }}
              MenuProps={{ slotProps: { paper: { sx: { maxHeight: 420 } } } }}
            >
              {metrics.map((m) => (
                <MenuItem key={m.key} value={m.key} sx={{ fontSize: 15 }}>{m.label}</MenuItem>
              ))}
            </Select>
          </Box>
        }
      />

      <Box sx={{ display: "flex", alignItems: "baseline", gap: 1.5, mb: 1 }}>
        <Typography sx={{ fontSize: 28, fontWeight: 800, letterSpacing: "-0.5px", fontVariantNumeric: "tabular-nums" }}>
          {formatMetricValue(metric.value, metric.unit)}
        </Typography>
        {metric.benchmark != null && (
          <Typography sx={{ fontSize: 15, color: "text.secondary" }}>
            benchmark {metric.benchmark}
            {metric.unit === "%" ? "%" : ""} · working band {metric.band?.[0]}–{metric.band?.[1]}
          </Typography>
        )}
      </Box>

      <Box sx={{ position: "relative" }}>
        <Box
          component="svg"
          viewBox={`0 0 ${W} ${H}`}
          onMouseMove={handleMove}
          onMouseLeave={() => setHover(null)}
          sx={{ width: "100%", height: "auto", display: "block", overflow: "visible" }}
        >
          <defs>
            <linearGradient id={`trend-fill-${metric.key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={c.line} stopOpacity={0.18} />
              <stop offset="100%" stopColor={c.line} stopOpacity={0} />
            </linearGradient>
          </defs>

          {/* Working band around the benchmark — the "is this normal" reference. */}
          {metric.band && (
            <g>
              <rect
                x={PAD.left}
                y={geometry.y(Math.min(metric.band[1], geometry.max))}
                width={innerW}
                height={Math.max(0, geometry.y(Math.max(metric.band[0], geometry.min)) - geometry.y(Math.min(metric.band[1], geometry.max)))}
                fill={dataColor.info.soft}
                opacity={0.75}
              />
              <text x={PAD.left + innerW - 6} y={geometry.y(Math.min(metric.band[1], geometry.max)) + 14}
                    fontSize={13} textAnchor="end" fill={dataColor.info.ink} opacity={0.8}>
                benchmark band
              </text>
            </g>
          )}

          {geometry.ticks.map((t, i) => (
            <g key={i}>
              <line x1={PAD.left} x2={W - PAD.right} y1={geometry.y(t)} y2={geometry.y(t)}
                    stroke={tokens.color.outline} strokeWidth={1} opacity={i === 0 ? 1 : 0.55} />
              <text x={PAD.left - 10} y={geometry.y(t) + 4} fontSize={13} textAnchor="end" fill={tokens.color.inkSecondary}>
                {formatTick(t)}
              </text>
            </g>
          ))}

          {metric.benchmark != null && (
            <line x1={PAD.left} x2={W - PAD.right} y1={geometry.y(metric.benchmark)} y2={geometry.y(metric.benchmark)}
                  stroke={dataColor.info.line} strokeWidth={1.5} strokeDasharray="6 5" opacity={0.7} />
          )}

          {/* X axis: the calendar month each wave landed in. */}
          {geometry.points.map((p, i) => (
            <text key={p.month} x={p.cx} y={H - 12} fontSize={13} textAnchor="middle"
                  fill={hover === i ? tokens.color.ink : tokens.color.inkSecondary}
                  fontWeight={hover === i ? 700 : 400}>
              {formatMonth(p.month, withYear)}
            </text>
          ))}

          {/* Box (not a bare <path>) so the emotion keyframes actually get injected — an
              inline `style` animation would name a rule that was never inserted. */}
          <Box component="path" key={`area-${seriesKey}`} d={geometry.area} fill={`url(#trend-fill-${metric.key})`}
               sx={{ animation: `${fadeUp} 520ms ${motion.easeOut} both` }} />

          <Box
            component="path"
            key={`line-${seriesKey}`}
            d={geometry.line}
            fill="none"
            stroke={c.line}
            strokeWidth={2.5}
            strokeLinecap="round"
            strokeLinejoin="round"
            pathLength={1}
            strokeDasharray={1}
            sx={{ animation: `${drawLine} 760ms ${motion.easeOut} both` }}
          />

          {active && (
            <line x1={active.cx} x2={active.cx} y1={PAD.top} y2={PAD.top + innerH}
                  stroke={c.line} strokeWidth={1} opacity={0.35} />
          )}

          {geometry.points.map((p, i) => (
            <Box
              component="circle"
              key={p.month}
              cx={p.cx}
              cy={p.cy}
              r={hover === i ? 6 : 3.5}
              fill={tokens.color.surface}
              stroke={c.line}
              strokeWidth={hover === i ? 3 : 2}
              sx={{
                animation: `${fadeUp} 320ms ${motion.easeOut} ${360 + i * 40}ms both`,
                transition: `r ${motion.duration.hover} ${motion.easeOut}`,
              }}
            />
          ))}
        </Box>

        {/* Tooltip is HTML, not SVG: it needs real text wrapping and the app's type scale. */}
        {active && (
          <Box
            sx={{
              position: "absolute", pointerEvents: "none",
              left: `${(active.cx / W) * 100}%`,
              top: `${(active.cy / H) * 100}%`,
              transform: "translate(-50%, calc(-100% - 14px))",
              background: tokens.color.ink, color: "#fff",
              borderRadius: tokens.radius.md, px: 1.25, py: 0.75, minWidth: 132,
              boxShadow: "0 10px 24px -12px rgba(16,24,40,0.6)",
              animation: `${fadeUp} 140ms ${motion.easeOut} both`,
            }}
          >
            <Typography sx={{ fontSize: 15, opacity: 0.75 }}>{formatMonth(active.month, true)}</Typography>
            <Typography sx={{ fontSize: 17, fontWeight: 800, fontVariantNumeric: "tabular-nums" }}>
              {formatCompact(active.value, metric.unit)}
            </Typography>
            {metric.benchmark != null && (
              <Typography sx={{ fontSize: 15, opacity: 0.75 }}>
                {active.value >= metric.benchmark ? "+" : ""}
                {(active.value - metric.benchmark).toFixed(2)} vs benchmark
              </Typography>
            )}
          </Box>
        )}
      </Box>

      <Typography sx={{ fontSize: 15, color: "text.secondary", mt: 1.5 }}>
        Each point is one monthly wave of the current cohort — its own audience size and its own
        measured channel affinity, counted from the HCP 360 panel.
      </Typography>
    </DashCard>
  );
}
