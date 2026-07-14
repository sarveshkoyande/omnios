import Button from "@mui/material/Button";
import { styled } from "@mui/material/styles";
import { tokens } from "../theme/tokens";

/**
 * TactileButton — the hero call-to-action. The theme already gives every
 * MuiButton its gradient/glass treatment; this styled() wrapper is the *large*
 * primary key: taller cap and a sublabel slot. (Reusable wrapper -> styled()
 * layer, not theme, per the MUI skill: only some buttons are hero keys.)
 */
export const TactileButton = styled(Button)(({ theme }) => ({
  padding: theme.spacing(2.5, 6),
  fontSize: tokens.fontSize.md,
  borderRadius: tokens.radius.md,
}));

/** Sublabel slot inside a TactileButton (white on the gradient face). */
export const KeycapSublabel = styled("span")({
  display: "block",
  fontSize: tokens.fontSize.xs,
  fontWeight: 500,
  letterSpacing: "0.06em",
  opacity: 0.85,
  textTransform: "none",
  marginTop: 2,
});
