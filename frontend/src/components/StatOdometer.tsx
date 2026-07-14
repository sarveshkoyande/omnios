import Typography from "@mui/material/Typography";
import { GlassPanel } from "../glass/primitives";
import { tokens } from "../theme/tokens";

/**
 * StatOdometer — retained name/API (Home + Library import it). Now a Tier-A
 * glass stat card: a large indigo figure over a small-caps label. `alert`
 * turns the figure danger-red for at-a-glance risk (e.g. unsubstantiated claims).
 */
export function StatOdometer({ value, label, alert }: { value: number | string; label: string; alert?: boolean }) {
  return (
    <GlassPanel
      tier="A"
      sx={{ flex: "1 1 0", minWidth: 128, px: 3, py: 2.5, display: "flex", flexDirection: "column", gap: 0.5 }}
    >
      <Typography
        sx={{
          fontSize: 30,
          fontWeight: 700,
          lineHeight: 1,
          fontVariantNumeric: "tabular-nums",
          color: alert ? tokens.color.danger : tokens.color.primary,
        }}
      >
        {value}
      </Typography>
      <Typography
        sx={{ fontSize: tokens.fontSize.xs, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: "text.secondary" }}
      >
        {label}
      </Typography>
    </GlassPanel>
  );
}
