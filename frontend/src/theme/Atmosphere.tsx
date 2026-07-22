/**
 * Atmosphere — historically the fixed, full-viewport drifting-mist background
 * behind the "light liquid glass" panels. Removed 2026-07-18 along with the
 * rest of the glass system: the flat Material page background now comes
 * straight from `MuiCssBaseline`'s `body` rule (tokens.color.bgBase), so
 * there is no separate atmosphere layer to render. Kept as a no-op so the
 * (now unused) import site can be dropped without a churny two-file diff.
 */
export function Atmosphere() {
  return null;
}
