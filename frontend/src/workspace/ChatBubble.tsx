import { styled } from "@mui/material/styles";
import { tokens, glass, glassFallback, indigoTint, gradientBrand } from "../theme/tokens";

const glassSupports = "@supports ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px)))";

/** AgentBubble — a Tier-A milk-glass panel with a small indigo accent dot. */
export const AgentBubble = styled("div")(({ theme }) => ({
  position: "relative",
  maxWidth: 640,
  padding: theme.spacing(2.5, 3.5),
  borderTopLeftRadius: 4,
  borderRadius: tokens.radius.md,
  background: glassFallback,
  border: glass.border,
  boxShadow: glass.shadow,
  color: tokens.color.text,
  fontSize: tokens.fontSize.md,
  lineHeight: 1.6,
  [glassSupports]: { background: glass.panel, backdropFilter: glass.blur, WebkitBackdropFilter: glass.blur },
  "&::before": {
    content: '""',
    position: "absolute",
    top: -4,
    left: 16,
    width: 8,
    height: 8,
    borderRadius: "50%",
    background: gradientBrand,
    boxShadow: "0 1px 3px rgba(79,70,229,0.4)",
  },
}));

/** UserBubble — brand-gradient, white text, right-aligned. */
export const UserBubble = styled("div")(({ theme }) => ({
  maxWidth: 640,
  marginLeft: "auto",
  padding: theme.spacing(2.5, 3.5),
  borderTopRightRadius: 4,
  borderRadius: tokens.radius.md,
  background: gradientBrand,
  color: "#fff",
  boxShadow: "0 6px 20px rgba(79,70,229,0.28)",
  fontSize: tokens.fontSize.md,
  lineHeight: 1.6,
}));

/** NarrationLine — quiet dashed aside for scene-setting text. */
export const NarrationLine = styled("div")(({ theme }) => ({
  maxWidth: 640,
  padding: theme.spacing(2, 0),
  borderTop: `1px dashed ${indigoTint(0.2)}`,
  borderBottom: `1px dashed ${indigoTint(0.2)}`,
  color: tokens.color.inkSoft,
  fontStyle: "italic",
  fontSize: tokens.fontSize.md,
}));

/** TurnBubble — a teammate's turn: glass panel with an accent left edge. */
export const TurnBubble = styled("div")<{ accent: string }>(({ theme, accent }) => ({
  position: "relative",
  maxWidth: 640,
  padding: theme.spacing(2.5, 3.5),
  borderRadius: tokens.radius.md,
  background: glassFallback,
  border: glass.border,
  borderLeft: `4px solid ${accent}`,
  boxShadow: glass.shadow,
  color: tokens.color.text,
  fontSize: tokens.fontSize.md,
  lineHeight: 1.6,
  [glassSupports]: { background: glass.panel, backdropFilter: glass.blur, WebkitBackdropFilter: glass.blur },
}));

/** BanterBubble — a recessed translucent side-remark, indented. */
export const BanterBubble = styled("div")<{ accent: string }>(({ theme, accent }) => ({
  maxWidth: 460,
  marginLeft: theme.spacing(9),
  padding: theme.spacing(1.5, 3),
  borderRadius: tokens.radius.pill,
  background: "rgba(255,255,255,0.45)",
  border: `1px solid ${indigoTint(0.1)}`,
  fontSize: tokens.fontSize.sm,
  color: tokens.color.inkSoft,
  "& b": { color: accent },
}));

export const ClarifyBadge = styled("span")({
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  fontSize: tokens.fontSize.xs,
  fontWeight: 700,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
  color: tokens.color.primary,
  background: indigoTint(0.1),
  border: glass.borderTint,
  borderRadius: tokens.radius.pill,
  padding: "3px 11px",
});
