/**
 * The Overview's dependency graph panel.
 *
 * `toCanvasInput`'s own invariant tests moved to `file-tree-graph.test.ts` when
 * `overview-graph-panel.tsx` switched from `DependencyCanvas` to `FileTreeCanvas`
 * (2026-08-18) and `toCanvasInput` itself was deleted -- `FileTreeCanvas` takes the route's
 * `bindings` directly, so there is no mapping layer left to test here. The rung-propagation and
 * vendor-survives-truncation checks that function protected are `file-tree-graph.test.ts`'s
 * "carries every distinct rung..." and "keeps a vendor named in knownVendorIds..." tests.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

afterEach(cleanup)

describe("OverviewGraphPanel", () => {
  it("says the picture is partial rather than drawing a smaller codebase", async () => {
    const { PartialGraphNotice } = await import("@/features/index-graph/overview-graph-panel")
    render(<PartialGraphNotice drawn={2} total={5} />)

    expect(screen.getByText(/2 of 5/)).not.toBeNull()
  })
})
