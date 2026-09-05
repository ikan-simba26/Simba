import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Electron loads the built files off disk, so assets must be referenced
  // relatively rather than from the server root.
  base: "./",
  resolve: {
    alias: {
      "@shared": fileURLToPath(new URL("../shared", import.meta.url)),
    },
  },
  server: {
    // The contract types live outside this package's root.
    fs: { allow: [".."] },
  },
});
