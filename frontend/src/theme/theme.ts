import { createTheme } from "@mui/material/styles";
import { tokens, focusRing } from "./tokens";

const SEMANTIC: Record<string, { solid: string; soft: string; ink: string }> = {
  success: { solid: tokens.color.success, soft: tokens.color.successSoft, ink: tokens.color.successInk },
  warning: { solid: tokens.color.warning, soft: tokens.color.warningSoft, ink: tokens.color.warningInk },
  error: { solid: tokens.color.error, soft: tokens.color.errorSoft, ink: tokens.color.error },
  info: { solid: tokens.color.info, soft: tokens.color.infoSoft, ink: tokens.color.infoInk },
  secondary: { solid: tokens.color.secondary, soft: tokens.color.emerald100, ink: tokens.color.secondaryDark },
};

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: tokens.color.primary, dark: tokens.color.primaryDark, contrastText: "#FFFFFF" },
    secondary: { main: tokens.color.secondary, dark: tokens.color.secondaryDark, contrastText: "#FFFFFF" },
    success: { main: tokens.color.success, light: tokens.color.emerald100, dark: tokens.color.secondaryDark, contrastText: "#FFFFFF" },
    warning: { main: tokens.color.warning, dark: tokens.color.warningDark, contrastText: "#FFFFFF" },
    error: { main: tokens.color.error, contrastText: "#FFFFFF" },
    info: { main: tokens.color.info, contrastText: "#FFFFFF" },
    background: { default: tokens.color.canvas, paper: tokens.color.surface },
    text: { primary: tokens.color.text, secondary: tokens.color.inkSecondary },
    divider: tokens.color.outline,
  },
  typography: {
    fontFamily: tokens.font.primary,
    h1: { fontSize: tokens.fontSize.display, fontWeight: 800, letterSpacing: "-0.01em", color: tokens.color.text },
    h2: { fontSize: tokens.fontSize.xxl, fontWeight: 700, color: tokens.color.text },
    h3: { fontSize: tokens.fontSize.lg, fontWeight: 700, color: tokens.color.text },
    button: { fontSize: tokens.fontSize.sm, fontWeight: 700, textTransform: "none" },
    body1: { fontSize: tokens.fontSize.md, color: tokens.color.text },
    body2: { fontSize: tokens.fontSize.sm, color: tokens.color.inkSecondary },
    caption: { fontSize: tokens.fontSize.xs, color: tokens.color.inkSecondary },
    overline: {
      fontFamily: tokens.font.primary,
      fontSize: tokens.fontSize.xs,
      fontWeight: 700,
      letterSpacing: "0.6px",
      textTransform: "uppercase",
      color: tokens.color.primary,
      lineHeight: 1.4,
    },
  },
  shape: { borderRadius: tokens.radius.sm },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: tokens.color.canvas,
          minHeight: "100vh",
          overflowWrap: "break-word",
        },
        "h1, h2, h3, h4, h5, h6, p, li, td, th": { overflowWrap: "break-word" },
        "::selection": { background: tokens.color.primaryContainer, color: tokens.color.text },
        "*": { scrollbarWidth: "thin", scrollbarColor: `${tokens.color.outlineStrong} transparent` },
        "*::-webkit-scrollbar": { width: 12, height: 12 },
        "*::-webkit-scrollbar-track": { background: "transparent" },
        "*::-webkit-scrollbar-thumb": {
          background: tokens.color.outline,
          borderRadius: 999,
          border: "3px solid transparent",
          backgroundClip: "content-box",
        },
        "*::-webkit-scrollbar-thumb:hover": { background: tokens.color.outlineStrong, backgroundClip: "content-box" },
        "*::-webkit-scrollbar-corner": { background: "transparent" },
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
    MuiAppBar: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          backgroundColor: tokens.color.primary,
          color: "#FFFFFF",
          border: "none",
          backgroundImage: "none",
          boxShadow: "none",
          borderRadius: 0,
          // AppBar's root DOM node also carries .MuiPaper-root (AppBar wraps
          // Paper internally), and that rule is registered after this one --
          // same-specificity same-property CSS is decided by source order, so
          // MuiPaper's `border: 1px solid outline` was winning and painting a
          // stray light line across the top of the gradient bar. Win it back
          // explicitly rather than relying on declaration order.
          "&.MuiPaper-root": {
            border: "none !important",
            borderRadius: "0 !important",
          },
        },
      },
    },
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          backgroundColor: tokens.color.surface,
          backgroundImage: "none",
          border: `1px solid ${tokens.color.outline}`,
          borderRadius: tokens.radius.md,
          color: tokens.color.text,
          boxShadow: "none",
        },
      },
    },
    MuiButton: {
      defaultProps: { disableRipple: true, disableElevation: true },
      styleOverrides: {
        root: {
          borderRadius: tokens.radius.sm,
          fontWeight: 700,
          textTransform: "none",
          transition: "background-color 120ms ease, color 120ms ease, border-color 120ms ease, transform 120ms ease",
          "&.Mui-focusVisible": focusRing,
        },
        contained: ({ ownerState }) => {
          const s = ownerState.color ? SEMANTIC[ownerState.color] : undefined;
          const fill = s ? s.solid : tokens.color.primary;
          const textColor = "#FFFFFF";
          return {
            backgroundColor: fill,
            color: textColor,
            border: "none",
            boxShadow: "none",
            "&:hover": { backgroundColor: s ? s.ink : tokens.color.primaryDark, transform: "translateY(-1px)" },
            "&:active": { transform: "translateY(1px)" },
            "&.Mui-disabled": { backgroundColor: tokens.color.outline, color: tokens.color.inkSecondary, boxShadow: "none" },
          };
        },
        outlined: {
          backgroundColor: tokens.color.surface,
          border: `1px solid ${tokens.color.outlineStrong}`,
          color: tokens.color.primary,
          boxShadow: "none",
          "&:hover": { backgroundColor: tokens.color.primaryContainer, borderColor: tokens.color.primary },
        },
        text: {
          color: tokens.color.primary,
          boxShadow: "none",
          "&:hover": { backgroundColor: tokens.color.primaryContainer },
        },
      },
    },
    MuiDivider: { styleOverrides: { root: { borderColor: tokens.color.outline } } },
    MuiChip: {
      styleOverrides: {
        root: ({ ownerState }) => {
          const s = ownerState.color ? SEMANTIC[ownerState.color] : undefined;
          return {
            borderRadius: tokens.radius.sm,
            backgroundColor: s ? s.soft : tokens.color.surface,
            border: s ? "none" : `1px solid ${tokens.color.outline}`,
            color: s ? s.ink : tokens.color.inkSecondary,
            fontWeight: 700,
            boxShadow: "none",
            ".MuiChip-label": { px: 1 },
          };
        },
      },
    },
    MuiOutlinedInput: {
      defaultProps: { size: "small" },
      styleOverrides: {
        root: {
          backgroundColor: tokens.color.surface,
          borderRadius: tokens.radius.sm,
          "& .MuiOutlinedInput-notchedOutline": { borderColor: tokens.color.outlineStrong },
          "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: tokens.color.primary },
          "&.Mui-focused .MuiOutlinedInput-notchedOutline": { borderColor: tokens.color.primary, borderWidth: 2 },
          "&.Mui-focused": focusRing,
          "&.Mui-disabled": { backgroundColor: tokens.color.canvas },
          "&.Mui-error .MuiOutlinedInput-notchedOutline": { borderColor: tokens.color.error },
        },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: { height: 8, borderRadius: tokens.radius.pill, backgroundColor: tokens.color.primaryContainer },
        bar: ({ ownerState }) => {
          const s = ownerState.color ? SEMANTIC[ownerState.color] : undefined;
          return { borderRadius: tokens.radius.pill, backgroundColor: s ? s.solid : tokens.color.emerald500 };
        },
      },
    },
    MuiDrawer: {
      styleOverrides: { paper: { borderRadius: 0, backgroundColor: tokens.color.surface, border: `1px solid ${tokens.color.outline}` } },
    },
    MuiDialog: {
      styleOverrides: { paper: { borderRadius: tokens.radius.lg, backgroundColor: tokens.color.surface, boxShadow: `0 8px 24px rgba(16,24,40,0.18)`, border: "none" } },
    },
    MuiBackdrop: { styleOverrides: { root: { backgroundColor: "rgba(16,24,40,0.5)" } } },
    MuiLink: { styleOverrides: { root: { color: tokens.color.primary, "&:focus-visible": focusRing } } },
  },
});

declare module "@mui/material/styles" {
  interface Palette {
    emerald: Record<50 | 100 | 200 | 400 | 500 | 600 | 700 | 800 | 900, string>;
  }
  interface PaletteOptions {
    emerald?: Record<number, string>;
  }
}

(theme.palette as typeof theme.palette & { emerald: Record<number, string> }).emerald = {
  50: tokens.color.emerald50,
  100: tokens.color.emerald100,
  200: tokens.color.emerald200,
  400: tokens.color.emerald400,
  500: tokens.color.emerald500,
  600: tokens.color.emerald600,
  700: tokens.color.emerald700,
  800: tokens.color.emerald800,
  900: tokens.color.emerald900,
};
