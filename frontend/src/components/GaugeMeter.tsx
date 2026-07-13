import { styled } from "@mui/material/styles";
import { tokens, shade, light } from "../theme/tokens";

/**
 * GaugeMeter — an analog VU-style meter for a 0–100 score: recessed dial face,
 * printed tick marks, enamel needle, machined hub screw. The number is also
 * printed below the dial so the reading never depends on needle angle alone.
 */
const Face = styled("div")({
  position: "relative",
  display: "inline-flex",
  flexDirection: "column",
  alignItems: "center",
});

const Readout = styled("div")({
  fontFamily: tokens.font.mono,
  fontSize: tokens.fontSize.xs,
  fontWeight: 700,
  color: shade(0.62),
  textShadow: `0 1px 0 ${light(0.9)}`,
});

export function GaugeMeter({ value, label }: { value: number; label: string }) {
  const pct = Math.max(0, Math.min(100, value));
  const angle = -90 + (pct / 100) * 180;
  const ticks = Array.from({ length: 11 }, (_, i) => -90 + i * 18);
  return (
    <Face>
      <svg width="92" height="54" viewBox="0 0 92 54" role="img" aria-label={`${label}: ${pct} out of 100`}>
        {/* Recessed dial face */}
        <path d="M6 50 A40 40 0 0 1 86 50" fill="none" stroke={shade(0.12)} strokeWidth="10" strokeLinecap="round" />
        <path d="M6 50 A40 40 0 0 1 86 50" fill="none" stroke={light(0.85)} strokeWidth="1" transform="translate(0 1.5)" />
        {/* Printed ticks */}
        {ticks.map((t) => (
          <line
            key={t}
            x1="46" y1="14" x2="46" y2="18"
            stroke={shade(0.45)} strokeWidth={t % 90 === 0 ? 2 : 1}
            transform={`rotate(${t} 46 50)`}
          />
        ))}
        {/* Enamel needle */}
        <line
          x1="46" y1="50" x2="46" y2="16"
          stroke={tokens.color.primary} strokeWidth="2.5" strokeLinecap="round"
          transform={`rotate(${angle} 46 50)`}
        />
        {/* Hub screw */}
        <circle cx="46" cy="50" r="5" fill={tokens.color.text} />
        <circle cx="45" cy="49" r="1.6" fill={light(0.4)} />
      </svg>
      <Readout>{label} {pct}/100</Readout>
    </Face>
  );
}
