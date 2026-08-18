/**
 * A repository's directory structure, with an edge from each file to the vendors its call sites
 * bind. See this module's test file for the shape this replaces and why.
 *
 * No DOM, no layout coordinates -- this only builds the tree and the edge list. Where each node
 * ends up on screen is the renderer's problem, the same separation `graph-layout.ts` already
 * draws between deriving and placing.
 */

import { BINDING_SOURCES, type BindingSource } from "@/api/types"

/** The one shape this module needs from `RiskRow` -- a caller passes its own rows through. */
export interface FileVendorRow {
  file: string
  vendor: string
  binding_source: BindingSource
}

export interface FileNode {
  kind: "file"
  name: string
  path: string
}

export interface FolderNode {
  kind: "folder"
  name: string
  path: string
  children: TreeNode[]
}

export type TreeNode = FolderNode | FileNode

export interface VendorSummary {
  vendorId: string
}

export interface FileVendorEdge {
  file: string
  vendorId: string
  rungs: BindingSource[]
}

export interface FileTreeGraph {
  tree: FolderNode
  vendors: VendorSummary[]
  edges: FileVendorEdge[]
}

function rungOrder(rung: BindingSource): number {
  const index = BINDING_SOURCES.indexOf(rung)
  return index === -1 ? BINDING_SOURCES.length : index
}

function insert(root: FolderNode, filePath: string): void {
  const segments = filePath.split("/").filter((s) => s.length > 0)
  let cursor = root
  let builtPath = ""
  segments.forEach((segment, index) => {
    builtPath = builtPath === "" ? segment : `${builtPath}/${segment}`
    const isLeaf = index === segments.length - 1
    const existing = cursor.children.find((c) => c.name === segment)
    if (existing !== undefined) {
      if (existing.kind === "folder") cursor = existing
      return
    }
    if (isLeaf) {
      cursor.children.push({ kind: "file", name: segment, path: builtPath })
    } else {
      const folder: FolderNode = { kind: "folder", name: segment, path: builtPath, children: [] }
      cursor.children.push(folder)
      cursor = folder
    }
  })
}

function sortTree(node: FolderNode): void {
  node.children.sort((a, b) => {
    if (a.kind !== b.kind) return a.kind === "folder" ? -1 : 1
    return a.name.localeCompare(b.name)
  })
  for (const child of node.children) {
    if (child.kind === "folder") sortTree(child)
  }
}

export function buildFileTreeGraph(rows: FileVendorRow[]): FileTreeGraph {
  const root: FolderNode = { kind: "folder", name: "", path: "", children: [] }
  const vendorIds = new Set<string>()
  // Nested by file then vendor, rather than a joined string key: a real file path may legally
  // contain any separator character this module could pick, and a joined key that collided
  // across two distinct (file, vendor) pairs would silently merge their edges' rungs.
  const edgeRungs = new Map<string, Map<string, Set<BindingSource>>>()

  for (const row of rows) {
    insert(root, row.file)
    vendorIds.add(row.vendor)
    const byVendor = edgeRungs.get(row.file) ?? new Map<string, Set<BindingSource>>()
    edgeRungs.set(row.file, byVendor)
    const rungs = byVendor.get(row.vendor) ?? new Set<BindingSource>()
    rungs.add(row.binding_source)
    byVendor.set(row.vendor, rungs)
  }

  sortTree(root)

  const edges: FileVendorEdge[] = [...edgeRungs.entries()].flatMap(([file, byVendor]) =>
    [...byVendor.entries()].map(([vendorId, rungs]) => ({
      file,
      vendorId,
      rungs: [...rungs].sort((a, b) => rungOrder(a) - rungOrder(b)),
    }))
  )

  return {
    tree: root,
    vendors: [...vendorIds].sort().map((vendorId) => ({ vendorId })),
    edges,
  }
}
