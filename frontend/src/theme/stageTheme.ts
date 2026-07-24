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

/**
 * CSS custom properties carrying the stage accent.
 *
 * A large amount of this app's chrome is styled with the *literal* strings from tokens.ts
 * (`tokens.color.primary`, `primaryContainer`, `onPrimaryContainer`) rather than through the
 * MUI palette — section-card headers, section labels, stage icons. Those cannot follow a
 * ThemeProvider palette override, which is why stage 2 stayed blue after the palette work.
 * Emitting the accent as CSS variables lets those call sites opt in one at a time by swapping
 * a literal for `var(--stage-x, <the original literal>)`: inside a stage the variable wins,
 * and anywhere else in the app the fallback keeps today's colours exactly.
 *
 * Planning resolves to the existing blue tokens, so stage 1 is unchanged by construction.
 */
export function stageVars(agent: StageAgentId): Record<string, string> {
  if (agent === "planning") {
    return {
      "--stage-primary": tokens.color.primary,
      "--stage-primary-dark": tokens.color.primaryDark,
      "--stage-primary-light": tokens.color.primaryContainer,
      "--stage-primary-container": tokens.color.primaryContainer,
      "--stage-on-primary-container": tokens.color.onPrimaryContainer,
      "--stage-tint-12": alpha(tokens.color.primary, 0.12),
    };
  }
  const { c1, c2 } = STAGE_AGENTS[agent];
  return {
    "--stage-primary": c1,
    "--stage-primary-dark": darken(c1, 0.2),
    "--stage-primary-light": c2,
    // Soft header/---container tint derived from the accent, standing in for primaryContainer.
    "--stage-primary-container": alpha(c1, 0.12),
    // Readable ink on that tint.
    "--stage-on-primary-container": darken(c1, 0.45),
    "--stage-tint-12": alpha(c1, 0.12),
  };
}

/** `var(--name, fallback)` helper so call sites stay readable and always degrade to today's colour. */
export const stageVar = (name: string, fallback: string) => `var(${name}, ${fallback})`;

/** The four accents most call sites need, pre-wrapped with their current-blue fallbacks. */
export const accent = {
  primary: stageVar("--stage-primary", tokens.color.primary),
  primaryDark: stageVar("--stage-primary-dark", tokens.color.primaryDark),
  container: stageVar("--stage-primary-container", tokens.color.primaryContainer),
  onContainer: stageVar("--stage-on-primary-container", tokens.color.onPrimaryContainer),
  tint12: stageVar("--stage-tint-12", "rgba(3, 78, 162, 0.12)"),
} as const;
