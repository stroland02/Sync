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
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
      // echarts measures a canvas jsdom never lays out and throws in its own teardown.
      // `echarts-jsdom-stub.tsx` carries why stubbing beats shimming a canvas here.
      "echarts-for-react": path.resolve(
        import.meta.dirname,
        "./src/components/charts/echarts-jsdom-stub.tsx",
      ),
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}", "scripts/**/*.test.ts"],
    // One file, and it only fills in `matchMedia`, which jsdom does not implement and the vendored
    // sidebar calls on mount. Its own docstring carries why the stub answers the way it does.
    setupFiles: ["./src/test-setup.ts"],
    // Raised from 5s on 2026-08-18, and the reason is a real cost rather than flake.
    //
    // The chassis got heavier. `M14-W366` made the sidebar render every destination on every route
    // instead of one area's run, and `M14-W377` added a codebase fact band, a rung panel and a
    // dependency canvas that mount with it. Several tests loop over every route rendering the whole
    // frame, so their cost is routes x frame, and the frame roughly tripled. They pass in ~10s alone
    // and tipped over 5s only under a loaded parallel run -- the banner loop reached 17s while three
    // agent workflows were running against the same worktree.
    //
    // This is a budget, not a fix. If a test needs more than this it is doing something this scope
    // does not cover; if the whole suite creeps toward it, the frame is the thing to look at rather
    // than this number.
    testTimeout: 20_000,
  },
})
