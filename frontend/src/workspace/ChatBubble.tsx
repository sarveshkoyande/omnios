import { keyframes } from "@emotion/react";
import { styled } from "@mui/material/styles";
// Aliased: TurnBubble below takes a styled-prop literally named `accent`, which would shadow
// this import inside that callback.
import { accent as stageAccent } from "../theme/stageTheme";
import { tokens, motion } from "../theme/tokens";

/** AgentBubble — a flat white surface with the stage agent's accent bar down its left edge. */
export const AgentBubble = styled("div")(({ theme }) => ({
  position: "relative",
  width: "fit-content",
  maxWidth: "90%",
  minWidth: 0,
  padding: theme.spacing(1, 1.5),
  borderRadius: tokens.radius.md,
  // See TurnBubble: the chat pane is white, so bubbles take the canvas grey.
  background: tokens.color.canvas,
  border: `1px solid ${tokens.color.outline}`,
  borderLeft: `4px solid ${stageAccent.primary}`,
  boxShadow: "none",
  color: tokens.color.text,
  fontSize: 15,
  lineHeight: 1.6,
  overflowWrap: "break-word",
  wordBreak: "break-word",
}));

/** UserBubble — solid brand card, white text, right-aligned. */
export const UserBubble = styled("div")(({ theme }) => ({
  width: "fit-content",
  maxWidth: "90%",
  marginLeft: "auto",
  padding: theme.spacing(1, 1.5),
  borderTopRightRadius: 4,
  borderRadius: tokens.radius.md,
  background: stageAccent.primary,
  color: "#fff",
  boxShadow: "none",
  fontSize: 15,
  lineHeight: 1.6,
  overflowWrap: "break-word",
  wordBreak: "break-word",
}));

/** NarrationLine — quiet dashed aside for scene-setting text. */
export const NarrationLine = styled("div")(({ theme }) => ({
  maxWidth: 640,
  padding: theme.spacing(2, 0),
  borderTop: `1px dashed ${tokens.color.outline}`,
  borderBottom: `1px dashed ${tokens.color.outline}`,
  color: tokens.color.inkSoft,
  fontStyle: "italic",
  fontSize: 15,
}));

/** TurnBubble — a teammate's turn: flat panel with a left accent edge. */
export const TurnBubble = styled("div")<{ accent: string }>(({ theme, accent }) => ({
  position: "relative",
  width: "fit-content",
  maxWidth: "90%",
  minWidth: 0,
  padding: theme.spacing(1, 1.5),
  borderRadius: tokens.radius.md,
  // Canvas grey, not white: the chat pane itself is white now, so a white bubble would be
  // invisible apart from its outline.
  background: tokens.color.canvas,
  border: `1px solid ${tokens.color.outline}`,
  borderLeft: `4px solid ${accent}`,
  boxShadow: "none",
  color: tokens.color.text,
  fontSize: 15,
  lineHeight: 1.6,
  overflowWrap: "break-word",
  wordBreak: "break-word",
}));

/** StatusLine — quiet ambient activity, not a message from anyone: the single agent's
 * internal work-steps get this instead of a peer bubble, so it never reads as a second
 * conversational identity. A soft pulsing dot + small italic caption, no avatar, no box. */
const dotPulse = keyframes`
  0%, 100% { opacity: 0.35; }
  50% { opacity: 1; }
`;

const statusIn = keyframes`
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
`;

export const StatusLine = styled("div")(({ theme }) => ({
  display: "flex",
  alignItems: "center",
  gap: theme.spacing(1),
  marginLeft: theme.spacing(7),
  color: tokens.color.inkSoft,
  fontSize: tokens.fontSize.sm,
  fontStyle: "italic",
  animation: `${statusIn} ${motion.duration.enter} ${motion.easeOut}`,
  "&::before": {
    content: '""',
    width: 6,
    height: 6,
    borderRadius: "50%",
    flex: "0 0 auto",
    background: tokens.color.secondary,
    animation: `${dotPulse} 1.6s ease-in-out infinite`,
  },
}));

export const ClarifyBadge = styled("span")({
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  fontSize: tokens.fontSize.xs,
  fontWeight: 700,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
  color: stageAccent.primary,
  background: stageAccent.container,
  border: `1px solid ${tokens.color.outline}`,
  borderRadius: tokens.radius.pill,
  padding: "3px 11px",
});
