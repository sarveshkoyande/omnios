---
type: Concept
title: DESIGN_BRIEF
timestamp: 2026-07-18T09:50:18Z
---

Use the `material-ui-styling` skill for this work.

> **Sync note (2026-07-18, 3rd revision):** this file documents the **Vivid Card System**,
> which replaced the flat single-accent "shadcn" look from the previous revision. Per
> `CLAUDE.md`, **`frontend/src/theme/tokens.ts` remains authoritative** over this document;
> if they disagree in the future, trust the code. History: **v1** was "light liquid glass"
> (blur, translucent milk-glass panels, drifting mist background) — dropped for being read
> as dated/heavy. **v2** replaced it with a flat, single-accent, shadcn-style neutral palette
> — dropped for reading as monochrome and low-energy ("everything is one color, it looks
> bad"). **v3 (current)** is a multi-color, card-forward system: a real two-stop brand
> gradient, four semantic status colors each with a soft-tint pill treatment, a pale
> blue-tinted page background with white cards, and *deliberately visible* borders on every
> card/panel/button — "clear boundaries" was explicit direction, not a nice-to-have.

## Mission

Apply this design language consistently across the entire OmniOS application. A reference
screen already exists (the Workspace screen: two-pane agent conversation + stage pipeline);
codify its look into a token system and component primitives, then bring every other
screen, state, and component up to exactly this standard. Do not invent a new direction —
extend this one with precision.

The design language is **Vivid Card System**: a pale blue-tinted page hosting white,
clearly-bordered cards; a saturated blue→violet gradient app bar as the one chrome moment;
and four semantic colors (success/warning/info/danger) each with a solid + soft-tint + ink
trio, used only for status meaning — never decoration. Confident and legible, not loud:
color always tells you something.

## Design tokens (single source of truth — `frontend/src/theme/tokens.ts`)

```ts
color: {
  // Brand — a real gradient, not a flattened single accent.
  primary:   "#2451C4",  // brand blue — gradient start, primary actions, active nav, focus ring
  secondary: "#7C3AED",  // brand violet — gradient end, second accent (e.g. "agent recommended")
  magenta:   "#7C3AED",  // alias of secondary
  // Ink — three-tier hierarchy, deliberately cool-blue-biased (never pure black/grey)
  text:      "#12162B",
  inkSoft:   "#5C6478",
  inkFaint:  "#8890A4",
  // Status — solid + soft-tint + on-tint-ink trio per intent. Used for pills, badges,
  // card-rail accents (a colored left border on a card, per intent).
  success: "#12946B", successSoft: "#E3F6EE", successInk: "#0B6B4C",
  warning: "#C2760A", warningSoft: "#FBEEDC", warningInk: "#8F5808",
  info:    "#1B87C9", infoSoft:    "#E1F1FC", infoInk:    "#12628F",
  danger:  "#D6304A", dangerSoft:  "#FCE6E9", dangerInk:  "#A11F35",
  // Surfaces
  surface:     "#FFFFFF", // cards, popovers, dialogs
  bgBase:      "#F3F5FB", // page background — pale blue tint, not flat white/grey
  bgBaseChat:  "#EAEEFA", // secondary tinted surface — chat pane, panel footers/frames
  border:       "#DDE2F0", // hairline dividers, subtle separators
  borderStrong: "#C2C9E0", // card/panel/button boundaries — deliberately visible
  input: "#E4E8F2",
  ring:  "#2451C4",
  accentSurface:     "#EAEEFC", // pale brand-tinted surface (hover/selected rows)
  accentSurfaceText: "#3B2E86",
}
fontSize: { xs:12, sm:13, md:14, lg:16, xl:20, xxl:24, display:32 }
font.primary: `"Segoe UI", "Segoe UI Variable", system-ui, -apple-system, "Roboto", sans-serif`
spacingUnit: 4   // theme.spacing(1|2|3|4|6|8) = 4/8/12/16/24/32
radius: { sm:8, md:12, lg:16, pill:999 }   // card-forward — larger/rounder than v2's form-control scale
```

```
glass.panel        #FFFFFF                          // solid card white — no translucency
glass.panelStrong   #EAEEFC (accentSurface)          // hovered/selected emphasis
glass.content       #FFFFFF
glass.blur / blurLight   "none"                      // no blur anywhere — color + borders do the work
glass.border        1.5px solid #C2C9E0 (borderStrong)  // deliberately visible
glass.borderTint    1.5px solid rgba(36,81,196,0.35)
glass.shadow         0 1px 2px rgba(18,22,43,0.04)   // barely-there — borders carry separation, not shadow
glass.shadowElevated 0 4px 10px -2px rgba(18,22,43,0.12), 0 16px 40px -16px rgba(36,81,196,0.22)
glassFallback        #FFFFFF
gradientBrand         linear-gradient(30deg, #2451C4, #7C3AED)   // real 2-stop gradient, 30° angle
gradientBrandVertical linear-gradient(180deg, #2451C4, #7C3AED)
```

Helpers: `shade(alpha)` = ink (`rgba(18,22,43,·)`) at alpha; `light(alpha)` = white at alpha;
`indigoTint(alpha)` = brand-blue (`rgba(36,81,196,·)`) at alpha; `violetTint(alpha)` =
brand-violet (`rgba(124,58,237,·)`) at alpha, used more sparingly (second-accent chips like
"agent recommended"). `focusRing` = 2px solid primary + 2px offset; `focusRingOnBrand` = same
in white, for use on the gradient app bar.

**MUI gotcha (read before adding a color):** every value that feeds `palette.*.main`
(primary/secondary/success/warning/error/info) **must be hex/rgb/hsl, never `oklch()`** —
MUI's `createPalette()` unconditionally runs `lighten()`/`darken()` on every intent's `main`
(even when `contrastText` is supplied), and its color parser only understands
`#nnn`/`#nnnnnn`/`rgb()`/`rgba()`/`hsl()`/`hsla()`/`color()`. An `oklch()` string throws
synchronously inside `createTheme()` and blanks the entire app on load. Every color in
`tokens.ts` is plain hex for exactly this reason — don't reintroduce `oklch()` there.

**Font:** the whole app runs on the Segoe UI stack that actually ships on Windows — no
borrowed webfont pitched then silently falling back. Data/figures (scores, percentages,
material numbers, ID codes) use this *same* stack with `font-variant-numeric: tabular-nums`
at the call site, not a separate decorative monospace face — `tokens.font.mono` was removed
for exactly this reason (it was `"Geist Mono"`, never actually loaded, silently falling back
anyway).

## The one saturated chrome moment: the app bar

`MuiAppBar` is `gradientBrand` at 30°, white text/icons, sticky, no border (the gradient
itself is the definition against the page). This is the only *chrome* saturated region.
Beyond it, the brand gradient/colors show up only in specific, deliberate spots:
- **Primary buttons** (`MuiButton` `contained`, default): `gradientBrand`, white text.
- A `color` prop on `Button`/`Chip`/`LinearProgress` (`success`/`warning`/`error`/`info`/
  `secondary`) **overrides** the default gradient/glass look with that intent's solid or
  soft-tint treatment (see below) — implemented as `ownerState`-aware theme overrides so a
  Delete button (`color="error"`) actually renders red, not the brand gradient.
- **WorkflowStepper's sliding indicator** and **UserBubble** chat bubbles: `gradientBrand`.
- A small `gradientBrand` accent dot on `AgentBubble` (top-left corner).
- **StatusPill chips** in the app bar: translucent white (`rgba(255,255,255,0.18)` fill,
  `rgba(255,255,255,0.32)` border) — deliberately *not* gradient-filled, or they'd blend
  into the bar itself.

Everything else is white/ink/status-color. If a design decision would add a new saturated
*chrome* region beyond the app bar, the answer is no — status color for meaning is fine
anywhere.

## Semantic status system (new in v3)

Four intents, each a solid/soft-tint/ink trio: **success** (mint green — high-potential,
approved, quality), **warning** (amber — needs attention, mid-confidence), **info** (sky
blue — neutral/informational), **danger** (coral red — destructive, error). Wired at the
theme level, not per-screen:
- `Chip` with `color="success"|"warning"|"error"|"info"` renders a soft-tint pill
  (`successSoft` background, `successInk` text, no border) instead of the default glass
  chip — a status Chip should read as green/amber/blue/red at a glance.
- `Button variant="contained" color="error"` (etc.) renders that intent's *solid* color, not
  the brand gradient — e.g. `PlansDrawer`'s Delete button.
- `LinearProgress color="success"` (etc.) renders that intent's solid bar color, not the
  brand gradient.
- A **colored card rail** (a 3–4px solid-color left border on an otherwise neutral-bordered
  card) is the pattern for a card whose whole point is a status, e.g. `ClaimCard`'s
  approved/in-review/draft rail. Card body stays `glass.border` (neutral); only the left
  edge carries the status color.

## Clear boundaries (hard rule)

Every card, panel, chip, and button has a **visible** `1.5px` border (`glass.border` /
`tokens.color.borderStrong`), not a hairline. Shadows are kept nearly imperceptible
(`glass.shadow`) — separation between "boxes" comes from the border + the white-card-on-
tinted-page contrast, not from elevation. This was explicit, repeated direction: "very clear
boundaries for each box."

## Component recipes (match the live app)

- **Top nav** (`App.tsx`): plain text links directly on the gradient app bar — translucent
  white (`rgba(255,255,255,0.72)`) inactive, solid white + bold + underline for the current
  page. *Not* the earlier white circular "bud" pill mechanism — that was designed for a flat
  white bar and would visually disappear against a colored one.
- **WorkflowStepper** (`WorkflowStepper.tsx`): a single full-width white `Bar`
  (`radius.pill`, visible border) holds 4 equal-width step buttons. A `gradientBrand`
  `IndicatorSolid` pill plus a blurred `IndicatorGlow` slide beneath the active step (560ms
  bouncy cubic-bezier). States: active = white text over the sliding pill; locked = `lock`
  icon + dimmed ink; done = `check_circle` icon; idle = plain ink text with the stage's icon.
- **Workspace two-pane layout** (`Workspace.tsx`): left chat pane on `bgBaseChat` (tinted,
  not glass), right stage pane on translucent white. Neither pane container carries its own
  border-radius — card treatment lives on the content inside.
- **Chat bubbles** (`ChatBubble.tsx`): `AgentBubble` = white card, `borderTopLeftRadius: 4`,
  small `gradientBrand` accent dot top-left. `UserBubble` = solid `gradientBrand` fill, white
  text, right-aligned. `TurnBubble` = white card with a 4px solid accent-color left edge —
  same "colored rail" idiom as `ClaimCard`. `StatusLine` = no bubble, a pulsing dot + italic
  caption.
- **Status-rail cards** (`ClaimCard.tsx` and the same idiom elsewhere): white card, visible
  neutral border, 4px solid status-color left rail; the status label itself is a soft-tint
  `Chip` (see semantic system above), not a solid-fill chip.
- **Intake / brief card** (`IntakeCard.tsx`): white panel, 32px padding, `edit_note` icon +
  header. Dashed-border upload dropzone, 9-row pre-filled `TextField`, "Skip" text link +
  gradient primary button footer row.
- **Chat composer**: white rounded field, attach/mic icon buttons in `inkSoft`, send button
  a small `gradientBrand` rounded square with a slow traveling blue→violet glow while there's
  text (`Composer.tsx`'s `GlowWrap`).
- **Buttons**: primary = `gradientBrand` (or a semantic solid color per `color` prop), white
  text. Secondary/outlined = white with a *visible* border. Tertiary/text = plain ink link.
- **Pill chips**: default = bordered white/glass pill; semantic `color` = soft-tint pill.
- **Empty states**: never blank — an italic `inkSoft` sentence describing what will appear.

## Typography

Segoe UI stack throughout (`font.primary`) — no separate display or data face. Scale
12/13/14/16/20/24/32. Section labels (`overline` variant): 12px, small caps, +0.08em
letter-spacing, brand-blue primary. Body in `text`, helper copy in `inkSoft`, tertiary
metadata in `inkFaint`.

## Voice & microcopy

Conversational, confident, second person, em-dash friendly: "Fill in the blanks below — or
paste your own brief in any wording." Buttons name the action ("Extract brief", not
"Submit"). Helper text explains what the system will do next, in the interface's voice.
Keep this register on every new screen.

## Accessibility & fallbacks (hard requirements)

- Text contrast ≥ 4.5:1 on every surface; `text` on `surface`/`bgBase` must pass everywhere.
- `prefers-reduced-transparency: reduce` and `prefers-contrast: more` collapse `.glass-surface`
  to `glassFallback` with a stronger border (global `MuiCssBaseline` override) — mostly moot
  now that surfaces are already opaque by default, but kept as an explicit guarantee.
- `prefers-reduced-motion: reduce` collapses animation/transition durations to 0.01ms
  globally.
- Keyboard-first: visible 2px brand-blue focus outline with offset (`focusRing`/
  `focusRingOnBrand` on the gradient app bar), logical tab order, focus trap in modals.
  Locked stepper steps are focusable and announce their locked state.

## Implementation rules (Material UI)

- All values above live in `frontend/src/theme/tokens.ts`; no raw hex/rgba/oklch in
  components — `theme.ts` derives the MUI theme from it via `createTheme({ components })`.
  Treat `tokens.ts` as authoritative over this document if they ever disagree again.
- Semantic color propagation is theme-level, not per-screen: `MuiButton`'s `contained` slot,
  `MuiChip`'s `root` slot, and `MuiLinearProgress`'s `bar` slot are `ownerState`-aware
  functions that branch on the `color` prop (success/warning/error/info/secondary) — adding
  a `color="success"` prop anywhere in the app gets the vivid treatment automatically, no
  local `sx` override needed.
- App-wide defaults via theme `components` overrides: `MuiAppBar` (gradient), `MuiPaper`/
  `MuiCard` (white, visible border, `radius.md`), `MuiDialog` (white, visible border,
  `radius.lg`), `MuiOutlinedInput` (white content field), `MuiChip`/`MuiButton`/
  `MuiLinearProgress` (semantic-aware per above), `MuiBackdrop` (ink scrim, no blur).
- Reusable primitives via `styled()`: `GlassPanel`/`GlassBase` (tier prop, now flat/bordered
  not glass), chat primitives (`AgentBubble`, `UserBubble`, `TurnBubble`, `StatusLine`,
  `ClarifyBadge`), `BrandButton`, `StatusPill`, `WorkflowStepper`'s
  `Bar`/`IndicatorSolid`/`IndicatorGlow`, `Composer`, `IntakeCard`.
- `sx` only for genuine one-off local adjustments; never scatter overrides where a theme
  rule belongs.
- Two deliberately **non**-token-driven color maps exist and should stay that way — they're
  functional multi-hue legends, not brand decoration: `workspace/planDocSkinCss.ts`
  (4-color toolkit-phase legend) and the flow-builder's per-category colors
  (`flowbuilder/nodes/styleDefaults.ts`'s `CATEGORY_COLORS`,
  `flowbuilder/canvas/LaneNode.tsx`'s `KIND_COLOR`).
- `flowbuilder.css` mirrors the core tokens as plain CSS custom properties (`--bg`,
  `--panel-bg`, `--border`, `--text`, `--text-muted`, `--accent`) scoped under
  `.wf-campaign-shell`, since that tool predates the token system and isn't a React/MUI
  surface — keep these in sync by hand whenever the brand/ink/border tokens change.

## Process — gates, not vibes

- **Phase 0 — Audit:** inventory every screen, route, and component; mark each as "matches
  reference" / "needs rework" / "missing states". List them.
- **Phase 1 — Codify (STOP for approval):** produce/update `tokens.ts` and the primitive
  component specs, plus a one-screen mockup showing how a non-reference screen adopts the
  system. **Do not restyle screens until approved.** (For v3, this was a published design
  concept artifact, iterated with the client before touching the app.)
- **Phase 2 — Foundation:** tokens, theme, primitives; verify the reference screen
  (Workspace) renders pixel-faithfully from the new primitives (this is the regression test).
- **Phase 3 — Screen-by-screen:** migrate each remaining screen. After each, screenshot,
  self-critique against this brief (chrome-saturation discipline, boundary visibility,
  semantic-color correctness, voice), fix, move on. Not yet complete for v3 — the foundation
  (tokens/theme/app-bar/nav) and the systemically-propagated pieces (any `color="..."` Chip/
  Button/LinearProgress, any hardcoded brand-hex call site) are done; per-screen ad-hoc
  micro-borders and bespoke card layouts are the remaining Phase 3 work.
- **Phase 4 — QA gate:** contrast on all surfaces; reduced-motion/-transparency/contrast
  modes; keyboard traversal incl. locked steps; performance budget; zero raw color values
  outside `tokens.ts`; every empty state has its sentence.

Elegance here is restraint executed precisely — color always means something. When
aesthetics and accessibility conflict, accessibility wins — find a solution that satisfies
both.
