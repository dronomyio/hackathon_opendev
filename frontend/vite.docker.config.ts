/**
 * vite.docker.config.ts
 *
 * Standalone Vite config for Docker builds.
 * Does NOT use Manus-specific plugins (vite-plugin-manus-runtime, jsxLocPlugin).
 * Used by the `build:docker` script in package.json.
 *
 * Output: dist/public/ (served by the Python FastAPI backend as static files)
 */
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "client", "src"),
      "@shared": path.resolve(import.meta.dirname, "shared"),
    },
  },
  envDir: path.resolve(import.meta.dirname),
  root: path.resolve(import.meta.dirname, "client"),
  publicDir: path.resolve(import.meta.dirname, "client", "public"),
  build: {
    outDir: path.resolve(import.meta.dirname, "dist/public"),
    emptyOutDir: true,
  },
});
