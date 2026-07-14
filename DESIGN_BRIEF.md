Use the `glassmorphism`, `frontend-design`, and `material-ui-styling` skills for this work.

## Mission

Apply this design language consistently across the entire OmniOS application. A reference screen already exists (the Workspace screen: two-pane agent conversation + stage pipeline); your job is to codify its look into a token system and component primitives, then bring every other screen, state, and component up to exactly this standard. Do not invent a new direction — extend this one with precision.

The design language is **light liquid glass**: an airy, pale-lavender atmosphere with frosted white ("milk glass") panels, dark indigo-ink text, and exactly one saturated brand moment — the gradient app bar and primary actions. Formal, calm, and highly legible; the glass is felt, never loud.

## Design tokens (single source of truth — derive everything from these)

```css
:root {
  /* Extracted from the reference screen — replace with exact brand-kit values if they differ */
  --brand-indigo:        #4F46E5;   /* app bar gradient start, primary actions */
  --brand-violet:        #7C3AED;   /* app bar gradient end */
  --brand-magenta:       #E935C1;   /* logo mark / rare highlight only — never for UI chrome */
  --ink:                 #1E1B33;   /* primary text, dark indigo-slate */
  --ink-soft:            #55517A;   /* secondary text, helper copy */
  --status-green:        #22C55E;   /* "agents online" dot */

  /* Atmosphere */
  --bg-base:             #E9EAFB;   /* pale periwinkle page base */
  --bg-mist-1:           #C9CFF8;   /* soft blue-violet mist blob */
  --bg-mist-2:           #E3D9FA;   /* soft lavender mist blob */

  /* Glass */
  --glass-panel:         rgba(255, 255, 255, 0.55);
  --glass-panel-strong:  rgba(255, 255, 255, 0.72);
  --glass-content:       rgba(255, 255, 255, 0.92);  /* Tier 0: inputs, tables, long text */
  --glass-blur:          blur(24px);
  --glass-border:        1px solid rgba(255, 255, 255, 0.65);
  --glass-border-tint:   1px solid rgba(79, 70, 229, 0.12);
  --glass-shadow:        0 8px 32px rgba(79, 70, 229, 0.10);
  --radius:              14px;
  --radius-lg:           20px;
  --radius-pill:         999px;

  --gradient-brand:      linear-gradient(90deg, var(--brand-indigo), var(--brand-violet));
}
```

## The atmosphere layer

Fixed, full-viewport pale field: `--bg-base` with two or three very large, heavily blurred radial mist blobs (`--bg-mist-1`, `--bg-mist-2`) drifting imperceptibly slowly (≥ 60s cycles, transform/opacity only, static under `prefers-reduced-motion`). The effect is soft daylight through frosted glass — bright, low-saturation, never busy. This field is what makes the milk-glass panels read; never place panels over flat white.

## The one saturated moment (hard rule)

The **app bar** is the single fully saturated element in the interface: `--gradient-brand` background, solid (not glass), white text and icons, sticky. Inside it: the logo mark, product name, section title, nav items as transparent-text-on-gradient with the **active item as a white pill with indigo text**, and right-aligned translucent white pill chips (status chips may carry a `--status-green` dot). Primary action buttons (`--gradient-brand`, white text, pill or `--radius`, arrow glyph allowed) are the only other saturated elements. Everything else in the UI is glass, white, or ink. If a design decision would add a second saturated region, the answer is no.

## Glass hierarchy

- **Tier A — Panels** (pane containers, section cards, stepper cards, chat bubbles): `--glass-panel`, `--glass-blur` (+ `-webkit-`), `--glass-border`, `--radius` to `--radius-lg`, `--glass-shadow`. Section cards open with an icon + small-caps letter-spaced label (e.g., BRIEF, AGENT TEAM) in `--brand-indigo` and a right-aligned collapse chevron.
- **Tier B — Emphasis panels** (active stage card, hovered/selected states): `--glass-panel-strong` with `--glass-border-tint` and slightly deeper shadow.
- **Tier 0 — Content surfaces** (text inputs, textareas, dense tables, long-form reading): `--glass-content`, hairline border, minimal blur or none. Readability is non-negotiable; glass frames content, it never sits under it.
- Performance budget: max ~6 `backdrop-filter` layers per viewport, never nest blurred elements.

## Component recipes (match the reference screen exactly)

- **Stage stepper**: horizontal cards connected by hairline rules. Active stage = Tier B card with a filled `--brand-indigo` circular icon, bold title, small-caps "STAGE n" sublabel. Locked stages = flat translucent chips with a lock icon in a frosted square, muted `--ink-soft` text. Completed stages = check icon, indigo tint.
- **Definition rows** (brief fields): label in `--ink`, hairline divider between rows, empty value rendered as an em dash "—" right-aligned, optional right-aligned hint text in `--ink-soft` (e.g., "percentages only"). Filled values right-aligned in medium weight.
- **Chat composer**: Tier 0 white rounded field with attach and mic icon buttons in `--ink-soft`, send button as a small `--gradient-brand` rounded square. Below it, one line of keyboard-hint microcopy in `--ink-soft`.
- **Buttons**: primary = gradient pill/rounded with white text (may carry a trailing arrow). Secondary = plain text link in `--ink` ("Skip — I'll just chat" pattern). No outlined gray buttons anywhere.
- **Status/pill chips**: translucent white pills, `--radius-pill`, small text, optional status dot.
- **Empty states**: never blank — an italic `--ink-soft` sentence describing what will appear and when ("Agents appear here and work in real time once the brief is complete.").

## Typography

Humanist grotesk with a friendly, precise voice (Segoe UI on Windows; fall back to a matching stack — `"Segoe UI", "Inter", system-ui, sans-serif` — or the brand-kit face if one exists). Scale 12/13/14/16/20/24/32. Section labels: 12–13px, small caps, +0.08em letter-spacing, `--brand-indigo`. Body in `--ink`, helper copy in `--ink-soft`. No pure black anywhere.

## Voice & microcopy

Conversational, confident, second person, em-dash friendly: "Fill in the blanks below — or paste your own brief in any wording." Buttons name the action ("Extract brief", not "Submit"). Helper text explains what the system will do next, in the interface's voice. Keep this register on every new screen.

## Accessibility & fallbacks (hard requirements)

- Text contrast ≥ 4.5:1 on every surface, tested against the worst-case mist behind the glass; `--ink` on `--glass-panel` must pass everywhere.
- Always pair `backdrop-filter` with `-webkit-backdrop-filter`; `@supports` fallback to solid `rgba(255,255,255,0.9)`.
- Implement `prefers-reduced-transparency` (near-opaque panels, no blur) and `prefers-contrast: more` (stronger borders, higher panel opacity).
- Keyboard-first: visible 2px `--brand-indigo` focus outline with offset on glass, logical tab order, focus trap in modals. Locked stages are focusable and announce their locked state.

## Implementation rules (Material UI)

- All values above live in one `tokens.css`; no raw hex/rgba in components.
- App-wide defaults via `createTheme({ components })`: palette, typography, shape, and slot overrides for AppBar (gradient), Paper/Card (Tier A glass), Dialog, TextField (Tier 0).
- Reusable primitives via `styled()`: `GlassPanel` (tier prop: A|B|0), `SectionCard` (icon + small-caps label + collapse), `StageStep` (state: active|locked|done), `DefinitionRow`, `BrandButton`, `PillChip`, `Composer`.
- `sx` only for genuine one-off local adjustments; never scatter overrides where a theme rule belongs.

## Process — gates, not vibes

- **Phase 0 — Audit:** inventory every screen, route, and component; mark each as "matches reference" / "needs rework" / "missing states". List them.
- **Phase 1 — Codify (STOP for approval):** produce tokens.css and the primitive component specs, plus a one-screen ASCII wireframe showing how a non-reference screen (e.g., Home or Claims Library) adopts the system. **Do not restyle screens until I approve.**
- **Phase 2 — Foundation:** tokens, theme, atmosphere layer, primitives; verify the reference screen renders pixel-faithfully from the new primitives (this is the regression test).
- **Phase 3 — Screen-by-screen:** migrate each remaining screen. After each, screenshot, self-critique against this brief (one saturated moment, tier discipline, contrast, voice), fix, move on.
- **Phase 4 — QA gate:** contrast on all surfaces; reduced-motion/-transparency/contrast modes; keyboard traversal incl. locked steps; Safari `-webkit-` rendering; Firefox fallback; performance budget; zero raw color values outside tokens.css; every empty state has its sentence.

Elegance here is restraint executed precisely. When aesthetics and accessibility conflict, accessibility wins — find a solution that satisfies both.