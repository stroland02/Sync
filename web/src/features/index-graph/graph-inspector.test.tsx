/**
 * The inspector's derivations, and the three places it must not collapse one nothing into another.
 *
 * Scope is `web/CLAUDE.md`'s: classification and derivation, never class names. The three honesty
 * guards are the reason this file exists — a vendor never indexed must not read as indexed at
 * nought, an integration nothing correlated must not read as nought calls, and an operation with
 * no recorded vendor change must not wear a chip saying it is fine.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { RepositoryGraphResponse } from "@/api/types"
import type { ForceNode } from "@/features/index-graph/force-map"
import {
  callSitesInFile,
  GraphInspector,
  observedFor,
  operationsOfVendor,
} from "@/features/index-graph/graph-inspector"

const { bindingSurface } = vi.hoisted(() => ({ bindingSurface: vi.fn() }))

vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useBindingSurface: () => bindingSurface(),
}))

afterEach(() => {
  cleanup()
  bindingSurface.mockReset()
})

beforeEach(() => {
  bindingSurface.mockReturnValue({ isPending: true, isError: false, data: undefined, refetch: vi.fn() })
})

function bind(over: Partial<RepositoryGraphResponse["bindings"][number]> = {}) {
  return {
    vendor_id: "stripe",
    operation_id: "charge",
    path: "src/a/route.ts",
    line: 4,
    symbol: "charge",
    binding_rung: "static" as const,
    ...over,
  }
}

function graphOf(over: Partial<RepositoryGraphResponse> = {}): RepositoryGraphResponse {
  return {
    repo_id: "org/one",
    vendors: [],
    bindings: [],
    observed_bindings: [],
    off_path: { unresolved: 0, unattributed: 0 },
    rungs: [],
    indexed_at: "2026-08-20T09:00:00Z",
    total_bindings: 0,
    truncated: false,
    ...over,
  } as RepositoryGraphResponse
}

function node(over: Partial<ForceNode> & Pick<ForceNode, "id" | "kind" | "label">): ForceNode {
  return { weight: 1, ...over }
}

function renderInspector(graph: RepositoryGraphResponse, selected: ForceNode | null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <GraphInspector
          repoId="org/one"
          graph={graph}
          node={selected}
          nodeCount={3}
          offPathTotal={graph.off_path.unresolved + graph.off_path.unattributed}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("the derivations behind each branch", () => {
  it("matches a file on its recorded path and never on its basename", () => {
    const graph = graphOf({
      bindings: [bind({ path: "src/a/route.ts" }), bind({ path: "src/b/route.ts" })],
    })

    // Both nodes are labelled `route.ts` on the map; only the path tells them apart.
    expect(callSitesInFile(graph, "src/a/route.ts")).toHaveLength(1)
    expect(callSitesInFile(graph, "route.ts")).toHaveLength(0)
  })

  it("counts an integration's operations distinctly", () => {
    const graph = graphOf({
      bindings: [
        bind({ operation_id: "charge" }),
        bind({ operation_id: "charge", path: "src/b.ts" }),
        bind({ operation_id: "refund" }),
        bind({ vendor_id: "twilio", operation_id: "sms" }),
      ],
    })

    expect(operationsOfVendor(graph, "stripe")).toEqual(["charge", "refund"])
    expect(operationsOfVendor(graph, "twilio")).toEqual(["sms"])
  })

  it("narrows observed edges to the integration, and to one of its operations", () => {
    const graph = graphOf({
      observed_bindings: [
        { vendor_id: "stripe", operation_id: "charge", binding_rung: "observed", calls: 12 },
        { vendor_id: "stripe", operation_id: "refund", binding_rung: "observed", calls: 3 },
        { vendor_id: "twilio", operation_id: "sms", binding_rung: "observed", calls: 9 },
      ],
    })

    expect(observedFor(graph, "stripe")).toHaveLength(2)
    expect(observedFor(graph, "stripe", "charge")).toHaveLength(1)
    expect(observedFor(graph, "twilio", "charge")).toHaveLength(0)
  })
})

describe("an integration the index has never written for", () => {
  it("marks the missing date absent rather than rendering a nought", () => {
    const graph = graphOf({
      vendors: [{ vendor_id: "stripe", indexed_call_sites: 0, last_indexed: null }],
      bindings: [bind()],
    })

    renderInspector(graph, node({ id: "vendor:stripe", kind: "vendor", label: "stripe", vendorId: "stripe" }))

    const panel = document.body.textContent ?? ""
    expect(panel).toContain("never recorded")
    // A date substituted here, or a 0 standing in for one, would report a measurement nobody took.
    expect(panel).not.toContain("Last indexed 0")
  })

  it("says nothing correlated rather than nought calls", () => {
    const graph = graphOf({ vendors: [], bindings: [bind()], observed_bindings: [] })

    renderInspector(graph, node({ id: "vendor:stripe", kind: "vendor", label: "stripe", vendorId: "stripe" }))

    const panel = document.body.textContent ?? ""
    // The graph payload carries no attachment timestamp, so this screen cannot tell an
    // unattached repository from a measured nought and must claim neither.
    expect(panel).toContain("no observed call has been correlated to this integration")
    expect(panel).not.toContain("0 calls")
  })
})

describe("an operation with no recorded vendor change", () => {
  it("says so in a sentence and wears no chip", () => {
    bindingSurface.mockReturnValue({
      isPending: false,
      isError: false,
      refetch: vi.fn(),
      data: {
        vendor_id: "stripe",
        operation_id: "charge",
        repo_id: "org/one",
        path_prefix: null,
        call_sites: { items: [], total: 0, next_offset: null },
        call_sites_common_directory: "",
        changes: { items: [], total: 0, next_offset: null },
        repositories: [],
        source_served: false,
      },
    })

    renderInspector(
      graphOf({ bindings: [bind()] }),
      node({ id: "op:stripe:charge", kind: "operation", label: "charge", vendorId: "stripe", operationId: "charge" }),
    )

    expect(screen.getByText("No vendor change is recorded against this operation.")).toBeTruthy()
    // An "OK" badge here is the traffic light `web/CLAUDE.md` refuses three times on the record.
    expect(document.querySelectorAll("[data-tone]:not([data-tone='neutral'])")).toHaveLength(0)
  })

  it("names the two reads that disagree rather than reporting no call sites", () => {
    bindingSurface.mockReturnValue({
      isPending: false,
      isError: false,
      refetch: vi.fn(),
      data: {
        vendor_id: "stripe",
        operation_id: "charge",
        repo_id: "org/one",
        path_prefix: null,
        call_sites: { items: [], total: 0, next_offset: null },
        call_sites_common_directory: "",
        changes: { items: [], total: 0, next_offset: null },
        repositories: [],
        source_served: false,
      },
    })

    renderInspector(
      graphOf({ bindings: [bind()] }),
      node({ id: "op:stripe:charge", kind: "operation", label: "charge", vendorId: "stripe", operationId: "charge" }),
    )

    expect(document.body.textContent).toContain("the two reads disagree")
  })
})

describe("nothing selected", () => {
  it("says which nothing it is and states what the map holds", () => {
    renderInspector(graphOf({ bindings: [bind()] }), null)

    const panel = document.body.textContent ?? ""
    expect(panel).toContain("Nothing selected")
    expect(panel).toContain("3 nodes are drawn")
  })
})

describe("a file whose call sites are not in the drawn subset", () => {
  it("names the disagreement instead of rendering a blank list", () => {
    renderInspector(
      graphOf({ bindings: [bind({ path: "src/b/route.ts" })], truncated: true }),
      node({ id: "file:src/a/route.ts", kind: "file", label: "route.ts", path: "src/a/route.ts" }),
    )

    expect(document.body.textContent).toContain("not in the drawn subset")
  })
})
