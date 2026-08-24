/**
 * One finding's place in the solutions workflow, as a table cell.
 *
 * What is under test is the classification: which of the four claims the cell makes for a given
 * ticket history, and that the two nothings — a read still in flight and a finding nothing was
 * sent for — never collapse into each other. The first must not offer the button, because "not
 * read yet" is not "not sent"; the second must, because that is the cell's whole job.
 *
 * Scope is `web/CLAUDE.md`'s: classification and structure, never class names.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import type { Ticket } from "@/api/types"
import { TicketCell } from "@/features/tickets/ticket-cell"

afterEach(cleanup)

function ticket(overrides: Partial<Ticket> = {}): Ticket {
  return {
    id: 1,
    finding_id: "f-1",
    repo_id: "demo",
    source: "operator",
    status: "requested",
    requested_at: "2026-08-20T10:00:00Z",
    picked_up_at: null,
    done_at: null,
    thread_id: null,
    outcome: null,
    detail: null,
    ...overrides,
  }
}

function renderCell(tickets: readonly Ticket[] | null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <TicketCell repoId="demo" findingId="f-1" tickets={tickets} />
    </QueryClientProvider>,
  )
}

describe("what the cell claims about one finding", () => {
  it("says the read is in flight rather than claiming nothing was sent", () => {
    renderCell(null)

    expect(screen.getByText(/not read yet/)).toBeTruthy()
    // The distinction the null is for: an unread list must not offer a write against it.
    expect(screen.queryByRole("button")).toBeNull()
  })

  it("offers the send when no ticket stands against this finding", () => {
    // Another finding's live ticket must not leak in: classification is per finding.
    renderCell([ticket({ finding_id: "f-other", status: "picked_up" })])

    expect(screen.getByRole("button", { name: /Send to workflow/ })).toBeTruthy()
  })

  it("reports a requested ticket as queued, which is not the same claim as running", () => {
    renderCell([ticket({ status: "requested" })])

    expect(screen.getByText("queued")).toBeTruthy()
    expect(screen.queryByText("in progress")).toBeNull()
    expect(screen.queryByRole("button")).toBeNull()
  })

  it("reports a picked-up ticket as in progress", () => {
    renderCell([ticket({ status: "picked_up", picked_up_at: "2026-08-20T10:05:00Z" })])

    expect(screen.getByText("in progress")).toBeTruthy()
    expect(screen.queryByText("queued")).toBeNull()
  })

  it("wears a finished run's own outcome and links the pull request it opened", () => {
    renderCell([
      ticket({
        status: "done",
        outcome: "opened",
        detail: "https://github.com/acme/repo/pull/7",
      }),
    ])

    expect(screen.getByText("opened")).toBeTruthy()
    const link = screen.getByRole("link", { name: "PR" })
    expect(link.getAttribute("href")).toBe("https://github.com/acme/repo/pull/7")
    // An opened pull request is a settled answer, not an invitation to send again.
    expect(screen.queryByRole("button")).toBeNull()
  })

  it("offers a second send beside an abandoned outcome, without hiding the outcome", () => {
    renderCell([ticket({ status: "done", outcome: "abandoned", detail: "no safe patch" })])

    // Both at once: the recorded outcome stays on screen, and the reader can try again.
    expect(screen.getByText("abandoned")).toBeTruthy()
    expect(screen.getByRole("button", { name: /Send again/ })).toBeTruthy()
  })

  it("classifies against the newest ticket when a finding was sent more than once", () => {
    renderCell([
      ticket({
        id: 1,
        status: "done",
        outcome: "abandoned",
        requested_at: "2026-08-19T10:00:00Z",
      }),
      ticket({ id: 2, status: "requested", requested_at: "2026-08-20T10:00:00Z" }),
    ])

    // The abandoned run is history; the live request is the standing claim.
    expect(screen.getByText("queued")).toBeTruthy()
    expect(screen.queryByRole("button")).toBeNull()
  })
})
