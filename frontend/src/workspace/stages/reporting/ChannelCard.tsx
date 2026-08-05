/**
 * Channel performance.
 *
 * The bar is the engagement rate the cohort's *measured* affinity for that channel implies
 * (benchmark × affinity lift); the count beside it is how many of those HCPs actually name
 * it their preferred channel. The two disagreeing is the interesting case — that gap is what
 * the agent's "under-weighted channel" recommendation is built on. Clicking a row filters
 * the dashboard to that channel's HCPs.
 */
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { hoverOnly, motion, tokens } from "../../../theme/tokens";
import { radius, CardTitle, DashCard, dataColor } from "./dashboardKit";
import type { ChannelRow } from "../../types";

export function ChannelCard({
  rows, activeChannel, onSelectChannel,
}: {
  rows: ChannelRow[];
  activeChannel?: string;
  onSelectChannel: (channel: string) => void;
}) {
  if (!rows.length) return null;
  const max = Math.max(...rows.map((r) => r.engagement_pct), 1);

  return (
    <DashCard sx={{ flex: "1 1 320px" }}>
      <CardTitle title="Channel performance" hint="Engagement rate implied by measured affinity" />
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
        {rows.map((row) => {
          const selected = row.channel === activeChannel;
          return (
            <Box
              key={row.channel}
              role="button"
              tabIndex={0}
              onClick={() => onSelectChannel(row.channel)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelectChannel(row.channel); }
              }}
              sx={{
                display: "flex", alignItems: "center", gap: 1.25, cursor: "pointer",
                borderRadius: radius.sm, px: 0.75, py: 0.5, mx: -0.75,
                background: selected ? dataColor.info.soft : "transparent",
                transition: `background ${motion.duration.hover} ${motion.easeOut}`,
                [hoverOnly]: { "&:hover": { background: selected ? dataColor.info.soft : "#F7F9FC" } },
                "&:focus-visible": { outline: `2px solid ${dataColor.info.line}`, outlineOffset: 2 },
              }}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 18, color: tokens.color.inkSecondary }}>
                {row.icon}
              </span>
              <Typography
                sx={{ fontSize: 15, fontWeight: 700, flex: "0 0 84px", minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}
                title={row.label}
              >
                {row.label}
              </Typography>
              <Box sx={{ flex: 1, height: 12, borderRadius: 6, background: "#F2F4F7", overflow: "hidden", minWidth: 40 }}>
                <Box sx={{
                  width: `${(row.engagement_pct / max) * 100}%`,
                  height: "100%",
                  borderRadius: 6,
                  background: dataColor.info.line,
                  transition: `width 620ms ${motion.easeOut}`,
                }} />
              </Box>
              <Typography sx={{ fontSize: 15, fontWeight: 800, width: 56, textAlign: "right", flex: "0 0 auto", fontVariantNumeric: "tabular-nums" }}>
                {row.engagement_pct}%
              </Typography>
              <Typography
                sx={{ fontSize: 15, color: "text.secondary", width: 52, textAlign: "right", flex: "0 0 auto", fontVariantNumeric: "tabular-nums" }}
                title={`${row.hcps.toLocaleString()} HCPs name this their preferred channel`}
              >
                {row.hcps.toLocaleString()}
              </Typography>
            </Box>
          );
        })}
      </Box>
      <Typography sx={{ fontSize: 15, color: "text.secondary", mt: 1.5 }}>
        Right-hand count is how many of the cohort name that channel their preferred one. Affinity
        scores are per-HCP 0–10 values from the panel's channel table.
      </Typography>
    </DashCard>
  );
}
