import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The built interface is served by the Python package (pbi2pptx/server.py).
export default defineConfig({
  plugins: [react()],
  build: { outDir: "../pbi2pptx/static", emptyOutDir: true },
});
