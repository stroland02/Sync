/**
 * The two derivations this screen carries weight on.
 *
 * `dispositionRows` is where a run with no outcome stops being the string "null" and becomes a
 * sentence, and `SolutionsFunnelRegion` is where three different nothings stopped being one
 * blank. Scope is `web/CLAUDE.md`'s: classification and derivation, never class names.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ApiStatusError } from "@/api/errors"
import { dispositionRows, SolutionsFunnelRegion } from "@/features/workflows/solutions-page"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const { useTickets } = vi.hoisted(() => ({ useTickets: vi.fn() }))
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useTickets,
}))

function renderFunnel(state: Record<string, unknown>) {
  useTickets.mockReturnValue({ isPending: false, isError: false, ...state })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const { container } = render(
    <QueryClientProvider client={client}>
      <SolutionsFunnelRegion repoId="demo" />
    </QueryClientProvider>
  )
  return container.textContent ?? ""
}

describe("dispositionRows", () => {
  /** The bucket the label map exists for: a run still going is not a run named "null". */
  it("renders the in-flight bucket as a sentence rather than the string null", () => {
    const rows = dispositionRows({ null: 3 })

    expect(rows).toEqual([{ key: "in flight, no outcome yet", value: 3 }])
  })

  /** A disposition the console has no word for is still a run that happened. */
  it("keeps a disposition outside the vocabulary, labelled with its own raw value", () => {
    const rows = dispositionRows({ opened: 1, quarantined: 2 })

    expect(rows.map((row) => row.key)).toEqual(["quarantined", "opened a pull request"])
  })

  it("returns rows largest first", () => {
    const rows = dispositionRows({ opened: 2, abandoned: 9, reported: 5 })

    expect(rows.map((row) => row.value)).toEqual([9, 5, 2])
    expect(rows[0].key).toBe("abandoned")
  })

  /** No runs at all is an empty ranking, never a vocabulary drawn at zero. */
  it("returns nothing for a payload that counted nothing", () => {
    expect(dispositionRows({})).toEqual([])
  })
})

describe("SolutionsFunnelRegion", () => {
  /**
   * The defect this pane was rebuilt for. Before, all three of these returned null, so a route
   * still being asked, a route that failed and a route holding no ticket rendered one blank.
   */
  it("says which nothing it is for each of the three that are not a funnel", () => {
    const pending = renderFunnel({ isPending: true })
    cleanup()
    const errored = renderFunnel({
      isError: true,
      error: new ApiStatusError(500, "/api/repositories/demo/tickets"),
    })
    cleanup()
    const empty = renderFunnel({ isSuccess: true, data: { tickets: [] } })

    for (const text of [pending, errored, empty]) expect(text.trim()).not.toBe("")
    expect(new Set([pending, errored, empty]).size).toBe(3)
  })

  it("names the tickets read while it is still in flight", () => {
    renderFunnel({ isPending: true })

    expect(screen.getByText(/Loading this workspace's remediation tickets/)).toBeTruthy()
  })

  it("offers a retry rather than an empty state when the route failed", () => {
    renderFunnel({
      isError: true,
      error: new ApiStatusError(500, "/api/repositories/demo/tickets"),
    })

    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy()
  })

  /** Asked-and-empty, explicitly not never-asked. */
  it("says the route answered and holds no ticket when the workspace has none", () => {
    renderFunnel({ isSuccess: true, data: { tickets: [] } })

    expect(screen.getByText(/no ticket has been raised in this workspace/)).toBeTruthy()
    expect(screen.getByText(/asked and holds none for this workspace/)).toBeTruthy()
  })
})
