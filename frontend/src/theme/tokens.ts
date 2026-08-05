/**
 * Design tokens — high-contrast Material language for OmniOS.
 * Every runtime color is sourced from this token object so the app can be
 * audited and re-skinned in one place.
 */
export const tokens = {
  color: {
    primary: "#034EA2",
    primaryDark: "#023B7A",
    secondary: "#047857",
    secondaryDark: "#065F46",
    warning: "#C2410C",
    warningDark: "#9A3412",
    error: "#B42318",
    errorSoft: "#FEE4E2",
    ink: "#101828",
    inkSecondary: "#475467",
    surface: "#FFFFFF",
    canvas: "#F4F6F8",
    outline: "#D0D7DE",
    outlineStrong: "#8C959F",
    primaryContainer: "#E3EDFA",
    onPrimaryContainer: "#012F63",
    emerald50: "#ECFDF5",
    emerald100: "#D1FAE5",
    emerald200: "#A7F3D0",
    emerald400: "#34D399",
    emerald500: "#10B981",
    emerald600: "#059669",
    emerald700: "#047857",
    emerald800: "#065F46",
    emerald900: "#064E3B",
    orangeContainer: "#FFEDD5",
    success: "#047857",
    successSoft: "#D1FAE5",
    successInk: "#047857",
    warningSoft: "#FFEDD5",
    warningInk: "#9A3412",
    info: "#034EA2",
    infoSoft: "#E3EDFA",
    infoInk: "#012F63",
    danger: "#B42318",
    dangerSoft: "#FEE4E2",
    dangerInk: "#B42318",
    text: "#101828",
    inkSoft: "#475467",
    inkFaint: "#475467",
    border: "#D0D7DE",
    borderStrong: "#8C959F",
    input: "#D0D7DE",
    ring: "#034EA2",
    accentSurface: "#E3EDFA",
    accentSurfaceText: "#012F63",
    bgBase: "#F4F6F8",
    bgBaseChat: "#F4F6F8",
    topBar: "#000000",
    /**
     * Home hero panel. Doubles as the fallback fill when /static/home/home-hero-bg.png
     * is absent, and as the base of the scrim painted over it — text contrast on the
     * hero must not depend on what the artwork happens to contain.
     */
    heroInk: "#04214A",
  },
  /**
   * 15px is the floor. Nothing in the product may render text below it — the old 13/14 rungs
   * (and a long tail of 8.5-12px literals in chips, badges and table cells) were unreadable
   * and failed accessibility guidance, so `xs` and `sm` now resolve to the same 15 as `md`.
   * They are kept as distinct names only so the hundreds of existing call sites keep working;
   * prefer `md` in new code, and use weight or colour for hierarchy instead of smaller text.
   */
  fontSize: { xs: 15, sm: 15, md: 15, lg: 17, xl: 20, xxl: 24, display: 28 },
  font: {
    primary: `'Nunito Sans', 'Segoe UI', system-ui, sans-serif`,
  },
  spacingUnit: 4,
  radius: { sm: 4, md: 8, lg: 12, pill: 999 },
  layout: {
    /**
     * Height of the sticky app bar, in px. Everything that sizes itself against
     * the remaining viewport (`calc(100vh - topBarHeight)`) must read this rather
     * than repeat the number: MUI's Toolbar defaults to 56px under 600px wide and
     * 64px above it, so a hardcoded 56 silently left the workspace column 8px
     * taller than the space available and put a small permanent scroll on the page.
     * App.tsx pins the Toolbar to this value at every breakpoint.
     */
    topBarHeight: 64,
    /**
     * Width of the right-hand chat pane. Shared, because the sub-bar above it has to
     * reserve exactly this much on its right so the folder tabs stop at the workspace
     * edge instead of running on over the chat. Two places, one number.
     */
    chatPaneWidth: "30vw",
    chatPaneMinWidth: 320,
  },
} as const;

/**
 * Motion tokens. The built-in CSS easings are too weak to read as intentional at
 * the short durations this app uses, so every transition should pull a curve from
 * here rather than falling back to `ease`.
 *
 * `ease-in` is deliberately absent: it delays the first frame, which is the frame
 * the user is watching, and makes the UI feel slower at an identical duration.
 */
export const motion = {
  // Enter/exit and anything the user triggered — starts fast, feels responsive.
  easeOut: "cubic-bezier(0.23, 1, 0.32, 1)",
  // Movement between two on-screen positions.
  easeInOut: "cubic-bezier(0.77, 0, 0.175, 1)",
  // Sheets and drawers that travel a long distance (Ionic's curve).
  easeDrawer: "cubic-bezier(0.32, 0.72, 0, 1)",
  duration: {
    press: "120ms",
    hover: "160ms",
    enter: "220ms",
    panel: "260ms",
    /**
     * Exits are deliberately shorter than enters. On the way in the user is being shown
     * something and the motion carries meaning; on the way out they have already decided
     * and are waiting on the app, so anything slower than this reads as lag.
     */
    exit: "150ms",
  },
} as const;

/** Same numbers as `motion.duration`, unitless, for APIs that want ms as a number (MUI). */
export const motionMs = {
  press: 120,
  hover: 160,
  enter: 220,
  panel: 260,
  exit: 150,
} as const;

/**
 * Hover effects must be gated behind this: touch devices fire `:hover` on tap and
 * leave the state stuck after the finger lifts.
 */
export const hoverOnly = "@media (hover: hover) and (pointer: fine)";

export const shade = (alpha: number) => `rgba(16, 24, 40, ${alpha})`;
export const light = (alpha: number) => `rgba(255, 255, 255, ${alpha})`;
export const indigoTint = (alpha: number) => `rgba(3, 78, 162, ${alpha})`;
export const violetTint = (alpha: number) => `rgba(4, 120, 87, ${alpha})`;

export const glass = {
  panel: tokens.color.surface,
  panelStrong: tokens.color.primaryContainer,
  content: tokens.color.surface,
  blur: "none",
  blurLight: "none",
  border: `1px solid ${tokens.color.outline}`,
  borderTint: `1px solid ${tokens.color.primary}`,
  shadow: "none",
  shadowElevated: `0 8px 24px rgba(16,24,40,0.18)`,
} as const;

export const glassFallback = tokens.color.surface;
export const gradientBrand = tokens.color.primary;
export const gradientBrandVertical = tokens.color.primary;

export const focusRing = {
  outline: `2px solid ${tokens.color.primary}`,
  outlineOffset: "2px",
} as const;

export const focusRingOnBrand = {
  outline: `2px solid ${tokens.color.surface}`,
  outlineOffset: "2px",
} as const;
