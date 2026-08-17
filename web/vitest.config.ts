/**
 * The console's test runner.
 *
 * Deliberately separate from `vite.config.ts` rather than a `test` key inside it: that config
 * loads the Tailwind plugin and a dev-server proxy, neither of which a test run has any use for,
 * and a runner that drags a CSS pipeline behind it is a runner people stop running.
 *
 * `jsdom` rather than a browser. What this suite is allowed to assert — classification,
 * derivation and structural invariants, never class names and never snapshots — needs a DOM to
 * query and nothing a real engine would render differently. Anything that genuinely depends on
 * rendered pixels is measured in Chrome and written into `DESIGN.md`, which is a different
 * discipline with a different gate.
 */

import path from "node:path"
import { defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}", "scripts/**/*.test.ts"],
    // One file, and it only fills in `matchMedia`, which jsdom does not implement and the vendored
    // sidebar calls on mount. Its own docstring carries why the stub answers the way it does.
    setupFiles: ["./src/test-setup.ts"],
    // The suite is pure functions and small component mounts; a run that needs a longer
    // default is a test reaching for something this scope does not cover.
    testTimeout: 5_000,
  },
})
