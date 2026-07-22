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
    proxy: {
      "/api": "http://127.0.0.1:8733",
    },
  },
});
