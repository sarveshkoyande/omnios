import { keyframes } from "@emotion/react";
import { motion } from "./tokens";

/**
 * Shared entrance keyframes.
 *
 * These are one-shot ENTRANCES only -- an element mounting into a view that was already
 * there. Anything that can be retargeted mid-flight (a value changing, a panel collapsing,
 * a drag) must stay a CSS transition instead: keyframes restart from frame zero when
 * re-triggered, transitions retarget from wherever they currently are.
 *
 * Nothing starts from `scale(0)` or from a large offset. Real objects do not appear out of
 * nothing and do not fly in from off-screen to sit 8px away; the distance is small enough
 * that the eye reads it as the element settling, not travelling.
 *
 * `prefers-reduced-motion` is handled globally in theme.ts (MuiCssBaseline), which collapses
 * every animation here to ~0ms, so the end state is what a reduced-motion user sees.
 */

/** Content settling into place from slightly below. The default for panels and cards. */
export const enterRise = keyframes`
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: none; }
`;

/** Agent-side chat: enters from the left edge it is aligned to. */
export const enterFromLeft = keyframes`
  from { opacity: 0; transform: translate3d(-10px, 6px, 0) scale(0.985); }
  to   { opacity: 1; transform: none; }
`;

/** User-side chat: mirrors enterFromLeft so the two speakers stay spatially distinct. */
export const enterFromRight = keyframes`
  from { opacity: 0; transform: translate3d(10px, 6px, 0) scale(0.985); }
  to   { opacity: 1; transform: none; }
`;

/** A small state marker landing -- a tick, a badge, a count. */
export const popIn = keyframes`
  from { opacity: 0; transform: scale(0.6); }
  60%  { opacity: 1; transform: scale(1.06); }
  to   { opacity: 1; transform: scale(1); }
`;

/** Quiet fade, for crossfades where movement would fight the content underneath. */
export const fadeIn = keyframes`
  from { opacity: 0; }
  to   { opacity: 1; }
`;

/**
 * Delay for the nth item of a group entering together. Capped deliberately: past ~6 items
 * the cascade stops reading as one gesture and starts reading as the app being slow, so
 * everything after the cap enters with the last delay rather than an ever-growing one.
 */
export const stagger = (index: number, step = 40, cap = 6) => `${Math.min(index, cap) * step}ms`;

/** `animation` shorthand for a one-shot entrance on the app's standard enter curve. */
export const enterWith = (name: ReturnType<typeof keyframes>, delay = "0ms", duration = motion.duration.enter) =>
  `${name} ${duration} ${motion.easeOut} ${delay} both`;
