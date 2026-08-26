/**
 * The finding detail, as the evidence/remediation split.
 *
 * The harness renders the real route — `/repositories/:repoId/findings/:findingId` — because the
 * pane foot's `TicketAction` needs a workspace and the previous harness mounted an unscoped path no
 * route declares. Every query the two panes read is spied, so a pane's state is the test's choice
 * rather than whatever a real fetch does in jsdom.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { NotFoundError } from "@/api/errors"
import * as queries from "@/api/queries"
import type { FindingDetail, WorkflowNode, WorkflowState } from "@/api/types"
import { FindingPage } from "@/features/findings/finding-page"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function finding(overrides: Partial<FindingDetail> = {}): FindingDetail {
  return {
    finding: {
      finding_id: "f1",
      binding_source: "static",
      severity: "breaking",
      file: "src/billing.ts",
      line: 42,
      repo_id: "acme/corp-app",
    },
    symbol: "stripe.charges.create",
    operation: "PostPaymentIntents",
    vendor: "stripe",
    args_keys: ["amount", "currency"],
    response_fields_read: ["status"],
    sdk_version: "18.0.0",
    known_changes: [],
    indexed_at: "2026-08-01T00:00:00Z",
    feed_fetched_at: null,
    context_savings: 100,
    context_savings_bound_reached: false,
    binding_source: "static",
    source_served: true,
    call_site_source: null,
    ...overrides,
  }
}

function node(name: string, evidence: Record<string, unknown>): WorkflowNode {
  return { name, evidence, standing: "ran", last_seen_at: null } as unknown as WorkflowNode
}

function workflow(overrides: Partial<WorkflowState> = {}): WorkflowState {
  return {
    nodes: [node("static_verify", { verify_ok: true }), node("await_ci", { attempt_ci_result: "passed" })],
    outcome: "opened",
    abandon_reason: null,
    report_reason: null,
    thread_id: "t-1",
    generation_count: 1,
    repo_id: "acme/corp-app",
    generations: [],
    ...overrides,
  } as WorkflowState
}

const PENDING = { data: undefined, isPending: true, isError: false, error: null, isSuccess: false, refetch: vi.fn() }

function answered<T>(data: T) {
  return { data, isPending: false, isError: false, error: null, isSuccess: true, refetch: vi.fn() }
}

function failed(error: unknown) {
  return { data: undefined, isPending: false, isError: true, error, isSuccess: false, refetch: vi.fn() }
}

/**
 * Every read the screen makes, defaulting to a finding that answered and a run that opened.
 *
 * `useTickets` and `useCreateTicket` are spied even where the test says nothing about them: the
 * pane foot mounts `TicketAction` in every state, and an unspied mutation hook reaches a fetch that
 * does not exist under jsdom.
 */
function mount({
  find = answered(finding()),
  run = answered(workflow()),
  patch = answered({
    diff: "- old\n+ new",
    strategy: "regenerate",
    rationale: "The vendor renamed the field this call reads.",
    stat: { files_changed: 1, lines_added: 1, lines_removed: 1 },
    target: { repo_id: "acme/corp-app", branch: "sync/f1", pr_url: null, pr_number: null },
    absent_because: null,
  }),
  dismissal = answered({ dismissed: false, reason: null, actor: null, history_count: 0 }),
}: {
  find?: unknown
  run?: unknown
  patch?: unknown
  dismissal?: unknown
} = {}) {
  vi.spyOn(queries, "useFinding").mockReturnValue(find as never)
  vi.spyOn(queries, "useWorkflow").mockReturnValue(run as never)
  vi.spyOn(queries, "usePatch").mockReturnValue(patch as never)
  vi.spyOn(queries, "useDismissal").mockReturnValue(dismissal as never)
  vi.spyOn(queries, "useTickets").mockReturnValue(answered({ tickets: [] }) as never)
  vi.spyOn(queries, "useCreateTicket").mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
  } as never)

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/repositories/acme%2Fcorp-app/findings/f1"]}>
        <Routes>
          <Route path="/repositories/:repoId/findings/:findingId" element={<FindingPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("FindingPage", () => {
  /**
   * Replaces "carries no page header, which is the twelfth page and the last exception". That
   * ruling was superseded by `CI-W622` — every screen names itself, larger than its own sections —
   * for the other eleven screens, and this rebuild closes the exception in the other direction.
   */
  it("names the finding in its heading, and states an operation the payload did not carry", () => {
    mount()
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("stripe · PostPaymentIntents")

    cleanup()
    mount({ find: answered(finding({ operation: null })) })
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("stripe")
    // Never dropped and never filled: a name one part short reads as a complete name for a
    // different thing, which is what `lib/detail-title.tsx` exists to prevent.
    expect(screen.getAllByText(/this binding names no operation/).length).toBeGreaterThan(0)
  })

  /**
   * Replaces "renders severity, repository link, and call site path and line in fact rail". All
   * three moved when the rail was deleted — severity and the call site into the identity band, the
   * repository into the left pane's "The binding, as recorded" — so the test follows the facts
   * rather than the arrangement that used to hold them.
   */
  it("keeps the subject in the identity band and every binding fact reachable", () => {
    mount()

    const identity = screen.getByTestId("finding-identity")
    expect(identity.textContent).toContain("breaking")
    expect(identity.textContent).toContain("src/billing.ts:42")
    expect(identity.textContent).toContain("f1")

    const repoLink = screen.getByRole("link", { name: "acme/corp-app" })
    expect(repoLink.getAttribute("href")).toBe("/repositories/acme%2Fcorp-app")
  })

  /**
   * The highest-value guard on this screen. The two nothings are one `instanceof NotFoundError`
   * apart, and collapsing them puts a false report of a failure over a true answer about the
   * finding. The run answers here so the sentence can only have come from the patch branch.
   */
  it("reads a 404 from the patch as the checkpointer holding no run, not as a failed request", () => {
    mount({ patch: failed(new NotFoundError("no run", "f1", "/api/x")) })

    expect(
      screen.getAllByText(/the checkpointer holds no run for this finding/).length,
    ).toBeGreaterThan(0)
    expect(screen.queryAllByText(/the API did not answer for this patch/)).toHaveLength(0)
  })

  /**
   * `verificationChain([])` returns two checks reading "This run carries no compile step", which is
   * the wrong nothing for a finding that has no run at all — it describes a run that ran and
   * skipped a step. The section is gated on a run existing.
   */
  it("does not describe checks for a finding whose run the checkpointer does not hold", () => {
    mount({ run: failed(new NotFoundError("no run", "f1", "/api/x")) })

    expect(screen.queryAllByText(/TypeScript compiled/)).toHaveLength(0)
    expect(screen.getAllByText(/nothing has checked anything/).length).toBeGreaterThan(0)
  })

  /** A pane that hides its own name until data arrives makes a loading screen unreadable. */
  it("names both panes while every read is still in flight", () => {
    mount({ find: PENDING, run: PENDING, patch: PENDING, dismissal: PENDING })

    expect(screen.getByRole("heading", { name: "Evidence" })).toBeTruthy()
    expect(screen.getByRole("heading", { name: "Remediation" })).toBeTruthy()
  })

  /** Absence is not zero, held at both ends of the same fact: the panel and the status band. */
  it("renders an empty change list as a counted zero, and the band agrees", () => {
    mount({ find: answered(finding({ known_changes: [] })) })

    expect(screen.getByText("No vendor change names this call site.")).toBeTruthy()
    expect(screen.getByText("Known changes").nextElementSibling?.textContent).toBe("0")
  })
})
