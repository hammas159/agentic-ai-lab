import { vitePlugin as remix } from "@remix-run/dev";
import { defineConfig } from "vite";

// The Python API is the same code path as the CLI; Remix proxies to it so the
// browser and `review-bot scan` can never disagree.
export default defineConfig({
  plugins: [remix()],
  server: { port: 5175, proxy: { "/api": "http://127.0.0.1:8110" } },
});
