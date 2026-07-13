import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import LinearProgress from "@mui/material/LinearProgress";
import Typography from "@mui/material/Typography";
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
const FMT_TO_LANE: Record<string, string> = {
  email: "Owned digital",
  banner: "Reach",
  detail_aid: "Field",
  social: "Patient-adjacent",
  video: "Owned digital",
  webpage: "Owned digital",
};

export function StageOperations({ result }: { result: PlanResult | null }) {
  if (!result) {
    return <ConsolePanel><Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>Complete Stage 1 to open campaign operations.</Typography></ConsolePanel>;
  }
  const alloc = result.stage_5_budget?.allocation ?? {};
  const ppnpp: Record<string, string> = {};
  (result.stage_2_4_pp_npp ?? []).forEach((p) => { ppnpp[p.channel] = p.bucket; });
  const touch = result.stage_2_4_strategy?.recommended_touchpoints ?? {};
  const lib = result.content_library ?? { assets: [], found: false };
  const exec = result.stage_9_execution_plan ?? { bands: [] };

  const assetsByLane: Record<string, typeof lib.assets> = {};
  lib.assets.forEach((a) => {
    const lane = FMT_TO_LANE[a.asset_format] ?? "Owned digital";
    (assetsByLane[lane] ??= []).push(a);
  });

  const lanes = Object.entries(alloc).sort((a, b) => b[1].pct - a[1].pct);

  return (
    <Box>
      <StageHead
        icon="dashboard"
        title="Campaign Operations"
        blurb="Execution runs as parallel tracks — one lane per channel, each with its own budget, tactics, content assets and readiness status."
      />

      {!lib.found && (
        <ConsolePanel sx={{ mb: 3 }}>
          <Typography sx={{ fontSize: 12, color: "text.secondary", background: "#FFF8E6", border: "1px solid #F0E0A8", borderRadius: 2, p: 1.5 }}>
            No content library indexed for this brand — lanes show tactics only. Run <code>scripts/build_content_library.py</code> to populate assets.
          </Typography>
        </ConsolePanel>
      )}

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 3, mb: 3 }}>
        {lanes.length ? lanes.map(([ch, v]) => {
          const assets = assetsByLane[ch] ?? [];
          const tps = touch[ch] ?? [];
          const ready = assets.length > 0;
          const amt = v.amount ? `$${Number(v.amount).toLocaleString()}` : "—";
          return (
            <ConsolePanel key={ch} sx={{ minWidth: 0 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 1.5 }}>
                <Box sx={{ width: 28, height: 28, borderRadius: 2, background: shade(0.06), display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 17, color: tokens.color.primary }}>{LANE_ICON[ch] ?? "donut_small"}</span>
                </Box>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography sx={{ fontWeight: 700, fontSize: 13 }}>{ch}</Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary", display: "block" }}>{v.pct}% · {amt} · {ppnpp[ch] ?? "—"}</Typography>
                </Box>
                <Chip size="small" color={ready ? "success" : "warning"} label={ready ? "Assets ready" : "Content needed"} sx={{ flex: "0 0 auto" }} />
              </Box>
              <LinearProgress variant="determinate" value={v.pct} sx={{ mb: 2 }} />

              <Typography variant="overline" sx={{ display: "block", mb: 0.5 }}>Tactics</Typography>
              <Box component="ul" sx={{ m: "0 0 12px", pl: 2, fontSize: 12 }}>
                {tps.length ? tps.map((t, i) => <li key={i}>{t}</li>) : <li style={{ color: shade(0.5) }}>No touchpoints mapped.</li>}
              </Box>

              <Typography variant="overline" sx={{ display: "block", mb: 0.5 }}>Content assets ({assets.length})</Typography>
              {assets.length ? assets.map((a, i) => (
                <Box key={i} sx={{ display: "flex", alignItems: "center", gap: 1, py: 0.5 }}>
                  <Chip size="small" label={a.asset_format} />
                  <Typography sx={{ fontSize: 11, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={a.title}>{a.title}</Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary", fontStyle: a.branded ? "normal" : "italic" }}>{a.branded ? "Branded" : "Unbranded"}</Typography>
                </Box>
              )) : (
                <Typography variant="caption" sx={{ color: "warning.dark", display: "flex", alignItems: "center", gap: 0.5 }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 14 }}>add_circle</span>
                  No approved asset yet — content production required.
                </Typography>
              )}
            </ConsolePanel>
          );
        }) : <Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>No channel allocation.</Typography>}
      </Box>

      {exec.bands.length > 0 && (
        <ConsolePanel title="Execution timeline (all lanes)">
          <PlanTable>
            <thead><tr><th>Task category</th><th>Weeks</th><th>Representative tasks</th></tr></thead>
            <tbody>
              {exec.bands.map((b, i) => (
                <tr key={i}>
                  <td>{b.category}</td>
                  <td>W{b.start_week}–W{b.end_week}</td>
                  <td>{b.tasks.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </PlanTable>
          {exec.mlr_delay_note && <Typography variant="caption" sx={{ color: "text.secondary", fontStyle: "italic", display: "block", mt: 1 }}>{exec.mlr_delay_note}</Typography>}
        </ConsolePanel>
      )}
    </Box>
  );
}
