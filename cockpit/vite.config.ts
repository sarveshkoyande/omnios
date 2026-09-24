import path from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const here = path.dirname(fileURLToPath(import.meta.url));

// Plan U7 / KTD7: the Flow step renders the existing Campaign Ops flow-builder straight from
// frontend/src (an alias, not a copy). frontend/ has its own node_modules, so any bare import
// inside an aliased file would otherwise resolve there and load a second React. Every bare
// package those files use is pinned to cockpit/node_modules instead, so one React instance
// runs and a Cockpit-only `npm install` is enough to build.
const shared = ["react", "react-dom", "@xyflow/react", "zustand", "zod", "@dagrejs/dagre"];
const sharedAliases = shared.map((pkg) => ({
  find: new RegExp(`^${pkg.replace("/", "\\/")}(?=/|$)`),
  replacement: path.join(here, "node_modules", pkg),
}));

// Second, independent Vite app for the new brand-workspace cockpit IA (see
// docs/ideation/2026-09-11-brand-workspace-ideation.html). Deliberately not folded into
// frontend/ -- that app is the existing stage-tab product; this one is the new workspace
// structure replacing it. Builds into its own static subtree so app/server.py can serve
// both side by side while the cockpit is being built out.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [{ find: /^@omni-frontend\//, replacement: `${path.join(here, "../frontend/src")}/` }, ...sharedAliases],
    dedupe: ["react", "react-dom"],
  },
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
