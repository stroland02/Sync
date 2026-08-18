/**
 * The derivation behind the file-tree canvas (owner decision 8, 2026-08-18): a repository's own
 * directory structure, with an edge from each file to the vendor its call sites bind. This
 * replaces the vendor-first shape `graph-layout.ts` drew -- `src/api/billing.ts ──▶ stripe`, not
 * `stripe ──▶ PostCharges ──▶ billing.ts:41`, because the reader opens this screen already
 * knowing their own repository and the payoff is seeing what it touches, not being taught a graph
 * shaped around the vendor.
 *
 * Scoped honestly to what real data supports today: `RiskRow` (`GET /api/vendors/{id}`) is a
 * page of *open findings*, not every indexed call site -- no route lists a repository's whole
 * call-site set regardless of finding status. So this tree draws the files Sync currently has
 * something to say about, and says so; it is not yet "every file this repository has," and a
 * caller must not claim otherwise.
 */

import { describe, expect, it } from "vitest"

import type { BindingSource } from "@/api/types"
import { buildFileTreeGraph } from "@/features/index-graph/file-tree-graph"
import type { FolderNode, TreeNode } from "@/features/index-graph/file-tree-graph"

function row(file: string, vendor: string, binding_source: BindingSource = "static") {
  return { file, line: 1, symbol: null, operation: null, vendor, change_kind: null, severity: "breaking", finding_id: "f1", binding_source }
}

function asFolder(node: TreeNode): FolderNode {
  if (node.kind !== "folder") throw new Error(`expected a folder node, got ${node.kind}`)
  return node
}

describe("buildFileTreeGraph", () => {
  it("nests a file under one folder node per path segment", () => {
    const graph = buildFileTreeGraph([row("src/api/billing.ts", "stripe")])

    const root = graph.tree
    expect(root.name).toBe("")
    expect(root.children.map((c) => c.name)).toEqual(["src"])
    const src = asFolder(root.children[0])
    expect(src.kind).toBe("folder")
    expect(src.children.map((c) => c.name)).toEqual(["api"])
    const api = asFolder(src.children[0])
    const file = api.children[0]
    expect(file.name).toBe("billing.ts")
    expect(file.kind).toBe("file")
  })

  it("shares one folder node across two files in the same directory", () => {
    const graph = buildFileTreeGraph([
      row("src/api/billing.ts", "stripe"),
      row("src/api/sms.ts", "twilio"),
    ])

    const src = asFolder(graph.tree.children[0])
    const api = asFolder(src.children[0])
    expect(api.children.map((c) => c.name).sort()).toEqual(["billing.ts", "sms.ts"])
  })

  it("draws one vendor node per distinct vendor named across every row", () => {
    const graph = buildFileTreeGraph([
      row("a.ts", "stripe"),
      row("b.ts", "stripe"),
      row("c.ts", "twilio"),
    ])

    expect(graph.vendors.map((v) => v.vendorId).sort()).toEqual(["stripe", "twilio"])
  })

  it("draws one edge per file-vendor pair, not one per call site", () => {
    const graph = buildFileTreeGraph([
      row("a.ts", "stripe"),
      row("a.ts", "stripe"), // a second call site in the same file, same vendor
    ])

    const edgesFromA = graph.edges.filter((e) => e.file === "a.ts")
    expect(edgesFromA).toHaveLength(1)
  })

  it("carries every distinct rung a file's call sites bind at, in the vocabulary's order", () => {
    const graph = buildFileTreeGraph([
      row("a.ts", "stripe", "observed"),
      row("a.ts", "stripe", "static"),
    ])

    expect(graph.edges[0].rungs).toEqual(["static", "observed"])
  })

  it("connects a file with calls to two vendors with two edges, not one merged edge", () => {
    const graph = buildFileTreeGraph([
      row("a.ts", "stripe"),
      row("a.ts", "twilio"),
    ])

    expect(graph.edges.map((e) => e.vendorId).sort()).toEqual(["stripe", "twilio"])
  })

  it("produces an empty tree and no vendors for no rows, not a crash", () => {
    const graph = buildFileTreeGraph([])

    expect(graph.tree.children).toEqual([])
    expect(graph.vendors).toEqual([])
    expect(graph.edges).toEqual([])
  })

  it("keeps folder children sorted before file children, then alphabetically", () => {
    const graph = buildFileTreeGraph([
      row("b.ts", "stripe"),
      row("a-folder/nested.ts", "stripe"),
      row("a.ts", "stripe"),
    ])

    expect(graph.tree.children.map((c) => c.name)).toEqual(["a-folder", "a.ts", "b.ts"])
  })
})
