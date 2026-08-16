import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import * as queries from "@/api/queries"
import type { WorkflowState } from "@/api/types"
import { PullRequestPage } from "@/features/pullrequests/pull-request-page"

afterEach(cleanup)

function renderScreen(findingId = "finding-123") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/findings/${findingId}/workflow/pull-request`]}>
        <Routes>
          <Route
            path="/findings/:findingId/workflow/pull-request"
            element={<PullRequestPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
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
})
