/**
 * Measured nought, apart from nobody having looked — on the panel the Signals level draws.
 *
 * `ObservedTelemetryResponse` gained `telemetry_attached_at` (Lane I, dashboard 7). Before it, a
 * screen genuinely could not separate "telemetry is attached and saw no calls" from "nothing ever
 * watched this repository", and said so. It can now, so saying it cannot is a false statement of a
 * limit that no longer exists — and rendering one screen for two facts is the collapse this console
 * exists to refuse.
 *
 * It guarded `observed-telemetry-card.tsx` until the Overview became the pipeline's doors on
 * 2026-08-19. The card's three tables were the Signals level's, drawn twice; the distinction was
 * the card's alone, and it moved here with it rather than being deleted alongside the duplication.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { SignalSourcePanel } from "@/features/telemetry/signal-source-panel"

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

function renderPanel(telemetryAttachedAt: string | null) {
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
        <SignalSourcePanel repoId="org/one" />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe("the observed-telemetry empty state", () => {
  it("says nothing ever watched, exactly once", () => {
    renderPanel(null)

    // One fact about the repository, not three about the panels. This asserted 3 while each of
    // the three panels rendered its own copy, which made the common case -- a deployment with no
    // telemetry attached -- a wall of the same paragraph repeated verbatim.
    expect(screen.getAllByText("Telemetry was never attached to this repository.").length).toBe(1)
  })

  it("names the command that would attach a source", () => {
    const { container } = renderPanel(null)

    // A reader told they have no telemetry and not how to attach any has a diagnosis and no next
    // step. `CI-W514` made this the rule for every empty state whose remedy is a command.
    expect(container.textContent).toContain("sync ingest")
  })

  it("still names all three things that would have been recorded", () => {
    const { container } = renderPanel(null)

    // Saying it once must not cost the reader what telemetry holds -- the reason the three panels
    // were worth keeping when there was nothing in them.
    for (const recorded of ["observed calls", "response shapes", "error windows"]) {
      expect(container.textContent).toContain(recorded)
    }
  })

  it("says traffic was watched and none arrived, when telemetry is attached", () => {
    renderPanel("2026-08-16T12:00:00Z")

    // A measured nought. The distinction is the whole point: this one is evidence, the other is
    // the absence of evidence.
    expect(screen.getByText("Telemetry is attached, and no observed calls arrived.")).not.toBeNull()
  })

  it("no longer lists the three meanings it can now tell apart", () => {
    const { container } = renderPanel(null)

    expect(container.textContent).not.toContain("answers the same way in all three cases")
  })
})
