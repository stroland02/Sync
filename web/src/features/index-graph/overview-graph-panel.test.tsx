/**
 * The Overview's dependency graph, and the mapping from payload to picture.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: derivation and structural invariants, never
 * class names and never a snapshot. What is held here is that the payload's distinctions survive
 * the mapping -- a graph that quietly rounds absence to zero draws a codebase that does not exist.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import type { RepositoryGraphResponse } from "@/api/types"
import { toCanvasInput } from "@/features/index-graph/overview-graph-panel"

afterEach(cleanup)

function payload(over: Partial<RepositoryGraphResponse> = {}): RepositoryGraphResponse {
  return {
    repo_id: "org/one",
    vendors: [{ vendor_id: "stripe", indexed_call_sites: 2, last_indexed: "2026-08-16T12:00:00Z" }],
    bindings: [
      {
        vendor_id: "stripe",
        operation_id: "PostCharges",
        path: "src/billing.ts",
        line: 42,
        symbol: "stripe.charges.create",
        binding_rung: "static",
      },
    ],
    total_bindings: 1,
    truncated: false,
    ...over,
  }
}

describe("toCanvasInput", () => {
  it("carries each binding's rung onto the edge that draws it", () => {
    const { rows } = toCanvasInput(payload())

    // `CLAUDE.md`: every binding carries the rung it came from, and so does every artifact
    // derived from it. The edge is such an artifact.
    expect(rows.map((r) => r.rung)).toEqual(["static"])
  })

  it("names the position a reader would open", () => {
    const { rows } = toCanvasInput(payload())

    expect(rows[0].file).toBe("src/billing.ts")
    expect(rows[0].line).toBe(42)
    expect(rows[0].operation).toBe("PostCharges")
  })

  it("marks a vendor's bindings as queried, because nothing-asked is not none-found", () => {
    const { vendors } = toCanvasInput(payload())

    // `bindingsQueried: false` with no rows means nothing was asked; `true` with no rows means
    // the answer was none. This route asks for every binding at once, so the answer arrived.
    expect(vendors[0].bindingsQueried).toBe(true)
  })

  it("leaves the open finding count null, because this route never counted findings", () => {
    const { vendors } = toCanvasInput(payload())

    // The graph route answers call sites and vendors. A zero here would be this panel asserting
    // a count it never read, which is the absence-versus-zero conflation the console refuses.
    expect(vendors[0].openFindingCount).toBeNull()
  })

  it("keeps a vendor that has call sites but no drawn edge", () => {
    const { vendors } = toCanvasInput(payload({ bindings: [] }))

    // A truncated response can name a vendor whose edges were cut. Dropping the node would
    // shrink the codebase the picture claims to show.
    expect(vendors.map((v) => v.vendorId)).toEqual(["stripe"])
  })
})

describe("OverviewGraphPanel", () => {
  it("says the picture is partial rather than drawing a smaller codebase", async () => {
    const { PartialGraphNotice } = await import("@/features/index-graph/overview-graph-panel")
    render(<PartialGraphNotice drawn={2} total={5} />)

    expect(screen.getByText(/2 of 5/)).not.toBeNull()
  })
})
