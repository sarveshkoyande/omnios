import { styled } from "@mui/material/styles";
import { tokens, shade, light } from "../theme/tokens";

/**
 * StatOdometer — mechanical tally counter: a dark recessed window with stamped
 * digits, label engraved into the desk below it. Digits use the text token as a
 * surface (#111827) with surface-token digits: 17.9:1 contrast.
 */
const Well = styled("div")(({ theme }) => ({
  display: "inline-flex",
  flexDirection: "column",
  alignItems: "center",
  gap: theme.spacing(1),
}));

const Window = styled("div")(({ theme }) => ({
  minWidth: theme.spacing(24) /* 3 × 32 on the 4px scale */,
  padding: theme.spacing(2, 3),
  textAlign: "center",
  background: `linear-gradient(180deg, ${shade(0.95)}, ${tokens.color.text} 40%)`,
  color: tokens.color.surface,
  fontFamily: tokens.font.mono,
  fontSize: tokens.fontSize.xl,
  fontWeight: 700,
  fontVariantNumeric: "tabular-nums",
  borderRadius: tokens.radius.sm,
  border: `1px solid ${shade(0.6)}`,
  boxShadow: `inset 0 2px 6px rgba(0,0,0,0.55), inset 0 -1px 0 ${light(0.12)}, 0 1px 0 ${light(0.9)}`,
}));

const Label = styled("div")({
  fontFamily: tokens.font.mono,
  fontSize: tokens.fontSize.xs,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: shade(0.62),
  textShadow: `0 1px 0 ${light(0.9)}`,
});

export function StatOdometer({ value, label, alert }: { value: number | string; label: string; alert?: boolean }) {
  return (
    <Well>
      <Window style={alert ? { color: tokens.color.secondary } : undefined}>{value}</Window>
      <Label>{label}</Label>
    </Well>
  );
}
