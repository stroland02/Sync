/**
 * The remediation pane: what the run produced, what checked it, and the figure refused in place.
 *
 * Two of these carry concerns ported out of files this rebuild deleted. The confidence-refusal
 * assertions came from `settled-output.test.tsx`, and they are the guard on the single refusal this
 * rebuild was most likely to lose — the reference draws a confidence bar exactly where our two
 * paragraphs now sit, which is precisely why the prose has to be held by a test rather than by
 * whoever remembers the argument.
 *
 * Derivation and structure only. Never class names, never a snapshot.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, within } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import * as queries from "@/api/queries"
import type { PatchResponse, WorkflowNode, WorkflowState } from "@/api/types"
import { RemediationPane } from "@/features/workflows/remediation-pane"

vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  usePatch: vi.fn(),
}))

afterEach(cleanup)

function node(over: Partial<WorkflowNode> = {}): WorkflowNode {
  return { name: "locate", status: "done", standing: "ran", evidence: {}, ...over }
}

function state(nodes: WorkflowNode[], over: Partial<WorkflowState> = {}): WorkflowState {
  return {
    nodes,
    outcome: null,
    abandon_reason: null,
    report_reason: null,
    thread_id: "finding-1:abc:0",
    generation_count: 1,
    repo_id: "org/svc",
    generations: [],
    ...over,
  }
}

function patch(over: Partial<PatchResponse> = {}): PatchResponse {
  return {
    diff: "--- a/one.ts\n+++ b/one.ts\n-const a = 1\n+const a = 2",
    strategy: "model",
    rationale: "The vendor renamed the field, so the call site reads the new name.",
    stat: { files_changed: 1, lines_added: 1, lines_removed: 1 },
    target: { repo_id: "org/svc", branch: "sync/fix-1", pr_url: "https://example.test/pr/7", pr_number: 7 },
    absent_because: null,
    ...over,
  }
}

function mockPatch(over: Record<string, unknown>) {
  vi.mocked(queries.usePatch).mockReturnValue({
    data: undefined,
    isPending: false,
    isError: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
    ...over,
  } as never)
}

function renderPane(data: WorkflowState) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RemediationPane repoId="org/one" findingId="finding-1" data={data} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("the change this run wrote", () => {
  it("renders the payload's own sentence and no diff when there is no diff", () => {
    mockPatch({ data: patch({ diff: null, stat: null, absent_because: "This run gave up before writing a patch." }) })

    const { container } = renderPane(state([]))

    expect(screen.getByText("This run gave up before writing a patch.")).not.toBeNull()
    // A run that decided against a patch, one that gave up and one still working are three
    // different sentences; the console renders the payload's rather than picking one.
    expect(container.querySelector("ol.overflow-x-auto")).toBeNull()
  })

  it("states the branch once, in the panel named for where the change went", () => {
    // Measured against the seed corpus on 2026-08-26: the diff panel's target list and the "Where
    // it went" panel both drew `sync/fix-post-charges-param`, one above the other, on one pane.
    mockPatch({ data: patch() })

    renderPane(state([]))

    expect(screen.getAllByText("sync/fix-1")).toHaveLength(1)
  })

  it("leaves Strategy to the top bar, so the pane cannot contradict it", () => {
    // `PatchResponse.strategy` and `nodes[patch].evidence.attempt_strategy` are two fields, and on
    // `9f176dea…` the tile read `agent` while the pane read "patch has produced no attempt". Two
    // Strategy values disagreeing on one screen is worse than one of them being absent.
    mockPatch({ data: patch({ strategy: null }) })

    const { container } = renderPane(
      state([node({ name: "patch", evidence: { attempt_strategy: "agent" } })]),
    )

    expect(container.textContent).not.toContain("Strategy")
  })

  it("says which nothing a missing rationale is, rather than falling back to the strategy", () => {
    mockPatch({ data: patch({ rationale: null }) })

    renderPane(state([]))

    expect(screen.getByText(/the run recorded no rationale for this patch/i)).not.toBeNull()
  })

  it("offers a retry when the patch route did not answer", () => {
    const refetch = vi.fn()
    mockPatch({ isError: true, error: new Error("nope"), refetch })

    renderPane(state([]))

    expect(screen.getByText(/the API did not answer for this patch/i)).not.toBeNull()
    expect(screen.getByRole("button", { name: "Check again" })).not.toBeNull()
  })
})

describe("what checked it", () => {
  it("always reports two checks, even when neither node exists", () => {
    // Dropping a check that did not happen leaves a shorter chain that looks complete, which is
    // how "we could not check" becomes invisible.
    mockPatch({ data: patch() })

    renderPane(state([]))

    expect(screen.getByRole("heading", { name: "TypeScript compiled" })).not.toBeNull()
    expect(screen.getByRole("heading", { name: "The customer's CI" })).not.toBeNull()
  })

  it("says a run parked on the customer's CI is waiting, never that it passed", () => {
    mockPatch({ data: patch() })

    renderPane(
      state([
        node({ name: "static_verify", evidence: { verify_ok: true } }),
        node({
          name: "await_ci",
          status: "current",
          standing: "due",
          evidence: { ci_url: "https://ci.test/run/9", attempt_ci_result: null },
        }),
      ]),
    )

    expect(
      screen.getByText(/waiting on the customer's CI. It has not passed and it has not failed/i),
    ).not.toBeNull()
    expect(screen.queryByText(/The customer's own suite accepted the patch/i)).toBeNull()
  })

  it("takes only the compiler output off static_verify, so the tsc verdict is stated once", () => {
    // `verify_ok` is the verdict the chain directly above has already put into a sentence. The
    // full `NodeEvidence` would render it again as a PASS chip — one fact at two weights.
    mockPatch({ data: patch() })

    renderPane(
      state([node({ name: "static_verify", evidence: { verify_ok: true, diagnostics: "no errors" } })]),
    )

    expect(screen.getByText("no errors")).not.toBeNull()
    expect(screen.queryByText(/^PASS/)).toBeNull()
    expect(screen.getAllByText(/The compiler accepted the patched tree/i)).toHaveLength(1)
  })

  it("says the run carries no replay step rather than leaving the slot blank", () => {
    mockPatch({ data: patch() })

    renderPane(state([]))

    expect(screen.getByText(/This run carries no replay step/i)).not.toBeNull()
  })
})

describe("the refusal is argued, not merely performed", () => {
  /**
   * Ported from `settled-output.test.tsx`. From `superlog-02`, read 2026-08-18: their
   * `rootCause.confidence` is a 0-10 scale where ten means direct verbatim evidence and zero means
   * speculative. That is the provenance rung with the information thrown away.
   */
  it("says a confidence score compresses the class of evidence the rung names", () => {
    mockPatch({ data: patch() })

    const { container } = renderPane(state([]))

    const text = container.textContent ?? ""
    expect(text).toContain("class of evidence")
    expect(text).toMatch(/compress|collaps/i)
  })

  it("still carries no scalar of its own while making that argument", () => {
    mockPatch({ data: patch({ diff: null, stat: null, absent_because: "No patch." }) })

    const { container } = renderPane(state([]))

    const text = container.textContent ?? ""
    expect(text).not.toMatch(/\b\d{1,2}\s*\/\s*(?:5|10)\b/)
    expect(text).not.toMatch(/confidence[:\s]+\d/i)
  })
})

describe("where it went", () => {
  it("separates a run that never reached CI from one that reached it and recorded no URL", () => {
    mockPatch({ data: patch() })

    const never = renderPane(state([]))
    expect(within(never.container).getByText(/the run never reached the customer's CI/i)).not.toBeNull()

    cleanup()

    const recorded = renderPane(
      state([node({ name: "await_ci", evidence: { ci_url: null } })]),
    )
    expect(
      within(recorded.container).getByText(/the run reached CI and recorded no URL/i),
    ).not.toBeNull()
  })

  it("says a patch was never pushed and that no pull request was opened", () => {
    mockPatch({ data: patch({ target: { repo_id: "org/svc", branch: null, pr_url: null, pr_number: null } }) })

    renderPane(state([]))

    expect(screen.getAllByText(/this patch was never pushed/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/no pull request was opened for this run/i)).not.toBeNull()
  })
})

describe("a reviewer's turn", () => {
  it("holds the reply box and names the three actions that cannot act", () => {
    mockPatch({ data: patch() })

    const { container } = renderPane(state([]))

    expect(screen.getByRole("heading", { name: "Reply to this run" })).not.toBeNull()
    const text = container.textContent ?? ""
    for (const action of ["copy the agent prompt", "give feedback", "restart the run"]) {
      expect(text.toLowerCase()).toContain(action)
    }
    expect(text).toContain("which no checkpoint channel records")
    expect(text).toContain("a write route that accepts a reviewer's judgement of a run")
    expect(text).toContain("a route that starts remediation, which would mutate the graph")
  })
})
