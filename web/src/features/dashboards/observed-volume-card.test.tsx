/**
 * Dashboard 7's frame — the sentences that keep the numbers honest.
 *
 * The derivation is covered next door. What is asserted here is the never-measured state, the
 * page-not-total caveat, and the absence of any rate.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { ObservedCallRow, ObservedTelemetryResponse } from "@/api/types"
import { ObservedVolumeCard } from "@/features/dashboards/observed-volume-card"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const { useRepositoryObserved } = vi.hoisted(() => ({ useRepositoryObserved: vi.fn() }))
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useRepositoryObserved,
}))

const call = (over: Partial<ObservedCallRow> = {}): ObservedCallRow => ({
  repo_id: "org/payments",
  vendor_id: "stripe",
  operation_id: "PostCharges",
  binding_rung: "observed",
  server_address: "api.stripe.com",
  http_method: "post",
  trace_id: "t1",
  url_template: "/v1/charges",
  call_count: 10,
  distinct_targets: 1,
  repeated_calls: 0,
  max_resend_count: 0,
  error_count: 3,
  first_seen: "2026-08-16T10:00:00Z",
  last_seen: "2026-08-16T10:00:00Z",
  ...over,
})

function renderCard(
  items: ObservedCallRow[],
  over: Partial<{ attachedAt: string | null; total: number }> = {},
) {
  const data: ObservedTelemetryResponse = {
    repo_id: "org/payments",
    telemetry_attached_at:
      over.attachedAt === undefined ? "2026-08-15T00:00:00Z" : over.attachedAt,
    calls: { items, total: over.total ?? items.length, next_offset: null },
    shapes: { items: [], total: 0, next_offset: null },
    error_windows: { items: [], total: 0, next_offset: null },
  }
  useRepositoryObserved.mockReturnValue({
    isPending: false,
    isError: false,
    isSuccess: true,
    data,
  })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/repositories/org%2Fpayments/signals"]}>
        <Routes>
          <Route path="/repositories/:repoId/signals" element={<ObservedVolumeCard />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe("ObservedVolumeCard", () => {
  /** The distinction this dashboard was specified for. */
  it("says never measured when no telemetry is attached, and does not say nought", () => {
    renderCard([], { attachedAt: null })

    expect(screen.getByText("Never measured.")).toBeTruthy()
    expect(screen.getByText(/absence of a measurement rather than a measurement of nothing/)).toBeTruthy()
  })

  /**
   * Decision 61: the headers stay, so a reader learns what a row would be from a screen with
   * none — and on this screen that matters twice over, because the two empty states say
   * different things and both now say them inside the table they describe.
   */
  it("keeps its column headers in both empty states", () => {
    renderCard([], { attachedAt: null })
    expect(screen.getByText("Operation")).toBeTruthy()
    expect(screen.getByText("Rung")).toBeTruthy()
    cleanup()

    renderCard([])
    expect(screen.getByText("Operation")).toBeTruthy()
  })

  it("spans the sentence across exactly as many columns as the header declares", () => {
    const { container } = renderCard([], { attachedAt: null })

    const headers = container.querySelectorAll("thead th").length
    expect(container.querySelector("tbody td")?.getAttribute("colspan")).toBe(String(headers))
  })

  /** Decision 63: moving a sentence into its new home may not shorten it. */
  it("keeps the whole never-measured sentence", () => {
    renderCard([], { attachedAt: null })

    expect(screen.getByText(/would look identical, and the two are not the same fact/)).toBeTruthy()
  })

  it("says a measured nought when telemetry is attached and saw nothing", () => {
    renderCard([])

    expect(screen.getByText(/Telemetry is attached and has seen no calls/)).toBeTruthy()
    expect(screen.getByText(/different answer from never having looked/)).toBeTruthy()
  })

  it("names the operation with its volume and its rung", () => {
    renderCard([call()])

    expect(screen.getByText("PostCharges")).toBeTruthy()
    expect(screen.getByText("10")).toBeTruthy()
    expect(screen.getByText("observed")).toBeTruthy()
  })

  /** `calls` is a page, and a ranking built from one can change. */
  it("says when the figures are a page rather than the whole set", () => {
    renderCard([call()], { total: 400 })

    expect(screen.getByText(/Counted over 1 of 400 observed-call rows/)).toBeTruthy()
    expect(screen.getByText(/ranking can change when the rest arrives/)).toBeTruthy()
  })

  it("says so plainly when it did count everything", () => {
    renderCard([call()])

    expect(screen.getByText(/Counted over all 1 observed-call rows/)).toBeTruthy()
  })

  it("refuses a failure rate and says why", () => {
    const { container } = renderCard([call()])

    expect(container.textContent).not.toMatch(/%/)
    expect(screen.getByText(/never divided into\s+them/)).toBeTruthy()
  })

  /** A slope needs two points; a flat line drawn from one reads as stability. */
  it("prints a figure instead of a line when the series is one day long", () => {
    renderCard([call()])

    expect(screen.getByText(/one day only/)).toBeTruthy()
  })
})
