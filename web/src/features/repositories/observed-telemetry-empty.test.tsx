/**
 * Measured nought, apart from nobody having looked — on the Codebase screen's telemetry card.
 *
 * `ObservedTelemetryResponse` gained `telemetry_attached_at` (Lane I, dashboard 7). Before it,
 * this card genuinely could not separate "telemetry is attached and saw no calls" from "nothing
 * ever watched this repository", and said so. It can now, so saying it cannot is a false
 * statement of a limit that no longer exists — and rendering one screen for two facts is the
 * collapse this console exists to refuse.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ObservedTelemetryCard } from "@/features/repositories/codebase-page"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const { useRepositoryObserved } = vi.hoisted(() => ({ useRepositoryObserved: vi.fn() }))
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useRepositoryObserved,
}))

const empty = { items: [], total: 0, next_offset: null }

function renderCard(telemetryAttachedAt: string | null) {
  useRepositoryObserved.mockReturnValue({
    isPending: false,
    isError: false,
    isSuccess: true,
    isFetching: false,
    data: {
      repo_id: "org/one",
      telemetry_attached_at: telemetryAttachedAt,
      calls: empty,
      shapes: empty,
      error_windows: empty,
    },
  })
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <ObservedTelemetryCard repoId="org/one" />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe("the observed-telemetry empty state", () => {
  it("says nothing ever watched, when nothing ever watched", () => {
    renderCard(null)

    expect(screen.getAllByText(/never attached/i).length).toBeGreaterThan(0)
    expect(screen.getByText("Telemetry was never attached to this repository.")).not.toBeNull()
  })

  it("says traffic was watched and none arrived, when telemetry is attached", () => {
    renderCard("2026-08-16T12:00:00Z")

    // A measured nought. The distinction is the whole point: this one is evidence, the other is
    // the absence of evidence.
    expect(screen.getByText("Telemetry is attached, and no call arrived.")).not.toBeNull()
  })

  it("no longer claims it cannot tell the two apart, because it can", () => {
    const { container } = renderCard(null)

    expect(container.textContent).not.toContain("cannot tell the two apart")
  })
})
