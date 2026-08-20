/**
 * The Telemetry page is the live instrument, not the role catalogue — the owner's ruling,
 * given twice (2026-08-19, 2026-08-20). This holds the page's structure to it: no
 * "Attached by role" region, the traffic instrument as the body, and the recorded
 * evidence tables below it.
 *
 * The honesty guard at the end is the one that would fail quietly: a rollup table drawn
 * while telemetry was never attached renders "0 observed operations" — a measured nought —
 * for a repository nobody ever watched, which is one nothing wearing the other's words.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { ObservedTelemetryResponse } from "@/api/types"
import { SignalsPage } from "@/features/signals/signals-page"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const { useRepositoryObserved } = vi.hoisted(() => ({ useRepositoryObserved: vi.fn() }))
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useRepositoryObserved,
}))

// The chart wrapper needs a real canvas to resolve theme tokens, which jsdom does not have.
// The structure under test is the page's, not echarts' — the stub keeps the accessible shape.
vi.mock("@/components/charts/echart", () => ({
  EChart: ({ ariaLabel }: { ariaLabel: string }) => <div role="img" aria-label={ariaLabel} />,
}))

const empty = { items: [], total: 0, next_offset: null }

const observed: ObservedTelemetryResponse = {
  repo_id: "org/one",
  telemetry_attached_at: "2026-08-16T12:00:00Z",
  calls: empty,
  shapes: empty,
  error_windows: empty,
  traffic: [
    {
      vendor_id: "stripe",
      operation_id: "POST /v1/charges",
      server_address: "api.stripe.com",
      http_method: "post",
      binding_rung: "static",
      url_template: "/v1/charges",
      traces: 3,
      requests: 240,
      errors: 8,
      unstatused: 2,
      distinct_targets: 1,
      max_resend: 0,
      first_seen: "2026-08-16T12:00:00Z",
      last_seen: "2026-08-19T14:10:00Z",
    },
  ],
  unattributed: [
    {
      vendor_id: "stripe",
      operation_id: "",
      server_address: "files.stripe.com",
      http_method: "get",
      binding_rung: "unresolved",
      url_template: "",
      traces: 1,
      requests: 12,
      errors: 0,
      unstatused: 0,
      distinct_targets: 1,
      max_resend: 0,
      first_seen: "2026-08-16T12:00:00Z",
      last_seen: "2026-08-19T14:10:00Z",
    },
  ],
  series: [{ bucket: "2026-08-19T14:00:00Z", requests: 240, errors: 8 }],
  totals: {
    requests: 240,
    errors: 8,
    unstatused: 2,
    unattributed_requests: 12,
    operations_observed: 1,
    operations_indexed: 4,
  },
}

function renderPage(data: ObservedTelemetryResponse) {
  useRepositoryObserved.mockReturnValue({
    isPending: false,
    isError: false,
    isSuccess: true,
    isFetching: false,
    dataUpdatedAt: Date.now(),
    data,
  })
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/repositories/org%2Fone/observed"]}>
        <Routes>
          <Route path="/repositories/:repoId/observed" element={<SignalsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe("the Telemetry page's structure", () => {
  it("renders no attached-by-role region", () => {
    renderPage(observed)

    expect(screen.queryByText("Attached by role")).toBeNull()
  })

  it("renders the traffic instrument: chart, per-operation rollup, and the unattributed gap", () => {
    renderPage(observed)

    expect(screen.getByText("Traffic over time")).not.toBeNull()
    expect(screen.getByText("Traffic by operation")).not.toBeNull()
    expect(screen.getByText("Unattributed traffic")).not.toBeNull()
  })

  it("keeps the recorded-evidence tables below the instrument", () => {
    renderPage(observed)

    const instrument = screen.getByText("Traffic by operation")
    const evidence = screen.getByText("Observed calls")
    // DOCUMENT_POSITION_FOLLOWING: the evidence panel comes after the instrument in the page.
    expect(instrument.compareDocumentPosition(evidence) & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(0)
  })

  it("draws no instrument for a repository telemetry never watched", () => {
    renderPage({ ...observed, telemetry_attached_at: null, traffic: [], unattributed: [], series: [] })

    // The rollup's "0 observed operations" footer is a measured nought; never-attached is not
    // one, and the panel below already says which nothing this is, exactly once.
    expect(screen.queryByText("Traffic by operation")).toBeNull()
    expect(screen.getAllByText("Telemetry was never attached to this repository.").length).toBe(1)
  })
})
