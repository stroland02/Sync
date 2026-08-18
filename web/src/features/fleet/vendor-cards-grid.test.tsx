/**
 * The per-vendor cards, and the composite figure they are not allowed to carry.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification and derivation, never class
 * names and never snapshots. Adopted from Lane F; most of what is asserted here is what came
 * back out, because each removal was a claim no payload supports.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { VendorCardsGrid } from "@/features/fleet/vendor-cards-grid"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const settled = (data: unknown) => ({ isPending: false, isError: false, isSuccess: true, data })

const { useRepositoryCoverage, useOverview } = vi.hoisted(() => ({
  useRepositoryCoverage: vi.fn(),
  useOverview: vi.fn(),
}))
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useRepositoryCoverage,
  useOverview,
}))

function renderGrid(vendors: Record<string, number>, overviewVendors: unknown[] | null) {
  useRepositoryCoverage.mockReturnValue(
    settled({ repo_id: "org/one", by_vendor: vendors, last_indexed: {}, total_call_sites: 9 })
  )
  useOverview.mockReturnValue(
    overviewVendors === null
      ? { isPending: true, isError: false, isSuccess: false, data: undefined }
      : settled({ repo_id: "org/one", vendors: overviewVendors, total_findings: 3 })
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <VendorCardsGrid repoId="org/one" />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe("VendorCardsGrid", () => {
  it("states each vendor's call sites and open findings", () => {
    renderGrid({ stripe: 4 }, [{ vendor_id: "stripe", open_finding_count: 2 }])

    expect(screen.getByText("stripe")).not.toBeNull()
    expect(screen.getByText(/4 call sites/)).not.toBeNull()
    expect(screen.getByText("2")).not.toBeNull()
  })

  it("renders an unanswered finding count as absence rather than as nought", () => {
    renderGrid({ stripe: 4 }, null)

    // The adopted file wrote `findingCountsByVendor[vendorId] ?? 0`, so a vendor the overview had
    // not answered for showed a confident "0 open findings". That is the absence-versus-zero
    // conflation, reached through a default rather than through a render.
    expect(screen.getByText("—")).not.toBeNull()
  })

  it("distinguishes a confirmed nought from an unanswered one", () => {
    renderGrid({ stripe: 4 }, [{ vendor_id: "stripe", open_finding_count: 0 }])

    expect(screen.getByText("0")).not.toBeNull()
    expect(screen.queryByText("—")).toBeNull()
  })

  it("carries no composite figure per vendor", () => {
    const { container } = renderGrid({ stripe: 4 }, [
      { vendor_id: "stripe", open_finding_count: 2 },
    ])

    // The adopted card drew a filled track at `openFindings / callSites`. That is a per-vendor
    // composite figure, refused on the record three times, and a *rate* besides -- findings per
    // call site is not a quantity either number measures. Counts are permitted; a scalar over
    // them is not, and nothing here may set a width from one.
    const widths = Array.from(container.querySelectorAll<HTMLElement>("[style]")).map(
      (el) => el.style.width
    )
    expect(widths.filter(Boolean)).toEqual([])
  })

  it("passes no verdict on a vendor", () => {
    const { container } = renderGrid({ stripe: 4 }, [
      { vendor_id: "stripe", open_finding_count: 0 },
    ])

    // `Clean` and `Active` were a green dot and a liveness pulse written as words. A vendor with
    // no open findings has no open findings; that is a count, and it is already on the card.
    expect(container.textContent).not.toMatch(/clean/i)
    expect(container.textContent).not.toMatch(/active/i)
  })

  it("says nothing is attached rather than drawing an empty grid", () => {
    renderGrid({}, [])

    expect(screen.getByText(/no vendor attached to this repository/)).not.toBeNull()
  })
})
