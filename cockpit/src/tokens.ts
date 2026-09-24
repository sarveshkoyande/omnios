/** Neumorphic design tokens. Base palette is deliberately monochromatic (per the design
 *  system: shadows carry the depth, not colour) -- risk/status/coverage signals are the
 *  one place colour is still load-bearing, since a pharma claim's risk tier is regulatory
 *  information, not decoration. Those map to a `tone` class name consumed by cockpit.css's
 *  `.pill.tone-*` rules (a shared inset pill shape, tinted by tone) rather than inline
 *  bg/ink styles, so every pill stays the same physical object across the app. */
export const tokens = {
  bg: "#FBFBFB",
  fg: "#231F20",
  muted: "#6D6E71",
  accent: "#5D2CC9",
  accentLight: "#421F8F",
  accent2: "#0E5FB7",
};

/** Kept for the one remaining inline-style caller (footnote colour). */
export const inkSoft = tokens.muted;

export type Tone = "neutral" | "info" | "success" | "warning" | "danger";

export const RISK_TONE: Record<string, Tone> = {
  Low: "success",
  Medium: "warning",
  High: "danger",
};

export const STATUS_TONE: Record<string, { tone: Tone; label: string }> = {
  draft: { tone: "neutral", label: "Draft" },
  in_review: { tone: "warning", label: "In review" },
  approved: { tone: "success", label: "Approved" },
};
