import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import LinearProgress from "@mui/material/LinearProgress";
import Typography from "@mui/material/Typography";
import { GlassPanel, PillChip } from "../glass/primitives";
import { tokens } from "../theme/tokens";
import type { Brand } from "../api";

/**
 * BrandPlate — a Tier-A glass card per portfolio brand: brand name, generic,
 * lifecycle chip, an "Activity" momentum bar (0–100, printed value so the read
 * never depends on the bar alone), metric pills, and a gradient plan CTA.
 *
 * Built on GlassPanel directly (not ConsolePanel/SectionCard, which wraps children in
 * its own inner Box — the flex/gap sx meant for these children was landing on that
 * wrapper's outer panel instead and never applying, leaving everything stacked with
 * only default margins).
 */
const LIFECYCLE_COLOR: Record<Brand["lifecycle_key"], "primary" | "success" | "secondary" | "warning"> = {
  launch: "primary",
  growth: "success",
  mature: "secondary",
  loe: "warning",
};

export function BrandPlate({ brand, onPlan }: { brand: Brand; onPlan: (name: string) => void }) {
  const momentum = Math.max(0, Math.min(100, brand.momentum));
  return (
    <GlassPanel tier="A" sx={{ p: 4, display: "flex", flexDirection: "column", gap: 2.5 }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 2 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h3" sx={{ fontSize: tokens.fontSize.xl, lineHeight: 1.2 }}>
            {brand.brand}
          </Typography>
          <Typography sx={{ fontSize: tokens.fontSize.sm, color: "text.secondary", mt: 0.25 }}>{brand.generic}</Typography>
        </Box>
        <Chip size="small" color={LIFECYCLE_COLOR[brand.lifecycle_key]} label={brand.lifecycle_label} sx={{ flex: "0 0 auto" }} />
      </Box>

      <Typography variant="body2" sx={{ color: "text.secondary" }}>
        {brand.therapy_area} · {brand.indications.length} indication{brand.indications.length === 1 ? "" : "s"}
      </Typography>

      <Box>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", mb: 0.75 }}>
          <Typography sx={{ fontSize: tokens.fontSize.xs, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: "text.secondary" }}>
            Activity
          </Typography>
          <Typography sx={{ fontSize: tokens.fontSize.sm, fontWeight: 700, color: "primary.main", fontVariantNumeric: "tabular-nums" }}>
            {momentum}/100
          </Typography>
        </Box>
        <LinearProgress variant="determinate" value={momentum} aria-label={`Activity ${momentum} of 100`} />
      </Box>

      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
        <PillChip label={`${brand.pubmed} papers`} />
        <PillChip label={`${brand.competitor_count} rivals`} />
        {brand.campaigns ? <PillChip label={`${brand.campaigns} plans`} /> : null}
      </Box>

      <Button variant="contained" color="primary" onClick={() => onPlan(brand.brand)}>
        Plan a campaign
      </Button>
    </GlassPanel>
  );
}
