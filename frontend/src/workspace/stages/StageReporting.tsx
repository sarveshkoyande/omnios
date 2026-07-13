import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { ConsolePanel } from "../../components/ConsolePanel";
import { PlanTable } from "./PlanTable";
import { StageHead } from "./StageHead";
import { shade, tokens } from "../../theme/tokens";
import type { PlanResult } from "../types";

const LANE_ICON: Record<string, string> = {
  Field: "groups",
  Events: "event",
  "Owned digital": "language",
  Reach: "campaign",
  "Patient-adjacent": "favorite",
  Peer: "diversity_3",
};

const ScoreTile = styled(Box)<{ tint?: string }>(({ theme, tint }) => ({
  textAlign: "center",
  borderRadius: 10,
  padding: theme.spacing(2, 1),
  background: tint ?? shade(0.03),
}));

const KpiCol = styled(Box)<{ accent: string }>(({ theme, accent }) => ({
  borderLeft: `3px solid ${accent}`,
  borderRadius: 8,
  border: `1px solid ${shade(0.14)}`,
  padding: theme.spacing(2),
}));

export function StageReporting({ result }: { result: PlanResult | null }) {
  if (!result) {
    return <ConsolePanel><Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>Complete Stage 1 to see the measurement framework.</Typography></ConsolePanel>;
  }
  const kpi = result.stage_7_kpi ?? { leading_indicators: [], lagging_indicators: [], operational_kpis: [] };
  const tml = result.stage_9_test_measure_learn?.rows ?? [];
  const alloc = result.stage_5_budget?.allocation ?? {};
  const inf = result.inferred_inputs;
  const lib: NonNullable<PlanResult["content_library"]> = result.content_library ?? { found: false, assets: [], counts: {} };

  const lifecycleLower = (inf.lifecycle_label || "").toLowerCase();
  const measurementFocus = /loss|exclusivity|decline/.test(lifecycleLower)
    ? "retention and adherence over new-patient acquisition"
    : /launch/.test(lifecycleLower)
      ? "awareness, reach and first-prescription conversion"
      : "share-of-voice conversion and depth of engagement";

  const leads = kpi.leading_indicators;
  const chRows = Object.entries(alloc).sort((a, b) => b[1].pct - a[1].pct);

  return (
    <Box>
      <StageHead
        icon="insights"
        title="Reporting & Insights"
        blurb="The closed-loop scorecard: which KPIs prove the plan worked, how each channel is measured, and what to learn next."
      />

      <ConsolePanel sx={{ mb: 3 }}>
        <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(88px, 1fr))", gap: 1.5 }}>
          <ScoreTile><Typography sx={{ fontSize: 20, fontWeight: 700 }}>{kpi.leading_indicators.length}</Typography><Typography variant="caption">Leading KPIs</Typography></ScoreTile>
          <ScoreTile><Typography sx={{ fontSize: 20, fontWeight: 700 }}>{kpi.lagging_indicators.length}</Typography><Typography variant="caption">Lagging KPIs</Typography></ScoreTile>
          <ScoreTile><Typography sx={{ fontSize: 20, fontWeight: 700 }}>{kpi.operational_kpis.length}</Typography><Typography variant="caption">Operational KPIs</Typography></ScoreTile>
          <ScoreTile><Typography sx={{ fontSize: 20, fontWeight: 700 }}>{Object.keys(alloc).length}</Typography><Typography variant="caption">Channels tracked</Typography></ScoreTile>
          <ScoreTile><Typography sx={{ fontSize: 20, fontWeight: 700 }}>{lib.counts?.assets ?? 0}</Typography><Typography variant="caption">Assets in market</Typography></ScoreTile>
        </Box>
      </ConsolePanel>

      <ConsolePanel title="Insights & read-outs" sx={{ mb: 3 }}>
        <Box component="ul" sx={{ m: 0, pl: 2.5, fontSize: 13, lineHeight: 1.7 }}>
          <li>Lifecycle posture: <b>{inf.lifecycle_label || "—"}</b> — measurement should weight {measurementFocus}.</li>
          <li>Priority audience <b>{inf.persona || "—"}</b> at the <b>{inf.stage_label || "—"}</b> journey stage — read leading indicators at the segment level, not just campaign level.</li>
          <li>{lib.counts?.approved_claims ?? 0} MLR-approved claims are live; unsubstantiated claims block reporting credibility — keep the claims-to-reference graph clean before scaling spend.</li>
          <li>No live performance data is connected yet. The scorecard below is the <b>measurement plan</b> (what to track and what good looks like), not observed results.</li>
        </Box>
      </ConsolePanel>

      <ConsolePanel title="KPI scorecard" sx={{ mb: 3 }}>
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

      <ConsolePanel title="Channel measurement framework" sx={{ mb: 3 }}>
        <PlanTable>
          <thead><tr><th>Channel</th><th>Share</th><th>Primary leading KPI</th><th>Target</th></tr></thead>
          <tbody>
            {chRows.map(([ch, v], i) => (
              <tr key={ch}>
                <td><span className="material-symbols-outlined" style={{ fontSize: 14, verticalAlign: "-3px", marginRight: 4 }}>{LANE_ICON[ch] ?? "donut_small"}</span>{ch}</td>
                <td>{v.pct}%</td>
                <td>{leads[i % (leads.length || 1)] ?? "—"}</td>
                <td><Typography component="span" sx={{ fontSize: 10, color: "warning.dark", background: "#FEF3C7", px: 1, borderRadius: 999 }}>Baseline needed</Typography></td>
              </tr>
            ))}
          </tbody>
        </PlanTable>
        <Typography variant="caption" sx={{ color: "text.secondary", fontStyle: "italic", display: "block", mt: 1 }}>
          Targets require a baseline from the first in-market period — no observed data is connected.
        </Typography>
      </ConsolePanel>

      {tml.length > 0 && (
        <ConsolePanel title="Test · Measure · Learn">
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
        </ConsolePanel>
      )}
    </Box>
  );
}
