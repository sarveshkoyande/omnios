import Button from "@mui/material/Button";
import { styled } from "@mui/material/styles";
import { tokens, shade, light } from "../theme/tokens";

/**
 * TactileButton — the hero keycap. The theme already gives every MuiButton key
 * travel; this styled() wrapper is the *large* enamel key reserved for primary
 * calls-to-action: taller cap, ridge line under the legend, mono sublabel slot.
 * (Reusable wrapper -> styled() layer, not theme, per the MUI skill: only some
 * buttons are hero keys.)
 */
export const TactileButton = styled(Button)(({ theme }) => ({
  padding: theme.spacing(3, 6),
  fontSize: tokens.fontSize.md,
  borderRadius: tokens.radius.md,
  // Keycap ridge: a second bevel line under the face so the cap reads molded.
  "&::after": {
    content: '""',
    position: "absolute",
    left: theme.spacing(2),
    right: theme.spacing(2),
    bottom: theme.spacing(1),
    height: 1,
    background: light(0.55),
    boxShadow: `0 -1px 0 ${shade(0.18)}`,
    pointerEvents: "none",
  },
  "&:active::after": { opacity: 0.4 },
}));

/** Mono machine-stamped sublabel for use inside a TactileButton. */
export const KeycapSublabel = styled("span")({
  display: "block",
  fontFamily: tokens.font.mono,
  fontSize: tokens.fontSize.xs,
  fontWeight: 400,
  letterSpacing: "0.06em",
  opacity: 0.75,
  textTransform: "none",
});
