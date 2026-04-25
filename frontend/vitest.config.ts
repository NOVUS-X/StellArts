import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["**/*.test.{ts,tsx}"],
    globals: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./"),
      "next/link": path.resolve(__dirname, "./__mocks__/next/link.tsx"),
      "next/navigation": path.resolve(
        __dirname,
        "./__mocks__/next/navigation.ts"
      ),
      "next/image": path.resolve(__dirname, "./__mocks__/next/image.tsx"),
    },
  },
});
