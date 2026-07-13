import { styled } from "@mui/material/styles";
import { tokens, shade, light, panelShadow, insetShadow } from "../theme/tokens";

/**
 * AgentBubble — a paper memo slip pinned to the desk: card stock, slight
 * rotation-free "pinned" corner accent, torn-off left edge via a dashed groove.
 */
export const AgentBubble = styled("div")(({ theme }) => ({
  position: "relative",
  maxWidth: 640,
  padding: theme.spacing(3, 4),
  borderTopLeftRadius: 2,
  borderRadius: tokens.radius.md,
  background: `${tokens.color.surface}`,
  border: `1px solid ${shade(0.16)}`,
  boxShadow: panelShadow,
  fontSize: tokens.fontSize.sm,
  lineHeight: 1.6,
  "&::before": {
    // Binder-pin accent, top-left.
    content: '""',
    position: "absolute",
    top: -4,
    left: 14,
    width: 8,
    height: 8,
    borderRadius: "50%",
    background: `radial-gradient(circle at 35% 30%, ${light(0.9)}, ${tokens.color.primary} 60%, ${shade(0.3)})`,
    boxShadow: `0 1px 2px ${shade(0.3)}`,
  },
}));

/** UserBubble — a stamped enamel ticket stub, right-aligned. */
export const UserBubble = styled("div")(({ theme }) => ({
  maxWidth: 640,
  marginLeft: "auto",
  padding: theme.spacing(3, 4),
  borderTopRightRadius: 2,
  borderRadius: tokens.radius.md,
  background: `linear-gradient(180deg, ${light(0.22)}, ${light(0)} 45%), ${tokens.color.primary}`,
  color: tokens.color.text,
  boxShadow: panelShadow,
  fontSize: tokens.fontSize.sm,
  lineHeight: 1.6,
}));

/** NarrationLine — a dashed-rule aside, no plate: quieter voice for scene-setting text. */
export const NarrationLine = styled("div")(({ theme }) => ({
  maxWidth: 640,
  padding: theme.spacing(2, 0),
  borderTop: `1px dashed ${shade(0.2)}`,
  borderBottom: `1px dashed ${shade(0.2)}`,
  color: shade(0.62),
  fontStyle: "italic",
  fontSize: tokens.fontSize.sm,
}));

/** TurnBubble — a teammate's sticky note: colored accent tab matching their portrait ring. */
export const TurnBubble = styled("div")<{ accent: string }>(({ theme, accent }) => ({
  position: "relative",
  maxWidth: 640,
  padding: theme.spacing(3, 4),
  borderRadius: tokens.radius.md,
  background: tokens.color.surface,
  border: `1px solid ${shade(0.16)}`,
  borderLeft: `4px solid ${accent}`,
  boxShadow: panelShadow,
  fontSize: tokens.fontSize.sm,
  lineHeight: 1.6,
}));

/** BanterBubble — a quiet side-remark: recessed, smaller, indented under the main turn. */
export const BanterBubble = styled("div")<{ accent: string }>(({ theme, accent }) => ({
  maxWidth: 460,
  marginLeft: theme.spacing(9),
  padding: theme.spacing(1.5, 3),
  borderRadius: 999,
  background: shade(0.05),
  boxShadow: insetShadow,
  fontSize: tokens.fontSize.xs,
  color: shade(0.7),
  "& b": { color: accent },
}));

export const ClarifyBadge = styled("span")({
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  fontFamily: tokens.font.mono,
  fontSize: tokens.fontSize.xs,
  fontWeight: 700,
  color: tokens.color.text,
  background: `linear-gradient(180deg, ${light(0.5)}, ${light(0)}), ${tokens.color.secondary}`,
  border: `1px solid ${shade(0.3)}`,
  borderRadius: 999,
  padding: "2px 10px",
});
