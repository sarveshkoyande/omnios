import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Second, independent Vite app for the new brand-workspace cockpit IA (see
// docs/ideation/2026-09-11-brand-workspace-ideation.html). Deliberately not folded into
// frontend/ -- that app is the existing stage-tab product; this one is the new workspace
// structure replacing it. Builds into its own static subtree so app/server.py can serve
// both side by side while the cockpit is being built out.
export default defineConfig({
  plugins: [react()],
  // The repo root also holds an unrelated Next.js/Prisma scaffold (see CLAUDE.md's
  // "root-level contamination" section) with its own postcss.config.mjs -- Vite's default
  // postcss-load-config search walks up from this directory and finds it, then fails
  // because that config's plugins (tailwindcss) aren't installed here. Pin css.postcss to
  // an empty inline config so it never searches upward for one.
  css: { postcss: {} },
  base: "/static/cockpit/",
  build: {
    outDir: "../app/static/cockpit",
    emptyOutDir: true,
  },
  server: {
    // Matches restart-server-tmp.ps1's port (8731) -- the frontend/ app's own vite.config.ts
    // has a documented history of pointing at the wrong port and silently 404ing every /api
    // call, so keep this one deliberately explicit.
    proxy: {
      "/api": "http://127.0.0.1:8731",
      "/static/brand_assets": "http://127.0.0.1:8731",
      "/static/agent_avatars": "http://127.0.0.1:8731",
    },
  },
});
