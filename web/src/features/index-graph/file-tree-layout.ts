/**
 * Positions for `file-tree-graph.ts`'s tree and vendor nodes, plus the viewport cull that makes
 * a large tree affordable to render. `fitViewport`, `zoomViewport`, `panViewport` and `Viewport`
 * are `graph-layout.ts`'s own and are re-exported rather than duplicated -- pan/zoom arithmetic
 * is the same question on any graph this canvas ever draws.
 *
 * `visibleNodes` is the "not a static SVG" half of owner decision 13: a repository can index tens
 * of thousands of call sites, and mounting a DOM node for every one of them regardless of what is
 * actually on screen is the thing a static SVG does. This module's contract is that a caller
 * renders only what `visibleNodes` returns for the current viewport, recomputed on every pan and
 * zoom -- the layout itself is computed once, and culling is a filter over it, not a second
 * layout pass.
 */

export { fitViewport, panViewport, zoomViewport, type Viewport, type Bounds } from "@/features/index-graph/viewport"

import type { Bounds } from "@/features/index-graph/viewport"
import type { FileTreeGraph, TreeNode } from "@/features/index-graph/file-tree-graph"

export const ROW_HEIGHT = 28
export const INDENT = 20
export const FILE_NODE_WIDTH = 220
export const VENDOR_COLUMN_GAP = 160
export const VENDOR_NODE_WIDTH = 160
export const VENDOR_NODE_HEIGHT = 40

export type FileTreeLayoutNode =
  | { id: string; kind: "folder" | "file"; name: string; path: string; depth: number; x: number; y: number; width: number; height: number }
  | { id: string; kind: "vendor"; vendorId: string; x: number; y: number; width: number; height: number }

export interface FileTreeLayoutEdge {
  id: string
  from: string
  to: string
}

export interface FileTreeLayout {
  nodes: FileTreeLayoutNode[]
  edges: FileTreeLayoutEdge[]
  bounds: Bounds
}

function walk(
  node: TreeNode,
  depth: number,
  cursor: { y: number },
  nodes: FileTreeLayoutNode[],
  fileY: Map<string, number>
): void {
  const y = cursor.y
  const x = depth * INDENT
  if (node.kind === "file") {
    nodes.push({ id: `path:${node.path}`, kind: "file", name: node.name, path: node.path, depth, x, y, width: FILE_NODE_WIDTH - x, height: ROW_HEIGHT })
    fileY.set(node.path, y)
    cursor.y += ROW_HEIGHT
    return
  }
  // The root folder ("") is a container only -- it never gets its own row, so a one-file
  // repository does not open on an empty "/" band above its only entry.
  if (node.path !== "") {
    nodes.push({ id: `path:${node.path}`, kind: "folder", name: node.name, path: node.path, depth, x, y, width: FILE_NODE_WIDTH - x, height: ROW_HEIGHT })
    cursor.y += ROW_HEIGHT
  }
  for (const child of node.children) walk(child, node.path === "" ? depth : depth + 1, cursor, nodes, fileY)
}

function boundsOf(nodes: { x: number; y: number; width: number; height: number }[]): Bounds {
  if (nodes.length === 0) return { x: 0, y: 0, width: 0, height: 0 }
  const left = Math.min(...nodes.map((n) => n.x))
  const top = Math.min(...nodes.map((n) => n.y))
  const right = Math.max(...nodes.map((n) => n.x + n.width))
  const bottom = Math.max(...nodes.map((n) => n.y + n.height))
  return { x: left, y: top, width: right - left, height: bottom - top }
}

export function layoutFileTree(graph: FileTreeGraph): FileTreeLayout {
  const treeNodes: FileTreeLayoutNode[] = []
  const fileY = new Map<string, number>()
  walk(graph.tree, 0, { y: 0 }, treeNodes, fileY)

  const vendorX = FILE_NODE_WIDTH + VENDOR_COLUMN_GAP
  const vendorNodes: FileTreeLayoutNode[] = graph.vendors.map((vendor) => {
    const connectedFiles = graph.edges.filter((e) => e.vendorId === vendor.vendorId).map((e) => fileY.get(e.file))
    const ys = connectedFiles.filter((y): y is number => y !== undefined)
    const centre = ys.length === 0 ? 0 : (Math.min(...ys) + Math.max(...ys) + ROW_HEIGHT) / 2
    return {
      id: `vendor:${vendor.vendorId}`,
      kind: "vendor",
      vendorId: vendor.vendorId,
      x: vendorX,
      y: centre - VENDOR_NODE_HEIGHT / 2,
      width: VENDOR_NODE_WIDTH,
      height: VENDOR_NODE_HEIGHT,
    }
  })

  const edges: FileTreeLayoutEdge[] = graph.edges.map((edge) => ({
    id: `edge:${edge.file}->${edge.vendorId}`,
    from: `path:${edge.file}`,
    to: `vendor:${edge.vendorId}`,
  }))

  const nodes = [...treeNodes, ...vendorNodes]
  return { nodes, edges, bounds: boundsOf(nodes) }
}

/**
 * Which of `nodes` a viewport this size, at this position, actually needs to draw.
 *
 * Overlap rather than containment: a node half in view is still visible and still needs to
 * render, so this excludes only a node whose bounds share no pixel with the viewport's.
 */
export function visibleNodes<T extends { x: number; y: number; width: number; height: number }>(
  nodes: T[],
  view: { x: number; y: number; width: number; height: number }
): T[] {
  return nodes.filter(
    (node) =>
      node.x + node.width >= view.x &&
      node.x <= view.x + view.width &&
      node.y + node.height >= view.y &&
      node.y <= view.y + view.height
  )
}
