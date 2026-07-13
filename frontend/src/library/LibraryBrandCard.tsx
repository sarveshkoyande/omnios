import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import LinearProgress from "@mui/material/LinearProgress";
import Typography from "@mui/material/Typography";
import { ConsolePanel } from "../components/ConsolePanel";
import { tokens } from "../theme/tokens";
import type { LibraryBrandSummary } from "./types";

const LIFECYCLE_COLOR: Record<string, "primary" | "success" | "secondary" | "warning"> = {
  launch: "primary",
  growth: "success",
  mature: "secondary",
  loe: "warning",
};

export function LibraryBrandCard({ brand, onOpen }: { brand: LibraryBrandSummary; onOpen: (name: string) => void }) {
  const pct = brand.claims ? Math.round((brand.approved / brand.claims) * 100) : 0;
  return (
    <ConsolePanel sx={{ display: "flex", flexDirection: "column", gap: 2, cursor: "pointer" }} onClick={() => onOpen(brand.brand)}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 2 }}>
        <Box>
          <Typography variant="h3" sx={{ fontSize: tokens.fontSize.lg }}>{brand.brand}</Typography>
          <Typography sx={{ fontFamily: tokens.font.mono, fontSize: tokens.fontSize.xs, color: "text.secondary" }}>
            {brand.generic_name}
          </Typography>
        </Box>
        {brand.lifecycle_key && (
          <Chip size="small" color={LIFECYCLE_COLOR[brand.lifecycle_key] ?? "primary"} label={brand.lifecycle_key} />
        )}
      </Box>

      <Typography variant="body2" sx={{ color: "text.secondary" }}>{brand.therapy_area}</Typography>

      <Box>
        <Box sx={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "text.secondary", mb: 0.5 }}>
          <span>MLR-approved claims</span>
          <span>{brand.approved}/{brand.claims}</span>
        </Box>
        <LinearProgress variant="determinate" value={pct} color="success" />
      </Box>

      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
        <Chip size="small" variant="outlined" label={`${brand.claims} claims`} />
        <Chip size="small" variant="outlined" label={`${brand.references} refs`} />
        <Chip size="small" variant="outlined" label={`${brand.modules} modules`} />
        <Chip size="small" variant="outlined" label={`${brand.images} images`} />
      </Box>

      <Button variant="contained" color="primary" onClick={() => onOpen(brand.brand)}>
        Review content
      </Button>
    </ConsolePanel>
  );
}
