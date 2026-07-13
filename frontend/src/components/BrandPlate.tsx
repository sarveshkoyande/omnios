import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { ConsolePanel } from "./ConsolePanel";
import { GaugeMeter } from "./GaugeMeter";
import { tokens, shade, light } from "../theme/tokens";
import type { Brand } from "../api";

/**
 * BrandPlate — an engraved brass nameplate mounted on a console panel: display-
 * face brand name, mono generic beneath, lifecycle as an enamel pin badge, the
 * momentum score as an analog gauge, and metrics as stamped tags.
 */
const Nameplate = styled("div")(({ theme }) => ({
  padding: theme.spacing(2, 3),
  borderRadius: tokens.radius.sm,
  border: `1px solid ${shade(0.2)}`,
  background: `linear-gradient(180deg, ${light(0.7)}, ${shade(0.06)}), ${tokens.color.surface}`,
  boxShadow: `inset 0 1px 0 ${light(0.9)}, 0 1px 2px ${shade(0.12)}`,
}));

const StampedTag = styled("span")(({ theme }) => ({
  display: "inline-flex",
  alignItems: "center",
  gap: theme.spacing(1),
  padding: theme.spacing(1, 2),
  fontFamily: tokens.font.mono,
  fontSize: tokens.fontSize.xs,
  color: shade(0.7),
  border: `1px solid ${shade(0.2)}`,
  borderRadius: tokens.radius.sm,
  boxShadow: `inset 0 1px 2px ${shade(0.1)}, 0 1px 0 ${light(0.9)}`,
}));

const LIFECYCLE_COLOR: Record<Brand["lifecycle_key"], "primary" | "success" | "secondary" | "warning"> = {
  launch: "primary",
  growth: "success",
  mature: "secondary",
  loe: "warning",
};

export function BrandPlate({ brand, onPlan }: { brand: Brand; onPlan: (name: string) => void }) {
  return (
    <ConsolePanel sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 2 }}>
        <Nameplate sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="h2" component="h3" sx={{ fontSize: tokens.fontSize.lg, lineHeight: 1.2 }}>
            {brand.brand}
          </Typography>
          <Typography sx={{ fontFamily: tokens.font.mono, fontSize: tokens.fontSize.xs, color: "text.secondary" }}>
            {brand.generic}
          </Typography>
        </Nameplate>
        <Chip size="small" color={LIFECYCLE_COLOR[brand.lifecycle_key]} label={brand.lifecycle_label} />
      </Box>

      <Typography variant="body2" sx={{ color: "text.secondary" }}>
        {brand.therapy_area} · {brand.indications.length} indication{brand.indications.length === 1 ? "" : "s"}
      </Typography>

      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 3, flexWrap: "wrap" }}>
        <GaugeMeter value={brand.momentum} label="Activity" />
        <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
          <StampedTag>{brand.trials_recruiting}/{brand.trials_total} trials</StampedTag>
          <StampedTag>{brand.pubmed} papers</StampedTag>
          <StampedTag>{brand.competitor_count} rivals</StampedTag>
          {brand.campaigns ? <StampedTag>{brand.campaigns} plans</StampedTag> : null}
        </Box>
      </Box>

      <Button variant="contained" color="primary" onClick={() => onPlan(brand.brand)}>
        Plan a campaign
      </Button>
    </ConsolePanel>
  );
}
