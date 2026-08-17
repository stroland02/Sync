/**
 * Panel-level behavior beyond `codebase-cards.ts`'s derivation: a card renders the absence
 * marker while its own scoped `/api/overview` query is still pending, and the scoped count
 * once that answer lands. Scope is `.claude/rules/console-dev-loop.md`'s — classification and
 * derivation, never class names, never a snapshot.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { OverviewResponse } from "@/api/types"
import { CodebasesPanel } from "@/features/fleet/codebases-panel"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

let mockRepositories: unknown

vi.mock("@/api/queries", () => ({
  useRepositories: () => mockRepositories,
}))

const { fetchOverview } = vi.hoisted(() => ({ fetchOverview: vi.fn() }))
vi.mock("@/api/client", () => ({ fetchOverview }))

const overview = (over: Partial<OverviewResponse>): OverviewResponse => ({
  repo_id: "org/repo",
  vendors: [],
  total_findings: 0,
  total_findings_bound: 0,
  total_findings_bound_reached: true,
  severity_counts: {},
  indexed_at: null,
  feed_fetched_at: null,
  binding_source: null,
  context_savings: 0,
  context_savings_bound_reached: true,
  ...over,
})

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <CodebasesPanel />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe("CodebasesPanel", () => {
  it("renders the absence marker on a card while its scoped overview is still pending", async () => {
    mockRepositories = { isPending: false, isError: false, data: { repo_ids: ["org/repo"] } }
    fetchOverview.mockReturnValue(new Promise<OverviewResponse>(() => {}))

    renderPanel()

    expect(await screen.findByText("org/repo")).toBeTruthy()
    expect(screen.getByText(/open findings not yet answered/)).toBeTruthy()
  })

  it("renders the scoped count once the answer for that repository arrives", async () => {
    mockRepositories = { isPending: false, isError: false, data: { repo_ids: ["org/repo"] } }
    fetchOverview.mockResolvedValue(overview({ total_findings: 3 }))

    renderPanel()

    expect(await screen.findByText("3 open findings")).toBeTruthy()
  })

  it("refuses to claim a card's scope from a different repository's answer", async () => {
    mockRepositories = { isPending: false, isError: false, data: { repo_ids: ["org/repo"] } }
    fetchOverview.mockResolvedValue(overview({ repo_id: "org/other", total_findings: 9 }))

    renderPanel()

    expect(await screen.findByText("org/repo")).toBeTruthy()
    expect(screen.queryByText("9 open findings")).toBeNull()
    expect(screen.getByText(/open findings not yet answered/)).toBeTruthy()
  })
})
