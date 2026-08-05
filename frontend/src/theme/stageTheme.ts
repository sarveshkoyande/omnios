/**
 * Stage colour — one product identity, four stage personalities.
 *
 * The product is Omni blue. Always. Top bar, sub-bar, buttons, links, inputs, focus rings,
 * panel headers, section labels, rails — none of them change when you move between stages.
 * The user must never be able to mistake a stage for a different application.
 *
 * A stage's own colour is a *marker*, not a paint job. It appears in a fixed, small set of
 * places (see `stageMark` below) and nowhere else. Everything that used to repaint the chrome
 * now resolves to blue by construction: `accent.*` carries the brand values and has no stage
 * variable behind it any more.
 *
 * Two exports, two meanings — pick deliberately:
 *
 *   accent      product chrome. Always Omni blue. The default for anything structural.
 *   stageMark   the stage's own hue. Only for the sanctioned marker slots.
 *
 * The sanctioned marker slots (this list is the budget — adding to it is a design change):
 *   1. the stage icon in the page head
 *   2. the active workspace tab (its number chip + top edge)
 *   3. the agent avatar ring and the 2px rule under the chat-pane header
 *   4. the 4px left edge of an agent's chat bubble
 *   5. the active row indicator in the left section rail
 *   6. highlight / recommendation badges on content the agent is pointing at
 *
 * Charts are NOT on that list. Data visualisation uses the semantic palette in
 * `stages/reporting/dashboardKit.tsx` (`dataColor`), where hue means status — painting a series
 * in the agent's brand colour would make an identity read as a measurement.
 */
import { alpha, darken } from "@mui/material/styles";
import { tokens } from "./tokens";
import { STAGE_AGENTS, type StageAgentId } from "../workspace/types";

/** The raw stage hue pair, for the handful of call sites that style with literal strings
 *  (inline SVG, CSS variables) rather than through a token. */
export function stageAccent(agent: StageAgentId) {
  if (agent === "planning") {
    return { primary: tokens.color.primary, light: tokens.color.primaryContainer };
  }
  const { c1, c2 } = STAGE_AGENTS[agent];
  return { primary: c1, light: c2 };
}

/**
 * CSS custom properties carrying the stage marker hue, published on the workspace subtree.
 *
 * Only the marker vars are emitted. The chrome variables this module used to publish
 * (`--stage-primary`, `--stage-primary-container`, ...) are deliberately gone: `accent.*`
 * below still reads them with `var(name, blue)`, so with nothing setting them every piece of
 * chrome falls back to brand blue in every stage — including Planning, which never differed.
 */
export function stageVars(agent: StageAgentId): Record<string, string> {
  const { primary } = stageAccent(agent);
  return {
    "--stage-mark": primary,
    // Soft wash for a badge or highlight chip sitting on white.
    "--stage-mark-soft": alpha(primary, 0.12),
    // Readable ink on that wash.
    "--stage-mark-ink": darken(primary, 0.45),
  };
}

/** `var(--name, fallback)` helper so call sites stay readable and always degrade to blue. */
export const stageVar = (name: string, fallback: string) => `var(${name}, ${fallback})`;

/**
 * Product chrome. Reads the (no longer emitted) stage chrome variables, so it always resolves
 * to its Omni-blue fallback. Kept as an indirection rather than inlined so there is exactly one
 * place to look if the product identity ever needs to shift again.
 */
export const accent = {
  primary: stageVar("--stage-primary", tokens.color.primary),
  primaryDark: stageVar("--stage-primary-dark", tokens.color.primaryDark),
  container: stageVar("--stage-primary-container", tokens.color.primaryContainer),
  onContainer: stageVar("--stage-on-primary-container", tokens.color.onPrimaryContainer),
  tint12: stageVar("--stage-tint-12", "rgba(3, 78, 162, 0.12)"),
  tint04: stageVar("--stage-tint-04", "rgba(3, 78, 162, 0.04)"),
} as const;

/**
 * The stage's own hue — for the marker slots listed at the top of this file only.
 * Outside the workspace subtree the variables are unset and this is blue, which is correct:
 * Home, Library and Prompt Library belong to no stage.
 */
export const stageMark = {
  primary: stageVar("--stage-mark", tokens.color.primary),
  soft: stageVar("--stage-mark-soft", tokens.color.primaryContainer),
  ink: stageVar("--stage-mark-ink", tokens.color.onPrimaryContainer),
} as const;
