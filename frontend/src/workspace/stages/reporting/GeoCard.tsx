/**
 * Performance by geography.
 *
 * Shade is the state's engagement index — its own HCPs' measured email affinity against the
 * panel mean — and the hover readout carries the count behind it, because a state with 9
 * HCPs and a state with 967 must never look equally authoritative. Clicking a state filters
 * the whole dashboard to it (a real drill-down: the cohort is re-counted server-side).
 */
import { useMemo, useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import { motion, tokens } from "../../../theme/tokens";
import { radius, CardTitle, DashCard, dataColor } from "./dashboardKit";
import type { GeoRow } from "../../types";

const US_STATES_GEO_URL = "https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json";

export function GeoCard({
  rows, activeState, onSelectState,
}: {
  rows: GeoRow[];
  activeState?: string;
  onSelectState: (stateCode: string) => void;
}) {
  const [hover, setHover] = useState<GeoRow | null>(null);
  const byName = useMemo(() => Object.fromEntries(rows.map((r) => [r.state, r])), [rows]);
  const indices = rows.map((r) => r.index);
  const min = Math.min(...indices, 100);
  const max = Math.max(...indices, 100);

  const fillFor = (row?: GeoRow) => {
    if (!row) return "#F2F4F7";
    const t = max === min ? 0.5 : (row.index - min) / (max - min);
    return `color-mix(in srgb, ${dataColor.info.line} ${Math.round(14 + 76 * t)}%, white)`;
  };

  const readout = hover ?? rows.find((r) => r.state_code === activeState) ?? null;

  return (
    <DashCard sx={{ flex: "1 1 320px" }}>
      <CardTitle title="Performance by geography" hint="Engagement index vs the panel mean" />

      <Box sx={{ minHeight: 40, mb: 0.5 }}>
        {readout ? (
          <Box sx={{ display: "flex", alignItems: "baseline", gap: 1.25, flexWrap: "wrap" }}>
            <Typography sx={{ fontSize: 17, fontWeight: 800 }}>{readout.state}</Typography>
            <Typography sx={{ fontSize: 15, color: "text.secondary" }}>
              {readout.hcps.toLocaleString()} HCPs · {readout.open_pct}% open · {readout.ctr_pct}% click
            </Typography>
            <Box sx={{
              fontSize: 15, fontWeight: 700, borderRadius: radius.sm, px: 0.75,
              color: readout.index >= 100 ? dataColor.positive.ink : dataColor.warning.ink,
              background: readout.index >= 100 ? dataColor.positive.soft : dataColor.warning.soft,
            }}>
              index {readout.index}
            </Box>
          </Box>
        ) : (
          <Typography sx={{ fontSize: 15, color: "text.secondary" }}>
            Hover a state for its cohort; click to filter the dashboard to it.
          </Typography>
        )}
      </Box>

      {/* d3's geoAlbersUsa is authored for a 960×500 frame at scale 1070; the scale below is
          that ratio applied to this frame, otherwise the projection overflows and the coasts
          get clipped. */}
      <ComposableMap
        projection="geoAlbersUsa"
        width={800}
        height={420}
        projectionConfig={{ scale: 890 }}
        style={{ width: "100%", height: "auto" }}
      >
        <Geographies geography={US_STATES_GEO_URL}>
          {({ geographies }) =>
            geographies.map((geo) => {
              const row = byName[geo.properties.name as string];
              const selected = row?.state_code && row.state_code === activeState;
              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  onMouseEnter={() => setHover(row ?? null)}
                  onMouseLeave={() => setHover(null)}
                  onClick={() => row && onSelectState(row.state_code)}
                  style={{
                    default: {
                      fill: fillFor(row),
                      stroke: selected ? tokens.color.ink : tokens.color.surface,
                      strokeWidth: selected ? 1.6 : 0.7,
                      outline: "none",
                      cursor: row ? "pointer" : "default",
                      transition: `fill ${motion.duration.hover} ${motion.easeOut}`,
                    },
                    hover: { fill: dataColor.info.line, stroke: tokens.color.surface, strokeWidth: 0.7, outline: "none", cursor: row ? "pointer" : "default" },
                    pressed: { fill: dataColor.info.ink, stroke: tokens.color.surface, strokeWidth: 0.7, outline: "none" },
                  }}
                />
              );
            })
          }
        </Geographies>
      </ComposableMap>

      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 1 }}>
        <Typography sx={{ fontSize: 15, color: "text.secondary" }}>Low</Typography>
        <Box sx={{
          flex: 1, height: 8, borderRadius: 4,
          background: `linear-gradient(90deg, color-mix(in srgb, ${dataColor.info.line} 14%, white), ${dataColor.info.line})`,
        }} />
        <Typography sx={{ fontSize: 15, color: "text.secondary" }}>High</Typography>
      </Box>
    </DashCard>
  );
}
