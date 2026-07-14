/**
 * Design tokens — "light liquid glass" (DESIGN_BRIEF.md, single source of truth).
 * Every value in the design system derives from these; no raw hex/rgba in
 * components. The reference screen (Workspace) is the visual contract.
 */
export const tokens = {
  color: {
    // Brand
    primary: "#4F46E5", // brand indigo — app bar gradient start, primary actions
    secondary: "#7C3AED", // brand violet — app bar gradient end
    magenta: "#E935C1", // logo mark / rare highlight only — never UI chrome
    // Ink
    text: "#1E1B33", // primary text, dark indigo-slate (never pure black)
    inkSoft: "#55517A", // secondary text, helper copy
    // Status
    success: "#22C55E", // "agents online" dot
    warning: "#D97706",
    danger: "#DC2626",
    // Atmosphere
    surface: "#FFFFFF",
    bgBase: "#E9EAFB", // pale periwinkle page base
    bgMist1: "#C9CFF8", // soft blue-violet mist blob
    bgMist2: "#E3D9FA", // soft lavender mist blob
  },
  /** Type scale 12/13/14/16/20/24/32 */
  fontSize: { xs: 12, sm: 13, md: 14, lg: 16, xl: 20, xxl: 24, display: 32 },
  font: {
    primary: `"Segoe UI", "Inter", system-ui, "Roboto", sans-serif`,
    // kept for not-yet-migrated skeuo screens; unused on glass surfaces
    display: `"Segoe UI", "Inter", system-ui, sans-serif`,
    mono: "ui-monospace, 'JetBrains Mono', monospace",
  },
  /** Spacing scale 4/8/12/16/24/32 — theme.spacing(1|2|3|4|6|8) */
  spacingUnit: 4,
  radius: { sm: 8, md: 14, lg: 20, pill: 999 },
} as const;

/** Shade: ink token at an alpha — neutral tints, dividers, soft shadows. */
export const shade = (alpha: number) => `rgba(30, 27, 51, ${alpha})`;
/** Highlight: surface (white) token at an alpha — glass edges/sheen. */
export const light = (alpha: number) => `rgba(255, 255, 255, ${alpha})`;
/** Indigo tint at an alpha — brand-tinted borders/shadows. */
export const indigoTint = (alpha: number) => `rgba(79, 70, 229, ${alpha})`;

/* ------------------------------------------------------------------ *
 * GLASS RECIPES — the four core elements: transparency, blur, border,
 * layered shadow. Tiers per the brief's glass hierarchy.
 * ------------------------------------------------------------------ */

export const glass = {
  /** Tier A — panels (pane containers, section/stepper cards, chat bubbles). */
  panel: "rgba(255, 255, 255, 0.55)",
  /** Tier B — emphasis (active stage, hovered/selected). */
  panelStrong: "rgba(255, 255, 255, 0.72)",
  /** Tier 0 — content surfaces (inputs, tables, long-form reading). */
  content: "rgba(255, 255, 255, 0.92)",
  blur: "blur(24px)",
  blurLight: "blur(12px)",
  border: "1px solid rgba(255, 255, 255, 0.65)",
  borderTint: "1px solid rgba(79, 70, 229, 0.12)",
  shadow: "0 8px 32px rgba(79, 70, 229, 0.10)",
  shadowElevated: "0 16px 48px rgba(79, 70, 229, 0.18)",
} as const;

/** Solid fallback for @supports / prefers-reduced-transparency. */
export const glassFallback = "rgba(255, 255, 255, 0.9)";

export const gradientBrand = `linear-gradient(90deg, ${tokens.color.primary}, ${tokens.color.secondary})`;
export const gradientBrandVertical = `linear-gradient(180deg, ${tokens.color.primary}, ${tokens.color.secondary})`;

/** Focus ring — WCAG 2.2 AA: always visible, 2px brand indigo, offset. */
export const focusRing = {
  outline: `2px solid ${tokens.color.primary}`,
  outlineOffset: "2px",
} as const;
/** Focus ring on the saturated app bar (indigo would vanish) — white instead. */
export const focusRingOnBrand = {
  outline: `2px solid ${tokens.color.surface}`,
  outlineOffset: "2px",
} as const;
