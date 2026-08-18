/**
 * Where every node on the indexing canvas sits, and which of them a given viewport needs to
 * render. Positioning reuses the derivations in `file-tree-graph.ts` and `operation-graph.ts`;
 * `fitViewport`/`zoomViewport`/`panViewport` are unchanged -- viewport arithmetic does not depend
 * on what the nodes mean, so this module does not re-derive it.
 *
 * The column order is the assertion that matters: files, then the operations they call, then the
 * vendors publishing them. Left to right is the reader's code reaching outward.
 */

import { describe, expect, it } from "vitest"

import { buildFileTree } from "@/features/index-graph/file-tree-graph"
import { layoutOperationGraph, visibleNodes } from "@/features/index-graph/file-tree-layout"
import { buildOperationGraph, type CallBindingRow } from "@/features/index-graph/operation-graph"

const binding = (over: Partial<CallBindingRow> = {}): CallBindingRow => ({
  file: "src/a.ts",
  vendorId: "stripe",
  operationId: "PostCharges",
  rung: "static",
  ...over,
})

function layoutOf(rows: CallBindingRow[]) {
  return layoutOperationGraph(
    buildFileTree(rows.map((r) => r.file)),
    buildOperationGraph(rows),
  )
}

describe("layoutOperationGraph", () => {
  it("gives every tree node, operation and vendor a position", () => {
    const ids = layoutOf([binding()]).nodes.map((n) => n.id)

    expect(ids).toContain("path:src")
    expect(ids).toContain("path:src/a.ts")
    expect(ids).toContain("operation:stripe:PostCharges")
    expect(ids).toContain("vendor:stripe")
  })

  it("places a file strictly to the right of its parent folder", () => {
    const layout = layoutOf([binding()])

    const folder = layout.nodes.find((n) => n.id === "path:src")!
    const file = layout.nodes.find((n) => n.id === "path:src/a.ts")!
    expect(file.x).toBeGreaterThan(folder.x)
  })

  /** Files, then operations, then vendors. The order is the picture's argument. */
  it("places the three columns left to right", () => {
    const layout = layoutOf([binding({ file: "deeply/nested/a.ts" })])

    const fileXs = layout.nodes.filter((n) => n.id.startsWith("path:")).map((n) => n.x)
    const operation = layout.nodes.find((n) => n.kind === "operation")!
    const vendor = layout.nodes.find((n) => n.id === "vendor:stripe")!

    expect(operation.x).toBeGreaterThan(Math.max(...fileXs))
    expect(vendor.x).toBeGreaterThan(operation.x)
  })

  it("routes a file to its vendor through the operation rather than straight across", () => {
    const layout = layoutOf([binding({ file: "a.ts" })])

    expect(layout.edges).toHaveLength(2)
    expect(layout.edges).toContainEqual({
      id: "edge:a.ts->stripe:PostCharges",
      from: "path:a.ts",
      to: "operation:stripe:PostCharges",
    })
    expect(layout.edges).toContainEqual({
      id: "edge:stripe:PostCharges->stripe",
      from: "operation:stripe:PostCharges",
      to: "vendor:stripe",
    })
    expect(layout.edges.some((e) => e.from.startsWith("path:") && e.to.startsWith("vendor:"))).toBe(
      false,
    )
  })

  it("draws one operation node per vendor even when two vendors share an operation name", () => {
    const layout = layoutOf([
      binding({ vendorId: "stripe", operationId: "Charge" }),
      binding({ vendorId: "adyen", operationId: "Charge" }),
    ])

    const operations = layout.nodes.filter((n) => n.kind === "operation")
    expect(operations).toHaveLength(2)
  })

  it("returns empty nodes and edges for an empty graph, not a crash", () => {
    const layout = layoutOf([])

    expect(layout.nodes).toEqual([])
    expect(layout.edges).toEqual([])
    expect(layout.bounds).toEqual({ x: 0, y: 0, width: 0, height: 0 })
  })
})

describe("visibleNodes", () => {
  it("excludes a node entirely outside the viewport", () => {
    const nodes = [
      { id: "in", x: 0, y: 0, width: 10, height: 10 },
      { id: "out", x: 10_000, y: 10_000, width: 10, height: 10 },
    ]
    const view = { x: 0, y: 0, width: 100, height: 100 }

    expect(visibleNodes(nodes, view).map((n) => n.id)).toEqual(["in"])
  })

  it("includes a node that only partially overlaps the viewport", () => {
    const nodes = [{ id: "edge", x: 90, y: 90, width: 20, height: 20 }]
    const view = { x: 0, y: 0, width: 100, height: 100 }

    expect(visibleNodes(nodes, view).map((n) => n.id)).toEqual(["edge"])
  })

  it("returns nothing for an empty node list", () => {
    expect(visibleNodes([], { x: 0, y: 0, width: 100, height: 100 })).toEqual([])
  })
})
