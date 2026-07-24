/**
 * Per-stage accent theming.
 *
 * Each workspace stage is owned by one agent (STAGE_AGENTS), and each agent already carries
 * its own two-tone identity: `c1` (primary) and `c2` (the lighter shade). This turns that
 * identity into the stage's actual theme, so the Engagement Orchestration window reads green,
 * Campaign Operations red, and Reporting & Insights orange — matching the agent you are
 * talking to in that window's chat pane.
 *
 * Planning & Strategy is deliberately NOT re-themed: the app's blue already belongs to it, so
 * `stageTheme("planning")` returns the base theme untouched and stage 1 renders exactly as before.
 *
 * Why a derived theme rather than a palette override alone: theme.ts bakes the literal
 * `tokens.color.primary` into its component styleOverrides (buttons, links, inputs, progress),
 * so those do not follow `palette.primary`. The overrides below re-state that same set against
 * the stage accent — anything reading `primary.main` from the palette follows automatically.
 */
import { createTheme, alpha, darken } from "@mui/material/styles";
import { theme } from "./theme";
import { tokens } from "./tokens";
import { STAGE_AGENTS, type StageAgentId } from "../workspace/types";

const cache = new Map<StageAgentId, typeof theme>();

export function stageTheme(agent: StageAgentId) {
  // Stage 1 keeps the house blue — nothing to derive.
  if (agent === "planning") return theme;

  const cached = cache.get(agent);
  if (cached) return cached;

  const { c1, c2 } = STAGE_AGENTS[agent];
  const dark = darken(c1, 0.2);
  // Stand-ins for the blue-derived container tokens, tinted from the stage accent.
  const container = alpha(c1, 0.1);
  const focusRing = `0 0 0 3px ${alpha(c1, 0.35)}`;

  const derived = createTheme(theme, {
    palette: {
      primary: { main: c1, light: c2, dark, contrastText: "#FFFFFF" },
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          "::selection": { background: container, color: tokens.color.text },
        },
      },
      MuiButton: {
        styleOverrides: {
          containedPrimary: {
            backgroundColor: c1,
            "&:hover": { backgroundColor: dark },
          },
          outlinedPrimary: {
            color: c1,
            borderColor: c1,
            "&:hover": { backgroundColor: container, borderColor: c1 },
          },
          textPrimary: {
            color: c1,
            "&:hover": { backgroundColor: container },
          },
        },
      },
      MuiLink: {
        styleOverrides: {
          root: { color: c1, "&:focus-visible": { boxShadow: focusRing } },
        },
      },
      MuiLinearProgress: {
        styleOverrides: {
          root: { backgroundColor: container },
          bar: { backgroundColor: c1 },
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: c1 },
            "&.Mui-focused .MuiOutlinedInput-notchedOutline": { borderColor: c1, borderWidth: 2 },
          },
        },
      },
      MuiTab: {
        styleOverrides: {
          root: { "&.Mui-selected": { color: c1 } },
        },
      },
      MuiTabs: {
        styleOverrides: {
          indicator: { backgroundColor: c1 },
        },
      },
    },
  });

  cache.set(agent, derived);
  return derived;
}

/** The accent pair for a stage, for the handful of places that style with raw token strings
 *  (CSS variables, inline SVG) rather than through the MUI palette. */
export function stageAccent(agent: StageAgentId) {
  if (agent === "planning") {
    return { primary: tokens.color.primary, light: tokens.color.primaryContainer };
  }
  const { c1, c2 } = STAGE_AGENTS[agent];
  return { primary: c1, light: c2 };
}
