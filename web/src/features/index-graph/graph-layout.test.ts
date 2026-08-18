/**
 * The dependency canvas's layout, tested where it is a derivation rather than a rendering.
 *
 * jsdom has no layout engine, so `getBoundingClientRect` answers zeroes and a geometry assertion
 * against the DOM is worthless. The whole point of putting node placement in a pure module is that
 * the hard part becomes arithmetic over a graph, which jsdom checks perfectly well. Everything
 * about rendered pixels stays out of here and is measured in Chrome, per
 * `.claude/rules/console-dev-loop.md`.
 *
 * Four properties this file exists to hold, each of which is one careless line away from becoming
 * a claim the payload cannot support:
 *
 * - **A rung belongs to a binding, and only to a binding.** The edge from a vendor to one of its
 *   operations is containment. Giving it the rung of the call sites underneath would be a rung
 *   nothing established, and aggregating the rungs beneath it would be the composite this console
 *   refuses in every other place it could appear.
 * - **Two rows disagreeing about a call site's rung stay two rungs.** Picking one would be a
 *   silent decision about evidence.
 * - **A call site nothing could attribute to an operation is a named absence**, not a row dropped
 *   and not a row filed under an invented operation.
 * - **Never-queried is not zero.** A vendor whose bindings were never fetched holds a different
 *   fact from one that was fetched and holds none.
 */

import { describe, expect, it } from "vitest"

import { BINDING_SOURCES, type BindingSource } from "@/api/types"
import {
  CANVAS_PADDING,
  MAX_ZOOM_IN,
  MAX_ZOOM_OUT,
  NODE_SIZE,
  type BindingRow,
  type DependencyGraphInput,
  type GraphNode,
  type VendorInput,
  columnX,
  edgeRungLabel,
  fitViewport,
  layoutDependencyGraph,
  panViewport,
  zoomViewport,
} from "@/features/index-graph/graph-layout"

function vendor(vendorId: string, over: Partial<VendorInput> = {}): VendorInput {
  return {
    vendorId,
    openFindingCount: 0,
    indexedCallSiteCount: 0,
    lastIndexed: null,
    bindingsQueried: true,
    ...over,
  }
}

function row(over: Partial<BindingRow> = {}): BindingRow {
  return {
    vendor: "stripe",
    operation: "PostCharges",
    file: "src/checkout.ts",
    line: 5,
    symbol: "stripe.charges.create",
    rung: "static",
    changeKind: null,
    ...over,
  }
}

/** The shape of the seeded graph the API actually answers with, shrunk to three vendors. */
const realistic: DependencyGraphInput = {
  vendors: [
    vendor("stripe", { openFindingCount: 10, indexedCallSiteCount: 31 }),
    vendor("seed-console-twilio", { openFindingCount: 1, indexedCallSiteCount: 2 }),
    vendor("seed-console-stripe", { openFindingCount: 4, indexedCallSiteCount: null }),
  ],
  rows: [
    row(),
    row({ file: "src/index.ts", line: 1 }),
    row({
      operation: "GetAccounts",
      file: "app/api/debug/get_demo_account/route.ts",
      line: 9,
      symbol: "stripe.accounts.list",
      changeKind: "response-optional-property-removed",
    }),
    row({ vendor: "seed-console-twilio", operation: "PostMessages", file: "lib/sms.ts", line: 42 }),
    row({ vendor: "seed-console-stripe", operation: null, file: "lib/unknown.ts", line: 7 }),
  ],
}

function nodesOfRank(layout: { nodes: GraphNode[] }, rank: number): GraphNode[] {
  return layout.nodes.filter((node) => node.rank === rank)
}

describe("layoutDependencyGraph — the three ranks", () => {
  it("puts every vendor, operation and call site on its own rank, left to right", () => {
    const layout = layoutDependencyGraph(realistic)

    expect(layout.nodes.length).toBeGreaterThan(0)
    for (const node of layout.nodes) {
      const rank = node.kind === "vendor" ? 0 : node.kind === "operation" ? 1 : 2
      expect(node.rank).toBe(rank)
      expect(node.x).toBe(columnX(node.rank))
      expect(node.width).toBe(NODE_SIZE[node.kind].width)
      expect(node.height).toBe(NODE_SIZE[node.kind].height)
    }
    expect(columnX(0)).toBeLessThan(columnX(1))
    expect(columnX(1)).toBeLessThan(columnX(2))
  })

  it("gives each rank at least one node for the graph the API actually answers with", () => {
    const layout = layoutDependencyGraph(realistic)

    for (const rank of [0, 1, 2]) {
      expect(nodesOfRank(layout, rank).length).toBeGreaterThan(0)
    }
  })

  it("stacks the nodes in a rank without overlapping them", () => {
    const layout = layoutDependencyGraph(realistic)

    for (const rank of [0, 1, 2]) {
      const stacked = nodesOfRank(layout, rank).sort((a, b) => a.y - b.y)
      expect(stacked.length).toBeGreaterThan(0)
      for (let i = 1; i < stacked.length; i += 1) {
        expect(stacked[i].y).toBeGreaterThanOrEqual(stacked[i - 1].y + stacked[i - 1].height)
      }
    }
  })

  it("centres a parent on the children it owns", () => {
    const layout = layoutDependencyGraph(realistic)

    const operations = nodesOfRank(layout, 1)
    expect(operations.length).toBeGreaterThan(0)
    for (const operation of operations) {
      const children = layout.edges
        .filter((edge) => edge.from === operation.id)
        .map((edge) => layout.nodes.find((node) => node.id === edge.to))
        .filter((node): node is GraphNode => node !== undefined)
      expect(children.length).toBeGreaterThan(0)
      const centres = children.map((child) => child.y + child.height / 2)
      const span = (Math.min(...centres) + Math.max(...centres)) / 2
      expect(operation.y + operation.height / 2).toBeCloseTo(span, 6)
    }
  })

  it("holds every node inside the bounds it reports", () => {
    const layout = layoutDependencyGraph(realistic)

    expect(layout.nodes.length).toBeGreaterThan(0)
    for (const node of layout.nodes) {
      expect(node.x).toBeGreaterThanOrEqual(layout.bounds.x)
      expect(node.y).toBeGreaterThanOrEqual(layout.bounds.y)
      expect(node.x + node.width).toBeLessThanOrEqual(layout.bounds.x + layout.bounds.width)
      expect(node.y + node.height).toBeLessThanOrEqual(layout.bounds.y + layout.bounds.height)
    }
  })

  it("derives the same canvas whatever order the rows arrived in", () => {
    const reversed: DependencyGraphInput = {
      vendors: [...realistic.vendors].reverse(),
      rows: [...realistic.rows].reverse(),
    }

    expect(layoutDependencyGraph(reversed)).toEqual(layoutDependencyGraph(realistic))
  })
})

describe("layoutDependencyGraph — the edges and what they may claim", () => {
  it("carries the rung on the binding edge and refuses to invent one for containment", () => {
    const layout = layoutDependencyGraph(realistic)

    const binds = layout.edges.filter((edge) => edge.relation === "binds")
    const contains = layout.edges.filter((edge) => edge.relation === "contains")
    expect(binds.length).toBeGreaterThan(0)
    expect(contains.length).toBeGreaterThan(0)

    for (const edge of binds) {
      expect(edge.rungs).not.toBeNull()
      expect(edge.rungs?.length).toBeGreaterThan(0)
    }
    for (const edge of contains) {
      // A vendor contains an operation. Nothing established that by evidence, so it holds no
      // rung -- not the rung of the call sites beneath it, and not a blend of them.
      expect(edge.rungs).toBeNull()
    }
  })

  it("writes every rung as its own word, so an edge reads without colour", () => {
    expect(BINDING_SOURCES.length).toBeGreaterThan(0)

    for (const rung of BINDING_SOURCES) {
      const label = edgeRungLabel({
        id: "e",
        from: "a",
        to: "b",
        relation: "binds",
        rungs: [rung],
      })
      expect(label).toBe(rung)
    }
    expect(
      edgeRungLabel({ id: "e", from: "a", to: "b", relation: "contains", rungs: null })
    ).toBeNull()
  })

  it("keeps both rungs when two rows disagree about one call site", () => {
    const layout = layoutDependencyGraph({
      vendors: [vendor("stripe")],
      rows: [row({ rung: "observed" }), row({ rung: "static" })],
    })

    const binds = layout.edges.filter((edge) => edge.relation === "binds")
    expect(binds).toHaveLength(1)
    // Ordered by the vocabulary's own order, not by which row arrived first.
    expect(binds[0].rungs).toEqual(["static", "observed"])
    expect(edgeRungLabel(binds[0])).toContain("static")
    expect(edgeRungLabel(binds[0])).toContain("observed")
  })

  it("gives every node but a vendor exactly one parent, and lands every edge on a real node", () => {
    const layout = layoutDependencyGraph(realistic)

    const ids = new Set(layout.nodes.map((node) => node.id))
    expect(layout.edges.length).toBeGreaterThan(0)
    for (const edge of layout.edges) {
      expect(ids.has(edge.from)).toBe(true)
      expect(ids.has(edge.to)).toBe(true)
    }

    const children = layout.nodes.filter((node) => node.kind !== "vendor")
    expect(children.length).toBeGreaterThan(0)
    for (const child of children) {
      expect(layout.edges.filter((edge) => edge.to === child.id)).toHaveLength(1)
    }
  })
})

describe("layoutDependencyGraph — what the payload does and does not say", () => {
  it("files a call site attributed to no operation under a named absence, rather than dropping it", () => {
    const layout = layoutDependencyGraph({
      vendors: [vendor("acme")],
      rows: [row({ vendor: "acme", operation: null, file: "lib/unknown.ts", line: 7 })],
    })

    const operations = layout.nodes.filter((node) => node.kind === "operation")
    expect(operations).toHaveLength(1)
    expect(operations[0].kind === "operation" && operations[0].operationId).toBeNull()
    expect(layout.nodes.filter((node) => node.kind === "call-site")).toHaveLength(1)
  })

  it("orders the unattributed group last, under whichever vendor holds it", () => {
    const layout = layoutDependencyGraph({
      vendors: [vendor("acme")],
      rows: [
        row({ vendor: "acme", operation: null, file: "a.ts", line: 1 }),
        row({ vendor: "acme", operation: "ZLast", file: "b.ts", line: 1 }),
        row({ vendor: "acme", operation: "AFirst", file: "c.ts", line: 1 }),
      ],
    })

    const operations = layout.nodes
      .filter((node) => node.kind === "operation")
      .sort((a, b) => a.y - b.y)
    expect(operations).toHaveLength(3)
    expect(operations.map((node) => (node.kind === "operation" ? node.operationId : "?"))).toEqual([
      "AFirst",
      "ZLast",
      null,
    ])
  })

  it("draws a vendor a row names even when the overview never listed it", () => {
    // Dropping it would be the console quietly narrowing the graph to whatever one route returned.
    const layout = layoutDependencyGraph({
      vendors: [],
      rows: [row({ vendor: "twilio" })],
    })

    const vendors = layout.nodes.filter((node) => node.kind === "vendor")
    expect(vendors).toHaveLength(1)
    expect(vendors[0].kind === "vendor" && vendors[0].vendor.vendorId).toBe("twilio")
    // Nothing counted this vendor's findings or call sites, so nothing may claim a figure.
    expect(vendors[0].kind === "vendor" && vendors[0].vendor.openFindingCount).toBeNull()
    expect(vendors[0].kind === "vendor" && vendors[0].vendor.indexedCallSiteCount).toBeNull()
    expect(vendors[0].kind === "vendor" && vendors[0].vendor.bindingsQueried).toBe(true)
  })

  it("keeps never-queried apart from queried-and-empty on the vendor node", () => {
    const layout = layoutDependencyGraph({
      vendors: [vendor("never", { bindingsQueried: false }), vendor("empty")],
      rows: [],
    })

    const byId = new Map(
      layout.nodes
        .filter((node) => node.kind === "vendor")
        .map((node) => [node.id, node] as const)
    )
    expect(byId.size).toBe(2)
    for (const node of byId.values()) {
      expect(node.kind === "vendor" && node.operationCount).toBe(0)
      expect(node.kind === "vendor" && node.callSiteCount).toBe(0)
    }
    const flags = [...byId.values()].map(
      (node) => node.kind === "vendor" && node.vendor.bindingsQueried
    )
    expect(flags).toContain(true)
    expect(flags).toContain(false)
  })

  it("counts a call site once however many findings name it, and keeps the change kinds it emitted", () => {
    const layout = layoutDependencyGraph({
      vendors: [vendor("stripe")],
      rows: [
        row({ changeKind: "request-property-removed" }),
        row({ changeKind: "response-optional-property-removed" }),
        row({ changeKind: null }),
      ],
    })

    const sites = layout.nodes.filter((node) => node.kind === "call-site")
    expect(sites).toHaveLength(1)
    // The detector's own vocabulary, deduplicated and sorted -- never a severity this screen made up,
    // and a row that emitted no kind contributes nothing rather than a placeholder.
    expect(sites[0].kind === "call-site" && sites[0].changeKinds).toEqual([
      "request-property-removed",
      "response-optional-property-removed",
    ])

    const vendorNode = layout.nodes.find((node) => node.kind === "vendor")
    expect(vendorNode?.kind === "vendor" && vendorNode.callSiteCount).toBe(1)
    expect(vendorNode?.kind === "vendor" && vendorNode.operationCount).toBe(1)
  })

  it("answers an empty graph with a drawable frame rather than a zero-sized one", () => {
    const layout = layoutDependencyGraph({ vendors: [], rows: [] })

    expect(layout.nodes).toHaveLength(0)
    expect(layout.edges).toHaveLength(0)
    const view = fitViewport(layout.bounds)
    expect(view.width).toBeGreaterThan(0)
    expect(view.height).toBeGreaterThan(0)
  })
})

describe("the viewport", () => {
  const bounds = { x: 0, y: 0, width: 1000, height: 500 }

  it("frames the graph with the canvas padding on every side", () => {
    const view = fitViewport(bounds)

    expect(view.x).toBe(bounds.x - CANVAS_PADDING)
    expect(view.y).toBe(bounds.y - CANVAS_PADDING)
    expect(view.width).toBe(bounds.width + 2 * CANVAS_PADDING)
    expect(view.height).toBe(bounds.height + 2 * CANVAS_PADDING)
  })

  it("zooms about the centre and undoes itself exactly", () => {
    const fit = fitViewport(bounds)
    const centre = { x: fit.x + fit.width / 2, y: fit.y + fit.height / 2 }

    const closer = zoomViewport(fit, 2, fit)
    expect(closer.width).toBeCloseTo(fit.width / 2, 6)
    expect(closer.height).toBeCloseTo(fit.height / 2, 6)
    expect(closer.x + closer.width / 2).toBeCloseTo(centre.x, 6)
    expect(closer.y + closer.height / 2).toBeCloseTo(centre.y, 6)

    const back = zoomViewport(closer, 0.5, fit)
    expect(back.width).toBeCloseTo(fit.width, 6)
    expect(back.x).toBeCloseTo(fit.x, 6)
  })

  it("stops zooming at the declared limits instead of running to a degenerate view", () => {
    const fit = fitViewport(bounds)

    let view = fit
    for (let i = 0; i < 20; i += 1) view = zoomViewport(view, 2, fit)
    expect(view.width).toBeCloseTo(fit.width / MAX_ZOOM_IN, 6)

    view = fit
    for (let i = 0; i < 20; i += 1) view = zoomViewport(view, 0.5, fit)
    expect(view.width).toBeCloseTo(fit.width * MAX_ZOOM_OUT, 6)
  })

  it("pans by the delta it is given and never lets the graph leave the frame", () => {
    const fit = fitViewport(bounds)
    const view = zoomViewport(fit, 2, fit)

    expect(panViewport(view, 0, 0, fit)).toEqual(view)

    const nudged = panViewport(view, 10, -20, fit)
    expect(nudged.x).toBeCloseTo(view.x + 10, 6)
    expect(nudged.y).toBeCloseTo(view.y - 20, 6)

    const shoved = panViewport(view, 100_000, 100_000, fit)
    expect(shoved.x + shoved.width / 2).toBeCloseTo(fit.x + fit.width, 6)
    expect(shoved.y + shoved.height / 2).toBeCloseTo(fit.y + fit.height, 6)
  })
})

describe("the rung vocabulary this canvas draws", () => {
  it("has a word for every rung the payload can carry", () => {
    // The canvas may never meet a rung it has no word for and quietly draw a bare line.
    expect(BINDING_SOURCES.length).toBeGreaterThan(0)
    const labels = BINDING_SOURCES.map((rung: BindingSource) =>
      edgeRungLabel({ id: "e", from: "a", to: "b", relation: "binds", rungs: [rung] })
    )
    expect(new Set(labels).size).toBe(BINDING_SOURCES.length)
    for (const label of labels) {
      expect(label).toBeTruthy()
    }
  })
})
