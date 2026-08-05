import { keyframes } from "@emotion/react";
import { styled } from "@mui/material/styles";
import { tokens, shade } from "../theme/tokens";

/**
 * A wave, not a blink: each dot lifts and brightens as the pulse passes through it. Opacity
 * alone made three dots that happened to flicker; the 2px lift is what makes them read as one
 * moving thing. Faster than it looks necessary (1.05s for the full cycle) because a quicker
 * loading indicator makes the wait itself feel shorter, at no cost to legibility.
 */
const pulse = keyframes`
  0%, 65%, 100% { opacity: 0.28; transform: translateY(0) scale(0.88); }
  30% { opacity: 1; transform: translateY(-2px) scale(1); }
`;

const Dot = styled("span")<{ delay: number }>(({ delay }) => ({
  width: 6,
  height: 6,
  borderRadius: "50%",
  background: shade(0.5),
  display: "inline-block",
  willChange: "transform, opacity",
  animation: `${pulse} 1.05s cubic-bezier(0.4, 0, 0.2, 1) infinite`,
  animationDelay: `${delay}s`,
}));

export function TypingDots() {
  return (
    <span style={{ display: "inline-flex", gap: 4, alignItems: "center", padding: `${tokens.spacingUnit}px 0` }}>
      <Dot delay={0} />
      <Dot delay={0.12} />
      <Dot delay={0.24} />
    </span>
  );
}
