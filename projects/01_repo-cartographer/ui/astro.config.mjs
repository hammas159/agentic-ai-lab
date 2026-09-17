import { defineConfig } from "astro/config";

// Static output: the whole site is generated from the JSON maps that
// `cartographer map --json` writes into public/data/. There is no server.
export default defineConfig({
  output: "static",
  server: { port: 4321 },
});
