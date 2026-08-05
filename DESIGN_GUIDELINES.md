# OmniOS — Design Guidelines

Extracted from the running code on 2026-08-03; §2.5 (stage colour) rewritten 2026-08-05.
**`frontend/src/theme/tokens.ts` is
authoritative.** Where this document and the code disagree, the code wins — this is a
description of the system, not a specification for it.

Related: `DESIGN_BRIEF.md` documents the *Vivid Card System* revision and its history.
This file is the current, code-level reference.

---

## 1. The short version

A **flat, high-contrast Material language**. Opaque white surfaces on a cool grey canvas,
separated by 1px outlines rather than shadows. Colour is used for meaning — never for
decoration. Depth is expressed with borders and containment, not elevation.

Four rules that explain most of the system:

1. **One product identity, four stage personalities.** The application is Omni blue
   everywhere. A stage's colour is a *marker* in a fixed handful of places, never a repaint
   of the chrome — see §2.5, which is the rule this system is most likely to be broken by.
2. **Every runtime colour comes from `tokens.color`.** No literal hex in components.
3. **Borders, not shadows.** `glass.shadow` is `"none"`. Only overlays that genuinely float
   (popovers, modals) may use `glass.shadowElevated`.
4. **Surfaces are opaque.** No translucency, no backdrop blur — see §7 for why.

---

## 2. Colour

### Brand

| Token | Hex | Use |
|---|---|---|
| `primary` | `#034EA2` | Brand blue. Actions, links, focus rings, active state. |
| `primaryDark` | `#023B7A` | Hover/pressed on primary. |
| `secondary` | `#047857` | Emerald. Secondary actions, the second stop in gradients. |
| `secondaryDark` | `#065F46` | Hover/pressed on secondary. |

### Neutrals

| Token | Hex | Use |
|---|---|---|
| `ink` / `text` | `#101828` | Primary text. |
| `inkSecondary` / `inkSoft` | `#475467` | Secondary text, captions, placeholders. |
| `surface` | `#FFFFFF` | Every card, panel and well. |
| `canvas` / `bgBase` | `#F4F6F8` | Page background. |
| `outline` | `#D0D7DE` | Default 1px border. The workhorse. |
| `outlineStrong` | `#8C959F` | Emphasised border, scrollbar thumb hover. |
| `topBar` | `#000000` | Top bar only. |

### Semantic

Each state ships as a **solid / soft / ink** triad — solid for fills, soft for backgrounds,
ink for text on soft.

| State | Solid | Soft | Ink |
|---|---|---|---|
| Success | `#047857` | `#D1FAE5` | `#047857` |
| Warning | `#C2410C` | `#FFEDD5` | `#9A3412` |
| Error / danger | `#B42318` | `#FEE4E2` | `#B42318` |
| Info | `#034EA2` | `#E3EDFA` | `#012F63` |

`primaryContainer` `#E3EDFA` / `onPrimaryContainer` `#012F63` are the accent-surface pair
used for section headers and selected rows.

### Tint helpers

Use these instead of hand-mixing alpha:

```ts
shade(a)       // rgba(16, 24, 40, a)   — ink at alpha
light(a)       // rgba(255, 255, 255, a)
indigoTint(a)  // rgba(3, 78, 162, a)   — primary at alpha
violetTint(a)  // rgba(4, 120, 87, a)   — secondary at alpha (name is historical)
```

`indigoTint(0.08)` is the standard hover wash; `indigoTint(0.1)` the standard hairline.

### 2.5 Stage colour — the marker budget

Each workspace stage is owned by one agent, and each agent has a hue (`STAGE_AGENTS` in
`workspace/types.ts`):

| Stage | Agent | Hue |
|---|---|---|
| 1 Planning & Strategy | Campaign Planning & Strategy | `#1768D1` blue |
| 2 Engagement Orchestration | Engagement Orchestration | `#047857` green |
| 3 Campaign Operations | Campaign Operations | `#cc0047` magenta |
| 4 Reporting & Insights | Reporting & Insights | `#e14b1e` orange |

**The product has one identity; the stages have four personalities.** Until 2026-08-05 the
stage hue was pushed through the whole MUI palette and the chrome: the top bar, the sub-bar,
every button, link, input, focus ring, panel header, section label and rail turned green in
stage 2 and orange in stage 4. Moving between tabs read as switching applications rather than
moving between sections of one, and the title + subheader bar changing colour per tab was the
loudest part of it. That is gone.

A stage hue may now appear in exactly these places — this list **is** the budget, and adding
to it is a design decision, not an implementation detail:

1. the stage icon in `StageHead`
2. the active `WorkflowStepper` tab — its number chip and its 3px top edge
3. the agent avatar ring, and the 2px rule under the chat-pane header
4. the 4px left edge of an agent chat bubble
5. the active row indicator in `PlanSectionsRail` / `StageSectionRail`
6. highlight / recommendation badges on content the agent is pointing at

Everything else — including every control the user can press — is brand blue.

**Charts are not on the list.** Data visualisation uses the semantic palette in
`stages/reporting/dashboardKit.tsx` (`dataColor`): blue is information, green at-or-above
benchmark, amber drifting, red breakage. A series painted in the agent's hue makes an identity
read as a status.

Two exports in `theme/stageTheme.ts` carry this split — pick deliberately:

```ts
accent      // product chrome. Always Omni blue. The default for anything structural.
stageMark   // the stage's own hue. Marker slots only.
```

Both are `var(--name, blue)` strings. `stageVars(agent)` publishes only the marker variables
(`--stage-mark`, `--stage-mark-soft`, `--stage-mark-ink`) on the workspace subtree; nothing
sets the chrome variables any more, so `accent.*` resolves to its blue fallback by
construction — in every stage, and on Home / Library, which belong to no stage.

There is no per-stage MUI theme. `stageTheme()` and its palette/component overrides were
deleted; `<ThemeProvider>` no longer wraps the workspace.

**Three patterns to reach for instead of colour:**

- *A coloured 4px left edge, not a coloured panel.* The Home stage cards are the reference:
  white surface, hairline border, coloured left edge, coloured avatar, blue button.
- *A rule, not a band.* A heading is closed by a 1px outline rule; the icon beside it carries
  the hue. No filled title bar.
- *Different imagery, not different paint.* Stages are told apart faster by their iconography
  — blueprint/nodes for planning, journey/touchpoints for orchestration, workflow/automation
  for operations, charts/analytics for reporting — than by being repainted.

---

## 3. Typography

Single family: **`'Nunito Sans', 'Segoe UI', system-ui, sans-serif`**.

| Token | px | Applied to |
|---|---|---|
| `xs` | 15 | Captions, chips, table cells, rail rows |
| `sm` | 15 | Body 2, buttons, option labels |
| `md` | 15 | Body 1, textarea input |
| `lg` | 17 | h3, panel titles |
| `xl` | 20 | Chat pane header |
| `xxl` | 24 | h2 |
| `display` | 28 | h1 |

Weights: **800** h1, **700** h2/h3/buttons/emphasis, **400** body. There is no 500 or 600
in the scale — if something needs emphasis it goes to 700.

`h1` carries `letterSpacing: -0.01em`. **Overline** is the section-label style: 13px, 700,
`0.6px` tracking, uppercase, primary blue, `lineHeight: 1.4`.

**15px is a hard floor (2026-08-04).** Nothing in the product may render text below it. The app
used to run at 13/14 with a long tail of 8.5–12px literals in chips, badges, table cells and the
plan-document skin; that text was unreadable and failed accessibility guidance, so 291 literals
were raised in one pass and `xs`/`sm` were collapsed onto 15.

Consequences worth knowing:

- `xs`, `sm` and `md` are now the **same size**. They survive as names only so existing call
  sites keep compiling — prefer `md` in new code.
- **Hierarchy comes from weight and colour, not size.** 400 vs 700, ink vs `inkSecondary`. Do
  not reach for a smaller size to demote something.
- Chips and badges holding text need **`height: 24` minimum**; 18–20px chips clip a 15px line.
- Do not add a literal `fontSize` below 15 anywhere, including inside CSS-in-string blocks
  (`planDocSkinCss.ts`) and plain `.css` files.

---

## 4. Space, shape, icons

- **Spacing unit: 4px.** MUI `theme.spacing(n)` = `4n`. Common: `p: 2` (8px), `px: 2, py: 1.5`.
- **Radius:** `sm: 4` (buttons, inputs, send key), `md: 8` (panels, cards, wells),
  `lg: 12`, `pill: 999` (chips, scrollbar thumbs).
- **Default shape** is `sm` — MUI `shape.borderRadius` is 4.
- **Icons:** Material Symbols Outlined, `FILL 0, wght 450, GRAD 0, opsz 24`, rendered at
  17–20px inline. Always `verticalAlign: middle`.

---

## 5. Surfaces and components

### Panel tiers (`src/glass/primitives.tsx`)

| Tier | Background | Border | Shadow | Use |
|---|---|---|---|---|
| **A** | `surface` | `outline` | none | Default panel |
| **B** | `primaryContainer` | `primary` | none | Accented / selected panel |
| **0** | `surface` | `outline` | none | Content well inside a panel |

`GlassPanel` sets `overflow: hidden` and `borderRadius: md`. The name is historical (§7).

### Building blocks

- **`SectionCard`** — panel with an accent header bar (`accent.container` background,
  bottom outline), optional icon, uppercase label, optional collapse chevron that rotates
  180° over `160ms ease`.
- **`DefinitionRow`** — label left, value right at weight 700, `1px` bottom outline, last
  row borderless. Empty values render `N/A` in secondary ink, never blank.
- **`PillChip`** — 26px tall, white, 1px outline, no shadow. Optional 8px success dot.
- **`BrandButton`** — contained, radius `sm`, `px: 3`, optional trailing arrow.
- **`ConsolePanel`** — titled container used for the plan/report surfaces.

### Stage accents

`src/theme/stageTheme.ts` exposes `accent` (product blue chrome) and `stageMark` (the stage
hue, marker slots only). Prefer `accent.*` over `tokens.color.primary*` inside stage UI — it
is the single seam to change if the product identity ever shifts. Reach for `stageMark.*`
only when the thing you are colouring is on the §2.5 list.

### Page heads

`StageHead` is the one page title per stage: coloured icon, ink title, secondary blurb, closed
by a 1px `outline` rule. It is not repeated — the agent's name is stated once more, in the chat
pane header directly above that agent's conversation, and nowhere else.

---

## 6. Interaction

- **Focus:** `2px solid primary`, `outlineOffset: 2` (`focusRing`). On a brand-coloured
  background use `focusRingOnBrand` (white ring). Never remove focus visibility.
- **Hover:** `indigoTint(0.08)` wash on icon buttons; `canvas` on option rows. **Always gate
  hover behind the `hoverOnly` media key** (`@media (hover: hover) and (pointer: fine)`) —
  touch devices fire `:hover` on tap and leave it stuck.
- **Pressed:** every pressable surface scales down. `0.97` buttons, `0.92` icon buttons,
  `0.94` the primary send key, `0.98` rows and option buttons, `0.995` full-width cards.
  Larger surface, smaller scale. Buttons also brighten via `filter: brightness(1.08)`.
- **Selection:** `::selection` is `primaryContainer` on ink.
- **Scrollbars:** thin, 12px, `outline` pill thumb with a 3px transparent border
  (`backgroundClip: content-box`), transparent track, `outlineStrong` on hover.

### Motion tokens

`tokens.ts` exports `motion`. **Never write a bare `ease` or a raw duration** — the built-in
CSS curves are too weak to read as intentional at these durations.

| Token | Value | Use |
|---|---|---|
| `motion.easeOut` | `cubic-bezier(0.23, 1, 0.32, 1)` | Enter, exit, and anything the user triggered |
| `motion.easeInOut` | `cubic-bezier(0.77, 0, 0.175, 1)` | Movement between two on-screen positions |
| `motion.duration.press` | 120ms | `:active` transforms |
| `motion.duration.hover` | 160ms | Colour, border, background |
| `motion.duration.enter` | 220ms | Element entrances |
| `motion.duration.panel` | 260ms | Panel collapse, larger surfaces |

`ease-in` is banned for UI: it delays the first frame — the frame the user is watching — so
it feels slower than `ease-out` at an identical duration. Nothing may exceed 300ms.

**Always name the properties you transition; never `transition: all`.** Only `transform` and
`opacity` are free (GPU, no layout or paint) — animating `height`, `width`, `padding` or
`margin` triggers the full pipeline.

**Prefer transitions over keyframes** for anything that can retrigger rapidly. A transition
retargets from its current value; a keyframe restarts from zero. `SectionCard` collapses via
a `grid-template-rows: 0fr → 1fr` transition for exactly this reason — note that its children
stay mounted, so a collapsed section is held out of the a11y tree with `inert` + `aria-hidden`.

Ambient (infinite) motion needs a purpose beyond decoration, because the user sees it every
session. The two that qualify: the composer glow (§8, gated on `hasText`) and the status/agent
pulse dots, which indicate live work. Decorative infinite loops on static icons were removed.

---

## 7. The glass layer — read this before adding translucency

The `glass` export in `tokens.ts` and the `src/glass/` directory are **the surviving API of
a removed design system**. The original v1 was "light liquid glass": translucent panels,
backdrop blur, and a full-viewport drifting-mist background.

That system was removed on **2026-07-18**. Today:

```ts
glass.blur       = "none"
glass.blurLight  = "none"
glass.shadow     = "none"
glass.panel      = tokens.color.surface   // fully opaque
```

`Atmosphere.tsx` is a no-op that returns `null`. The page background now comes straight
from `MuiCssBaseline`'s `body` rule.

**Consequence:** importing `glass` and expecting frosted translucency gets you a flat white
box. Re-introducing glass is a **token-level change**, not a per-component one — see the
companion prompt in `PROMPT_glow_liquid_glass.md`.

---

## 8. The composer glow — the one ambient effect

`src/workspace/Composer.tsx` is the reference implementation for a glow, and the pattern to
copy rather than reinvent.

```
GlowWrap (position: relative, radius md)
├── ::before  inset -3   blur(7px)   opacity 0.6   ← tight ring
├── ::after   inset -7   blur(15px)  opacity 0.45  ← diffuse halo
└── Well      zIndex 1, opaque #fff                ← content sits on top
```

Both pseudos paint a `conic-gradient(from var(--omni-glow-angle), primary, secondary, primary)`
and run two animations together: `travelCCW` (6s linear, rotates the angle to `-360deg`) and
`glowBreath` (2.8s ease-in-out, opacity 0.21 ↔ 0.3).

Three details that make it work — preserve them:

1. **`--omni-glow-angle` is registered with `@property`** (`syntax: "<angle>"`,
   `inherits: false`, `initialValue: 0deg`). Without that registration a custom property
   animates discretely and the gradient jumps instead of rotating.
2. **The glow lives on the wrapper, not the well.** A negative-z pseudo on the well itself
   paints *above* the well's own background and bleeds through the interior.
3. **It is gated:** `active={hasText && !disabled}`. The glow is feedback that the input is
   live, not permanent decoration.

---

## 9. Checklist

- [ ] Every colour from `tokens.color` — no literal hex
- [ ] Border for separation; shadow only on genuinely floating overlays
- [ ] Type size from the 13/14/15/17/20/24/28 scale; weight 400 or 700
- [ ] Spacing a multiple of 4
- [ ] Focus ring intact and visible
- [ ] Easing and duration from `motion`; no bare `ease`, no `transition: all`, nothing over 300ms
- [ ] Hover gated behind `hoverOnly`; every pressable surface has an `:active` scale
- [ ] Chrome (bars, buttons, links, inputs, panel headers, rails) is `accent.*` — blue in every stage
- [ ] `stageMark.*` used only for a slot on the §2.5 list; charts use `dataColor`, never the stage hue
- [ ] No empty placeholder panels — render nothing, or render `N/A`
- [ ] Ambient motion justified; anything decorative respects `prefers-reduced-motion`
