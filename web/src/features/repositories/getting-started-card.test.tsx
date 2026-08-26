/**
 * Which nothing an empty setup checklist is, and why the three probed states may never be two.
 *
 * `/api/setup` answering with no items rendered "0 / 0 ready" over a bare chip row — a ratio with
 * no denominator, and a completed-looking nothing standing in for a probe list that is empty.
 * Those are different facts and this pane now says which.
 *
 * Scope is `.claude/rules/test-discipline.md`'s: classification, never class names.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { GettingStartedCard } from "@/features/repositories/getting-started-card"
import type { SetupItem } from "@/features/settings/api"

const { fetchSetup } = vi.hoisted(() => ({ fetchSetup: vi.fn() }))
vi.mock("@/features/settings/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/settings/api")>()),
  fetchSetup,
}))

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

/** `settled` is the one string that only exists once the query has resolved — never a timer. */
async function renderPane(items: SetupItem[], settled: RegExp) {
  fetchSetup.mockResolvedValue({
    repo_id: "org/payments",
    operator: { forge_login: null },
    items,
  })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const view = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/repositories/org%2Fpayments"]}>
        <GettingStartedCard repoId="org/payments" />
      </MemoryRouter>
    </QueryClientProvider>
  )
  await screen.findByText(settled)
  return view
}

function item(over: Partial<SetupItem>): SetupItem {
  return {
    id: "id",
    label: "A prerequisite",
    state: "missing",
    detail: "",
    fix: null,
    ...over,
  }
}

describe("an empty setup checklist", () => {
  it("says the probe list was empty rather than that every prerequisite is satisfied", async () => {
    const { container } = await renderPane([], /No prerequisite was probed for this codebase\./)
    const text = container.textContent ?? ""

    expect(text).toContain("No prerequisite was probed for this codebase.")
    // A ratio over a zero denominator, and the completion sentence beside it, were the two ways
    // this pane used to render an unprobed deployment as a finished one.
    expect(text).not.toContain("0 / 0 ready")
    expect(text).not.toContain("Everything the full loop needs is in place")
  })
})

describe("the three probed states", () => {
  it("keeps 'not answered' apart from 'missing', because a probe that never ran claims nothing", async () => {
    const { container } = await renderPane(
      [
        item({ id: "index", label: "Indexed", state: "unanswered" }),
        item({ id: "model", label: "Model connected", state: "missing" }),
      ],
      /0 \/ 2 ready/
    )

    // Every chip carries its probed word, so the state is legible without its icon or its colour
    // — `console-surface.md`: a status colour is never the only channel. Collapsing `unanswered`
    // onto `missing` would claim a probe that never ran.
    expect(screen.getByTitle("Indexed — not answered")).toBeTruthy()
    expect(screen.getByTitle("Model connected — missing")).toBeTruthy()
    expect(container.textContent ?? "").toContain("0 / 2 ready")
  })
})
