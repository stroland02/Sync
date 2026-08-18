import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { RunRow } from "@/api/types"
import { RunsCard } from "@/features/fleet/runs-table"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const mockQueryState: { runs: unknown } = { runs: undefined }

// `hasLiveRun` comes through unmocked. It is a pure predicate over the page this file already
// builds, so mocking it would mean maintaining a second answer to "is a run in flight" that could
// disagree with the one the table actually calls — and the table's freshness line reads it.
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useRuns: () => mockQueryState.runs,
}))

function settled(items: RunRow[], total = items.length) {
  return {
    isPending: false,
    isError: false,
    isSuccess: true,
    data: {
      items,
      total,
      next_offset: null,
    },
  }
}

function renderCard() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <RunsCard />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("RunsCard rehearsal discrimination", () => {
  it("labels rehearsal runs distinctly from live runs", () => {
    const liveRun: RunRow = {
      thread_id: "finding-live-1:prod-run-1:0",
      finding_id: "finding-live-1",
      run_id: "prod-run-1",
      current_node: null,
      outcome: "opened",
      abandon_reason: null,
      last_checkpoint_at: "2026-08-05T12:00:00Z",
    }

    const rehearsalRun: RunRow = {
      thread_id: "finding-rehearse-1:rehearsal-2026-08-05:0",
      finding_id: "finding-rehearse-1",
      run_id: "rehearsal-2026-08-05",
      current_node: null,
      outcome: "reported",
      abandon_reason: null,
      last_checkpoint_at: "2026-08-05T12:00:00Z",
    }

    mockQueryState.runs = settled([liveRun, rehearsalRun])
    renderCard()

    expect(screen.getByText("live")).toBeTruthy()
    expect(screen.getByText("rehearsal")).toBeTruthy()
    expect(screen.getByText("halted before the remote")).toBeTruthy()
  })

  it("keeps its column headers when there is nothing to list", () => {
    mockQueryState.runs = settled([])
    renderCard()

    // Decision 61: the shape of the data is legible before there is data, so a reader learns what
    // a run IS from a screen that has none. Swapping the whole table for a paragraph takes that
    // away exactly when it is most useful.
    expect(screen.getByRole("columnheader", { name: /outcome/i })).not.toBeNull()
    expect(screen.getByText(/No run has ever checkpointed/)).not.toBeNull()
  })
})
