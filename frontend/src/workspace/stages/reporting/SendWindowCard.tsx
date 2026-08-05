/**
 * Best send windows — day × session, straight from the panel's email day/time preference
 * columns. Each cell is the share of the current cohort whose most-preferred email window it
 * is, with the raw HCP count in the tooltip. This is measured preference, not modelled
 * open-time, which is why it is the one card on the page with no benchmark applied to it.
 */
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { motion, tokens } from "../../../theme/tokens";
import { radius, CardTitle, DashCard, dataColor } from "./dashboardKit";
import type { SendWindows } from "../../types";

export function SendWindowCard({ windows }: { windows: SendWindows }) {
  if (!windows?.rows?.length) return null;
  const max = Math.max(...windows.rows.flatMap((r) => r.cells), 0.01);
  // Stated back on the card because this grid is a full split of the cohort: the server
  // apportions the shares so they land on exactly 100%, and the footnote is the proof.
  const gridTotal = windows.rows.flatMap((r) => r.cells).reduce((sum, v) => sum + v, 0);
  const best = windows.rows.reduce<{ day: string; session: string; share: number; count: number } | null>(
    (acc, row) => {
      row.cells.forEach((share, i) => {
        if (!acc || share > acc.share) {
          acc = { day: row.day, session: windows.sessions[i], share, count: row.counts[i] };
        }
      });
      return acc;
    },
    null,
  );

  return (
    <DashCard sx={{ flex: "1 1 420px" }}>
      <CardTitle
        title="Preferred send windows"
        hint={best ? `Peak: ${best.day} ${best.session.toLowerCase()} — ${best.count.toLocaleString()} HCPs` : undefined}
      />
      <Box sx={{ overflowX: "auto" }}>
        <Box sx={{
          display: "grid",
          gridTemplateColumns: `88px repeat(${windows.sessions.length}, minmax(76px, 1fr))`,
          gap: 0.5,
          minWidth: 380,
        }}>
          <Box />
          {windows.sessions.map((s) => (
            <Typography key={s} sx={{ fontSize: 15, fontWeight: 700, color: "text.secondary", textAlign: "center" }}>
              {s}
            </Typography>
          ))}
          {windows.rows.map((row) => (
            <Box key={row.day} sx={{ display: "contents" }}>
              <Typography sx={{ fontSize: 15, fontWeight: 700, alignSelf: "center" }}>{row.day.slice(0, 3)}</Typography>
              {row.cells.map((share, i) => {
                const t = share / max;
                const strong = t > 0.62;
                return (
                  <Box
                    key={i}
                    title={`${row.day} ${windows.sessions[i]} — ${row.counts[i].toLocaleString()} HCPs (${share}%)`}
                    sx={{
                      borderRadius: radius.sm,
                      background: share > 0
                        ? `color-mix(in srgb, ${dataColor.info.line} ${Math.round(10 + 80 * t)}%, white)`
                        : "#F7F9FC",
                      color: strong ? "#fff" : tokens.color.ink,
                      textAlign: "center",
                      py: 1,
                      fontSize: 15,
                      fontWeight: 700,
                      fontVariantNumeric: "tabular-nums",
                      transition: `background 420ms ${motion.easeOut}`,
                      cursor: "default",
                    }}
                  >
                    {share > 0 ? `${share}%` : "—"}
                  </Box>
                );
              })}
            </Box>
          ))}
        </Box>
      </Box>
      <Typography sx={{ fontSize: 15, color: "text.secondary", mt: 1.5 }}>
        {windows.total.toLocaleString()} stated preferences in this cohort, split across the grid —
        cells total {gridTotal.toFixed(2)}% · source
        <Box component="span" sx={{ fontFamily: "monospace", ml: 0.5 }}>global_day_time_preference_data</Box>
      </Typography>
    </DashCard>
  );
}
