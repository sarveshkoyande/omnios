import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Builds straight into the FastAPI static dir: app.mount("/static", ...) already
// serves it, so /static/v2/ works with zero server changes beyond the /v2 route.
export default defineConfig({
  plugins: [react()],
  base: "/static/v2/",
  build: {
    outDir: "../app/static/v2",
    emptyOutDir: true,
  },
  server: {
    // FastAPI serves app/static at /static, so image paths like /static/home/... 404
    // under `npm run dev` unless they are proxied — they only work in the built bundle.
    // Proxy the asset directories individually and NOT `/static` wholesale: `base` is
    // "/static/v2/", so a blanket /static rule would hijack Vite's own module requests
    // and take the dev server down with it.
    proxy: {
      "/api": "http://127.0.0.1:8733",
      "/static/home": "http://127.0.0.1:8733",
      "/static/agent_avatars": "http://127.0.0.1:8733",
      "/static/brand_assets": "http://127.0.0.1:8733",
      "/static/agent_image": "http://127.0.0.1:8733",
    },
  },
});
