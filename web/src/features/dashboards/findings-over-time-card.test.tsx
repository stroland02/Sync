/**
 * Dashboard 1's frame — the three readings the bars would otherwise invite.
 *
 * A dated bar chart of API findings is read as the vendors' timeline, a missing day is read as a
 * zero, and a series is read as the current backlog. All three are wrong and each is asserted.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { FindingsOverTimeResponse } from "@/api/types"
import { FindingsOverTimeCard } from "@/features/dashboards/findings-over-time-card"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const { useFindingsOverTime } = vi.hoisted(() => ({ useFindingsOverTime: vi.fn() }))
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useFindingsOverTime,
}))

function renderCard(over: Partial<FindingsOverTimeResponse> = {}) {
  const data: FindingsOverTimeResponse = {
    repo_id: null,
    severities: ["breaking", "warning", "deprecation", "addition", "info"],
    days: [{ day: "2026-08-16", counts: { breaking: 2 } }],
    by_rung: { static: 2 },
    total: 2,
    still_open: 1,
    ...over,
  }
  useFindingsOverTime.mockReturnValue({
    isPending: false,
    isError: false,
    isSuccess: true,
    data,
  })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <FindingsOverTimeCard />
    </QueryClientProvider>
  )
}

describe("FindingsOverTimeCard", () => {
  /** The misreading this card exists to pre-empt. */
  it("says the dates are Sync's own, not the vendors' publication timeline", () => {
    renderCard()

    expect(screen.getByText(/not\s+the day the API changed/)).toBeTruthy()
    expect(screen.getByText(/no publication date to draw|carries a publication date to draw/)).toBeTruthy()
  })

  it("says a day with no bar was not measured at nought", () => {
    renderCard()

    expect(screen.getByText(/A day with no bar is a day nothing was recorded/)).toBeTruthy()
    expect(screen.getByText(/may be one with no changes or one with no run/)).toBeTruthy()
  })

  /** Filtering to still-open would make yesterday's bar shrink as patches land. */
  it("says the series counts findings as produced, and reports the open count apart from it", () => {
    renderCard({ total: 9, still_open: 4 })

    expect(screen.getByText(/9 findings recorded across/)).toBeTruthy()
    expect(screen.getByText(/4 are still\s+open/)).toBeTruthy()
    expect(screen.getByText(/shrink its own past every time work\s+landed/)).toBeTruthy()
  })

  it("carries the rungs the findings rest on", () => {
    renderCard({ by_rung: { observed: 1, static: 3 } })

    expect(screen.getByText("observed")).toBeTruthy()
    expect(screen.getByText("static")).toBeTruthy()
    expect(screen.getByText(/cannot be attributed to one cannot be fixed/)).toBeTruthy()
  })

  it("distinguishes an empty graph from a lost one", () => {
    renderCard({ days: [], total: 0, still_open: 0, by_rung: {} })

    expect(screen.getByText(/read that found nothing rather than a read that did not happen/)).toBeTruthy()
  })

  it("renders no percentage", () => {
    const { container } = renderCard({ total: 9, still_open: 4 })

    expect(container.textContent).not.toMatch(/%/)
  })
})
