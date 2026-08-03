# Prompt — input glow, background glow, liquid glass

Paste the block below into a coding agent working in this repo. It assumes
`DESIGN_GUIDELINES.md` is available for the token reference.

Context it needs to know up front, and the reason this prompt is longer than "add some
glass": the liquid-glass system **used to exist here and was deliberately removed** on
2026-07-18. `glass.blur` is `"none"`, `glass.shadow` is `"none"`, `glass.panel` is opaque
white, and `Atmosphere.tsx` returns `null`. Adding `backdropFilter` to one component
therefore produces a single frosted box floating in a flat app. The work is to restore the
layer coherently.

---

## The prompt

````text
Work in the OmniOS frontend (`frontend/src/`). Read `DESIGN_GUIDELINES.md` first — it is a
code-accurate description of the current design system. Keep every existing token; add to
the system rather than replacing it.

Three related changes. Do them in this order, because each depends on the one before.

────────────────────────────────────────────────────────────
1. RESTORE THE GLASS LAYER AT TOKEN LEVEL
────────────────────────────────────────────────────────────
`frontend/src/theme/tokens.ts` currently exports a flattened `glass` object left over from
a design system that was removed. Reinstate it as a real material, and add the values the
new effects need:

  glass = {
    panel:         "rgba(255, 255, 255, 0.72)",
    panelStrong:   "rgba(227, 237, 250, 0.78)",   // primaryContainer, translucent
    content:       "rgba(255, 255, 255, 0.86)",   // wells: readable, still glassy
    blur:          "blur(20px) saturate(180%)",
    blurLight:     "blur(12px) saturate(140%)",
    border:        `1px solid rgba(255, 255, 255, 0.55)`,
    borderTint:    `1px solid ${indigoTint(0.35)}`,
    shadow:        `0 1px 2px ${shade(0.04)}, 0 8px 24px ${shade(0.06)}`,
    shadowElevated:`0 8px 24px ${shade(0.18)}`,
  }

Add a `glassEdge` helper for the top highlight that sells the material — a 1px inset white
gradient along the upper edge, fading to transparent by ~40%.

Constraints:
  * `backdrop-filter` needs something behind it. It is only legible over the background
    glow from step 2 — do not ship step 1 without step 2.
  * Provide an opaque fallback via `@supports not (backdrop-filter: blur(1px))`. Text
    legibility is not negotiable.
  * Do NOT make every panel glass. Glass is for floating/overlay surfaces: the composer,
    intake cards, popovers, the ask card, stage headers. Dense data surfaces — plan tables,
    the flow builder canvas, report tables — stay opaque. Glass behind a data grid is
    unreadable and looks cheap.

Update `src/glass/primitives.tsx` so tier A becomes the glass surface, tier B the tinted
glass surface, and tier 0 stays effectively opaque (it is the content well that has to keep
text crisp).

────────────────────────────────────────────────────────────
2. BACKGROUND IMAGE GLOW
────────────────────────────────────────────────────────────
Bring back `src/theme/Atmosphere.tsx`, which is currently a no-op returning null. It should
render a fixed, full-viewport, `pointer-events: none`, `zIndex: -1` layer behind everything,
composed of:

  * The flat `tokens.color.canvas` base, so the fallback is the current design.
  * Two or three large, very soft radial gradients — `primary` (#034EA2) and `secondary`
    (#047857) at 6–10% alpha, 40–60vw wide, positioned off-centre and partly off-screen.
    These are the colour bed the backdrop-filter picks up.
  * Optional: a subtle noise/grain overlay at ~2–3% opacity to stop the gradients banding
    on wide displays.

Motion: drift the blobs slowly — 30–60s, `ease-in-out`, `alternate`, translating only a few
percent. It must read as "the light moved slightly", never as an animated wallpaper. Wrap
all of it in `@media (prefers-reduced-motion: reduce)` and hold it static there.

Mount `<Atmosphere />` once at app root, above the router.

Performance: animate `transform` and `opacity` only. No animated `filter`, no animated
`background-position` on a full-viewport element. Add `will-change: transform` to the blobs
and nothing else.

────────────────────────────────────────────────────────────
3. GLOW AROUND CHAT INPUT BOXES
────────────────────────────────────────────────────────────
`src/workspace/Composer.tsx` already implements exactly the glow that is wanted. DO NOT
rewrite it. Extract it and reuse it.

The existing pattern:
  GlowWrap (position relative, radius md)
    ::before  inset -3, conic-gradient(from var(--omni-glow-angle), primary, secondary,
              primary), blur(7px), opacity .6
    ::after   inset -7, same gradient, blur(15px), opacity .45
    Well      zIndex 1, opaque, content sits on top
  animations: travelCCW 6s linear infinite  +  glowBreath 2.8s ease-in-out infinite
  gated by:   active={hasText && !disabled}

Three things about it are load-bearing. Preserve all three:
  a) `--omni-glow-angle` is registered with `@property` (syntax "<angle>"). Without that
     registration the custom property animates discretely and the gradient jumps.
  b) The glow lives on the WRAPPER, not the well. A negative-z pseudo on the well paints
     above the well's own background and bleeds through the interior.
  c) It is gated on input state. It is feedback that the field is live, not decoration.

Tasks:
  * Extract `GlowWrap` (plus the keyframes and the `@property` registration) into
    `src/components/GlowRing.tsx` as a reusable component. Keep the `active` prop.
  * Apply it to every chat/prompt input in the app — at minimum `IntakeCard`,
    `HomeIntakeCard`, and the tab-chat composer. Search for `TextArea`, `InputBase` and
    `placeholder=` to find the rest.
  * With glass now live, change the composer's `Well` from `background: "#fff"` to
    `glass.content` + `backdropFilter: glass.blurLight` + `glassEdge`. Keep it the most
    opaque glass in the app — it holds typed text.
  * Add `@media (prefers-reduced-motion: reduce)` — keep the glow visible as a static ring,
    drop `travelCCW` and `glowBreath`.

────────────────────────────────────────────────────────────
ACCEPTANCE
────────────────────────────────────────────────────────────
  * `npm run build` passes (`tsc -b && vite build`) with no new type errors.
  * Text contrast on every glass surface still meets WCAG AA against the brightest point of
    the background glow behind it. Check the composer over a gradient blob specifically.
  * With `prefers-reduced-motion: reduce`, nothing moves anywhere.
  * With `backdrop-filter` unsupported, every surface falls back opaque and remains legible.
  * Data-dense surfaces (plan tables, flow builder, report tables) are unchanged and opaque.
  * No literal hex in components — everything through `tokens` / `glass` / the tint helpers.
  * Scrolling a long plan document stays at 60fps. If it does not, reduce blur radius before
    reducing blur quality — large `backdrop-filter` areas are the usual cost.
````

---

## Suggested sequencing

The three steps are individually shippable, but the order matters: glass over a flat grey
canvas looks like a bug, so if you only take one step, take **step 2**, and if you take
two, take **2 then 3**. Step 1 is the largest surface-area change and the one most likely to
need contrast tuning.
