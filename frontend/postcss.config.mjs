// This app doesn't use any PostCSS plugins (plain CSS + MUI's emotion-based styling) --
// this file exists only so Vite's PostCSS auto-detection stops HERE instead of walking up
// to the repo root's postcss.config.mjs, which belongs to the unrelated create-next-app +
// Tailwind scaffold contaminating the repo root (see ../CLAUDE.md's "root-level
// contamination" section) and requires a `tailwindcss` dependency this app never installs.
export default {
  plugins: {},
};
