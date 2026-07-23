import { keyframes } from "@emotion/react";
import { styled } from "@mui/material/styles";
import { tokens } from "../theme/tokens";

/** AgentBubble — a flat solid surface with a small primary accent dot. */
export const AgentBubble = styled("div")(({ theme }) => ({
  position: "relative",
  width: "fit-content",
  maxWidth: "90%",
  minWidth: 0,
  padding: theme.spacing(2.5, 3.5),
  borderTopLeftRadius: 4,
  borderRadius: tokens.radius.md,
  background: tokens.color.surface,
  border: `1px solid ${tokens.color.outline}`,
  boxShadow: "none",
  color: tokens.color.text,
  fontSize: 13,
  lineHeight: 1.6,
  overflowWrap: "break-word",
  wordBreak: "break-word",
  "&::before": {
    content: '""',
    position: "absolute",
    top: -4,
    left: 16,
    width: 8,
    height: 8,
    borderRadius: "50%",
    background: tokens.color.primary,
  },
}));

/** UserBubble — solid brand card, white text, right-aligned. */
export const UserBubble = styled("div")(({ theme }) => ({
  width: "fit-content",
  maxWidth: "90%",
  marginLeft: "auto",
  padding: theme.spacing(2.5, 3.5),
  borderTopRightRadius: 4,
  borderRadius: tokens.radius.md,
  background: tokens.color.primary,
  color: "#fff",
  boxShadow: "none",
  fontSize: 13,
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
  fontSize: 13,
}));

/** TurnBubble — a teammate's turn: flat panel with a left accent edge. */
export const TurnBubble = styled("div")<{ accent: string }>(({ theme, accent }) => ({
  position: "relative",
  width: "fit-content",
  maxWidth: "90%",
  minWidth: 0,
  padding: theme.spacing(2.5, 3.5),
  borderRadius: tokens.radius.md,
  background: tokens.color.surface,
  border: `1px solid ${tokens.color.outline}`,
  borderLeft: `4px solid ${accent}`,
  boxShadow: "none",
  color: tokens.color.text,
  fontSize: 13,
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
  animation: `${statusIn} 320ms ease`,
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
  color: tokens.color.primary,
  background: tokens.color.primaryContainer,
  border: `1px solid ${tokens.color.outline}`,
  borderRadius: tokens.radius.pill,
  padding: "3px 11px",
});
