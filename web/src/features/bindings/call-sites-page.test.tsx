/**
 * The call-sites screen's status band, and the seam a rail press has to cross.
 *
 * Three claims, none of them covered elsewhere.
 *
 * **The band's noun carries the narrowing.** `describeRecordWindow` knows nothing of the rail, so
 * over a selection that fits one page it would say "This is all 1 call site" beside a pager
 * reporting one filtered out.
 *
 * **A press writes the facet and the offset reset in one `setSearchParams`.** Two writes gave the
 * second a `prev` predating the first and the facet was discarded with no error -- the owner's
 * report of 2026-08-19. The rail has its own tests and the route has its own tests; the seam
 * between them is where both stay green while the table never moves.
 *
 * **A read that has not answered says so.** The band states which silence it is rather than
 * reporting the absence of an answer as a count.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { CallSitesPage } from "@/features/bindings/call-sites-page"

const requested: string[] = []

function site(id: string, vendorId: string, operationId: string) {
  return {
    id,
    repo_id: "demo",
    path: `src/${vendorId}.ts`,
    line: 12,
    col: 3,
    vendor_id: vendorId,
    operation_id: operationId,
    symbol: "call",
    args_keys: [],
    response_fields_read: [],
    loop_depth: 0,
    binding_status: "unchecked",
    sdk_version: "1.0.0",
    indexed_at: null,
  }
}

/**
 * The narrowed page counts one row and the vendor facet still counts two.
 *
 * That is the payload's own arrangement rather than a convenience: `unfiltered_total` is the sum
 * over the vendor facet, which `graph/store.py` counts ignoring the vendor narrowing alone.
 */
function callSitesPayload(vendorIds: string[]) {
  const items =
    vendorIds.length > 0
      ? [site("cs-1", "stripe", "PostCharges")]
      : [site("cs-1", "stripe", "PostCharges"), site("cs-2", "openai", "CreateCompletion")]
  return {
    repo_id: "demo",
    items,
    total: items.length,
    next_offset: null,
    by_vendor: { openai: 1, stripe: 1 },
    by_operation: { CreateCompletion: 1, PostCharges: 1 },
    by_loop_depth: { "0": 2 },
    by_binding_status: { unchecked: 2 },
    unfiltered_total: 2,
    vendor_ids: vendorIds,
    operation_ids: [],
    loop_depths: [],
    binding_statuses: [],
    path_prefix: null,
    source_served: false,
  }
}

const TOPOLOGY = {
  repo_id: "demo",
  totals: { call_sites: 2, vendors: 2, operations: 2, files: 2 },
  by_vendor: [{ vendor_id: "stripe", call_sites: 1, operations: 1, files: 1 }],
  busiest_operations: [
    { vendor_id: "stripe", operation_id: "PostCharges", call_sites: 1, files: 1 },
  ],
  multi_vendor_files: [],
  by_loop_depth: { "0": 2 },
}

const OVERVIEW = {
  repo_id: "demo",
  vendors: [],
  total_findings: 0,
  total_findings_bound: 0,
  total_findings_bound_reached: false,
  severity_counts: {},
  bindings_by_rung: {},
  last_index_run: null,
}

/** `null` for the call-sites route leaves that one read in flight and answers the rest. */
function stubFetch(callSites: (vendorIds: string[]) => unknown | null) {
  vi.stubGlobal("fetch", (input: string) => {
    requested.push(String(input))
    const url = new URL(String(input), "http://localhost")
    if (url.pathname.endsWith("/topology")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(TOPOLOGY) } as Response)
    }
    if (url.pathname.startsWith("/api/overview")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(OVERVIEW) } as Response)
    }
    const body = callSites(url.searchParams.getAll("vendor_id"))
    if (body === null) return new Promise<Response>(() => {})
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
  })
}

function renderCallSites(search = "") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/repositories/demo/call-sites${search}`]}>
        <Routes>
          <Route path="/repositories/:repoId/call-sites" element={<CallSitesPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function band(name: string) {
  return document.querySelector(`[data-band="${name}"]`)?.textContent ?? ""
}

beforeEach(() => {
  requested.length = 0
  window.localStorage.clear()
  stubFetch(callSitesPayload)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("what the call-sites band says", () => {
  it("claims the whole set only when nothing is narrowing it", async () => {
    renderCallSites()

    await waitFor(() => expect(band("status")).toContain("This is all 2 call sites."))
    expect(band("status")).toContain("Call sites in demo")
  })

  it("names the narrowing in the count it claims", async () => {
    renderCallSites("?call_sites_vendor=stripe")

    // The bare sentence would read as the whole set beside a pager saying one was excluded.
    await waitFor(() =>
      expect(band("status")).toContain("This is all 1 call site matching this narrowing."),
    )
    expect(band("status")).toContain("filtered out")
  })

  it("says which silence it is while the call sites are still in flight", async () => {
    stubFetch(() => null)
    renderCallSites()

    await waitFor(() => expect(band("status")).toContain("asking for the call sites in demo"))
    // Never a nought: nothing answered, so there is no count to report.
    expect(band("status")).not.toContain("This is all")
  })

  it("puts the column choice in the controls band once there is a table", async () => {
    renderCallSites()

    expect(await screen.findByRole("button", { name: /choose columns/i })).toBeTruthy()
    expect(band("controls")).toContain("Columns")
  })
})

describe("pressing a facet", () => {
  it("sends the facet and the reset offset in the same request", async () => {
    renderCallSites("?call_sites_offset=50")
    fireEvent.click(await screen.findByRole("button", { name: /stripe/i }))

    // Two writes in one handler discarded one of them: the rail looked pressed, the offset stayed,
    // and nothing was refetched for the narrowed set.
    await waitFor(() => {
      const last = requested[requested.length - 1]
      expect(last).toContain("vendor_id=stripe")
      expect(last).toContain("offset=0")
    })
  })
})
