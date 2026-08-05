import { useMemo } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { BarChart } from "@mui/x-charts/BarChart";
import { PieChart } from "@mui/x-charts/PieChart";
import { accent } from "../../theme/stageTheme";
import { tokens } from "../../theme/tokens";
import type { DataBlockColumn } from "../../api";

export type ChartMode = "bar" | "pie";

type Row = Record<string, string | number | null>;

/** Beyond this a bar chart is a wall of ticks and a pie is unreadable — the tail is bucketed. */
const MAX_CATEGORIES = 12;
/** One series per value of the second dimension; more than this and the legend eats the chart. */
const MAX_SERIES = 8;

/**
 * Series shading.
 *
 * Deliberately steps of the *current stage accent* rather than a new categorical palette:
 * every other chart in this app (StageReporting's donut, trend lines and heatmap) is shaded
 * the same way, and the accent changes per workspace tab, so a fixed multi-hue palette would
 * be the only thing on the page that doesn't follow the agent you're talking to.
 */
export function seriesShade(index: number, count: number): string {
  const pct = count <= 1 ? 100 : Math.round((0.32 + 0.68 * (1 - index / (count - 1))) * 100);
  return `color-mix(in srgb, ${accent.primary} ${pct}%, white)`;
}

const label = (value: string | number | null): string =>
  value == null || value === "" ? "(unspecified)" : String(value);

/** Rank by count and fold the tail into one "Other" bucket, so the chart stays legible while
 *  still totalling the same as the table above it. */
function topN(entries: [string, number][], limit: number): [string, number][] {
  if (entries.length <= limit) return entries;
  const sorted = [...entries].sort((a, b) => b[1] - a[1]);
  const head = sorted.slice(0, limit - 1);
  const tail = sorted.slice(limit - 1).reduce((sum, [, n]) => sum + n, 0);
  return [...head, [`Other (${sorted.length - head.length})`, tail]];
}

function numberOf(row: Row, key: string): number {
  const raw = row[key];
  return typeof raw === "number" ? raw : Number(raw ?? 0) || 0;
}

/**
 * Which columns can be charted: exactly one numeric measure plotted against the first one or
 * two text dimensions. Returns null when the block has no numeric column at all (an HCP
 * roster, say) — the caller then hides the chart toggle rather than drawing an empty axis.
 */
export function chartableColumns(columns: DataBlockColumn[]): { dims: string[]; measure: string } | null {
  const measure = columns.find((c) => c.type === "number");
  const dims = columns.filter((c) => c.type === "text").map((c) => c.key);
  if (!measure || !dims.length) return null;
  return { dims: dims.slice(0, 2), measure: measure.key };
}

export function BlockChart({
  rows,
  columns,
  mode,
  height = 300,
}: {
  rows: Row[];
  columns: DataBlockColumn[];
  mode: ChartMode;
  height?: number;
}) {
  const spec = chartableColumns(columns);

  const model = useMemo(() => {
    if (!spec) return null;
    const [dim, splitDim] = spec.dims;
    const categories = topN(
      Object.entries(
        rows.reduce<Record<string, number>>((acc, row) => {
          const key = label(row[dim]);
          acc[key] = (acc[key] ?? 0) + numberOf(row, spec.measure);
          return acc;
        }, {}),
      ),
      MAX_CATEGORIES,
    );
    if (!splitDim) return { categories, splitDim: null, series: [] as { label: string; data: number[] }[] };

    const splitTotals = rows.reduce<Record<string, number>>((acc, row) => {
      const key = label(row[splitDim]);
      acc[key] = (acc[key] ?? 0) + numberOf(row, spec.measure);
      return acc;
    }, {});
    const splitKeys = topN(Object.entries(splitTotals), MAX_SERIES).map(([key]) => key);
    const kept = new Set(splitKeys.filter((k) => !k.startsWith("Other (")));
    const otherKey = splitKeys.find((k) => k.startsWith("Other ("));
    const cells: Record<string, Record<string, number>> = {};
    rows.forEach((row) => {
      const cat = label(row[dim]);
      const raw = label(row[splitDim]);
      const bucket = kept.has(raw) ? raw : otherKey;
      if (!bucket) return;
      cells[bucket] = cells[bucket] ?? {};
      cells[bucket][cat] = (cells[bucket][cat] ?? 0) + numberOf(row, spec.measure);
    });
    return {
      categories,
      splitDim,
      series: splitKeys.map((key) => ({
        label: key,
        data: categories.map(([cat]) => cells[key]?.[cat] ?? 0),
      })),
    };
  }, [rows, spec]);

  if (!spec || !model || !model.categories.length) {
    return (
      <Typography sx={{ color: "text.secondary", fontStyle: "italic", py: 2 }}>
        Nothing to chart in this result.
      </Typography>
    );
  }

  const names = model.categories.map(([name]) => name);
  const values = model.categories.map(([, value]) => value);

  if (mode === "pie") {
    return (
      <PieChart
        height={height}
        series={[
          {
            data: names.map((name, i) => ({ id: name, value: values[i], label: name })),
            innerRadius: 42,
            paddingAngle: 1,
            cornerRadius: 3,
            highlightScope: { fade: "global", highlight: "item" },
          },
        ]}
        colors={names.map((_, i) => seriesShade(i, names.length))}
        slotProps={{ legend: { direction: "vertical", position: { vertical: "middle", horizontal: "end" } } }}
      />
    );
  }

  // Horizontal bars: the categories here are specialty / segment / state names, which are far
  // too long to sit under a vertical axis without overlapping or being rotated to unreadable.
  const series = model.splitDim
    ? model.series.map((s, i) => ({ ...s, stack: "total", color: seriesShade(i, model.series.length) }))
    : [{ data: values, label: "HCPs", color: seriesShade(0, 1) }];

  return (
    <Box>
      <BarChart
        layout="horizontal"
        height={Math.max(height, names.length * 28 + 70)}
        yAxis={[{ data: names, scaleType: "band", width: 168 }]}
        xAxis={[{ label: "HCPs" }]}
        series={series}
        margin={{ left: 8, right: 16, top: 8, bottom: 8 }}
        grid={{ vertical: true }}
        hideLegend={!model.splitDim}
        sx={{ "& .MuiChartsAxis-tickLabel": { fontSize: tokens.fontSize.md } }}
      />
    </Box>
  );
}
