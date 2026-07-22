import { useEffect, useRef, useState } from "react";
import { keyframes } from "@emotion/react";
import Typography from "@mui/material/Typography";
import { GlassPanel } from "../glass/primitives";
import { tokens } from "../theme/tokens";

const settleIn = keyframes`
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
`;

/** Ease-out count from 0 (or the previous value) up to `target` over `duration`ms. */
function useCountUp(target: number, duration = 900) {
  const [display, setDisplay] = useState(0);
  const fromRef = useRef(0);

  useEffect(() => {
    const from = fromRef.current;
    if (from === target) return;
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
      setDisplay(Math.round(from + (target - from) * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
      else fromRef.current = target;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  return display;
}

/**
 * StatOdometer — a Tier-A glass stat card: a large indigo figure over a small-caps
 * label. Numeric values roll up from their previous value (a real odometer effect,
 * matching the name) rather than just snapping to the new number; non-numeric
 * values (already-formatted strings) render as-is. `alert` turns the figure
 * danger-red for at-a-glance risk (e.g. unsubstantiated claims).
 */
export function StatOdometer({ value, label, alert }: { value: number | string; label: string; alert?: boolean }) {
  const numeric = typeof value === "number";
  const animated = useCountUp(numeric ? value : 0);

  return (
    <GlassPanel
      tier="A"
      sx={{
        flex: "1 1 0",
        minWidth: 128,
        px: 3,
        py: 2.5,
        display: "flex",
        flexDirection: "column",
        gap: 0.5,
        animation: `${settleIn} 420ms ease`,
      }}
    >
      <Typography
        sx={{
          fontSize: 30,
          fontWeight: 700,
          lineHeight: 1,
          fontVariantNumeric: "tabular-nums",
          color: alert ? tokens.color.danger : tokens.color.primary,
        }}
      >
        {numeric ? animated.toLocaleString() : value}
      </Typography>
      <Typography
        sx={{ fontSize: tokens.fontSize.xs, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: "text.secondary" }}
      >
        {label}
      </Typography>
    </GlassPanel>
  );
}
