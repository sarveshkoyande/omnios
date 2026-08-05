/**
 * The plan-derived measurement framework: the KPI scorecard, channel measurement table and
 * test·measure·learn cycles that the *plan run* produced (stage 5/7/9), as opposed to the
 * panel-derived dashboard above it. Both belong on this tab — one is what the plan committed
 * to measure, the other is what the audience data currently says.
 */
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { ConsolePanel } from "../../../components/ConsolePanel";
import { PlanTable } from "../PlanTable";
import { indigoTint, tokens } from "../../../theme/tokens";
import type { PlanResult } from "../../types";

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

export function MeasurementPlan({ result }: { result: PlanResult }) {
  const kpi = result.stage_7_kpi ?? { leading_indicators: [], lagging_indicators: [], operational_kpis: [] };
  const tml = result.stage_9_test_measure_learn?.rows ?? [];
  const alloc = result.stage_5_budget?.allocation ?? {};
  const leads = kpi.leading_indicators;
  const chRows = Object.entries(alloc).sort((a, b) => b[1].pct - a[1].pct);

  return (
    <>
      <ConsolePanel id="rep-kpi" title="KPI scorecard (measurement plan)" collapsible defaultOpen={false} sx={{ mb: 3 }}>
        <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 2 }}>
          <KpiCol accent={tokens.color.success}>
            <Typography sx={{ display: "flex", alignItems: "center", gap: 1, fontWeight: 700, fontSize: 15, mb: 1 }}>
              <span className="material-symbols-outlined" style={{ fontSize: 15 }}>trending_up</span>Leading
              <Box component="span" sx={{ ml: "auto" }}>{kpi.leading_indicators.length}</Box>
            </Typography>
            <Box component="ul" sx={{ m: 0, pl: 2, fontSize: 15 }}>{leads.map((i, k) => <li key={k}>{i}</li>)}</Box>
          </KpiCol>
          <KpiCol accent="#0B6FA8">
            <Typography sx={{ display: "flex", alignItems: "center", gap: 1, fontWeight: 700, fontSize: 15, mb: 1 }}>
              <span className="material-symbols-outlined" style={{ fontSize: 15 }}>flag</span>Lagging
              <Box component="span" sx={{ ml: "auto" }}>{kpi.lagging_indicators.length}</Box>
            </Typography>
            <Box component="ul" sx={{ m: 0, pl: 2, fontSize: 15 }}>{kpi.lagging_indicators.map((i, k) => <li key={k}>{i}</li>)}</Box>
          </KpiCol>
          <KpiCol accent="#5A32E0">
            <Typography sx={{ display: "flex", alignItems: "center", gap: 1, fontWeight: 700, fontSize: 15, mb: 1 }}>
              <span className="material-symbols-outlined" style={{ fontSize: 15 }}>settings</span>Operational
              <Box component="span" sx={{ ml: "auto" }}>{kpi.operational_kpis.length}</Box>
            </Typography>
            <Box component="ul" sx={{ m: 0, pl: 2, fontSize: 15 }}>{kpi.operational_kpis.map((i, k) => <li key={k}>{i}</li>)}</Box>
          </KpiCol>
        </Box>
        {kpi.cadence_note && (
          <Typography variant="caption" sx={{ color: "text.secondary", fontStyle: "italic", display: "block", mt: 1.5 }}>
            Review cadence: {kpi.cadence_note}
          </Typography>
        )}
      </ConsolePanel>

      <ConsolePanel id="rep-channels" title="Channel measurement framework" collapsible defaultOpen={false} sx={{ mb: 3 }}>
        <PlanTable>
          <thead><tr><th>Channel</th><th>Share</th><th>Primary leading KPI</th><th>Target</th></tr></thead>
          <tbody>
            {chRows.map(([ch, v], i) => (
              <tr key={ch}>
                <td>
                  <span className="material-symbols-outlined" style={{ fontSize: 15, verticalAlign: "-3px", marginRight: 4 }}>
                    {LANE_ICON[ch] ?? "donut_small"}
                  </span>
                  {ch}
                </td>
                <td>{v.pct}%</td>
                <td>{leads[i % (leads.length || 1)] ?? "N/A"}</td>
                <td>
                  <Typography component="span" sx={{ fontSize: 15, color: "warning.dark", background: "#FEF3C7", px: 1, borderRadius: 999 }}>
                    Baseline needed
                  </Typography>
                </td>
              </tr>
            ))}
          </tbody>
        </PlanTable>
      </ConsolePanel>

      <ConsolePanel id="rep-tml" title="Test · Measure · Learn" collapsible defaultOpen={false}>
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
