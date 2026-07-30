import { useEffect, useMemo, useState } from "react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { ConsolePanel } from "../../components/ConsolePanel";
import { PlanTable } from "./PlanTable";
import { StageHead } from "./StageHead";
import { indigoTint, tokens } from "../../theme/tokens";
import { accent } from "../../theme/stageTheme";
import { fetchReportingInsights } from "../../api";
import type { PlanResult, ReportingInsights, ReportingKpi, ReportingSignal, SegmentRow } from "../types";

const TIME_WINDOWS = [
  { label: "Last 3 months", months: 3 },
  { label: "Last 6 months", months: 6 },
  { label: "Last 12 months", months: 12 },
];

/** A single email-funnel metric card: label + exact current-period percentage. */
const EmailMetricCard = styled(Box)(({ theme }) => ({
  flex: "1 1 150px",
  minWidth: 140,
  borderRadius: tokens.radius.md,
  border: `1px solid ${indigoTint(0.14)}`,
  background: "rgba(255,255,255,0.55)",
  padding: theme.spacing(1.5),
  display: "flex",
  flexDirection: "column",
  gap: 2,
}));

const LANE_ICON: Record<string, string> = {
  Field: "groups",
  Events: "event",
  "Owned digital": "language",
  Reach: "campaign",
  "Patient-adjacent": "favorite",
  Peer: "diversity_3",
};

const KpiCol = styled(Box)<{ accent: string }>(({ theme, accent }) => ({
  borderLeft: `3px solid ${accent}`,
  borderRadius: tokens.radius.sm,
  border: `1px solid ${indigoTint(0.12)}`,
  padding: theme.spacing(2),
  background: "rgba(255,255,255,0.4)",
}));

// A measurement card: big target headline + band + context. Primary cards get an accent ring.
const InsightCard = styled(Box)<{ primary?: boolean }>(({ theme, primary }) => ({
  borderRadius: tokens.radius.md,
  border: `1px solid ${primary ? accent.primary : indigoTint(0.14)}`,
  boxShadow: primary ? `0 0 0 1px ${accent.primary}22` : "none",
  padding: theme.spacing(1.75),
  background: "rgba(255,255,255,0.55)",
  display: "flex",
  flexDirection: "column",
  gap: theme.spacing(0.25),
  minWidth: 0,
}));

function metricHeadline(m: ReportingKpi | ReportingSignal): string {
  if ("value_display" in m && m.value_display) return m.value_display;
  if (m.band) return m.band;
  if (m.value_pct != null) return `${m.value_pct}%`;
  return "—";
}

/** Horizontal count bars for a demographic dimension (counts are comparable within a dim). */
function SegmentBars({ rows }: { rows: SegmentRow[] }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 0.6 }}>
      {rows.map((r) => (
        <Box key={r.value} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Typography variant="caption" sx={{ flex: "0 0 42%", minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }} title={r.value}>
            {r.value}
          </Typography>
          <Box sx={{ flex: 1, height: 8, borderRadius: 4, background: indigoTint(0.08), overflow: "hidden" }}>
            <Box sx={{ width: `${(r.count / max) * 100}%`, height: "100%", background: accent.primary, borderRadius: 4 }} />
          </Box>
          <Typography variant="caption" sx={{ flex: "0 0 auto", fontWeight: 700, color: "text.secondary" }}>{r.count}</Typography>
        </Box>
      ))}
    </Box>
  );
}

function DemoBlock({ title, rows }: { title: string; rows?: SegmentRow[] }) {
  if (!rows?.length) return null;
  return (
    <Box sx={{ flex: 1, minWidth: 200 }}>
      <Typography variant="caption" sx={{ fontWeight: 700, display: "block", mb: 0.75, color: "text.secondary" }}>{title}</Typography>
      <SegmentBars rows={rows} />
    </Box>
  );
}

/** Day × hour-of-day open-rate heatmap — cell shade intensity on the current stage accent. */
function OpensHeatmap({ hours, rows }: { hours: string[]; rows: { day: string; cells: number[] }[] }) {
  const max = Math.max(0.01, ...rows.flatMap((r) => r.cells));
  return (
    <Box sx={{ overflowX: "auto" }}>
      <PlanTable>
        <thead>
          <tr>
            <th>Day</th>
            {hours.map((h) => <th key={h}>{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.day}>
              <td><b>{r.day}</b></td>
              {r.cells.map((v, i) => (
                <td key={i} style={{ background: v > 0 ? `${accent.primary}${Math.round((v / max) * 70 + 8).toString(16).padStart(2, "0")}` : undefined, fontVariantNumeric: "tabular-nums" }}>
                  {v > 0 ? `${v}%` : ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </PlanTable>
    </Box>
  );
}

/** Ranked horizontal bar list (state-level CTR) — a lighter-weight substitute for a full
 * choropleth map, same information (relative ranking + exact value) without a mapping library. */
function StateCtrList({ rows }: { rows: { state: string; ctr_pct: number }[] }) {
  const max = Math.max(0.01, ...rows.map((r) => r.ctr_pct));
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 0.6, maxHeight: 320, overflowY: "auto" }}>
      {rows.map((r) => (
        <Box key={r.state} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Typography variant="caption" sx={{ flex: "0 0 34%", minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {r.state}
          </Typography>
          <Box sx={{ flex: 1, height: 9, borderRadius: 4, background: indigoTint(0.08), overflow: "hidden" }}>
            <Box sx={{ width: `${(r.ctr_pct / max) * 100}%`, height: "100%", background: accent.primary, borderRadius: 4 }} />
          </Box>
          <Typography variant="caption" sx={{ flex: "0 0 auto", fontWeight: 700, color: "text.secondary", minWidth: 44, textAlign: "right" }}>{r.ctr_pct}%</Typography>
        </Box>
      ))}
    </Box>
  );
}

const DONUT_SHADES = [1, 0.6, 0.28]; // opacity steps on the stage accent, darkest -> lightest

/** CSS conic-gradient donut (no chart library) shaded in steps of the current stage accent. */
function SegmentDonut({ rows }: { rows: { segment: string; pct: number }[] }) {
  let acc = 0;
  const stops = rows.map((r, i) => {
    const start = acc;
    acc += r.pct;
    const color = `${accent.primary}${Math.round(DONUT_SHADES[i % DONUT_SHADES.length] * 255).toString(16).padStart(2, "0")}`;
    return `${color} ${start}% ${acc}%`;
  });
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 3, flexWrap: "wrap" }}>
      <Box
        sx={{
          width: 150,
          height: 150,
          borderRadius: "50%",
          background: `conic-gradient(${stops.join(", ")})`,
          display: "grid",
          placeItems: "center",
          flex: "0 0 auto",
        }}
      >
        <Box sx={{ width: 84, height: 84, borderRadius: "50%", background: tokens.color.surface }} />
      </Box>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
        {rows.map((r, i) => (
          <Box key={r.segment} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Box sx={{ width: 12, height: 12, borderRadius: "3px", background: `${accent.primary}${Math.round(DONUT_SHADES[i % DONUT_SHADES.length] * 255).toString(16).padStart(2, "0")}`, flex: "0 0 auto" }} />
            <Typography variant="caption">{r.segment} — <b>{r.pct}%</b></Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
}

const StatTile = styled(Box)(({ theme }) => ({
  flex: "1 1 180px",
  minWidth: 160,
  borderRadius: tokens.radius.md,
  background: accent.primary,
  color: "#fff",
  padding: theme.spacing(2),
  display: "flex",
  flexDirection: "column",
  gap: 4,
}));

export function StageReporting({ result, projectId }: { result: PlanResult | null; projectId: string | null }) {
  const [insights, setInsights] = useState<ReportingInsights | null>(null);
  const [months, setMonths] = useState(6);
  const [specialty, setSpecialty] = useState<string>("");

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    fetchReportingInsights(projectId, { months, specialty: specialty || null })
      .then((d) => { if (!cancelled) setInsights(d); })
      .catch(() => { if (!cancelled) setInsights(null); });
    return () => { cancelled = true; };
  }, [projectId, result, months, specialty]);

  if (!result && !insights) {
    return <ConsolePanel><Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>Complete Stage 1 to see the measurement framework.</Typography></ConsolePanel>;
  }

  const demo = insights?.demographics;
  const specialtyOptions = useMemo(() => (demo?.by_specialty ?? []).map((r) => r.value), [demo]);

  return (
    <Box>
      <StageHead
        icon="insights"
        title="Reporting & Insights"
        blurb="The closed-loop scorecard: the KPIs that prove the plan worked, the audience they measure, and how every touch is tagged and tested."
        agent="reporting"
      />

      {insights && (
        <>
          {/* Filters — apply to the email metrics funnel below. */}
          <ConsolePanel id="rep-filters" sx={{ mb: 3 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 2, flexWrap: "wrap" }}>
              <Typography variant="caption" sx={{ fontWeight: 700, color: "text.secondary" }}>Filters</Typography>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Typography variant="caption" sx={{ color: "text.secondary" }}>Time</Typography>
                <Select size="small" value={months} onChange={(e) => setMonths(Number(e.target.value))} sx={{ minWidth: 150, fontSize: 13 }}>
                  {TIME_WINDOWS.map((w) => <MenuItem key={w.months} value={w.months}>{w.label}</MenuItem>)}
                </Select>
              </Box>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Typography variant="caption" sx={{ color: "text.secondary" }}>Specialty</Typography>
                <Select size="small" value={specialty} onChange={(e) => setSpecialty(e.target.value)} displayEmpty sx={{ minWidth: 170, fontSize: 13 }}>
                  <MenuItem value="">All specialties</MenuItem>
                  {specialtyOptions.map((s) => <MenuItem key={s} value={s}>{s}</MenuItem>)}
                </Select>
              </Box>
            </Box>
          </ConsolePanel>

          {/* Email metrics funnel — exact current-period percentage, in delivery order, plus a
              monthly split for every metric. */}
          {insights.email_metrics && (
            <ConsolePanel id="rep-email-metrics" title="Email metrics" sx={{ mb: 3 }}>
              <Box sx={{ display: "flex", gap: 1.25, flexWrap: "wrap", mb: 2.5 }}>
                {insights.email_metrics.metrics.map((m) => (
                  <EmailMetricCard key={m.key}>
                    <Typography variant="caption" sx={{ fontWeight: 700 }}>{m.label}</Typography>
                    <Typography sx={{ fontSize: 24, fontWeight: 800, color: "text.primary", lineHeight: 1.1 }}>{m.value_pct}%</Typography>
                  </EmailMetricCard>
                ))}
              </Box>

              <Typography variant="caption" sx={{ fontWeight: 700, color: "text.secondary", display: "block", mb: 1 }}>
                Split by month
              </Typography>
              <Box sx={{ overflowX: "auto" }}>
                <PlanTable>
                  <thead>
                    <tr>
                      <th>Metric</th>
                      {insights.email_metrics.months.map((mo) => <th key={mo}>{mo}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {insights.email_metrics.metrics.map((m) => (
                      <tr key={m.key}>
                        <td><b>{m.label}</b></td>
                        {m.monthly.map((row) => (
                          <td key={row.month}>{row.value_pct}%</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </PlanTable>
              </Box>
              <Typography variant="caption" sx={{ color: "text.secondary", fontStyle: "italic", display: "block", mt: 1.5 }}>
                {insights.email_metrics.note} Showing: {insights.email_metrics.specialty}.
              </Typography>
            </ConsolePanel>
          )}

          {/* Email deep-dive: open-time heatmap + CTR by state, delivered-by-segment + subject
              line performance, and reach tiles — all on the current stage accent. */}
          {insights.email_deepdive && (
            <>
              <Box sx={{ display: "flex", gap: 3, flexWrap: "wrap", mb: 3, alignItems: "stretch" }}>
                <ConsolePanel title="Opens — by time of day" sx={{ flex: "1 1 420px", minWidth: 0 }}>
                  <OpensHeatmap hours={insights.email_deepdive.opens_by_time.hours} rows={insights.email_deepdive.opens_by_time.rows} />
                </ConsolePanel>
                <ConsolePanel title="CTR by state" sx={{ flex: "1 1 320px", minWidth: 0 }}>
                  <StateCtrList rows={insights.email_deepdive.ctr_by_state} />
                </ConsolePanel>
              </Box>

              <Box sx={{ display: "flex", gap: 3, flexWrap: "wrap", mb: 3, alignItems: "stretch" }}>
                <ConsolePanel title="Delivered by segment" sx={{ flex: "1 1 320px", minWidth: 0 }}>
                  <SegmentDonut rows={insights.email_deepdive.delivered_by_segment} />
                </ConsolePanel>
                <ConsolePanel title="Subject line performance" sx={{ flex: "2 1 480px", minWidth: 0 }}>
                  <Box sx={{ overflowX: "auto" }}>
                    <PlanTable>
                      <thead>
                        <tr>
                          <th>Asset name</th><th>Segment</th><th>Subject line</th><th>A/B testing</th><th>Wave type</th>
                          <th>Emails sent</th><th>Deliveries</th><th>Opens</th><th>Clicks</th><th>Open rate</th><th>CTR</th>
                        </tr>
                      </thead>
                      <tbody>
                        {insights.email_deepdive.subject_lines.map((r, i) => (
                          <tr key={i}>
                            <td>{r.asset_name}</td>
                            <td>{r.segment || "—"}</td>
                            <td>{r.subject_line}</td>
                            <td>{r.ab_testing}</td>
                            <td>{r.wave_type}</td>
                            <td>{r.emails_sent}</td>
                            <td>{r.deliveries}</td>
                            <td>{r.opens}</td>
                            <td>{r.clicks}</td>
                            <td>{r.open_rate_pct}%</td>
                            <td>{r.ctr_pct}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </PlanTable>
                  </Box>
                </ConsolePanel>
              </Box>

              <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap", mb: 3 }}>
                <StatTile>
                  <Typography variant="caption" sx={{ opacity: 0.85 }}>Unique HCP reached</Typography>
                  <Typography sx={{ fontSize: 26, fontWeight: 800 }}>{insights.email_deepdive.tiles.unique_hcp_reached.toLocaleString()}</Typography>
                </StatTile>
                <StatTile>
                  <Typography variant="caption" sx={{ opacity: 0.85 }}>Unique HCP engaged</Typography>
                  <Typography sx={{ fontSize: 26, fontWeight: 800 }}>{insights.email_deepdive.tiles.unique_hcp_engaged.toLocaleString()}</Typography>
                </StatTile>
                <StatTile>
                  <Typography variant="caption" sx={{ opacity: 0.85 }}>Unique HCP deep engaged</Typography>
                  <Typography sx={{ fontSize: 26, fontWeight: 800 }}>{insights.email_deepdive.tiles.unique_hcp_deep_engaged.toLocaleString()}</Typography>
                </StatTile>
                <StatTile>
                  <Typography variant="caption" sx={{ opacity: 0.85 }}>Unique subject lines</Typography>
                  <Typography sx={{ fontSize: 26, fontWeight: 800 }}>{insights.email_deepdive.tiles.unique_subject_lines}</Typography>
                </StatTile>
              </Box>
            </>
          )}

          {/* Stage-promotion funnel — the signals that move an HCP to the next journey stage. */}
          <ConsolePanel id="rep-funnel" title={`Stage-promotion signals — ${insights.funnel.stage}`} sx={{ mb: 3 }}>
            <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 1.5 }}>{insights.funnel.note}</Typography>
            <Box sx={{ display: "flex", gap: 1, alignItems: "stretch", flexWrap: "wrap" }}>
              {insights.funnel.signals.map((s, i) => (
                <Box key={s.label} sx={{ display: "flex", alignItems: "center", gap: 1, flex: "1 1 200px" }}>
                  <InsightCard primary={s.primary} sx={{ flex: 1 }}>
                    <Typography variant="caption" sx={{ fontWeight: 700 }}>{s.label}</Typography>
                    <Typography sx={{ fontSize: 22, fontWeight: 800, color: s.primary ? accent.primary : "text.primary", lineHeight: 1.1 }}>{metricHeadline(s)}</Typography>
                    <Typography variant="caption" sx={{ color: "text.secondary" }}>{s.note}</Typography>
                    {s.primary && <Chip size="small" label="primary promotion signal" sx={{ mt: 0.5, height: 18, fontSize: 10, alignSelf: "flex-start", bgcolor: `${accent.primary}18`, color: accent.primary }} />}
                  </InsightCard>
                  {i < insights.funnel.signals.length - 1 && (
                    <span className="material-symbols-outlined" style={{ fontSize: 20, color: indigoTint(0.4) }}>arrow_forward</span>
                  )}
                </Box>
              ))}
            </Box>
          </ConsolePanel>

          {/* Delivery & engagement KPI cards. */}
          <ConsolePanel id="rep-kpicards" title="Delivery & engagement KPIs" sx={{ mb: 3 }}>
            <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 1.5 }}>
              {insights.kpis.map((k) => (
                <InsightCard key={k.label} primary={k.primary}>
                  <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 1 }}>
                    <Typography variant="caption" sx={{ fontWeight: 700 }}>{k.label}</Typography>
                    <Chip size="small" label={k.kind === "volume" ? "volume" : "rate"} variant="outlined" sx={{ height: 18, fontSize: 10 }} />
                  </Box>
                  <Typography sx={{ fontSize: 24, fontWeight: 800, color: k.primary ? accent.primary : "text.primary", lineHeight: 1.1 }}>{metricHeadline(k)}</Typography>
                  {k.sub && <Typography variant="caption" sx={{ color: "text.secondary" }}>{k.sub}</Typography>}
                  {k.note && <Typography variant="caption" sx={{ color: "text.disabled", fontStyle: "italic" }}>{k.note}</Typography>}
                </InsightCard>
              ))}
            </Box>
            <Typography variant="caption" sx={{ color: "text.secondary", fontStyle: "italic", display: "block", mt: 1.5 }}>{insights.caveat}</Typography>
          </ConsolePanel>

          {/* Real HCP-panel demographics. */}
          {demo?.available && (
            <ConsolePanel id="rep-demographics" title={`HCP audience — ${demo.total_hcps?.toLocaleString()} in panel`} sx={{ mb: 3 }}>
              <Box sx={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
                <DemoBlock title="By specialty" rows={demo.by_specialty} />
                <DemoBlock title="By preferred channel" rows={demo.by_preferred_channel} />
                <DemoBlock title="By segment" rows={demo.by_segment} />
              </Box>
              <Typography variant="caption" sx={{ color: "text.secondary", fontStyle: "italic", display: "block", mt: 1.5 }}>
                Live counts from the HCP 360 panel. Ask the Reporting agent (left) to segment or list specific HCPs.
              </Typography>
            </ConsolePanel>
          )}

          {/* Link/tagging (UTM) matrix deliverable. */}
          <ConsolePanel id="rep-tagging" title="Link & tagging matrix (UTM taxonomy)" sx={{ mb: 3 }}>
            <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 1 }}>{insights.tagging.note}</Typography>
            <Box sx={{ overflowX: "auto" }}>
              <PlanTable>
                <thead><tr>{insights.tagging.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                <tbody>
                  {insights.tagging.rows.map((r) => (
                    <tr key={r.parameter}>
                      <td style={{ fontFamily: "monospace", fontSize: 12 }}>{r.parameter}</td>
                      <td>{r.convention}</td>
                      <td style={{ fontFamily: "monospace", fontSize: 12, color: accent.primary }}>{r.example}</td>
                    </tr>
                  ))}
                </tbody>
              </PlanTable>
            </Box>
          </ConsolePanel>

          {/* A/B test design. */}
          <ConsolePanel id="rep-test" title="Test design" sx={{ mb: 3 }}>
            <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 1 }}>{insights.test_design.approach}</Typography>
            <PlanTable>
              <thead><tr><th>Test</th><th>Variants</th><th>Measure</th><th></th></tr></thead>
              <tbody>
                {insights.test_design.rows.map((r) => (
                  <tr key={r.test}>
                    <td><b>{r.test}</b></td>
                    <td>{r.variants}</td>
                    <td>{r.measure}</td>
                    <td>{r.primary && <Chip size="small" label="primary" sx={{ height: 18, fontSize: 10, bgcolor: `${accent.primary}18`, color: accent.primary }} />}</td>
                  </tr>
                ))}
              </tbody>
            </PlanTable>
            <Typography variant="caption" sx={{ color: "text.secondary", fontStyle: "italic", display: "block", mt: 1 }}>{insights.test_design.note}</Typography>
          </ConsolePanel>
        </>
      )}

      {result && <MeasurementPlan result={result} />}
    </Box>
  );
}

/** The plan-derived measurement framework (KPI scorecard, channel measurement, test·measure·learn). */
function MeasurementPlan({ result }: { result: PlanResult }) {
  const kpi = result.stage_7_kpi ?? { leading_indicators: [], lagging_indicators: [], operational_kpis: [] };
  const tml = result.stage_9_test_measure_learn?.rows ?? [];
  const alloc = result.stage_5_budget?.allocation ?? {};
  const leads = kpi.leading_indicators;
  const chRows = Object.entries(alloc).sort((a, b) => b[1].pct - a[1].pct);

  return (
    <>
      <ConsolePanel id="rep-kpi" title="KPI scorecard (measurement plan)" sx={{ mb: 3 }}>
        <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 2 }}>
          <KpiCol accent={tokens.color.success}>
            <Typography sx={{ display: "flex", alignItems: "center", gap: 1, fontWeight: 700, fontSize: 12, mb: 1 }}>
              <span className="material-symbols-outlined" style={{ fontSize: 15 }}>trending_up</span>Leading<Box component="span" sx={{ ml: "auto" }}>{kpi.leading_indicators.length}</Box>
            </Typography>
            <Box component="ul" sx={{ m: 0, pl: 2, fontSize: 11 }}>{leads.map((i, k) => <li key={k}>{i}</li>)}</Box>
          </KpiCol>
          <KpiCol accent="#0B6FA8">
            <Typography sx={{ display: "flex", alignItems: "center", gap: 1, fontWeight: 700, fontSize: 12, mb: 1 }}>
              <span className="material-symbols-outlined" style={{ fontSize: 15 }}>flag</span>Lagging<Box component="span" sx={{ ml: "auto" }}>{kpi.lagging_indicators.length}</Box>
            </Typography>
            <Box component="ul" sx={{ m: 0, pl: 2, fontSize: 11 }}>{kpi.lagging_indicators.map((i, k) => <li key={k}>{i}</li>)}</Box>
          </KpiCol>
          <KpiCol accent="#5A32E0">
            <Typography sx={{ display: "flex", alignItems: "center", gap: 1, fontWeight: 700, fontSize: 12, mb: 1 }}>
              <span className="material-symbols-outlined" style={{ fontSize: 15 }}>settings</span>Operational<Box component="span" sx={{ ml: "auto" }}>{kpi.operational_kpis.length}</Box>
            </Typography>
            <Box component="ul" sx={{ m: 0, pl: 2, fontSize: 11 }}>{kpi.operational_kpis.map((i, k) => <li key={k}>{i}</li>)}</Box>
          </KpiCol>
        </Box>
        {kpi.cadence_note && <Typography variant="caption" sx={{ color: "text.secondary", fontStyle: "italic", display: "block", mt: 1.5 }}>Review cadence: {kpi.cadence_note}</Typography>}
      </ConsolePanel>

      <ConsolePanel id="rep-channels" title="Channel measurement framework" sx={{ mb: 3 }}>
        <PlanTable>
          <thead><tr><th>Channel</th><th>Share</th><th>Primary leading KPI</th><th>Target</th></tr></thead>
          <tbody>
            {chRows.map(([ch, v], i) => (
              <tr key={ch}>
                <td><span className="material-symbols-outlined" style={{ fontSize: 14, verticalAlign: "-3px", marginRight: 4 }}>{LANE_ICON[ch] ?? "donut_small"}</span>{ch}</td>
                <td>{v.pct}%</td>
                <td>{leads[i % (leads.length || 1)] ?? "N/A"}</td>
                <td><Typography component="span" sx={{ fontSize: 10, color: "warning.dark", background: "#FEF3C7", px: 1, borderRadius: 999 }}>Baseline needed</Typography></td>
              </tr>
            ))}
          </tbody>
        </PlanTable>
      </ConsolePanel>

      <ConsolePanel id="rep-tml" title="Test · Measure · Learn">
        {tml.length > 0 ? (
          <Box sx={{ overflowX: "auto" }}>
            <PlanTable>
              <thead><tr><th>Test</th><th>Measure</th><th>Channels</th><th>Frequency</th><th>What good looks like</th></tr></thead>
              <tbody>
                {tml.map((t, i) => (
                  <tr key={i}>
                    <td><b>{t.test}</b></td><td>{t.measure}</td><td>{t.channels}</td><td>{t.frequency}</td><td>{t.what_good_looks_like}</td>
                  </tr>
                ))}
              </tbody>
            </PlanTable>
          </Box>
        ) : (
          <Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>
            No test · measure · learn cycles defined yet.
          </Typography>
        )}
      </ConsolePanel>
    </>
  );
}
