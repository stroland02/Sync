/**
 * Extracted from `graph-layout.ts` when `file-tree-canvas.tsx` replaced `dependency-canvas.tsx`
 * (owner decisions 8/13, 2026-08-18): pan/zoom/fit arithmetic does not depend on what the nodes
 * mean, so it outlives the vendor-shaped graph it was first written for. Tests carried over
 * unchanged from `graph-layout.test.ts`'s own viewport coverage.
 */

import { describe, expect, it } from "vitest"

import { fitViewport, panViewport, zoomViewport } from "@/features/index-graph/viewport"

describe("fitViewport", () => {
  it("frames the bounds with padding on every side", () => {
    const view = fitViewport({ x: 0, y: 0, width: 100, height: 50 })
    expect(view.x).toBeLessThan(0)
    expect(view.y).toBeLessThan(0)
    expect(view.width).toBeGreaterThan(100)
    expect(view.height).toBeGreaterThan(50)
  })
})

describe("zoomViewport", () => {
  it("shrinks the view around its own centre when zooming in", () => {
    const fit = fitViewport({ x: 0, y: 0, width: 100, height: 100 })
    const zoomed = zoomViewport(fit, 2, fit)
    expect(zoomed.width).toBeLessThan(fit.width)
    expect(zoomed.x + zoomed.width / 2).toBeCloseTo(fit.x + fit.width / 2)
  })

  it("clamps zoom-in at the configured limit", () => {
    const fit = fitViewport({ x: 0, y: 0, width: 100, height: 100 })
    const zoomed = zoomViewport(fit, 1000, fit)
    expect(zoomed.width).toBeGreaterThan(0)
  })
})

describe("panViewport", () => {
  it("moves the view by the given delta", () => {
    const fit = fitViewport({ x: 0, y: 0, width: 1000, height: 1000 })
    const panned = panViewport(fit, 50, 0, fit)
    expect(panned.x).toBeGreaterThan(fit.x)
  })

  it("keeps the view's centre inside the fitted bounds", () => {
    const fit = fitViewport({ x: 0, y: 0, width: 100, height: 100 })
    const panned = panViewport(fit, 100_000, 0, fit)
    const centre = panned.x + panned.width / 2
    expect(centre).toBeLessThanOrEqual(fit.x + fit.width)
  })
})
