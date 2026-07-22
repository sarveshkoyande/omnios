import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { keyframes } from "@mui/system";
import { tokens } from "../../../../theme/tokens";

// Full-canvas loading state for the workflow stage. Deliberately thin glass:
// the canvas underneath stays visible (just blurred), with a drifting
// blue/purple glow and twinkling star sprinkles layered on top.

const glowDriftA = keyframes`
  0%   { transform: translate3d(-18%, -12%, 0) scale(1);    filter: hue-rotate(0deg); }
  33%  { transform: translate3d(20%, 12%, 0) scale(1.2);    filter: hue-rotate(18deg); }
  66%  { transform: translate3d(6%, -18%, 0) scale(0.9);    filter: hue-rotate(-12deg); }
  100% { transform: translate3d(-18%, -12%, 0) scale(1);    filter: hue-rotate(0deg); }
`;

const glowDriftB = keyframes`
  0%   { transform: translate3d(16%, 14%, 0) scale(1.1);    filter: hue-rotate(0deg); }
  40%  { transform: translate3d(-22%, -4%, 0) scale(0.85);  filter: hue-rotate(-20deg); }
  75%  { transform: translate3d(-4%, 18%, 0) scale(1.15);   filter: hue-rotate(14deg); }
  100% { transform: translate3d(16%, 14%, 0) scale(1.1);    filter: hue-rotate(0deg); }
`;

const twinkle = keyframes`
  0%, 100% { opacity: 0; transform: scale(.35) rotate(0deg); }
  50%      { opacity: 1; transform: scale(1) rotate(25deg); }
`;

const iconGlow = keyframes`
  0%, 100% { filter: drop-shadow(0 0 10px rgba(98,216,255,.75)) drop-shadow(0 0 18px rgba(128,94,255,.5)); transform: rotate(0deg); }
  50%      { filter: drop-shadow(0 0 16px rgba(128,94,255,.9)) drop-shadow(0 0 28px rgba(98,216,255,.65)); transform: rotate(12deg); }
`;

const dotPulse = keyframes`
  0%, 100% { opacity: .28; transform: translateY(0); }
  50%      { opacity: 1; transform: translateY(-2px); }
`;

const messages = ["AI is generating the workflow", "AI is updating the workflow"];
const MESSAGE_SEGMENT_S = 3.1;

// Each message get own slot (100 / messages.length percent of full cycle).
// Hump (fade-in + visible + fade-out) fill only part of slot, rest stay
// opacity 0 -> real blank pause before/after neighbor message, no overlap.
const MESSAGE_SLOT_PCT = 100 / messages.length;
const FADE_IN_END_PCT = MESSAGE_SLOT_PCT * 0.16;
const VISIBLE_END_PCT = MESSAGE_SLOT_PCT * 0.64;
const FADE_OUT_END_PCT = MESSAGE_SLOT_PCT * 0.82;

const messageReveal = keyframes`
  0%    { opacity: 0; transform: translateY(6px); }
  ${FADE_IN_END_PCT}%  { opacity: 1; transform: translateY(0); }
  ${VISIBLE_END_PCT}%  { opacity: 1; transform: translateY(0); }
  ${FADE_OUT_END_PCT}%, 100% { opacity: 0; transform: translateY(-6px); }
`;

const STAR_PATH = "polygon(50% 0%, 61% 39%, 100% 50%, 61% 61%, 50% 100%, 39% 61%, 0% 50%, 39% 39%)";

const stars = [
  { top: "12%", left: "10%", size: 14, duration: "3.4s", delay: "0s" },
  { top: "20%", left: "84%", size: 10, duration: "4.1s", delay: "1.2s" },
  { top: "72%", left: "8%", size: 9, duration: "3.8s", delay: "2s" },
  { top: "78%", left: "88%", size: 13, duration: "4.6s", delay: ".6s" },
  { top: "45%", left: "94%", size: 7, duration: "3.2s", delay: "2.6s" },
  { top: "88%", left: "42%", size: 8, duration: "3.9s", delay: "1.7s" },
  { top: "8%", left: "48%", size: 8, duration: "3.6s", delay: "2.3s" },
  { top: "55%", left: "4%", size: 10, duration: "4.3s", delay: ".9s" },
];

function StarSprinkle({
  top,
  left,
  size,
  duration,
  delay,
}: {
  top: string;
  left: string;
  size: number;
  duration: string;
  delay: string;
}) {
  return (
    <Box
      aria-hidden="true"
      sx={{
        position: "absolute",
        top,
        left,
        width: size,
        height: size,
        zIndex: 2,
        opacity: 0,
        clipPath: STAR_PATH,
        background: "linear-gradient(135deg, #ffffff, #8fd8ff 45%, #a98bff)",
        boxShadow: "0 0 10px rgba(150,160,255,.55)",
        animation: `${twinkle} ${duration} ease-in-out infinite`,
        animationDelay: delay,
      }}
    />
  );
}

export function AgentWorkingOverlay() {
  return (
    <Box
      role="status"
      aria-live="polite"
      sx={{
        position: "absolute",
        inset: 0,
        zIndex: 20,
        overflow: "hidden",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        px: 2,
        // Thin, true-glass wash — the canvas underneath must read through.
        background: "rgba(245, 246, 253, .28)",
        backdropFilter: "blur(9px) saturate(130%)",
        WebkitBackdropFilter: "blur(9px) saturate(130%)",
      }}
    >
      {/* drifting blue/purple glow, blended over the blurred canvas */}
      <Box
        aria-hidden="true"
        sx={{
          position: "absolute",
          top: "-10%",
          left: "-10%",
          width: "62%",
          height: "62%",
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(98,178,255,.55), transparent 70%)",
          filter: "blur(55px)",
          mixBlendMode: "plus-lighter",
          animation: `${glowDriftA} 9s ease-in-out infinite`,
          pointerEvents: "none",
        }}
      />
      <Box
        aria-hidden="true"
        sx={{
          position: "absolute",
          bottom: "-14%",
          right: "-8%",
          width: "58%",
          height: "58%",
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(148,94,255,.5), transparent 70%)",
          filter: "blur(60px)",
          mixBlendMode: "plus-lighter",
          animation: `${glowDriftB} 11s ease-in-out infinite`,
          pointerEvents: "none",
        }}
      />

      {stars.map((star, index) => (
        <StarSprinkle key={index} {...star} />
      ))}

      <Box
        sx={{
          position: "relative",
          zIndex: 3,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 1.5,
          px: { xs: 3, sm: 4 },
          py: 3,
          borderRadius: 4,
          border: "1px solid rgba(255,255,255,.55)",
          background: "rgba(255,255,255,.2)",
          boxShadow: "0 12px 40px rgba(45,73,164,.16), inset 0 1px 0 rgba(255,255,255,.5)",
          backdropFilter: "blur(6px)",
          WebkitBackdropFilter: "blur(6px)",
        }}
      >
        <Box
          aria-hidden="true"
          sx={{
            width: 30,
            height: 30,
            clipPath: STAR_PATH,
            background: "linear-gradient(135deg, #62d8ff, #8067ff)",
            animation: `${iconGlow} 2.4s ease-in-out infinite`,
          }}
        />

        <Box sx={{ position: "relative", minHeight: 24, width: "min(360px, 82vw)", textAlign: "center" }}>
          {messages.map((message, index) => (
            <Typography
              key={message}
              sx={{
                position: "absolute",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: { xs: 13, sm: 14 },
                fontWeight: 700,
                color: tokens.color.text,
                textShadow: "0 1px 12px rgba(255,255,255,.85)",
                animation: `${messageReveal} ${messages.length * MESSAGE_SEGMENT_S}s ease-in-out infinite`,
                animationDelay: `${index * MESSAGE_SEGMENT_S}s`,
              }}
            >
              {message}
            </Typography>
          ))}
        </Box>

        <Box sx={{ display: "flex", gap: 0.75 }} aria-hidden="true">
          {[0, 1, 2].map((dot) => (
            <Box
              key={dot}
              sx={{
                width: 5,
                height: 5,
                borderRadius: 1,
                background: dot === 1 ? "#846eff" : "#62cfff",
                animation: `${dotPulse} 1.2s ease-in-out infinite`,
                animationDelay: `${dot * 180}ms`,
              }}
            />
          ))}
        </Box>
      </Box>
    </Box>
  );
}
