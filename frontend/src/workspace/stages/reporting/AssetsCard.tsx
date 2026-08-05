/**
 * Top-performing assets.
 *
 * Ranked by the cohort's own preferred-content tags (`global_content_affinity_score_data`) —
 * the audience column is the number of HCPs who name that tag their top content interest, and
 * the rates are that tag group's own affinity run through the benchmarks. So this is a demand
 * ranking grounded in the panel, not a leaderboard of assets nobody has sent yet.
 */
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { tokens } from "../../../theme/tokens";
import { CardTitle, DashCard, dataColor } from "./dashboardKit";
import type { AssetRow } from "../../types";

/** Cell tint scaled inside the column's own range — comparing a 20% open against a 3% click
 *  on one colour ramp would make every click cell look broken. */
function cellTint(value: number, min: number, max: number, tone: "info" | "positive") {
  const t = max === min ? 0.5 : (value - min) / (max - min);
  const color = tone === "info" ? dataColor.info.line : dataColor.positive.line;
  return `color-mix(in srgb, ${color} ${Math.round(8 + 26 * t)}%, white)`;
}

const th = {
  textAlign: "left" as const,
  fontSize: 15,
  fontWeight: 700,
  color: tokens.color.inkSecondary,
  padding: "8px 10px",
  borderBottom: `1px solid ${tokens.color.outline}`,
  whiteSpace: "nowrap" as const,
};

const td = {
  fontSize: 15,
  padding: "9px 8px",
  borderBottom: `1px solid ${tokens.color.outline}`,
  fontVariantNumeric: "tabular-nums" as const,
};

export function AssetsCard({ rows }: { rows: AssetRow[] }) {
  if (!rows.length) return null;
  const opens = rows.map((r) => r.open_pct);
  const clicks = rows.map((r) => r.ctr_pct);
  const openRange: [number, number] = [Math.min(...opens), Math.max(...opens)];
  const clickRange: [number, number] = [Math.min(...clicks), Math.max(...clicks)];

  return (
    <DashCard sx={{ flex: "2 1 460px" }}>
      <CardTitle title="Top performing assets" hint="Ranked on the cohort's own content demand" />
      <Box sx={{ overflowX: "auto" }}>
        <Box component="table" sx={{ width: "100%", borderCollapse: "collapse", minWidth: 440 }}>
          <thead>
            <tr>
              <Box component="th" sx={th}>Asset</Box>
              <Box component="th" sx={th}>Type</Box>
              <Box component="th" sx={{ ...th, textAlign: "right" }}>HCPs</Box>
              <Box component="th" sx={{ ...th, textAlign: "right" }}>Open</Box>
              <Box component="th" sx={{ ...th, textAlign: "right" }}>Click</Box>
              <Box component="th" sx={{ ...th, textAlign: "right" }}>Conv.</Box>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <Box component="tr" key={row.name} sx={{ "&:hover td": { background: "#FAFBFC" } }}>
                <Box component="td" sx={{ ...td, fontWeight: 700, maxWidth: 240 }}>{row.tag}</Box>
                <Box component="td" sx={{ ...td, color: "text.secondary" }}>{row.type}</Box>
                <Box component="td" sx={{ ...td, textAlign: "right" }}>{row.audience.toLocaleString()}</Box>
                <Box component="td" sx={{ ...td, textAlign: "right", background: cellTint(row.open_pct, openRange[0], openRange[1], "info"), fontWeight: 700 }}>
                  {row.open_pct}%
                </Box>
                <Box component="td" sx={{ ...td, textAlign: "right", background: cellTint(row.ctr_pct, clickRange[0], clickRange[1], "info"), fontWeight: 700 }}>
                  {row.ctr_pct}%
                </Box>
                <Box component="td" sx={{ ...td, textAlign: "right", color: dataColor.positive.ink, fontWeight: 700 }}>
                  {row.conversion_pct}%
                </Box>
              </Box>
            ))}
          </tbody>
        </Box>
      </Box>
      <Typography sx={{ fontSize: 15, color: "text.secondary", mt: 1.5 }}>
        Asset shapes are mapped from the content tag; rates are that tag group's measured affinity
        against the benchmark.
      </Typography>
    </DashCard>
  );
}
