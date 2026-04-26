import { defineConfig } from "vite";

export default defineConfig({
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        popup: "src/popup/popup.html",
        options: "src/options/options.html",
        background: "src/background/background.ts",
        content: "src/content/content.ts"
      },
      output: {
        entryFileNames: "src/[name]/[name].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]"
      }
    }
  }
});
