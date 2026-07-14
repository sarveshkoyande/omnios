import { createTheme } from "@mui/material/styles";
import {
  tokens,
  shade,
  light,
  indigoTint,
  glass,
  glassFallback,
  gradientBrand,
  focusRing,
} from "./tokens";

/**
 * Theme layer (createTheme({ components })) — the "all instances" scope per the
 * material-ui-styling skill. The light-liquid-glass look of every AppBar, Paper,
 * Button, Chip, TextField, Dialog etc. lives here so views never restyle them
 * locally. Design contract: DESIGN_BRIEF.md.
 *
 * Hard rules encoded here:
 *  - The AppBar is the ONE fully-saturated element (brand gradient, white text).
 *  - Everything else is glass, white, or ink. Primary buttons are the only other
 *    saturated element (brand gradient, white text).
 *  - Every glass surface pairs backdrop-filter with -webkit-, and degrades to a
 *    solid via @supports and the two a11y media queries in CssBaseline.
 *  - Focus is a 2px indigo outline, offset, never removed (white on the app bar).
 */

/** Tier-A glass, expressed as emotion style object with a solid fallback. */
const glassTierA = {
  background: glassFallback,
  border: glass.border,
  boxShadow: glass.shadow,
  backgroundImage: "none",
  "@supports ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px)))": {
    background: glass.panel,
    backdropFilter: glass.blur,
    WebkitBackdropFilter: glass.blur,
  },
} as const;

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: tokens.color.primary, contrastText: "#FFFFFF" },
    secondary: { main: tokens.color.secondary, contrastText: "#FFFFFF" },
    success: { main: tokens.color.success, contrastText: "#FFFFFF" },
    warning: { main: tokens.color.warning, contrastText: tokens.color.text },
    error: { main: tokens.color.danger, contrastText: "#FFFFFF" },
    background: { default: tokens.color.bgBase, paper: glass.panel },
    text: { primary: tokens.color.text, secondary: tokens.color.inkSoft },
    divider: indigoTint(0.12),
  },
  typography: {
    fontFamily: tokens.font.primary,
    h1: { fontSize: tokens.fontSize.display, fontWeight: 700, letterSpacing: "-0.01em", color: tokens.color.text },
    h2: { fontSize: tokens.fontSize.xxl, fontWeight: 700, color: tokens.color.text },
    h3: { fontSize: tokens.fontSize.xl, fontWeight: 700, color: tokens.color.text },
    subtitle1: { fontSize: tokens.fontSize.lg, fontWeight: 600 },
    body1: { fontSize: tokens.fontSize.md },
    body2: { fontSize: tokens.fontSize.sm },
    caption: { fontSize: tokens.fontSize.xs, color: tokens.color.inkSoft },
    overline: {
      // Section labels: small caps, +0.08em, brand indigo.
      fontFamily: tokens.font.primary,
      fontSize: tokens.fontSize.xs,
      fontWeight: 700,
      letterSpacing: "0.08em",
      textTransform: "uppercase",
      color: tokens.color.primary,
      lineHeight: 1.4,
    },
    button: { fontSize: tokens.fontSize.sm, fontWeight: 600, textTransform: "none" },
  },
  spacing: tokens.spacingUnit, // spacing(1|2|3|4|6|8) = 4/8/12/16/24/32
  shape: { borderRadius: tokens.radius.md },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: tokens.color.bgBase,
          minHeight: "100vh",
        },
        "::selection": { background: indigoTint(0.22), color: tokens.color.text },
        ".material-symbols-outlined": {
          fontFamily: "'Material Symbols Outlined'",
          fontWeight: "normal",
          fontStyle: "normal",
          fontSize: 20,
          lineHeight: 1,
          letterSpacing: "normal",
          textTransform: "none",
          display: "inline-block",
          whiteSpace: "nowrap",
          wordWrap: "normal",
          direction: "ltr",
          WebkitFontSmoothing: "antialiased",
          verticalAlign: "middle",
          fontVariationSettings: "'FILL' 0, 'wght' 450, 'GRAD' 0, 'opsz' 24",
        },
        // Accessibility: collapse glass to solid, kill blur everywhere.
        "@media (prefers-reduced-transparency: reduce)": {
          "*, *::before, *::after": {
            backdropFilter: "none !important",
            WebkitBackdropFilter: "none !important",
          },
          ".glass-surface": {
            background: `${glassFallback} !important`,
          },
        },
        "@media (prefers-contrast: more)": {
          ".glass-surface": {
            background: "rgba(255,255,255,0.9) !important",
            borderColor: `${shade(0.35)} !important`,
          },
        },
        "@media (prefers-reduced-motion: reduce)": {
          "*, *::before, *::after": {
            animationDuration: "0.01ms !important",
            animationIterationCount: "1 !important",
            transitionDuration: "0.01ms !important",
          },
        },
      },
    },

    MuiAppBar: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          // THE one saturated moment: solid brand gradient, white content.
          background: gradientBrand,
          color: "#FFFFFF",
          borderBottom: "none",
          boxShadow: "0 2px 12px rgba(79,70,229,0.28)",
        },
      },
    },

    MuiPaper: {
      defaultProps: { elevation: 0, className: "glass-surface" },
      styleOverrides: {
        root: {
          ...glassTierA,
          borderRadius: tokens.radius.md,
          color: tokens.color.text,
        },
      },
    },

    MuiButton: {
      defaultProps: { disableRipple: true, disableElevation: true },
      styleOverrides: {
        root: {
          borderRadius: tokens.radius.md,
          fontWeight: 600,
          transition: "transform 120ms ease, box-shadow 120ms ease, filter 120ms ease, background 120ms ease",
          "&.Mui-focusVisible": focusRing,
        },
        // Primary action: brand gradient, white text (the only other saturated element).
        contained: {
          background: gradientBrand,
          color: "#FFFFFF",
          border: "none",
          boxShadow: "0 4px 14px rgba(79,70,229,0.30)",
          "&:hover": { filter: "brightness(1.06)", boxShadow: "0 6px 18px rgba(79,70,229,0.36)", transform: "translateY(-1px)" },
          "&:active": { transform: "translateY(1px)", filter: "brightness(0.98)" },
          "&.Mui-disabled": { background: shade(0.12), color: shade(0.4), boxShadow: "none" },
        },
        // "Outlined" is repurposed as a translucent glass pill — never grey.
        outlined: {
          ...glassTierA,
          color: tokens.color.text,
          borderRadius: tokens.radius.pill,
          "&:hover": { background: glass.panelStrong, borderColor: light(0.8) },
          "&.Mui-disabled": { background: shade(0.06), color: shade(0.4), borderColor: shade(0.1) },
        },
        // Secondary: plain ink text link ("Skip — I'll just chat").
        text: {
          color: tokens.color.text,
          boxShadow: "none",
          "&:hover": { background: indigoTint(0.06), boxShadow: "none" },
          "&:active": { background: indigoTint(0.1) },
        },
      },
    },

    MuiDivider: {
      styleOverrides: {
        root: { borderColor: indigoTint(0.12) },
      },
    },

    MuiChip: {
      defaultProps: { className: "glass-surface" },
      styleOverrides: {
        root: {
          ...glassTierA,
          borderRadius: tokens.radius.pill,
          fontSize: tokens.fontSize.xs,
          fontWeight: 600,
          color: tokens.color.text,
          boxShadow: "none",
        },
        colorPrimary: { color: tokens.color.primary },
      },
    },

    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          // Tier 0 — content surface: near-opaque white, hairline, readable.
          background: glass.content,
          borderRadius: tokens.radius.md,
          "& .MuiOutlinedInput-notchedOutline": { borderColor: indigoTint(0.2) },
          "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: indigoTint(0.35) },
          "&.Mui-focused .MuiOutlinedInput-notchedOutline": { borderColor: tokens.color.primary, borderWidth: 2 },
          "&.Mui-focused": focusRing,
          "&.Mui-disabled": { background: shade(0.04) },
          "&.Mui-error .MuiOutlinedInput-notchedOutline": { borderColor: tokens.color.danger },
        },
      },
    },

    MuiLinearProgress: {
      styleOverrides: {
        root: { height: 8, borderRadius: tokens.radius.pill, background: indigoTint(0.12) },
        bar: { borderRadius: tokens.radius.pill, background: gradientBrand },
      },
    },

    MuiDrawer: {
      styleOverrides: {
        paper: { ...glassTierA, borderRadius: 0 },
      },
    },

    MuiDialog: {
      styleOverrides: {
        paper: {
          background: glass.panelStrong,
          border: glass.border,
          boxShadow: glass.shadowElevated,
          borderRadius: tokens.radius.lg,
          "@supports ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px)))": {
            backdropFilter: glass.blur,
            WebkitBackdropFilter: glass.blur,
          },
        },
      },
    },
    MuiBackdrop: {
      styleOverrides: {
        root: {
          backgroundColor: "rgba(30,27,51,0.32)",
          backdropFilter: "blur(4px)",
          WebkitBackdropFilter: "blur(4px)",
        },
      },
    },

    MuiLink: {
      styleOverrides: {
        root: { color: tokens.color.primary, "&:focus-visible": focusRing },
      },
    },
  },
});
