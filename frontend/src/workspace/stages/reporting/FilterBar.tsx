/**
 * Dashboard filter bar.
 *
 * Each drop-down is a real drill-down: the value goes to the server, the HCP 360 cohort is
 * re-counted under it, and every card on the page re-derives from that smaller population.
 * Option counts come back with the facets and are computed with the *other* filters already
 * applied, so the bar can never offer a combination that returns an empty cohort.
 */
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Typography from "@mui/material/Typography";
import { tokens } from "../../../theme/tokens";
import { radius, dataColor } from "./dashboardKit";
import type { FacetValue, ReportingFilterKey, ReportingFilters, ReportingInsights } from "../../types";

const TIME_WINDOWS = [3, 6, 12, 24];

const DIMENSIONS: { key: ReportingFilterKey; label: string; all: string; width: number }[] = [
  { key: "specialty", label: "Specialty", all: "All", width: 208 },
  { key: "segment", label: "Segment", all: "All", width: 208 },
  { key: "channel", label: "Channel", all: "All", width: 168 },
  { key: "state", label: "State", all: "All", width: 132 },
  { key: "brand", label: "Brand", all: "Any", width: 156 },
];

/** The label lives inside the control rather than above it: this bar is sticky, and a second
 *  line of labels costs the same vertical space on every screen of the dashboard. */
const selectSx = {
  fontSize: 15,
  height: 38,
  background: tokens.color.surface,
  "& .MuiOutlinedInput-notchedOutline": { borderColor: tokens.color.outline },
  "& .MuiSelect-select": { display: "flex", alignItems: "center", gap: 0.5, py: 0.5 },
};

function ControlLabel({ text }: { text: string }) {
  return (
    <Typography component="span" sx={{ fontSize: 15, color: "text.secondary", fontWeight: 700, mr: 0.5 }}>
      {text}
    </Typography>
  );
}

export function FilterBar({
  insights,
  filters,
  months,
  busy,
  onChange,
  onMonthsChange,
  onReset,
}: {
  insights: ReportingInsights | null;
  filters: ReportingFilters;
  months: number;
  busy: boolean;
  onChange: (key: ReportingFilterKey, value: string) => void;
  onMonthsChange: (months: number) => void;
  onReset: () => void;
}) {
  const facets = insights?.filters?.facets;
  const grounding = insights?.grounding;
  const activeCount = Object.values(filters).filter(Boolean).length;

  const options = (key: ReportingFilterKey): FacetValue[] => facets?.[key] ?? [];

  return (
    <Box
      sx={{
        position: "sticky", top: 0, zIndex: 3,
        display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap",
        background: tokens.color.surface,
        border: `1px solid ${tokens.color.outline}`,
        borderRadius: radius.md,
        px: 1.5, py: 1.25, mb: 2,
        boxShadow: "0 1px 2px rgba(16,24,40,0.04)",
      }}
    >
      <Select
        size="small"
        value={months}
        onChange={(e) => onMonthsChange(Number(e.target.value))}
        renderValue={(v) => <><ControlLabel text="Period" />Last {v} months</>}
        sx={{ ...selectSx, minWidth: 178 }}
      >
        {TIME_WINDOWS.map((m) => (
          <MenuItem key={m} value={m} sx={{ fontSize: 15 }}>Last {m} months</MenuItem>
        ))}
      </Select>

      {DIMENSIONS.map((dim) => (
        <Select
          key={dim.key}
          size="small"
          displayEmpty
          value={filters[dim.key] ?? ""}
          onChange={(e) => onChange(dim.key, e.target.value)}
          renderValue={(v) => (
            <>
              <ControlLabel text={dim.label} />
              <Box component="span" sx={{
                minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                fontWeight: v ? 700 : 400,
              }}>
                {v || dim.all}
              </Box>
            </>
          )}
          sx={{ ...selectSx, minWidth: dim.width, maxWidth: dim.width }}
          MenuProps={{ slotProps: { paper: { sx: { maxHeight: 380 } } } }}
        >
          <MenuItem value="" sx={{ fontSize: 15 }}>{dim.all}</MenuItem>
          {options(dim.key).map((o) => (
            <MenuItem key={o.value} value={o.value} sx={{ fontSize: 15, display: "flex", gap: 1.5 }}>
              <Box component="span" sx={{ flex: 1 }}>{o.value}</Box>
              <Box component="span" sx={{ color: "text.secondary", fontVariantNumeric: "tabular-nums" }}>
                {o.count.toLocaleString()}
              </Box>
            </MenuItem>
          ))}
        </Select>
      ))}

      <Box sx={{ flex: 1 }} />

      {/* Cohort readout: the population every number on the page is counted over. */}
      {grounding && (
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Box
            sx={{
              display: "inline-flex", alignItems: "center", gap: 0.75,
              background: dataColor.info.soft, color: dataColor.info.ink,
              borderRadius: radius.sm, px: 1.25, py: 0.5,
              fontSize: 15, fontWeight: 700,
              opacity: busy ? 0.55 : 1,
              transition: "opacity 160ms ease",
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 17 }}>groups</span>
            {grounding.cohort_size.toLocaleString()} HCPs
            <Box component="span" sx={{ fontWeight: 400, opacity: 0.85 }}>
              / {grounding.panel_size.toLocaleString()} panel
            </Box>
          </Box>
          {activeCount > 0 && (
            <Button size="small" onClick={onReset} sx={{ fontSize: 15, textTransform: "none" }}>
              Clear {activeCount} filter{activeCount > 1 ? "s" : ""}
            </Button>
          )}
        </Box>
      )}
    </Box>
  );
}
