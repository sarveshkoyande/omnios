import { createTheme } from "@mui/material/styles";
import {
  tokens,
  shade,
  light,
  enamelFace,
  raisedShadow,
  raisedShadowHover,
  pressedShadow,
  insetShadow,
  panelShadow,
  paperGrain,
  brushedMetal,
  focusRing,
} from "./tokens";

/**
 * Theme layer (createTheme({ components })) — per the material-ui-styling skill this
 * is the "all instances" scope: the skeuomorphic look of every Button, Paper, Chip,
 * TextField etc. lives here so views never restyle them locally.
 *
 * Contrast decisions (WCAG 2.2 AA, accessibility beats realism):
 *  - primary/secondary/success/warning fills take TEXT (#111827) labels — white
 *    fails 4.5:1 on all four (e.g. 3.7:1 on #FA3C00); dark passes (4.85:1+).
 *    Reads as printed keycap legends, which suits the metaphor anyway.
 *  - error keeps white text (4.8:1 on #DC2626).
 *  - Focus is a 2px offset outline everywhere, never removed, never shadow-only.
 */
export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: tokens.color.primary, contrastText: tokens.color.text },
    secondary: { main: tokens.color.secondary, contrastText: tokens.color.text },
    success: { main: tokens.color.success, contrastText: tokens.color.text },
    warning: { main: tokens.color.warning, contrastText: tokens.color.text },
    error: { main: tokens.color.danger, contrastText: tokens.color.surface },
    background: { default: tokens.color.surface, paper: tokens.color.surface },
    text: { primary: tokens.color.text, secondary: shade(0.62) },
    divider: shade(0.16),
  },
  typography: {
    fontFamily: tokens.font.primary,
    h1: { fontFamily: tokens.font.display, fontSize: tokens.fontSize.xxl, fontWeight: 400, letterSpacing: "0.01em" },
    h2: { fontFamily: tokens.font.display, fontSize: tokens.fontSize.xl, fontWeight: 400 },
    h3: { fontSize: tokens.fontSize.lg, fontWeight: 700 },
    subtitle1: { fontSize: tokens.fontSize.md, fontWeight: 500 },
    body1: { fontSize: tokens.fontSize.md },
    body2: { fontSize: tokens.fontSize.sm },
    caption: { fontSize: tokens.fontSize.xs },
    overline: {
      fontFamily: tokens.font.mono,
      fontSize: tokens.fontSize.xs,
      fontWeight: 700,
      letterSpacing: "0.08em",
      textTransform: "uppercase",
    },
    button: { fontSize: tokens.fontSize.sm, fontWeight: 700, textTransform: "none" },
  },
  spacing: tokens.spacingUnit, // spacing(1|2|3|4|6|8) = 4/8/12/16/24/32
  shape: { borderRadius: tokens.radius.md },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          // The desk: surface token washed with a whisper of the text token, plus
          // paper grain. Lighting/texture only — no new palette values.
          backgroundColor: tokens.color.surface,
          backgroundImage: `${paperGrain}, linear-gradient(180deg, ${shade(0.045)}, ${shade(0.025)})`,
          minHeight: "100vh",
        },
        "::selection": { background: tokens.color.secondary, color: tokens.color.text },
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
        "@media (prefers-reduced-motion: reduce)": {
          "*, *::before, *::after": {
            animationDuration: "0.01ms !important",
            animationIterationCount: "1 !important",
            transitionDuration: "0.01ms !important",
          },
        },
      },
    },

    MuiButton: {
      defaultProps: { disableRipple: true, disableElevation: true },
      styleOverrides: {
        root: {
          borderRadius: tokens.radius.md,
          border: `1px solid ${shade(0.3)}`,
          transition: "transform 120ms ease, box-shadow 120ms ease, filter 120ms ease",
          boxShadow: raisedShadow,
          "&:hover": { boxShadow: raisedShadowHover, transform: "translateY(-1px)" },
          "&:active": { boxShadow: pressedShadow, transform: "translateY(1px)" },
          "&.Mui-focusVisible": focusRing,
          "&.Mui-disabled": {
            // Unplugged key: flat, no travel, but AA-readable label.
            boxShadow: "none",
            border: `1px solid ${shade(0.2)}`,
            background: shade(0.08),
            color: shade(0.55),
          },
        },
        outlined: {
          // Bare aluminium key: neutral face, same travel.
          background: enamelFace(tokens.color.surface),
          color: tokens.color.text,
          borderColor: shade(0.3),
          "&:hover": { background: enamelFace(tokens.color.surface), borderColor: shade(0.45) },
        },
        text: {
          // Engraved flat control: no plate, deboss on press instead of travel.
          border: "1px solid transparent",
          boxShadow: "none",
          color: tokens.color.text,
          "&:hover": { background: shade(0.06), boxShadow: "none", transform: "none" },
          "&:active": { background: shade(0.1), boxShadow: `inset 0 1px 2px ${shade(0.2)}`, transform: "none" },
        },
      },
      // v9 variants API: map color props to enamel keycap faces.
      variants: [
        { props: { variant: "contained", color: "primary" }, style: { background: enamelFace(tokens.color.primary) } },
        { props: { variant: "contained", color: "secondary" }, style: { background: enamelFace(tokens.color.secondary) } },
        { props: { variant: "contained", color: "success" }, style: { background: enamelFace(tokens.color.success) } },
        { props: { variant: "contained", color: "error" }, style: { background: enamelFace(tokens.color.danger) } },
      ],
    },

    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          backgroundImage: paperGrain,
          border: `1px solid ${shade(0.14)}`,
          boxShadow: panelShadow,
        },
      },
    },

    MuiDivider: {
      styleOverrides: {
        root: {
          // Embossed groove: shade line with a highlight line beneath.
          borderColor: shade(0.16),
          "&::after": { content: "none" },
          boxShadow: `0 1px 0 ${light(0.9)}`,
        },
      },
    },

    MuiChip: {
      styleOverrides: {
        root: {
          fontFamily: tokens.font.mono,
          fontSize: tokens.fontSize.xs,
          fontWeight: 700,
          border: `1px solid ${shade(0.25)}`,
          boxShadow: `inset 0 1px 0 ${light(0.5)}, 0 1px 2px ${shade(0.15)}`,
        },
        colorSuccess: { background: enamelFace(tokens.color.success), color: tokens.color.text },
        colorWarning: { background: enamelFace(tokens.color.warning), color: tokens.color.text },
        colorPrimary: { background: enamelFace(tokens.color.primary), color: tokens.color.text },
        colorSecondary: { background: enamelFace(tokens.color.secondary), color: tokens.color.text },
      },
    },

    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          background: tokens.color.surface,
          boxShadow: insetShadow,
          borderRadius: tokens.radius.md,
          "& .MuiOutlinedInput-notchedOutline": { borderColor: shade(0.28) },
          "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: shade(0.45) },
          "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
            borderColor: tokens.color.primary,
            borderWidth: 2,
          },
          "&.Mui-focused": focusRing,
          "&.Mui-disabled": { background: shade(0.06), boxShadow: "none" },
          "&.Mui-error .MuiOutlinedInput-notchedOutline": { borderColor: tokens.color.danger },
        },
      },
    },

    MuiLinearProgress: {
      styleOverrides: {
        root: {
          // Thermometer groove: recessed track, glossy mercury bar.
          height: 10,
          borderRadius: tokens.radius.sm,
          background: shade(0.12),
          boxShadow: insetShadow,
        },
        bar: {
          borderRadius: tokens.radius.sm,
          backgroundImage: `linear-gradient(180deg, ${light(0.45)}, ${light(0)} 55%)`,
        },
      },
    },

    MuiAppBar: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          background: brushedMetal,
          color: tokens.color.text,
          borderBottom: `1px solid ${shade(0.25)}`,
          boxShadow: `0 1px 0 ${light(0.9)} inset, 0 2px 6px ${shade(0.18)}`,
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
