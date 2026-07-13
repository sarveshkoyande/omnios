import { keyframes } from "@emotion/react";
import { styled } from "@mui/material/styles";
import { tokens, shade } from "../theme/tokens";

const blink = keyframes`
  0%, 60%, 100% { opacity: 0.3; }
  30% { opacity: 1; }
`;

const Dot = styled("span")<{ delay: number }>(({ delay }) => ({
  width: 6,
  height: 6,
  borderRadius: "50%",
  background: shade(0.5),
  display: "inline-block",
  animation: `${blink} 1.3s infinite`,
  animationDelay: `${delay}s`,
}));

export function TypingDots() {
  return (
    <span style={{ display: "inline-flex", gap: 4, alignItems: "center", padding: `${tokens.spacingUnit}px 0` }}>
      <Dot delay={0} />
      <Dot delay={0.2} />
      <Dot delay={0.4} />
    </span>
  );
}
