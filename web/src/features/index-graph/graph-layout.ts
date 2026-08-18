/**
 * Where every node on the dependency canvas sits, derived from the graph and from nothing else.
 *
 * This module has no DOM in it, on purpose. jsdom answers `getBoundingClientRect` with zeroes, so a
 * canvas that decided its own geometry while rendering would be a canvas nothing could test —
 * `.claude/rules/console-dev-loop.md` puts pixels in Chrome and derivations here, and node placement
 * is a derivation with a wrong answer. The component below it reads positions; it never computes
 * them.
 *
 * **The graph is the API dependency graph, not a schema.** Three ranks — vendor, operation, call
 * site — and the two edge kinds between them are not the same kind of claim:
 *
 * - **operation → call site is a binding, and it carries the rung it was established at.** That is
 *   the column `sync.core.models` writes and `RiskRow.binding_source` / `BindingCallSite.binding_rung`
 *   carry to the console. It is what makes this canvas worth drawing rather than decorative.
 * - **vendor → operation is containment, and it carries no rung.** Nothing established it by
 *   evidence: the operation belongs to the vendor because the payload names the pair. Handing it the
 *   rung of the call sites underneath would invent provenance, and reducing those rungs to one value
 *   would be the composite this console refuses everywhere else. `rungs` is `null` there and the
 *   canvas says so in words.
 *
 * A rung is a class of evidence, not a position on a scale, so nothing here orders rungs, scores
 * them, or lets the layout imply one is better than another. `BINDING_SOURCES` supplies the one
 * ordering used — the vocabulary's own declared order — and it is used only to make a multi-rung
 * label deterministic.
 */

import { BINDING_SOURCES, type BindingSource } from "@/api/types"

/**
 * One row of the graph as the console receives it.
 *
 * `RiskRow` (`/api/vendors/{id}`) and `BindingCallSite` (`.../operations/{id}/bindings`) both
 * project onto this. Deliberately not either of those types: the canvas takes its data as props so
 * a caller can assemble it from whichever routes it already holds, and a component typed to one
 * route could not be given the other.
 */
export interface BindingRow {
  vendor: string
  /** `null` when nothing could attribute the call site to an operation. A named absence, not a gap. */
  operation: string | null
  file: string
  line: number
  symbol: string | null
  /** The rung the binding between this call site and that operation was established at. */
  rung: BindingSource
  /** The kind the detector emitted, or `null` when it emitted none. Never a severity invented here. */
  changeKind?: string | null
}

/** What the vendor-level routes know about a vendor, with every unanswered question left `null`. */
export interface VendorInput {
  vendorId: string
  /** `/api/overview`. `null` when no count was read for this scope — different from a count of nought. */
  openFindingCount: number | null
  /**
   * `/api/repositories/{repo_id}/coverage`. `null` when coverage was never read, which includes
   * every repository whose id contains a slash: that route answers 404 for those (`B147`).
   */
  indexedCallSiteCount: number | null
  /** The newest `indexed_at` among this vendor's call sites. Staleness, never a promise of currency. */
  lastIndexed: string | null
  /**
   * Whether this vendor's bindings were fetched at all. `false` with no rows means nothing was asked;
   * `true` with no rows means the answer was none. Collapsing those two is the defect this flag exists
   * to prevent.
   */
  bindingsQueried: boolean
}

export interface DependencyGraphInput {
  vendors: VendorInput[]
  rows: BindingRow[]
}

export type NodeKind = "vendor" | "operation" | "call-site"

/**
 * Node extents in graph units, which are the SVG's own user units.
 *
 * Not spacing tokens: `DESIGN.md`'s four spacing values govern the distance between a label and its
 * value inside a card, and these are the size of the card itself on an infinite plane. They are
 * page-layout numbers used once, in one module, the way `layouts/` spells the sidebar's width.
 */
export const NODE_SIZE = {
  vendor: { width: 264, height: 152 },
  operation: { width: 216, height: 84 },
  "call-site": { width: 300, height: 100 },
} as const satisfies Record<NodeKind, { width: number; height: number }>

export const COLUMN_GAP = 112
/** Between two call sites of one operation. */
export const SIBLING_GAP = 16
/** Between two operation groups of one vendor. */
export const GROUP_GAP = 40
/** Between two vendors. Wide enough that a vendor card centred on one short child cannot meet its neighbour. */
export const VENDOR_GAP = 96
/** The margin `fitViewport` frames the graph with. */
export const CANVAS_PADDING = 64

export const MAX_ZOOM_IN = 4
export const MAX_ZOOM_OUT = 2

interface NodeBase {
  id: string
  x: number
  y: number
  width: number
  height: number
  rank: 0 | 1 | 2
}

export interface VendorNode extends NodeBase {
  kind: "vendor"
  rank: 0
  vendor: VendorInput
  /** Operation groups drawn under this vendor, including the unattributed one. */
  operationCount: number
  /** Distinct call sites drawn under this vendor. Not the coverage figure, which counts a different set. */
  callSiteCount: number
}

export interface OperationNode extends NodeBase {
  kind: "operation"
  rank: 1
  vendorId: string
  /** `null` is the group holding call sites nothing could attribute to an operation. */
  operationId: string | null
  callSiteCount: number
}

export interface CallSiteNode extends NodeBase {
  kind: "call-site"
  rank: 2
  vendorId: string
  operationId: string | null
  file: string
  line: number
  symbol: string | null
  /** Every distinct rung the rows gave this binding, in the vocabulary's declared order. */
  rungs: BindingSource[]
  /** Every distinct change kind the detector emitted here. Empty when it emitted none. */
  changeKinds: string[]
}

export type GraphNode = VendorNode | OperationNode | CallSiteNode

export type GraphEdge =
  | { id: string; from: string; to: string; relation: "contains"; rungs: null }
  | { id: string; from: string; to: string; relation: "binds"; rungs: BindingSource[] }

export interface Bounds {
  x: number
  y: number
  width: number
  height: number
}

export type Viewport = Bounds

export interface DependencyGraphLayout {
  nodes: GraphNode[]
  edges: GraphEdge[]
  bounds: Bounds
}

/** The x of a rank's column. Ranks are laid out left to right and never share a column. */
export function columnX(rank: 0 | 1 | 2): number {
  if (rank === 0) return 0
  if (rank === 1) return NODE_SIZE.vendor.width + COLUMN_GAP
  return NODE_SIZE.vendor.width + COLUMN_GAP + NODE_SIZE.operation.width + COLUMN_GAP
}

/**
 * What an edge says about itself, as a word.
 *
 * A binding edge reads as its rung, which is the whole point: the label is the channel, and colour
 * is not used at all here, so nothing about the edge depends on a reader distinguishing two hues.
 * A containment edge returns `null` — it has nothing to claim, and a placeholder word would be a
 * claim.
 */
export function edgeRungLabel(edge: GraphEdge): string | null {
  if (edge.relation === "contains") return null
  return edge.rungs.join(" + ")
}

function rungOrder(rung: BindingSource): number {
  const index = BINDING_SOURCES.indexOf(rung)
  return index === -1 ? BINDING_SOURCES.length : index
}

function sortedRungs(rungs: Iterable<BindingSource>): BindingSource[] {
  return [...new Set(rungs)].sort((a, b) => rungOrder(a) - rungOrder(b))
}

interface SiteAccumulator {
  file: string
  line: number
  symbol: string | null
  rungs: Set<BindingSource>
  changeKinds: Set<string>
}

interface OperationAccumulator {
  operationId: string | null
  sites: Map<string, SiteAccumulator>
}

interface VendorAccumulator {
  vendorId: string
  operations: Map<string, OperationAccumulator>
}

/** The key the unattributed group is filed under. Never rendered; the node carries `operationId: null`. */
const UNATTRIBUTED = " unattributed"

function collect(input: DependencyGraphInput): VendorAccumulator[] {
  const vendors = new Map<string, VendorAccumulator>()
  const ensure = (vendorId: string): VendorAccumulator => {
    const existing = vendors.get(vendorId)
    if (existing !== undefined) return existing
    const created: VendorAccumulator = { vendorId, operations: new Map() }
    vendors.set(vendorId, created)
    return created
  }

  for (const vendor of input.vendors) ensure(vendor.vendorId)

  for (const row of input.rows) {
    const vendor = ensure(row.vendor)
    const operationKey = row.operation === null ? UNATTRIBUTED : row.operation
    let operation = vendor.operations.get(operationKey)
    if (operation === undefined) {
      operation = { operationId: row.operation, sites: new Map() }
      vendor.operations.set(operationKey, operation)
    }
    const siteKey = `${row.file}:${row.line}:${row.symbol ?? ""}`
    let site = operation.sites.get(siteKey)
    if (site === undefined) {
      site = {
        file: row.file,
        line: row.line,
        symbol: row.symbol,
        rungs: new Set(),
        changeKinds: new Set(),
      }
      operation.sites.set(siteKey, site)
    }
    site.rungs.add(row.rung)
    if (row.changeKind !== null && row.changeKind !== undefined && row.changeKind !== "") {
      site.changeKinds.add(row.changeKind)
    }
  }

  return [...vendors.values()].sort((a, b) => a.vendorId.localeCompare(b.vendorId))
}

/**
 * A vendor the overview never listed, but which a row names.
 *
 * Every count is `null`, because nothing counted them. Dropping the vendor instead would narrow the
 * drawn graph to whatever one route happened to return, silently.
 */
function unlistedVendor(vendorId: string): VendorInput {
  return {
    vendorId,
    openFindingCount: null,
    indexedCallSiteCount: null,
    lastIndexed: null,
    bindingsQueried: true,
  }
}

function centreOf(node: { y: number; height: number }): number {
  return node.y + node.height / 2
}

/** The y that centres a box of `height` on the span its children occupy. */
function centredOn(children: { y: number; height: number }[], height: number): number {
  const centres = children.map(centreOf)
  return (Math.min(...centres) + Math.max(...centres)) / 2 - height / 2
}

export function layoutDependencyGraph(input: DependencyGraphInput): DependencyGraphLayout {
  const declared = new Map(input.vendors.map((vendor) => [vendor.vendorId, vendor]))
  const nodes: GraphNode[] = []
  const edges: GraphEdge[] = []
  let cursor = 0

  for (const [vendorIndex, vendor] of collect(input).entries()) {
    if (vendorIndex > 0) cursor += VENDOR_GAP

    const named = [...vendor.operations.entries()]
      .filter(([key]) => key !== UNATTRIBUTED)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([, operation]) => operation)
    const unattributed = vendor.operations.get(UNATTRIBUTED)
    // The unattributed group always sits last, so its position is a stated convention rather than
    // an accident of whichever row arrived first.
    const operations = unattributed === undefined ? named : [...named, unattributed]

    const operationNodes: OperationNode[] = []
    let vendorCallSites = 0

    for (const [operationIndex, operation] of operations.entries()) {
      if (operationIndex > 0) cursor += GROUP_GAP

      const operationNodeId = `op:${vendor.vendorId}/${operation.operationId ?? UNATTRIBUTED}`
      const siteNodes: CallSiteNode[] = []
      const sites = [...operation.sites.entries()].sort(([a], [b]) => a.localeCompare(b))

      for (const [siteIndex, [siteKey, site]] of sites.entries()) {
        if (siteIndex > 0) cursor += SIBLING_GAP
        const node: CallSiteNode = {
          id: `site:${operationNodeId}/${siteKey}`,
          kind: "call-site",
          rank: 2,
          x: columnX(2),
          y: cursor,
          width: NODE_SIZE["call-site"].width,
          height: NODE_SIZE["call-site"].height,
          vendorId: vendor.vendorId,
          operationId: operation.operationId,
          file: site.file,
          line: site.line,
          symbol: site.symbol,
          rungs: sortedRungs(site.rungs),
          changeKinds: [...site.changeKinds].sort(),
        }
        cursor += node.height
        siteNodes.push(node)
        nodes.push(node)
        edges.push({
          id: `binds:${node.id}`,
          from: operationNodeId,
          to: node.id,
          relation: "binds",
          rungs: node.rungs,
        })
      }

      const operationNode: OperationNode = {
        id: operationNodeId,
        kind: "operation",
        rank: 1,
        x: columnX(1),
        y:
          siteNodes.length === 0
            ? cursor
            : centredOn(siteNodes, NODE_SIZE.operation.height),
        width: NODE_SIZE.operation.width,
        height: NODE_SIZE.operation.height,
        vendorId: vendor.vendorId,
        operationId: operation.operationId,
        callSiteCount: siteNodes.length,
      }
      if (siteNodes.length === 0) cursor += operationNode.height
      operationNodes.push(operationNode)
      nodes.push(operationNode)
      vendorCallSites += siteNodes.length
    }

    const vendorNode: VendorNode = {
      id: `vendor:${vendor.vendorId}`,
      kind: "vendor",
      rank: 0,
      x: columnX(0),
      y:
        operationNodes.length === 0
          ? cursor
          : centredOn(operationNodes, NODE_SIZE.vendor.height),
      width: NODE_SIZE.vendor.width,
      height: NODE_SIZE.vendor.height,
      vendor: declared.get(vendor.vendorId) ?? unlistedVendor(vendor.vendorId),
      operationCount: operationNodes.length,
      callSiteCount: vendorCallSites,
    }
    if (operationNodes.length === 0) cursor += vendorNode.height
    nodes.push(vendorNode)
    for (const operationNode of operationNodes) {
      edges.push({
        id: `contains:${operationNode.id}`,
        from: vendorNode.id,
        to: operationNode.id,
        relation: "contains",
        rungs: null,
      })
    }
  }

  return { nodes, edges, bounds: boundsOf(nodes) }
}

function boundsOf(nodes: GraphNode[]): Bounds {
  if (nodes.length === 0) return { x: 0, y: 0, width: 0, height: 0 }
  const left = Math.min(...nodes.map((node) => node.x))
  const top = Math.min(...nodes.map((node) => node.y))
  const right = Math.max(...nodes.map((node) => node.x + node.width))
  const bottom = Math.max(...nodes.map((node) => node.y + node.height))
  return { x: left, y: top, width: right - left, height: bottom - top }
}

/** The whole graph, framed. */
export function fitViewport(bounds: Bounds): Viewport {
  return {
    x: bounds.x - CANVAS_PADDING,
    y: bounds.y - CANVAS_PADDING,
    width: bounds.width + 2 * CANVAS_PADDING,
    height: bounds.height + 2 * CANVAS_PADDING,
  }
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(Math.max(value, low), high)
}

/**
 * Zoom about the view's own centre, bounded at both ends.
 *
 * The limits are relative to the fitted view rather than absolute, so they mean the same thing on a
 * graph with three call sites and on one with three hundred.
 */
export function zoomViewport(view: Viewport, factor: number, fit: Viewport): Viewport {
  const width = clamp(view.width / factor, fit.width / MAX_ZOOM_IN, fit.width * MAX_ZOOM_OUT)
  const height = view.height * (width / view.width)
  const centreX = view.x + view.width / 2
  const centreY = view.y + view.height / 2
  return { x: centreX - width / 2, y: centreY - height / 2, width, height }
}

/** Pan by a delta already converted into graph units, with the view's centre held inside the graph. */
export function panViewport(view: Viewport, dx: number, dy: number, fit: Viewport): Viewport {
  const centreX = clamp(view.x + view.width / 2 + dx, fit.x, fit.x + fit.width)
  const centreY = clamp(view.y + view.height / 2 + dy, fit.y, fit.y + fit.height)
  return { x: centreX - view.width / 2, y: centreY - view.height / 2, width: view.width, height: view.height }
}
