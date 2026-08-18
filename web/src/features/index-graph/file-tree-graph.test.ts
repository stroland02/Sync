/**
 * The directory tree behind the indexing canvas.
 *
 * Edges, operations, vendors and rungs moved to `operation-graph.ts` when the canvas gained its
 * middle level; what is left here is the tree, and these are the assertions that were always
 * about the tree rather than about what it connected to.
 */

import { describe, expect, it } from "vitest"

import { buildFileTree, type FolderNode, type TreeNode } from "@/features/index-graph/file-tree-graph"

function asFolder(node: TreeNode): FolderNode {
  if (node.kind !== "folder") throw new Error(`expected a folder node, got ${node.kind}`)
  return node
}

describe("buildFileTree", () => {
  it("nests a file under one folder node per path segment", () => {
    const tree = buildFileTree(["src/api/billing.ts"])

    const src = asFolder(tree.children[0])
    expect(src.name).toBe("src")
    const api = asFolder(src.children[0])
    expect(api.name).toBe("api")
    expect(api.children[0]).toEqual({
      kind: "file",
      name: "billing.ts",
      path: "src/api/billing.ts",
    })
  })

  it("shares one folder node across two files in the same directory", () => {
    const tree = buildFileTree(["src/a.ts", "src/b.ts"])

    expect(tree.children).toHaveLength(1)
    expect(asFolder(tree.children[0]).children).toHaveLength(2)
  })

  it("keeps folder children sorted before file children, then alphabetically", () => {
    const tree = buildFileTree(["z.ts", "a.ts", "lib/b.ts"])

    expect(tree.children.map((c) => c.name)).toEqual(["lib", "a.ts", "z.ts"])
  })

  it("produces an empty tree for no paths, not a crash", () => {
    expect(buildFileTree([])).toEqual({ kind: "folder", name: "", path: "", children: [] })
  })
})
