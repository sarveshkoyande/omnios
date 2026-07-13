/**
 * Design tokens — verbatim from the skeumorphism skill's Style Foundations.
 * Every other value in the design system must derive from these (alpha tints of
 * `text` for shade, alpha tints of `surface` for highlight), never ad-hoc hex.
 */
export const tokens = {
  color: {
    primary: "#FA3C00",
    secondary: "#F08321",
    success: "#16A34A",
    warning: "#D97706",
    danger: "#DC2626",
    surface: "#FFFFFF",
    text: "#111827",
  },
  /** Type scale 12/14/16/20/24/32 */
  fontSize: { xs: 12, sm: 14, md: 16, lg: 20, xl: 24, xxl: 32 },
  font: {
    primary: "'Roboto', 'Segoe UI', Arial, sans-serif",
    display: "'Germania One', 'Roboto', sans-serif",
    mono: "'JetBrains Mono', ui-monospace, monospace",
  },
  /** Spacing scale 4/8/12/16/24/32 — theme.spacing(1|2|3|4|6|8) */
  spacingUnit: 4,
  radius: { sm: 4, md: 8 },
} as const;

/** Shade: text token at an alpha — used for every border, shadow and neutral tint. */
export const shade = (alpha: number) => `rgba(17, 24, 39, ${alpha})`;
/** Highlight: surface token at an alpha — used for every bevel/sheen highlight. */
export const light = (alpha: number) => `rgba(255, 255, 255, ${alpha})`;

/* ---- Material recipes (lighting, not palette: gradients/shadows built from the
   two tokens above so the "physical" look introduces no new colors). ---- */

/** Top-lit enamel/keycap face over any base color. */
export const enamelFace = (base: string) =>
  `linear-gradient(180deg, ${light(0.28)} 0%, ${light(0)} 42%, ${shade(0.08)} 100%), ${base}`;

/** Raised edge: machined hard edge + ambient falloff. */
export const raisedShadow = [
  `0 2px 0 ${shade(0.28)}`,
  `0 3px 6px ${shade(0.22)}`,
  `inset 0 1px 0 ${light(0.65)}`,
].join(", ");

export const raisedShadowHover = [
  `0 3px 0 ${shade(0.28)}`,
  `0 6px 12px ${shade(0.26)}`,
  `inset 0 1px 0 ${light(0.7)}`,
].join(", ");

/** Pressed: travel consumed, light now falls inside the key. */
export const pressedShadow = [
  `0 0 0 ${shade(0.28)}`,
  `inset 0 2px 4px ${shade(0.35)}`,
  `inset 0 -1px 0 ${light(0.4)}`,
].join(", ");

/** Milled input well / recessed tray. */
export const insetShadow = [
  `inset 0 2px 4px ${shade(0.18)}`,
  `inset 0 1px 2px ${shade(0.12)}`,
  `inset 0 -1px 0 ${light(0.9)}`,
].join(", ");

/** Card-stock panel sitting on the desk. */
export const panelShadow = [
  `0 1px 2px ${shade(0.1)}`,
  `0 4px 10px ${shade(0.12)}`,
  `inset 0 1px 0 ${light(0.9)}`,
].join(", ");

/** Embossed groove divider (dark line over light line). */
export const grooveBorder = `1px solid ${shade(0.16)}`;
export const grooveHighlight = `1px solid ${light(0.9)}`;

/** Paper-grain texture: tiny SVG noise, 2.5% opacity — felt, not seen. */
export const paperGrain =
  `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='160' height='160' filter='url(%23n)' opacity='0.025'/%3E%3C/svg%3E")`;

/** Brushed-metal header strip (vertical grain via 1px banding of the two tokens). */
export const brushedMetal =
  `repeating-linear-gradient(90deg, ${shade(0.05)} 0px, ${light(0.35)} 1px, ${shade(0.02)} 2px), ` +
  `linear-gradient(180deg, ${light(0.65)}, ${shade(0.1)}), #FFFFFF`;

/** Focus ring — WCAG 2.2 AA: always visible, 2px, offset so it reads on any fill. */
export const focusRing = {
  outline: `2px solid ${tokens.color.text}`,
  outlineOffset: "2px",
} as const;
export const focusRingOnDark = {
  outline: `2px solid ${tokens.color.surface}`,
  outlineOffset: "2px",
} as const;
