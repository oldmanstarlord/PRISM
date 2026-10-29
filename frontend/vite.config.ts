import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  test: {
    maxWorkers: 2,
    css: { include: /terminal\.css/ },
    environment: "jsdom",
    setupFiles: [],
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
  },
});
