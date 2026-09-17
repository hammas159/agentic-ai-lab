import { defineConfig } from "vite";
import solid from "vite-plugin-solid";

// The Python side serves the API; Vite proxies to it in development so the
// UI and `db-surgeon check` stay the same code path.
export default defineConfig({
  plugins: [solid()],
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8095" },
  },
});
