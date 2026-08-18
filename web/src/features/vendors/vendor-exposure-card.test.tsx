/**
 * What this vendor costs, per decision 29 — test suite for the page's opening answer.
 *
 * The distinctions this card must not erase are the ones asserted here: a rung on every row, a
 * three-valued `observed` where the third value is "nothing looked", and no ratio anywhere.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { VendorOperationsResponse } from "@/api/types"
import { VendorExposureCard } from "@/features/vendors/vendor-exposure-card"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const { useVendorOperations } = vi.hoisted(() => ({ useVendorOperations: vi.fn() }))
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useVendorOperations,
}))

const settled = (data: VendorOperationsResponse) => ({
  isPending: false,
  isError: false,
  isSuccess: true,
  data,
})

function payload(over: Partial<VendorOperationsResponse> = {}): VendorOperationsResponse {
  return {
    vendor_id: "stripe",
    repo_id: null,
    telemetry_attached_at: null,
    operations: [
      {
        operation_id: "PostCharges",
        call_site_count: 4,
        repository_count: 2,
        binding_rung: "static",
        observed: null,
      },
    ],
    ...over,
  }
}

function renderCard(data: VendorOperationsResponse) {
  useVendorOperations.mockReturnValue(settled(data))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <VendorExposureCard vendorId="stripe" repoId={data.repo_id ?? "seed-console"} />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe("VendorExposureCard", () => {
  it("names each operation this codebase calls, with how many places call it", () => {
    renderCard(payload())

    expect(screen.getByText("PostCharges")).toBeTruthy()
    expect(screen.getByText("4")).toBeTruthy()
  })

  it("carries the rung on every row, because an unattributed binding cannot be fixed", () => {
    renderCard(payload())

    expect(screen.getByText("static")).toBeTruthy()
  })

  it("says nothing looked, rather than not observed, when telemetry never attached", () => {
    renderCard(payload())

    expect(screen.getByText(/never measured/i)).toBeTruthy()
    expect(screen.queryByText(/^not observed$/i)).toBeNull()
  })

  it("separates an operation traffic confirmed from one it did not, once telemetry is attached", () => {
    renderCard(
      payload({
        repo_id: "org/payments",
        telemetry_attached_at: "2026-08-16T12:00:00Z",
        operations: [
          {
            operation_id: "PostCharges",
            call_site_count: 2,
            repository_count: 1,
            binding_rung: "static",
            observed: true,
          },
          {
            operation_id: "GetCharges",
            call_site_count: 1,
            repository_count: 1,
            binding_rung: "static",
            observed: false,
          },
        ],
      })
    )

    expect(screen.getByText(/traffic confirmed/i)).toBeTruthy()
    expect(screen.getByText(/no traffic seen/i)).toBeTruthy()
  })

  /** A composite of "called a lot" and "confirmed by traffic" is exactly the score this refuses. */
  it("renders no percentage and no score", () => {
    const { container } = renderCard(payload())

    expect(container.textContent).not.toMatch(/%/)
  })

  it("distinguishes calling nothing from never having been indexed", () => {
    renderCard(payload({ operations: [] }))

    expect(screen.getByText(/does not call/i)).toBeTruthy()
  })

  /**
   * Decision 40: a table states its record count, because the count is how a reader knows what
   * they are looking at. This table is not paged -- the route is an aggregate bounded by the
   * vendor's operation surface -- so the honest count says *all of them* rather than implying a
   * page whose remainder the reader is missing.
   *
   * Matched on the container's text: the count is interpolated, so the sentence is split across
   * nodes and an element-scoped matcher would miss it.
   */
  it("says how many operations it is showing, and that it is all of them", () => {
    const { container } = renderCard(
      payload({
        operations: [
          {
            operation_id: "PostCharges",
            call_site_count: 2,
            repository_count: 1,
            binding_rung: "static",
            observed: null,
          },
          {
            operation_id: "GetCharges",
            call_site_count: 1,
            repository_count: 1,
            binding_rung: "static",
            observed: null,
          },
        ],
      })
    )

    expect(container.textContent).toMatch(/Showing all 2 operations/i)
  })

  it("counts one operation in the singular", () => {
    const { container } = renderCard(payload())

    expect(container.textContent).toMatch(/Showing all 1 operation /i)
  })
})
