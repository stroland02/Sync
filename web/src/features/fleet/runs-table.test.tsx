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

vi.mock("@/api/queries", () => ({
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
})
