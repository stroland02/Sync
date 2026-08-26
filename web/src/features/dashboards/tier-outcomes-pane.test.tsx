/**
 * Dashboard 5's frame — the claims the bars are not allowed to imply.
 *
 * **Moved here 2026-08-26 with the card it covers.** `TierOutcomesCard` lived in `features/runs/`
 * and was mounted only by the Corpus screen, which is a locked bento now; the surface is
 * `features/dashboards/tier-outcomes-pane.tsx`. Every assertion is unchanged, and the grain
 * sentence stays visible in the pinned footer rather than moving behind the hint.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { AbandonmentResponse } from "@/api/types"
import { TierOutcomesPane } from "@/features/dashboards/tier-outcomes-pane"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const { useAbandonment } = vi.hoisted(() => ({ useAbandonment: vi.fn() }))
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useAbandonment,
}))

const group = (over: Partial<AbandonmentResponse["groups"][number]> = {}) => ({
  change_kind: "response-field-type-changed",
  tier: 0,
  attempt_count: 0,
  distinct_finding_count: 0,
  abandoned_attempt_count: 0,
  abandoned_distinct_finding_count: 0,
  abandon_reason_codes: {},
  ...over,
})

function renderCard(groups: AbandonmentResponse["groups"]) {
  useAbandonment.mockReturnValue({
    isPending: false,
    isError: false,
    isSuccess: true,
    data: { groups },
  })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <TierOutcomesPane />
    </QueryClientProvider>
  )
}

describe("the tier-outcomes pane", () => {
  /** The plan's own warning: four rows must read as a young corpus, not a broken chart. */
  it("says a thin corpus is thin rather than drawing a confident cascade", () => {
    renderCard([group({ tier: 0, attempt_count: 4, abandoned_attempt_count: 1 })])

    expect(screen.getByText(/too few to read a cascade from/)).toBeTruthy()
    expect(screen.getByText(/thin because the corpus is young, not because the chart is broken/)).toBeTruthy()
  })

  it("drops the thinness warning once there is enough to read", () => {
    renderCard([group({ tier: 0, attempt_count: 80, abandoned_attempt_count: 10 })])

    expect(screen.queryByText(/too few to read a cascade from/)).toBeNull()
  })

  /** "settled" is not "succeeded", and the difference is a claim about pull request quality. */
  it("refuses to read settled as succeeded", () => {
    renderCard([group({ tier: 0, attempt_count: 80 })])

    expect(screen.getByText(/does not mean the pull\s+request it opened was any good/)).toBeTruthy()
  })

  it("says a missing tier had nothing routed to it", () => {
    renderCard([group({ tier: 0, attempt_count: 80 })])

    expect(screen.getByText(/not the same as having attempted\s+and settled everything/)).toBeTruthy()
  })

  it("says attempts, never findings", () => {
    renderCard([group({ tier: 0, attempt_count: 80 })])

    expect(screen.getByText(/attempts rather than\s+findings/)).toBeTruthy()
  })

  it("distinguishes an empty corpus from a lost one", () => {
    renderCard([])

    expect(screen.getByText(/cannot be backfilled/)).toBeTruthy()
  })

  it("renders no percentage", () => {
    const { container } = renderCard([group({ tier: 0, attempt_count: 80, abandoned_attempt_count: 9 })])

    expect(container.textContent).not.toMatch(/%/)
  })
})
