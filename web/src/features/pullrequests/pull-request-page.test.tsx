import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import * as queries from "@/api/queries"
import type { WorkflowState } from "@/api/types"
import { PullRequestPage } from "@/features/pullrequests/pull-request-page"

afterEach(cleanup)

/**
 * The registry's own address, which carries `repoId`. The route path here used to omit it, so the
 * screen rendered with `repoId` undefined — the state the workspace links were broken in.
 */
function renderScreen(findingId = "finding-123", repoId: string | null = "acme/web") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const path =
    repoId === null
      ? "/findings/:findingId/workflow/pull-request"
      : "/repositories/:repoId/findings/:findingId/workflow/pull-request"
  const entry =
    repoId === null
      ? `/findings/${findingId}/workflow/pull-request`
      : `/repositories/${encodeURIComponent(repoId)}/findings/${findingId}/workflow/pull-request`
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path={path} element={<PullRequestPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function mockWorkflow(state: WorkflowState) {
  vi.spyOn(queries, "useWorkflow").mockReturnValue({
    data: state,
    isLoading: false,
    isError: false,
    error: null,
    isSuccess: true,
    refetch: vi.fn(),
  } as any)
}

const OPENED: WorkflowState = {
  nodes: [
    {
      name: "open_pr",
      status: "done",
      standing: "ran",
      evidence: { pr_number: 101, pr_url: "https://github.com/example/repo/pull/101" },
    },
    { name: "push_branch", status: "done", standing: "ran", evidence: { branch: "sync/fix" } },
  ],
  outcome: "opened",
  abandon_reason: null,
  report_reason: null,
  thread_id: "finding-123:abc:0",
  generation_count: 1,
  repo_id: "org/my-service",
  generations: [],
}

describe("PullRequestPage", () => {
  it("renders repository link in the fact rail when repo_id is present", () => {
    const mockState: WorkflowState = {
      nodes: [
        {
          name: "open_pr",
          status: "done",
          standing: "ran",
          evidence: { pr_number: 101, pr_url: "https://github.com/example/repo/pull/101" },
        },
        {
          name: "push_branch",
          status: "done",
          standing: "ran",
          evidence: { branch: "sync/fix" },
        },
      ],
      outcome: "opened",
      abandon_reason: null,
      report_reason: null,
      thread_id: "finding-123:abc:0",
      generation_count: 1,
      repo_id: "org/my-service",
      generations: [],
    }

    vi.spyOn(queries, "useWorkflow").mockReturnValue({
      data: mockState,
      isLoading: false,
      isError: false,
      error: null,
      isSuccess: true,
      refetch: vi.fn(),
    } as any)

    renderScreen("finding-123")

    expect(screen.getByText("Repository")).toBeTruthy()
    const repoLink = screen.getByRole("link", { name: "org/my-service" })
    expect(repoLink.getAttribute("href")).toBe("/repositories/org%2Fmy-service")
  })

  it("builds its workspace links from the address's repository", () => {
    mockWorkflow(OPENED)

    renderScreen("finding-123", "acme/web")

    // The defect: `repoId` was passed through unchecked, `workspacePath(undefined)` is
    // `/repositories/`, and both of these resolved to the console's unknown-address screen.
    expect(screen.getByRole("link", { name: "finding-123" }).getAttribute("href")).toBe(
      "/repositories/acme%2Fweb/findings/finding-123",
    )
    expect(screen.getByRole("link", { name: "the solution workflow" }).getAttribute("href")).toBe(
      "/repositories/acme%2Fweb/findings/finding-123/workflow",
    )
  })

  it("refuses an address with no repository rather than linking to /repositories/", () => {
    mockWorkflow(OPENED)

    renderScreen("finding-123", null)

    expect(screen.getByText("No screen at this address.")).toBeTruthy()
  })

  it("states the run's counts and what this route cannot date", () => {
    mockWorkflow(OPENED)

    renderScreen("finding-123")

    // Two of the five, because `static_verify`, `replay` and `await_ci` are not on this payload.
    expect(screen.getByText("2 of 5")).toBeTruthy()
    expect(screen.getByText("1 of 1")).toBeTruthy()
    expect(
      screen.getByText(/carries no indexed_at and no binding rung/),
    ).toBeTruthy()
  })
})
