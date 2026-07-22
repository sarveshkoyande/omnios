import { motion } from "framer-motion";
import Box from "@mui/material/Box";
import { tokens } from "../theme/tokens";

/**
 * Animated floating-gradient backdrop — slow-drifting blurred blobs in the
 * app's blue/purple palette. Ported from a Tailwind/shadcn reference to the
 * app's MUI + emotion stack (no Tailwind here), and grounded in tokens.ts.
 *
 * Renders as an absolute layer meant to sit behind hero content; pass a
 * `style` to place it (e.g. `inset: 0`). Blobs are pointer-events:none so
 * anything overlaid stays interactive.
 */

type Blob = {
  size: number;
  from: string;
  to: string;
  x: number[];
  y: number[];
  scale: number[];
  duration: number;
  place: React.CSSProperties;
};

// Saturated palette — reads against a dark hero band.
const BLOBS: Blob[] = [
  {
    size: 384,
    from: tokens.color.primary, // brand blue
    to: "#6D28D9", // deep violet
    x: [0, 100, 0],
    y: [0, 50, 0],
    scale: [1, 1.2, 1],
    duration: 8,
    place: { top: "6%", left: "8%" },
  },
  {
    size: 420,
    from: "#7C3AED", // purple
    to: tokens.color.primaryDark, // dark blue
    x: [0, -100, 0],
    y: [0, -50, 0],
    scale: [1, 1.3, 1],
    duration: 10,
    place: { bottom: "4%", right: "8%" },
  },
  {
    size: 360,
    from: "#3B82F6", // sky blue
    to: "#8B5CF6", // light violet
    x: [0, 60, 0],
    y: [0, -100, 0],
    scale: [1, 1.15, 1],
    duration: 12,
    place: { top: "42%", left: "46%" },
  },
];

// Pastel palette — soft washes that read as a light glow over a light canvas.
const BLOBS_LIGHT: Blob[] = [
  {
    size: 620,
    from: "#BFD8FF", // soft sky
    to: "#DCC9FF", // soft lilac
    x: [0, 120, 0],
    y: [0, 70, 0],
    scale: [1, 1.2, 1],
    duration: 20,
    place: { top: "-6%", left: "4%" },
  },
  {
    size: 680,
    from: "#D7C6FF", // pale violet
    to: "#C7E0FF", // pale blue
    x: [0, -120, 0],
    y: [0, -60, 0],
    scale: [1, 1.25, 1],
    duration: 26,
    place: { bottom: "-8%", right: "2%" },
  },
  {
    size: 560,
    from: "#CFE4FF", // light blue
    to: "#E4D6FF", // light violet
    x: [0, 80, 0],
    y: [0, -120, 0],
    scale: [1, 1.15, 1],
    duration: 32,
    place: { top: "38%", left: "42%" },
  },
];

export function FloatingGradient({ style, light = false }: { style?: React.CSSProperties; light?: boolean }) {
  const blobs = light ? BLOBS_LIGHT : BLOBS;
  return (
    <Box sx={{ position: "absolute", inset: 0, overflow: "hidden" }} style={style} aria-hidden>
      {blobs.map((b, i) => (
        <motion.div
          key={i}
          animate={{ x: b.x, y: b.y, scale: b.scale }}
          transition={{ duration: b.duration, repeat: Infinity, ease: "easeInOut" }}
          style={{
            position: "absolute",
            height: b.size,
            width: b.size,
            borderRadius: "50%",
            opacity: light ? 0.55 : 0.4,
            filter: light ? "blur(90px)" : "blur(64px)",
            backgroundImage: `linear-gradient(90deg, ${b.from}, ${b.to})`,
            ...b.place,
          }}
        />
      ))}
    </Box>
  );
}

export default FloatingGradient;
