/**
 * The indexing canvas's three levels: file -> operation -> vendor.
 *
 * The coordinator's dispatch asked for vendor -> operation -> call site, the shape owner decision
 * 8 names and rejects ("this is a different build from the schema-visualiser shape"). The ruling
 * was to reconcile rather than revert: keep decision 8's framing — the reader's own file tree —
 * and insert the operation level the dispatch was really after. src/api/billing.ts -> PostCharges
 * -> stripe.
 *
 * What that buys, and what these assert: EVERY edge now carries the rung it was established at.
 * The two-level shape could only put a rung on file -> vendor, which is a rung on a hop that
 * spans two bindings.
 */

import { describe, expect, it } from "vitest"

import { buildOperationGraph, type CallBindingRow } from "@/features/index-graph/operation-graph"

const row = (over: Partial<CallBindingRow> = {}): CallBindingRow => ({
  file: "src/api/billing.ts",
  vendorId: "stripe",
  operationId: "PostCharges",
  rung: "static",
  ...over,
})

describe("buildOperationGraph", () => {
  it("puts the operation between the file and the vendor", () => {
    const graph = buildOperationGraph([row()])

    expect(graph.operations).toEqual([{ operationId: "PostCharges", vendorId: "stripe" }])
    expect(graph.fileEdges).toEqual([
      {
        file: "src/api/billing.ts",
        operationId: "PostCharges",
        vendorId: "stripe",
        rungs: ["static"],
      },
    ])
    expect(graph.vendorEdges).toEqual([
      { operationId: "PostCharges", vendorId: "stripe", rungs: ["static"] },
    ])
  })

  /** The point of the level. A rung on file -> vendor spanned two bindings and named neither. */
  it("carries a rung on every edge, on both hops", () => {
    const graph = buildOperationGraph([row({ rung: "observed" })])

    expect(graph.fileEdges.every((edge) => edge.rungs.length > 0)).toBe(true)
    expect(graph.vendorEdges.every((edge) => edge.rungs.length > 0)).toBe(true)
  })

  it("keeps two rungs on one hop as two rungs, never collapsing to the stronger", () => {
    const graph = buildOperationGraph([row({ rung: "static" }), row({ rung: "observed" })])

    expect(graph.fileEdges[0].rungs).toEqual(["static", "observed"])
  })

  it("orders rungs by the vocabulary rather than by arrival", () => {
    const graph = buildOperationGraph([row({ rung: "observed" }), row({ rung: "static" })])

    expect(graph.fileEdges[0].rungs).toEqual(["static", "observed"])
  })

  it("joins two files calling one operation to the same operation node", () => {
    const graph = buildOperationGraph([
      row({ file: "a.ts" }),
      row({ file: "b.ts" }),
    ])

    expect(graph.operations).toHaveLength(1)
    expect(graph.fileEdges).toHaveLength(2)
    expect(graph.vendorEdges).toHaveLength(1)
  })

  it("keeps two vendors' identically named operations apart", () => {
    const graph = buildOperationGraph([
      row({ vendorId: "stripe", operationId: "Charge" }),
      row({ vendorId: "adyen", operationId: "Charge" }),
    ])

    expect(graph.operations).toHaveLength(2)
  })

  /**
   * An indexed call site that names no operation cannot get an operation node without the canvas
   * inventing one. It is off the path, and off-path is a place on this screen rather than a
   * silent drop.
   */
  it("routes a binding naming no operation off-path instead of inventing a node", () => {
    const graph = buildOperationGraph([row({ operationId: "" })])

    expect(graph.operations).toEqual([])
    expect(graph.fileEdges).toEqual([])
    expect(graph.unroutable).toEqual([
      { file: "src/api/billing.ts", vendorId: "stripe", rungs: ["static"] },
    ])
  })

  it("reports no unroutable bindings as an empty list rather than omitting the field", () => {
    expect(buildOperationGraph([row()]).unroutable).toEqual([])
  })

  it("names a vendor the caller knows about even when no row draws an edge to it", () => {
    const graph = buildOperationGraph([], ["stripe"])

    expect(graph.vendors).toEqual([{ vendorId: "stripe" }])
    expect(graph.operations).toEqual([])
  })

  it("sorts every level so the picture does not reshuffle between reads", () => {
    const graph = buildOperationGraph([
      row({ vendorId: "zed", operationId: "B", file: "z.ts" }),
      row({ vendorId: "acme", operationId: "A", file: "a.ts" }),
    ])

    expect(graph.vendors.map((v) => v.vendorId)).toEqual(["acme", "zed"])
    expect(graph.operations.map((o) => o.operationId)).toEqual(["A", "B"])
    expect(graph.fileEdges.map((e) => e.file)).toEqual(["a.ts", "z.ts"])
  })
})
