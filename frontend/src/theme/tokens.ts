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
  },
  fontSize: { xs: 13, sm: 14, md: 15, lg: 17, xl: 20, xxl: 24, display: 28 },
  font: {
    primary: `'Nunito Sans', 'Segoe UI', system-ui, sans-serif`,
  },
  spacingUnit: 4,
  radius: { sm: 4, md: 8, lg: 12, pill: 999 },
} as const;

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
