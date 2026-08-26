/**
 * Findings: what is broken in this workspace, as a destination rather than a drill-down.
 *
 * The console had five nav routes and no findings list. A finding was reachable only by going
 * through a vendor, a signal or a detector first, so the one question the product exists to answer
 * -- *what is broken here* -- had no screen. This is that screen.
 *
 * **The fixture now mocks `useChangeUnits`, `useTickets` and the dismissal tally.** The grouped
 * view is the default and the page reads all three unconditionally, so without them every
 * assertion below would land on a loading state rather than on its subject.
 *
 * **The two empty-state assertions keep their wording and change their source.** They used to come
 * from `TriageTabs`; they come from `TriageEmpty` in the table pane now. Proven red by deleting the
 * `TriageEmpty` call and watching both go silent.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification, derivation and structural
 * invariants, never class names and never a snapshot.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { FindingsPage } from "@/features/findings/findings-page"
import type { RiskRow, VendorFindingsPage } from "@/api/types"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function row(overrides: Partial<RiskRow> = {}): RiskRow {
  return {
    name: "stripe-postcharges-4b1c9e",
    file: "src/billing/charge.ts",
    line: 42,
    symbol: "createCharge",
    operation: "PostCharges",
    vendor: "stripe",
    change_kind: "removed",
    severity: "breaking",
    finding_id: "f-91ac",
    binding_source: "resolved",
    ...overrides,
  }
}

const mockState: { page: unknown; units: unknown[] } = { page: null, units: [] }

const settled = (data: unknown) => ({
  isPending: false,
  isError: false,
  isSuccess: true,
  data,
  error: null,
  isFetching: false,
  refetch: () => undefined,
})

vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useWorkspaceFindings: () => settled(mockState.page),
  // The page gates its body on this too -- an unmocked detector roll-up stays pending and the
  // table never renders, so every assertion below fails on a loading state rather than on its
  // subject. The names matter: the empty panel reports which detectors stood behind a zero.
  useDetectors: () =>
    settled({ detectors: [{ detector: "vendor_change", total: 1 }], by_rung: {}, total_open_findings: 1 }),
  useChangeUnits: () => settled({ items: mockState.units, total: mockState.units.length, next_offset: null }),
  useTickets: () => settled({ tickets: [] }),
  useFinding: () => settled(undefined),
  useWorkflow: () => settled(undefined),
}))

vi.mock("@/features/findings/dismissed-note", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/findings/dismissed-note")>()),
  useDismissalTally: () => ({ isPending: false, isError: false, data: { total: 7, counts: {} } }),
}))

function page(items: RiskRow[], overrides: Partial<VendorFindingsPage> = {}) {
  return {
    items,
    total: items.length,
    next_offset: null,
    repo_id: "org/one",
    vendor_id: null,
    severity_counts: { breaking: 1 },
    severity_total: items.length,
    order: "severity",
    severity_order: ["breaking", "behavioural"],
    indexed_at: null,
    feed_fetched_at: null,
    binding_source: "resolved",
    context_savings: 0,
    ...overrides,
  } as unknown as VendorFindingsPage
}

// The flat table is one press away rather than the default since M15 Task 7 -- the change unit
// leads, because one vendor change breaking eleven call sites is one decision. These guards are
// about the flat table's rows, so they open it explicitly rather than relying on a default that
// has deliberately moved.
function renderFindings(entry = "/repositories/org%2Fone/findings?findings_view=flat") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/repositories/:repoId/findings" element={<FindingsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe("the findings screen", () => {
  it("links each row to the finding, inside this workspace", () => {
    mockState.page = page([row()])
    const { container } = renderFindings()

    // The whole point of the screen, and the thing W436 found broken everywhere else: the link has
    // to carry the workspace, because `/findings/:id` is not a route the router serves.
    const link = container.querySelector('a[href="/repositories/org%2Fone/findings/f-91ac"]')
    expect(link).not.toBeNull()
  })

  it("builds the operation link from the row's own vendor, not from a page-level one", () => {
    mockState.page = page([row({ vendor: "shopify", operation: "GetOrder" })])
    const { container } = renderFindings()

    // A workspace-wide list holds several vendors at once, so a page-level vendor would put every
    // row's operation under one vendor's binding surface. Each row carries its own.
    const link = container.querySelector(
      'a[href="/repositories/org%2Fone/bindings/vendors/shopify/operations/GetOrder"]'
    )
    expect(link).not.toBeNull()
  })

  it("shows the rung on every row, because a finding that cannot be attributed cannot be fixed", () => {
    mockState.page = page([row({ binding_source: "static" })])
    const { container } = renderFindings()

    // `CLAUDE.md`: every binding carries the rung it came from, and so does every artifact derived
    // from it. The rung is never a hideable column.
    expect(container.textContent).toMatch(/static/i)
  })

  it("says the count is this workspace's, and never states it unscoped", () => {
    mockState.page = page([row(), row({ finding_id: "f-2" })])
    const { container } = renderFindings()
    const text = container.textContent ?? ""

    // Asserting that "org/one" appears anywhere is not this assertion: the breadcrumb prints it,
    // so a figure that had lost its scope entirely still passed that version of this test. It has
    // to be the *figure* that names the workspace, which is what this phrasing pins.
    expect(text).toContain("findings in org/one")
  })

  it("distinguishes an empty workspace from one nothing has looked at", () => {
    // Absence apart from zero, which is one of the four distinctions this console exists for.
    // "No open findings" on its own reads as a clean bill of health, so the screen has to say
    // which nothing it is -- and the test asserts *both* sides, which is what its name promises.
    // The sentences now come from `TriageEmpty` in the table pane rather than from `TriageTabs`.
    mockState.page = page([], { indexed_at: null, severity_total: 0, severity_counts: {} })
    const before = renderFindings().container.textContent ?? ""
    expect(before).toMatch(/nothing has checked/i)
    expect(before).not.toMatch(/no open findings under/i)

    cleanup()

    mockState.page = page([], {
      indexed_at: "2026-08-18T00:00:00Z",
      severity_total: 0,
      severity_counts: {},
    })
    const after = renderFindings().container.textContent ?? ""
    expect(after).toMatch(/no open findings under/i)
    expect(after).not.toMatch(/nothing has checked/i)
  })

  // Superseded 2026-08-24 by the owner's Stitch specification, which puts a prominent page title
  // and a one-line subtitle at the top of every screen's content. The old ruling -- the trail
  // names the page, so a page does not have to -- was coherent and was not wrong for the console
  // it described; what retired it is that the trail rendered the `h1` at 13px, smaller than the
  // 18px `h2` of every section inside it.
  //
  // There is still exactly one top-level heading. It moved into `ScreenFrame` with the subtitle;
  // it did not multiply.
  it("names itself once, at the page step", () => {
    mockState.page = page([row()])
    renderFindings()

    const headings = screen.getAllByRole("heading", { level: 1 })
    expect(headings).toHaveLength(1)
    expect(headings[0].className).toContain("text-page")
  })
})

describe("which question the screen opens on (M15 Task 7)", () => {
  it("leads with the change rather than the flat list", async () => {
    // The plan's whole point: 24 findings are 13 change units, and a flat default shows a reader
    // 24 problems where there are 13. If this regresses, the grouping still exists and nobody
    // sees it -- which is indistinguishable from not having built it.
    mockState.page = page([row()])
    renderFindings("/repositories/org%2Fone/findings")

    expect(
      (await screen.findByRole("button", { name: /By change/ })).getAttribute("aria-pressed"),
    ).toBe("true")
  })

  it("keeps the flat list reachable, because 'where exactly' is a real question too", async () => {
    mockState.page = page([row()])
    renderFindings("/repositories/org%2Fone/findings?findings_view=flat")

    expect(
      (await screen.findByRole("button", { name: /Every finding/ })).getAttribute("aria-pressed"),
    ).toBe("true")
  })
})

describe("the inspector drawer", () => {
  it("stays shut with nothing selected rather than opening on an empty pane", () => {
    mockState.page = page([row()])
    renderFindings()

    // A drawer over a table a reader is scanning is a modal cost, and paying it to say "nothing
    // selected" is the failure mode the owner's ruling replaces.
    expect(screen.queryByRole("dialog")).toBeNull()
  })

  it("opens on the row an operator pressed", () => {
    mockState.page = page([row()])
    renderFindings()

    fireEvent.click(screen.getByRole("button", { name: "Inspect" }))

    expect(screen.getByRole("dialog")).toBeTruthy()
  })

  it("says a key this window does not hold is not a row that is gone, and keeps the key", () => {
    // Clearing the parameter would tell a reader their link was wrong, which is one of three
    // possibilities and the only one this page can rule out.
    mockState.page = page([row()])
    renderFindings("/repositories/org%2Fone/findings?findings_view=flat&inspect=not-on-this-page")

    expect(screen.getByText("not-on-this-page")).toBeTruthy()
    expect(screen.getByText(/behind a severity chip/)).toBeTruthy()
    expect(window.location.search).not.toContain("inspect=")
  })
})

describe("what the status band carries", () => {
  it("states the dismissal standing and its fleet scope beside a workspace table", () => {
    // The table lists open findings only. Without this a finding somebody deliberately set aside
    // reads as one nobody has looked at -- and the figure is every repository's, which is exactly
    // the attribution a workspace-scoped screen has to spell out rather than imply.
    mockState.page = page([row()])
    const { container } = renderFindings()
    const text = container.textContent ?? ""

    expect(text).toMatch(/7 findings stand dismissed/)
    expect(text).toMatch(/across every repository this deployment holds/)
  })
})
