/**
 * Reporting & Insights — the executive analytics workspace.
 *
 * Layout, top to bottom: filter bar → the agent's insight ticker → collapsible deep-dive
 * shelf → KPI rail → single-metric trend chart → funnel / geography / channel mix → journey
 * → top assets + audience composition → send windows.
 *
 * Two rules this screen is built on:
 *  1. Every number is counted from the HCP 360 panel for the *current filter combination*
 *     (server-side, `strategy/hcp_panel_metrics.py`) — filters are a real drill-down, so any
 *     selection made anywhere on the page refetches and re-derives the whole dashboard.
 *  2. The trend chart shows one metric at a time, chosen from the drop-down or by clicking a
 *     KPI card, so a rate and a volume are never forced onto a shared axis.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { ConsolePanel } from "../../components/ConsolePanel";
import { StageHead } from "./StageHead";
import { AssetsCard } from "./reporting/AssetsCard";
import { AudienceCard } from "./reporting/AudienceCard";
import { ChannelCard } from "./reporting/ChannelCard";
import { DeepDivePanels } from "./reporting/DeepDivePanels";
import { FilterBar } from "./reporting/FilterBar";
import { FunnelCard } from "./reporting/FunnelCard";
import { GeoCard } from "./reporting/GeoCard";
import { InsightsTicker } from "./reporting/InsightsTicker";
import { JourneyCard } from "./reporting/JourneyCard";
import { MeasurementPlan } from "./reporting/MeasurementPlan";
import { MetricRail } from "./reporting/MetricRail";
import { SendWindowCard } from "./reporting/SendWindowCard";
import { TrendChart } from "./reporting/TrendChart";
import { Shimmer } from "./reporting/dashboardKit";
import { motion, tokens } from "../../theme/tokens";
import { fetchReportingInsights } from "../../api";
import type { PlanResult, ReportingFilterKey, ReportingFilters, ReportingInsights } from "../types";

const DEFAULT_METRIC = "open";

export function StageReporting({ result, projectId }: { result: PlanResult | null; projectId: string | null }) {
  const [insights, setInsights] = useState<ReportingInsights | null>(null);
  const [filters, setFilters] = useState<ReportingFilters>({});
  const [months, setMonths] = useState(6);
  const [metricKey, setMetricKey] = useState(DEFAULT_METRIC);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Distinguishes "first load, nothing to show" from "refetching, keep the old numbers up".
  const loadedOnce = useRef(false);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    setBusy(true);
    fetchReportingInsights(projectId, { ...filters, months })
      .then((data) => {
        if (cancelled) return;
        setInsights(data);
        setError(data.available === false ? (data.message ?? "No data for this filter combination.") : null);
        loadedOnce.current = true;
      })
      .catch(() => {
        if (!cancelled) setError("Could not load the reporting data.");
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => { cancelled = true; };
  }, [projectId, result, filters, months]);

  const metrics = useMemo(() => insights?.metrics ?? [], [insights]);

  // A metric the payload no longer carries (or the very first render) falls back rather than
  // leaving the chart empty.
  useEffect(() => {
    if (metrics.length && !metrics.some((m) => m.key === metricKey)) setMetricKey(metrics[0].key);
  }, [metrics, metricKey]);

  const setFilter = useCallback((key: ReportingFilterKey, value: string) => {
    setFilters((prev) => {
      const next = { ...prev };
      if (!value || prev[key] === value) delete next[key];  // clicking the active value clears it
      else next[key] = value;
      return next;
    });
  }, []);

  const resetFilters = useCallback(() => setFilters({}), []);

  if (!projectId) {
    return (
      <ConsolePanel>
        <Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>
          Open or create a project to see the reporting dashboard.
        </Typography>
      </ConsolePanel>
    );
  }

  const headlineKeys = insights?.headline_keys ?? [];
  const headlineMetrics = headlineKeys.length
    ? headlineKeys.map((k) => metrics.find((m) => m.key === k)).filter(Boolean) as typeof metrics
    : metrics.slice(0, 6);

  return (
    <Box>
      <StageHead
        icon="insights"
        title="Reporting & Insights"
        blurb="The closed-loop scorecard, counted live off the HCP 360 panel: what the audience is, what it is likely to do, and what to change next."
        agent="reporting"
      />

      <FilterBar
        insights={insights}
        filters={filters}
        months={months}
        busy={busy}
        onChange={setFilter}
        onMonthsChange={setMonths}
        onReset={resetFilters}
      />

      <InsightsTicker insights={insights} onSelectMetric={setMetricKey} />

      {error && (
        <Box sx={{
          border: `1px solid ${tokens.color.outline}`, borderRadius: tokens.radius.md,
          background: tokens.color.surface, p: 2, mb: 2.5,
        }}>
          <Typography sx={{ fontSize: 15, fontWeight: 700, mb: 0.5 }}>{error}</Typography>
          <Typography sx={{ fontSize: 15, color: "text.secondary" }}>
            Widen or clear a filter — the cohort has to contain at least one HCP for the dashboard
            to have anything to count.
          </Typography>
        </Box>
      )}

      {insights?.available && (
        <>
          {/* The deep-dive shelf sits directly under the agent's ticker: these are the
              summaries a reader wants before the charts, not a footer. */}
          <Box sx={{ mb: 2 }}>
            <DeepDivePanels insights={insights} />
          </Box>

          <MetricRail
            metrics={headlineMetrics}
            selectedKey={metricKey}
            loading={busy && !loadedOnce.current}
            onSelect={setMetricKey}
          />

          {/* Chart runs the full width now that the agent feed is a ticker above. */}
          <Box sx={{ display: "flex", mb: 2 }}>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <TrendChartSlot metrics={metrics} metricKey={metricKey} onSelect={setMetricKey} busy={busy} />
            </Box>
          </Box>

          <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap", mb: 2, alignItems: "stretch" }}>
            <FunnelCard steps={insights.funnel?.steps ?? []} />
            <GeoCard
              rows={insights.geo ?? []}
              activeState={filters.state}
              onSelectState={(code) => setFilter("state", code)}
            />
            <ChannelCard
              rows={insights.channels ?? []}
              activeChannel={filters.channel}
              onSelectChannel={(channel) => setFilter("channel", channel)}
            />
          </Box>

          {/* The journey takes the full width on its own: five nodes plus their drop-off
              branches do not survive being squeezed into half a column. */}
          <Box sx={{ display: "flex", mb: 2 }}>
            <JourneyCard steps={insights.journey ?? []} />
          </Box>

          <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap", mb: 2, alignItems: "stretch" }}>
            <AssetsCard rows={insights.assets ?? []} />
            <AudienceCard
              breakdowns={{
                segment: insights.breakdowns?.segment ?? [],
                specialty: insights.breakdowns?.specialty ?? [],
              }}
              filters={filters}
              onSelect={setFilter}
            />
          </Box>

          {insights.send_windows && (
            <Box sx={{ display: "flex", mb: 3 }}>
              <SendWindowCard windows={insights.send_windows} />
            </Box>
          )}
        </>
      )}

      {!insights && busy && (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <Shimmer sx={{ height: 132, borderRadius: `${tokens.radius.md}px` }} />
          <Shimmer sx={{ height: 340, borderRadius: `${tokens.radius.md}px` }} />
        </Box>
      )}

      {result && (
        <Box sx={{ mt: 1, transition: `opacity ${motion.duration.panel} ${motion.easeOut}` }}>
          <MeasurementPlan result={result} />
        </Box>
      )}
    </Box>
  );
}

/** Holds the chart's place while the first payload is still in flight, so the page does not
 *  reflow when it lands. */
function TrendChartSlot({
  metrics, metricKey, onSelect, busy,
}: {
  metrics: ReportingInsights["metrics"];
  metricKey: string;
  onSelect: (key: string) => void;
  busy: boolean;
}) {
  if (!metrics?.length) return <Shimmer sx={{ height: 380, borderRadius: `${tokens.radius.md}px` }} />;
  return <TrendChart metrics={metrics} selectedKey={metricKey} onSelect={onSelect} busy={busy} />;
}
