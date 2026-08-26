/**
 * Dashboard 6's frame — the three sentences that keep the chart readable.
 *
 * The bars are covered by `abandon-reasons-option.test.ts`. What is asserted here is the prose,
 * because on this screen a reader decides which change kinds are not mechanically safe, and the
 * grain and the two absence cases are what make that decision sound.
 *
 * **Moved here 2026-08-26 with the card it covers.** `AbandonReasonsCard` was a `MetricPanel` on
 * `features/runs/` mounted only by the Corpus screen; that screen is a locked bento now and the
 * surface moved to `features/dashboards/abandon-reasons-pane.tsx` beside the page that mounts it.
 * Every assertion below is unchanged, including the grain sentence — the pane keeps it in the
 * pinned footer rather than the hint, because a claim behind a hover is a claim a reader who does
 * not hover never sees.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { AbandonmentResponse } from "@/api/types"
import { AbandonReasonsPane } from "@/features/dashboards/abandon-reasons-pane"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const { useAbandonment } = vi.hoisted(() => ({ useAbandonment: vi.fn() }))
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useAbandonment,
}))

const group = (codes: Record<string, number>) => ({
  change_kind: "response-field-type-changed",
  tier: 0,
  attempt_count: 0,
  distinct_finding_count: 0,
  abandoned_attempt_count: 0,
  abandoned_distinct_finding_count: 0,
  abandon_reason_codes: codes,
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
      <AbandonReasonsPane />
    </QueryClientProvider>
  )
}

describe("the why-runs-gave-up pane", () => {
  it("says attempts rather than findings, because that is the grain", () => {
    renderCard([group({ locate_failed: 3 })])

    expect(screen.getByText(/attempts rather than findings/)).toBeTruthy()
    expect(screen.getByText(/3 abandoned attempts carry a recorded reason/)).toBeTruthy()
  })

  it("says a reason with no attempts was counted and found empty", () => {
    renderCard([group({ locate_failed: 1 })])

    expect(screen.getByText(/counted and found empty, not\s+left out/)).toBeTruthy()
  })

  it("refuses to read a pre-column row as unclassified", () => {
    renderCard([group({ null: 2 })])

    expect(screen.getByText(/recorded before the reason was stored as a code/)).toBeTruthy()
    expect(screen.getByText(/cannot be backfilled/)).toBeTruthy()
  })

  /**
   * Measured on the running console 2026-08-26: this corpus holds one abandoned attempt and it
   * predates the reason column, so the ranking is empty while the count is not — and the card drew
   * an axis pair with no bars on it, which reads as broken rather than as empty.
   */
  it("draws no ranking when no attempt carries a code, and says which nothing that is", () => {
    renderCard([group({ null: 2 })])

    expect(screen.getByText("No abandoned attempt carries a recorded reason.")).toBeTruthy()
    expect(screen.getByText(/not the same as nothing having been abandoned/)).toBeTruthy()
    expect(screen.queryByText("No attempt has been abandoned.")).toBeNull()
  })

  it("says nothing about pre-column rows when there are none", () => {
    renderCard([group({ locate_failed: 1 })])

    expect(screen.queryByText(/cannot be backfilled/)).toBeNull()
  })

  it("shows a code the vocabulary does not declare rather than dropping it", () => {
    renderCard([group({ something_new: 1 })])

    expect(screen.getByText("something_new")).toBeTruthy()
    expect(screen.getByText(/still a reason a run gave up/)).toBeTruthy()
  })

  it("distinguishes an empty corpus from an unread one", () => {
    renderCard([])

    expect(screen.getByText(/count of nought rather than a question nobody asked/)).toBeTruthy()
  })

  it("renders no percentage", () => {
    const { container } = renderCard([group({ locate_failed: 3, push_failed: 1 })])

    expect(container.textContent).not.toMatch(/%/)
  })
})
