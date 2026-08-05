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
    // Port 8000 is uvicorn's default and what `python -m uvicorn app.server:app` actually
    // binds locally. This file used to point at 8733 and restart-server.ps1.txt at 8731,
    // while the server listened on 8000 -- so under `npm run dev` every /api call hit a
    // closed port and surfaced as the useWorkspace catch-alls ("Something went wrong
    // reaching the agent"), which name no port and made it look like an agent fault.
    // FastAPI serves app/static at /static, so image paths like /static/home/... 404
    // under `npm run dev` unless they are proxied — they only work in the built bundle.
    // Proxy the asset directories individually and NOT `/static` wholesale: `base` is
    // "/static/v2/", so a blanket /static rule would hijack Vite's own module requests
    // and take the dev server down with it.
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/static/home": "http://127.0.0.1:8000",
      "/static/agent_avatars": "http://127.0.0.1:8000",
      "/static/brand_assets": "http://127.0.0.1:8000",
      "/static/agent_image": "http://127.0.0.1:8000",
    },
  },
});
