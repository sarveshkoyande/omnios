/**
 * Audience composition — who is actually in the cohort, by target-list segment and by
 * specialty, with each group's own measured email affinity beside its size.
 *
 * Rows are filter handles: clicking one drills the whole dashboard into that group.
 */
import { useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { hoverOnly, motion, tokens } from "../../../theme/tokens";
import { radius, CardTitle, DashCard, dataColor } from "./dashboardKit";
import type { BreakdownRow, ReportingFilterKey } from "../../types";

const TABS: { key: ReportingFilterKey; label: string }[] = [
  { key: "segment", label: "Segment" },
  { key: "specialty", label: "Specialty" },
];

function Row({
  row, max, selected, onSelect,
}: {
  row: BreakdownRow;
  max: number;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <Box
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(); } }}
      sx={{
        display: "flex", alignItems: "center", gap: 1.25, cursor: "pointer",
        px: 0.75, py: 0.6, mx: -0.75, borderRadius: radius.sm,
        background: selected ? dataColor.info.soft : "transparent",
        transition: `background ${motion.duration.hover} ${motion.easeOut}`,
        [hoverOnly]: { "&:hover": { background: selected ? dataColor.info.soft : "#F7F9FC" } },
        "&:focus-visible": { outline: `2px solid ${dataColor.info.line}`, outlineOffset: 2 },
      }}
    >
      <Typography sx={{ fontSize: 15, flex: "0 0 44%", minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }} title={row.value}>
        {row.value}
      </Typography>
      <Box sx={{ flex: 1, height: 10, borderRadius: 5, background: "#F2F4F7", overflow: "hidden", minWidth: 40 }}>
        <Box sx={{
          width: `${(row.count / max) * 100}%`, height: "100%", borderRadius: 5,
          background: dataColor.info.line, transition: `width 620ms ${motion.easeOut}`,
        }} />
      </Box>
      <Typography sx={{ fontSize: 15, fontWeight: 700, width: 66, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
        {row.count.toLocaleString()}
      </Typography>
      <Typography sx={{ fontSize: 15, color: "text.secondary", width: 58, textAlign: "right", fontVariantNumeric: "tabular-nums" }}
                  title="Mean email affinity, 0–100">
        {Math.round(row.email_affinity * 100)}
      </Typography>
    </Box>
  );
}

export function AudienceCard({
  breakdowns, filters, onSelect,
}: {
  breakdowns: { segment: BreakdownRow[]; specialty: BreakdownRow[] };
  filters: Partial<Record<ReportingFilterKey, string>>;
  onSelect: (key: ReportingFilterKey, value: string) => void;
}) {
  const [tab, setTab] = useState<ReportingFilterKey>("segment");
  const rows = (tab === "segment" ? breakdowns.segment : breakdowns.specialty) ?? [];
  const max = Math.max(...rows.map((r) => r.count), 1);

  return (
    <DashCard sx={{ flex: "1 1 330px" }}>
      <CardTitle
        title="Audience composition"
        hint="Size and measured email affinity per group"
        action={
          <Box sx={{ display: "flex", gap: 0.5, background: "#F2F4F7", borderRadius: radius.sm, p: 0.25 }}>
            {TABS.map((t) => (
              <Box
                key={t.key}
                role="button"
                tabIndex={0}
                onClick={() => setTab(t.key)}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setTab(t.key); } }}
                sx={{
                  px: 1.25, py: 0.4, borderRadius: radius.sm, fontSize: 15, fontWeight: 700, cursor: "pointer",
                  background: tab === t.key ? tokens.color.surface : "transparent",
                  color: tab === t.key ? tokens.color.ink : tokens.color.inkSecondary,
                  boxShadow: tab === t.key ? "0 1px 3px rgba(16,24,40,0.14)" : "none",
                  transition: `background ${motion.duration.hover} ${motion.easeOut}, color ${motion.duration.hover} ${motion.easeOut}`,
                }}
              >
                {t.label}
              </Box>
            ))}
          </Box>
        }
      />
      <Box sx={{ display: "flex", flexDirection: "column", gap: 0.4 }}>
        {rows.map((row) => (
          <Row
            key={row.value}
            row={row}
            max={max}
            selected={filters[tab] === row.value}
            onSelect={() => onSelect(tab, row.value)}
          />
        ))}
      </Box>
      <Typography sx={{ fontSize: 15, color: "text.secondary", mt: 1.5 }}>
        Click a row to drill the dashboard into it. Right-hand number is mean email affinity (0–100).
      </Typography>
    </DashCard>
  );
}
