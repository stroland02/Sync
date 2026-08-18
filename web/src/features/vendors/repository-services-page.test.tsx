/**
 * The API services one repository calls — the list screen the owner asked for.
 *
 * *"an api services page that list all the different services"*. Two answers reach it and they have
 * different grains: `/api/repositories/{repo_id}/coverage` names a service the index bound a call
 * site to, and `/api/overview?repo_id=` names a service with at least one open finding. Neither is a
 * superset of the other, both echo the scope they were computed for, and this screen's whole job is
 * to render the union without letting either grain be read as the other.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification, derivation and structural
 * invariants. Never class names, never snapshots.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, within } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { NotFoundError } from "@/api/errors"
import { RepositoryServicesPage } from "@/features/vendors/repository-services-page"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const settled = (data: unknown) => ({
  isPending: false,
  isError: false,
  isSuccess: true,
  data,
  refetch: vi.fn(),
})

const failed = (error: unknown) => ({
  isPending: false,
  isError: true,
  isSuccess: false,
  data: undefined,
  error,
  refetch: vi.fn(),
})

const { useOverview, useRepositoryCoverage } = vi.hoisted(() => ({
  useOverview: vi.fn(),
  useRepositoryCoverage: vi.fn(),
}))
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useOverview,
  useRepositoryCoverage,
}))

function renderAt(repoId: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/repositories/${encodeURIComponent(repoId)}/services`]}>
        <Routes>
          <Route path="/repositories/:repoId/services" element={<RepositoryServicesPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

/** Both answers scoped to `org/one`: stripe is in both, twilio only indexed, openai only open. */
function bothAnswered() {
  useOverview.mockReturnValue(
    settled({
      repo_id: "org/one",
      vendors: [
        { vendor_id: "stripe", open_finding_count: 4 },
        { vendor_id: "openai", open_finding_count: 0 },
      ],
    })
  )
  useRepositoryCoverage.mockReturnValue(
    settled({
      repo_id: "org/one",
      by_vendor: { stripe: 3, twilio: 1 },
      last_indexed: { stripe: "2026-08-17T10:00:00Z", twilio: "2026-08-16T09:00:00Z" },
      total_call_sites: 4,
    })
  )
}

function rowsOf(container: HTMLElement) {
  return Array.from(container.querySelectorAll("tbody tr")) as HTMLElement[]
}

function rowNamed(container: HTMLElement, service: string) {
  const rows = rowsOf(container)
  expect(rows.length).toBeGreaterThan(0)
  const row = rows.find((candidate) => candidate.textContent?.includes(service))
  expect(row).toBeDefined()
  return row as HTMLElement
}

describe("the API services one repository calls", () => {
  it("lists one row per service either scoped answer names, and neither answer alone", () => {
    bothAnswered()

    const { container } = renderAt("org/one")

    // stripe from both, openai from the open-findings answer only, twilio from the index only.
    const rows = rowsOf(container)
    expect(rows.length).toBe(3)
    expect(rows.map((row) => within(row).getAllByRole("cell")[0]?.textContent)).toEqual([
      "openai",
      "stripe",
      "twilio",
    ])
  })

  it("renders a confirmed zero as words and never as the absence marker", () => {
    bothAnswered()

    const { container } = renderAt("org/one")

    // The overview named openai with a count of 0. That is an answer about openai, not a question.
    const cells = within(rowNamed(container, "openai")).getAllByRole("cell")
    expect(cells[1]?.textContent).toContain("No open findings")
    expect(cells[1]?.textContent).not.toContain("—")
  })

  it("renders a service the open-findings answer never named as absence, not as zero", () => {
    bothAnswered()

    const { container } = renderAt("org/one")

    // twilio has indexed call sites and no row in `vendors`. The vendor breakdown is a GROUP BY
    // over open findings, so nothing computed a figure for twilio — printing 0 would invent one.
    const cells = within(rowNamed(container, "twilio")).getAllByRole("cell")
    expect(cells[1]?.textContent).toContain("—")
    expect(cells[1]?.textContent).not.toContain("0")
  })

  it("renders a service the index never bound as absence in the call-site column", () => {
    bothAnswered()

    const { container } = renderAt("org/one")

    // A vendor absent from `by_vendor` is a question this route cannot answer, not a zero.
    const cells = within(rowNamed(container, "openai")).getAllByRole("cell")
    expect(cells[2]?.textContent).toContain("—")
    expect(cells[2]?.textContent).not.toContain("0")
  })

  it("carries each service's own call-site count and its own index time", () => {
    bothAnswered()

    const { container } = renderAt("org/one")

    const cells = within(rowNamed(container, "stripe")).getAllByRole("cell")
    expect(cells[2]?.textContent).toContain("3")
    expect(cells[3]?.textContent).not.toContain("—")
  })

  it("opens each service in the vendor record, carrying this repository as the scope", () => {
    bothAnswered()

    renderAt("org/one")

    const link = screen.getByRole("link", { name: /stripe/i })
    expect(link.getAttribute("href")).toBe("/vendors/stripe?repo_id=org%2Fone")
  })

  it("refuses to render any service under a repository the overview was not computed for", () => {
    useOverview.mockReturnValue(
      settled({ repo_id: null, vendors: [{ vendor_id: "stripe", open_finding_count: 4 }] })
    )
    useRepositoryCoverage.mockReturnValue(
      settled({ repo_id: "org/one", by_vendor: { stripe: 3 }, last_indexed: {}, total_call_sites: 3 })
    )

    const { container } = renderAt("org/one")

    expect(rowsOf(container).length).toBe(0)
    expect(container.textContent).toContain("computed for a different scope")
  })

  it("drops the index columns, and keeps the list, when coverage names another repository", () => {
    useOverview.mockReturnValue(
      settled({ repo_id: "org/one", vendors: [{ vendor_id: "stripe", open_finding_count: 4 }] })
    )
    useRepositoryCoverage.mockReturnValue(
      settled({ repo_id: "org/two", by_vendor: { fake: 99 }, last_indexed: {}, total_call_sites: 99 })
    )

    const { container } = renderAt("org/one")

    expect(rowsOf(container).length).toBe(1)
    expect(container.textContent).not.toContain("fake")
    expect(screen.queryByRole("columnheader", { name: /call sites/i })).toBeNull()
    expect(container.textContent).toContain("index coverage that arrived names its scope")
  })

  it("names the transport defect rather than claiming the API does not hold the identifier", () => {
    useOverview.mockReturnValue(
      settled({ repo_id: "org/one", vendors: [{ vendor_id: "stripe", open_finding_count: 4 }] })
    )
    useRepositoryCoverage.mockReturnValue(
      failed(
        new NotFoundError(
          "not found",
          "/api/repositories/org%2Fone/coverage",
          "/api/repositories/org%2Fone/coverage"
        )
      )
    )

    const { container } = renderAt("org/one")

    // The repository exists and the API lists it. "The API does not hold that identifier" is false
    // here: the address never matched a route, because the converter cannot take a slash.
    expect(container.textContent).not.toContain("does not hold that identifier")
    expect(container.textContent).toContain("cannot match a repository identifier containing a slash")
    expect(rowsOf(container).length).toBe(1)
    expect(screen.queryByRole("columnheader", { name: /call sites/i })).toBeNull()
  })

  it("says nothing is bound here rather than drawing an empty table", () => {
    useOverview.mockReturnValue(settled({ repo_id: "org/one", vendors: [] }))
    useRepositoryCoverage.mockReturnValue(
      settled({ repo_id: "org/one", by_vendor: {}, last_indexed: {}, total_call_sites: 0 })
    )

    const { container } = renderAt("org/one")

    expect(rowsOf(container).length).toBe(0)
    expect(container.textContent).toContain("This repository was never indexed, or it was indexed")
  })

  it("states on screen that it cannot show the operations each service exposes", () => {
    bothAnswered()

    const { container } = renderAt("org/one")

    expect(container.textContent).toContain("operations")
  })
})
