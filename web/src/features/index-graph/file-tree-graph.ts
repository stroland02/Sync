/**
 * A repository's directory structure, as a tree.
 *
 * No DOM, no layout coordinates -- this only builds the tree. Where each node ends up on screen
 * is the renderer's problem, the same separation the layout module draws between deriving and
 * placing.
 *
 * **This module used to derive the canvas's edges too, and no longer does.** The canvas gained
 * the operation level (`operation-graph.ts`), so an edge is now file -> operation -> vendor and
 * every edge carries the rung it was established at; the two-level file -> vendor derivation this
 * file held could only hang a rung on a hop spanning two bindings, which named neither. It is
 * deleted rather than left beside its replacement, so nothing can build a second tree from a
 * second source and disagree about it.
 */

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

/** The directory tree the given paths imply, folders before files and alphabetical within each. */
/**
 * The path a file is drawn at once collapsed folders stand in for their contents.
 *
 * The aggregation every large-graph tool does (`references/notes/codebase-graph-ui.md`): a
 * directory is one node until a reader opens it, and everything inside it attaches to that
 * node. **Re-attaching rather than dropping is the whole point** — a collapsed folder's edges
 * are its subtree's edges, so collapsing changes the resolution of the picture and never its
 * claims. The shallowest collapsed ancestor wins, so collapsing a parent subsumes its children.
 */
export function visiblePath(path: string, collapsed: ReadonlySet<string>): string {
  if (collapsed.size === 0) return path
  const segments = path.split("/")
  for (let end = 1; end < segments.length; end += 1) {
    const ancestor = segments.slice(0, end).join("/")
    if (collapsed.has(ancestor)) return ancestor
  }
  return path
}

/**
 * Every folder at or below `depth`, for the default collapse of a tree too large to read.
 *
 * Depth rather than a node budget: a reader can predict "everything below the top level is
 * folded", and cannot predict "the first two hundred nodes are drawn".
 */
export function foldersAtDepth(root: FolderNode, depth: number): string[] {
  const found: string[] = []
  const walk = (node: FolderNode, level: number) => {
    for (const child of node.children) {
      if (child.kind !== "folder") continue
      if (level + 1 >= depth) found.push(child.path)
      else walk(child, level + 1)
    }
  }
  walk(root, 0)
  return found
}

export function buildFileTree(paths: string[]): FolderNode {
  const root: FolderNode = { kind: "folder", name: "", path: "", children: [] }
  for (const path of paths) insert(root, path)
  sortTree(root)
  return root
}
