import { keyframes } from "@emotion/react";
import { styled } from "@mui/material/styles";
import { tokens } from "./tokens";

/**
 * Atmosphere — the fixed, full-viewport pale field the milk-glass panels read
 * against (never place panels over flat white). Two large, heavily-blurred mist
 * blobs drift imperceptibly (≥60s, transform/opacity only). Decorative and
 * inert to a11y (aria-hidden); frozen under prefers-reduced-motion.
 */
const driftA = keyframes`
  0%   { transform: translate3d(0, 0, 0) scale(1); }
  50%  { transform: translate3d(4vw, 3vh, 0) scale(1.08); }
  100% { transform: translate3d(0, 0, 0) scale(1); }
`;
const driftB = keyframes`
  0%   { transform: translate3d(0, 0, 0) scale(1.05); }
  50%  { transform: translate3d(-5vw, -2vh, 0) scale(1); }
  100% { transform: translate3d(0, 0, 0) scale(1.05); }
`;

const Field = styled("div")({
  position: "fixed",
  inset: 0,
  zIndex: 0,
  overflow: "hidden",
  pointerEvents: "none",
  background: tokens.color.bgBase,
});

const Blob = styled("div")<{ variant: "a" | "b" }>(({ variant }) => ({
  position: "absolute",
  borderRadius: "50%",
  filter: "blur(120px)",
  willChange: "transform",
  ...(variant === "a"
    ? {
        width: "62vw",
        height: "62vw",
        top: "-18vw",
        left: "-12vw",
        background: tokens.color.bgMist1,
        opacity: 0.75,
        animation: `${driftA} 72s ease-in-out infinite`,
      }
    : {
        width: "56vw",
        height: "56vw",
        bottom: "-20vw",
        right: "-10vw",
        background: tokens.color.bgMist2,
        opacity: 0.8,
        animation: `${driftB} 84s ease-in-out infinite`,
      }),
  "@media (prefers-reduced-motion: reduce)": { animation: "none" },
}));

export function Atmosphere() {
  return (
    <Field aria-hidden="true">
      <Blob variant="a" />
      <Blob variant="b" />
    </Field>
  );
}
