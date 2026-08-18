/**
 * Where every node on the file-tree canvas sits, and which of them a given viewport needs to
 * render. Positioning reuses `file-tree-graph.ts`'s derivation; `fitViewport`/`zoomViewport`/
 * `panViewport` are `graph-layout.ts`'s own, unchanged -- viewport arithmetic does not depend on
 * what the nodes mean, so this module does not re-derive it.
 */

import { describe, expect, it } from "vitest"

import { buildFileTreeGraph } from "@/features/index-graph/file-tree-graph"
import { layoutFileTree, visibleNodes } from "@/features/index-graph/file-tree-layout"

describe("layoutFileTree", () => {
  it("gives every tree node and every vendor node a position", () => {
    const graph = buildFileTreeGraph([{ file: "src/a.ts", vendor: "stripe", binding_source: "static" }])
    const layout = layoutFileTree(graph)

    const ids = layout.nodes.map((n) => n.id)
    expect(ids).toContain("path:src")
    expect(ids).toContain("path:src/a.ts")
    expect(ids).toContain("vendor:stripe")
  })

  it("places a file strictly to the right of its parent folder", () => {
    const graph = buildFileTreeGraph([{ file: "src/a.ts", vendor: "stripe", binding_source: "static" }])
    const layout = layoutFileTree(graph)

    const folder = layout.nodes.find((n) => n.id === "path:src")!
    const file = layout.nodes.find((n) => n.id === "path:src/a.ts")!
    expect(file.x).toBeGreaterThan(folder.x)
  })

  it("places the vendor column to the right of every file column", () => {
    const graph = buildFileTreeGraph([{ file: "deeply/nested/a.ts", vendor: "stripe", binding_source: "static" }])
    const layout = layoutFileTree(graph)

    const vendor = layout.nodes.find((n) => n.id === "vendor:stripe")!
    const fileXs = layout.nodes.filter((n) => n.id.startsWith("path:")).map((n) => n.x)
    expect(vendor.x).toBeGreaterThan(Math.max(...fileXs))
  })

  it("draws one edge per file-vendor pair at the derivation's own positions", () => {
    const graph = buildFileTreeGraph([{ file: "a.ts", vendor: "stripe", binding_source: "static" }])
    const layout = layoutFileTree(graph)

    expect(layout.edges).toHaveLength(1)
    expect(layout.edges[0].from).toBe("path:a.ts")
    expect(layout.edges[0].to).toBe("vendor:stripe")
  })

  it("returns empty nodes and edges for an empty graph, not a crash", () => {
    const graph = buildFileTreeGraph([])
    const layout = layoutFileTree(graph)

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
