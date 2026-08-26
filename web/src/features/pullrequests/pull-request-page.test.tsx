import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, within } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { NotFoundError } from "@/api/errors"
import * as queries from "@/api/queries"
import type { DismissalState, PatchResponse, WorkflowState } from "@/api/types"
import { PullRequestPage } from "@/features/pullrequests/pull-request-page"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

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
    isPending: false,
    isFetching: false,
    isError: false,
    error: null,
    isSuccess: true,
    refetch: vi.fn(),
  } as never)
}

function mockWorkflowError(error: Error) {
  vi.spyOn(queries, "useWorkflow").mockReturnValue({
    data: undefined,
    isLoading: false,
    isPending: false,
    isFetching: false,
    isError: true,
    error,
    isSuccess: false,
    refetch: vi.fn(),
  } as never)
}

function mockPatch(patch: PatchResponse | undefined, error: Error | null = null) {
  vi.spyOn(queries, "usePatch").mockReturnValue({
    data: patch,
    isLoading: false,
    isPending: patch === undefined && error === null,
    isFetching: false,
    isError: error !== null,
    error,
    isSuccess: patch !== undefined,
    refetch: vi.fn(),
  } as never)
}

function mockDismissal(state: DismissalState) {
  vi.spyOn(queries, "useDismissal").mockReturnValue({
    data: state,
    isLoading: false,
    isPending: false,
    isFetching: false,
    isError: false,
    error: null,
    isSuccess: true,
    refetch: vi.fn(),
  } as never)
}

const OPEN_RULING: DismissalState = {
  dismissed: false,
  reason: null,
  actor: null,
  history_count: 0,
}

const NO_PATCH: PatchResponse = {
  diff: null,
  strategy: null,
  rationale: null,
  stat: null,
  target: { repo_id: null, branch: "sync/fix", pr_url: null, pr_number: null },
  absent_because:
    "This run opened a pull request but its checkpoint no longer carries the patch -- the diff is on the branch named beside this.",
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
  it("renders the repository as a link in the bundle header when repo_id is present", () => {
    mockWorkflow(OPENED)
    mockPatch(NO_PATCH)
    mockDismissal(OPEN_RULING)

    const { container } = renderScreen("finding-123")

    const header = container.querySelector('[data-testid="bundle-header"]')!
    expect(within(header as HTMLElement).getByText("Repository")).toBeTruthy()
    const repoLink = within(header as HTMLElement).getByRole("link", { name: "org/my-service" })
    expect(repoLink.getAttribute("href")).toBe("/repositories/org%2Fmy-service")
  })

  it("builds its workspace links from the address's repository", () => {
    mockWorkflow(OPENED)
    mockPatch(NO_PATCH)
    mockDismissal(OPEN_RULING)

    renderScreen("finding-123", "acme/web")

    // The defect: `repoId` was passed through unchecked, `workspacePath(undefined)` is
    // `/repositories/`, and both of these resolved to the console's unknown-address screen.
    expect(screen.getByRole("link", { name: "finding-123" }).getAttribute("href")).toBe(
      "/repositories/acme%2Fweb/findings/finding-123",
    )
    expect(screen.getByRole("link", { name: "The solution workflow" }).getAttribute("href")).toBe(
      "/repositories/acme%2Fweb/findings/finding-123/workflow",
    )
  })

  it("refuses an address with no repository rather than linking to /repositories/", () => {
    mockWorkflow(OPENED)
    mockPatch(NO_PATCH)
    mockDismissal(OPEN_RULING)

    renderScreen("finding-123", null)

    expect(screen.getByText("No screen at this address.")).toBeTruthy()
  })

  it("states the run's counts and what this route cannot date", () => {
    mockWorkflow(OPENED)
    mockPatch(NO_PATCH)
    mockDismissal(OPEN_RULING)

    renderScreen("finding-123")

    // Two of the five, because `static_verify`, `replay` and `await_ci` are not on this payload.
    expect(screen.getByText("2 of 5")).toBeTruthy()
    // The two things this route cannot say, because it reads the checkpointer and not the graph.
    expect(screen.getByText(/dated by an index run/)).toBeTruthy()
    expect(screen.getByText(/attributed to a binding rung/)).toBeTruthy()
  })

  /**
   * The screen owns its own scrollbars. At `flow` this is one unbounded column and the panes below
   * are decoration — which is the failure the whole rebuild wave exists to catch, and it is
   * invisible to every assertion about content.
   */
  it("occupies the chassis as a locked screen rather than one scrolling column", () => {
    mockWorkflow(OPENED)
    mockPatch(NO_PATCH)
    mockDismissal(OPEN_RULING)

    const { container } = renderScreen("finding-123")

    expect(container.querySelector('[data-band="content"][data-screen="locked"]')).not.toBeNull()
  })

  /**
   * Owner decision 47, read structurally: the chain is pinned in the change pane's foot, outside
   * the body that scrolls. Beneath a sixty-line diff in a scroller it is discoverable only by
   * scrolling, which is the click this console refuses to ask for.
   */
  it("pins the verification chain outside the scrolling body of the change pane", () => {
    mockWorkflow(OPENED)
    mockPatch(NO_PATCH)
    mockDismissal(OPEN_RULING)

    const { container } = renderScreen("finding-123")

    const chain = container.querySelector('[data-testid="verification-chain"]')
    expect(chain).not.toBeNull()
    expect(chain!.closest("footer")).not.toBeNull()
  })

  /**
   * The reference puts `Overall Agent Confidence 98%` in this position. Two checks are reported as
   * two checks and the absence of a combined figure is stated rather than merely arranged for.
   */
  it("reports the two checks separately and says there is no combined figure", () => {
    mockWorkflow(OPENED)
    mockPatch(NO_PATCH)
    mockDismissal(OPEN_RULING)

    renderScreen("finding-123")

    expect(screen.getByText("TypeScript compiled")).toBeTruthy()
    expect(screen.getByText("The customer's CI")).toBeTruthy()
    expect(screen.getByText(/no combined figure/)).toBeTruthy()
  })

  /**
   * Four different runs produce no diff for four different reasons and the API tells them apart.
   * A generic "no patch" panel here would render all four as one.
   */
  it("says which nothing a missing diff is, in the payload's own words", () => {
    mockWorkflow(OPENED)
    mockPatch(NO_PATCH)
    mockDismissal(OPEN_RULING)

    renderScreen("finding-123")

    expect(screen.getByText(/checkpoint no longer carries the patch/)).toBeTruthy()
  })

  /**
   * The absence phrases in `bundle-facts.ts` are keyed by a run's outcome, so they are reachable
   * only once a run has answered. Over a 404 they would say *the run has not opened one yet* about
   * a finding the checkpointer holds no run for at all — one nothing rendered as another.
   */
  it("does not describe a missing run as a run that has not got there yet", () => {
    mockWorkflowError(new NotFoundError("no run", "finding-123", "/api/workflows/finding-123"))
    mockPatch(undefined, new NotFoundError("no patch", "finding-123", "/api/findings/finding-123/patch"))
    mockDismissal(OPEN_RULING)

    const { container } = renderScreen("finding-123")

    const header = within(container.querySelector('[data-testid="bundle-header"]') as HTMLElement)
    expect(header.queryByText(/the run has not opened one yet/)).toBeNull()
    expect(header.queryByText(/the run has not pushed anything yet/)).toBeNull()
    expect(header.getByText(/no run for this finding/)).toBeTruthy()
  })
})
