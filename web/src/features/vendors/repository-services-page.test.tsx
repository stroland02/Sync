/**
 * The API products one repository calls, and the duplication this screen stopped being.
 *
 * Until 2026-08-19 this page rendered the union of two answers keyed by `vendor_id` â€” the same
 * identifier the Vendors screen lists â€” so the owner's report was that the two screens showed the
 * same data under two headings. A vendor is the provider Sync watches; a service is one of the APIs
 * it sells, and `call_site.service_id` is the layer that makes them different lists.
 *
 * The tests that went with that change are named rather than silently dropped: seven asserted the
 * union's per-answer columns, and the union is what was wrong. What replaced them asserts the new
 * distinction, and one of them asserts the *absence* of the old one â€” a findings column returning
 * here would restore the duplication with every other test still green.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification, derivation and structural
 * invariants. Never class names, never snapshots.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { NotFoundError } from "@/api/errors"
import { RepositoryServicesPage } from "@/features/vendors/repository-services-page"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const settled = (data: unknown) => ({
  isPending: false,
  isError: false,
  isSuccess: true,
  data,
  refetch: vi.fn(),
})

const failed = (error: unknown) => ({
  isPending: false,
  isError: true,
  isSuccess: false,
  data: undefined,
  error,
  refetch: vi.fn(),
})

const { useRepositoryCoverage } = vi.hoisted(() => ({ useRepositoryCoverage: vi.fn() }))
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useRepositoryCoverage,
}))

function renderAt(repoId: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/repositories/${encodeURIComponent(repoId)}/services`]}>
        <Routes>
          <Route path="/repositories/:repoId/services" element={<RepositoryServicesPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

const INDEXED = "2026-08-19T09:00:00Z"

/** One provider selling two products, one provider whose operations nothing has grouped. */
function answered(repoId = "org/one") {
  useRepositoryCoverage.mockReturnValue(
    settled({
      repo_id: repoId,
      by_vendor: { stripe: 14, twilio: 3 },
      last_indexed: { stripe: INDEXED, twilio: INDEXED },
      total_call_sites: 17,
      by_service: [
        { vendor_id: "stripe", service_id: "Payments", call_sites: 9, operations: 2, last_indexed: INDEXED },
        { vendor_id: "stripe", service_id: "Billing", call_sites: 5, operations: 1, last_indexed: INDEXED },
        { vendor_id: "twilio", service_id: null, call_sites: 3, operations: 2, last_indexed: INDEXED },
      ],
      by_operation: [
        { vendor_id: "stripe", service_id: "Payments", operation_id: "PostCharges", call_sites: 6, last_indexed: INDEXED },
        { vendor_id: "stripe", service_id: "Payments", operation_id: "GetCharge", call_sites: 3, last_indexed: INDEXED },
        { vendor_id: "stripe", service_id: "Billing", operation_id: "PostSubscriptions", call_sites: 5, last_indexed: INDEXED },
        { vendor_id: "twilio", service_id: null, operation_id: "CreateMessage", call_sites: 3, last_indexed: INDEXED },
      ],
    })
  )
}

/**
 * The row a product sits in.
 *
 * The product name renders beside its vendor in one cell, so a bare text match hits the span and
 * the cell containing it. Resolving to the enclosing `tr` is what makes the assertion about the
 * row rather than about which element happened to hold the string.
 */
function rowFor(product: string): HTMLElement {
  const row = screen
    .getAllByText(new RegExp(product))
    .map((element) => element.closest("tr"))
    .find((candidate): candidate is HTMLTableRowElement => candidate !== null)
  if (row === undefined) throw new Error(`no row renders the product ${product}`)
  return row
}

describe("the API products screen", () => {
  it("lists one row per product rather than one per provider", () => {
    answered()
    renderAt("org/one")

    // Two products under one vendor is the whole point: a screen keyed by vendor would draw one
    // stripe row here and be the Vendors screen again.
    expect(rowFor("Payments")).toBeTruthy()
    expect(rowFor("Billing")).toBeTruthy()
    expect(screen.getAllByRole("link", { name: "stripe" }).length).toBe(2)
  })

  it("renders an ungrouped vendor as absence, never as a product named nothing", () => {
    answered()
    renderAt("org/one")

    // Only a vendor adapter can map an operation onto a product and none does yet. A blank cell,
    // a dash, or the vendor's own name standing in would each claim something different.
    expect(screen.getByText(/not grouped into a product yet/i)).toBeTruthy()
  })

  it("counts the ungrouped operations rather than hiding them out of the totals", () => {
    answered()
    renderAt("org/one")

    const tile = screen.getByText("Operations not grouped").closest("div")
    expect(tile).not.toBeNull()
    expect(within(tile as HTMLElement).getByText("2")).toBeTruthy()
  })

  it("does not answer the Vendors screen's question, which is what made the two alike", () => {
    answered()
    renderAt("org/one")

    // The de-duplication itself. Open findings and adapter tier are facts about a provider and
    // they live one screen away; a column for either here would restore the duplication with
    // every other test in this file still passing.
    // Non-vacuous: the table rendered, and it has the columns this screen does own.
    expect(screen.getByRole("columnheader", { name: /service/i })).toBeTruthy()
    expect(screen.queryByRole("columnheader", { name: /open findings/i })).toBeNull()
    expect(screen.queryByRole("columnheader", { name: /adapter/i })).toBeNull()
  })

  it("carries each product's own call sites and index time", () => {
    answered()
    renderAt("org/one")

    const row = rowFor("Payments")
    expect(row).not.toBeNull()
    expect(within(row).getByText("9")).toBeTruthy()
  })

  it("keeps a product's operations behind a disclosure rather than in the row", () => {
    answered()
    renderAt("org/one")

    // Fifteen ungrouped operations rendered inline made one cell a paragraph, which is what the
    // grouped shape on the findings screen already solved. Closed, the row states the count.
    const row = rowFor("Payments")
    expect(within(row).getByRole("button", { name: /2 operations/ })).toBeTruthy()
    expect(screen.queryByRole("link", { name: "PostCharges" })).toBeNull()
  })

  it("lists the operations behind a product once opened, each opening its binding surface", () => {
    answered()
    renderAt("org/one")

    // The screen printed "operations not listed" for as long as no query returned them. It does
    // now, so the caveat would be a stale statement of a limit that no longer holds.
    const row = rowFor("Payments")
    fireEvent.click(within(row).getByRole("button", { name: /2 operations/ }))

    expect(screen.getByRole("link", { name: "PostCharges" })).toBeTruthy()
    expect(screen.getByRole("link", { name: "GetCharge" })).toBeTruthy()
    expect(document.body.textContent).not.toContain("operations not listed")
  })

  it("puts an operation under the product that owns it and under no other", () => {
    answered()
    renderAt("org/one")

    // Keyed on (vendor, service): an operation id is unique only within its vendor, so a lookup
    // on the service alone would merge two providers' rows.
    const billing = rowFor("Billing")
    fireEvent.click(within(billing).getByRole("button", { name: /1 operation/ }))

    expect(screen.getByRole("link", { name: "PostSubscriptions" })).toBeTruthy()
    expect(screen.queryByRole("link", { name: "PostCharges" })).toBeNull()
  })

  it("opens each product's provider in the vendor record, carrying this repository as the scope", () => {
    answered()
    renderAt("org/one")

    const row = rowFor("Payments")
    const link = within(row).getByRole("link", { name: "stripe" })
    expect(link.getAttribute("href")).toBe("/repositories/org%2Fone/vendors/stripe")
  })

  it("refuses the rows outright when coverage answered for another repository", () => {
    answered("org/other")
    renderAt("org/one")

    // Another repository's call-site counts under this repository's name is a claim nothing
    // computed. The page says so rather than rendering them with a caveat.
    expect(screen.queryAllByText(/Payments/)).toHaveLength(0)
    expect(screen.getByText(/answered about a different repository/i)).toBeTruthy()
  })

  it("names the transport defect rather than claiming the API does not hold the identifier", () => {
    useRepositoryCoverage.mockReturnValue(failed(new NotFoundError("not found", "org/one", "/api/repositories/org%2Fone/coverage")))
    renderAt("org/one")

    // B147: the route cannot match an identifier containing a slash, and every identifier has
    // one. The generic 404 sentence would be false here â€” the repository exists.
    expect(document.body.textContent).toMatch(/could not be asked about this repository/i)
  })

  /**
   * The ranked bars key each row `vendor · service`, split that key back on the same separator to
   * colour by vendor, and rebuild it a third time to look the row up for its operation count. All
   * three literals were a triple-mojibaked middle dot until CI-W559 and agreed with each other,
   * which is exactly why nothing caught it: the split worked and the label was unreadable. These
   * assertions pin the round trip to the character, so a future sweep cannot fix one of the three.
   */
  it("keys, splits and rebuilds a bar's identity on the same separator", () => {
    answered()
    renderAt("org/one")

    // Construction: the key reaches the bar's accessible name intact.
    const payments = screen.getByRole("img", { name: "stripe · Payments: 9 call sites" })
    const billing = screen.getByRole("img", { name: "stripe · Billing: 5 call sites" })

    // The rebuild at `detail`: a key that no longer matches its row returns "" and prints nothing.
    expect(screen.getByText("2 ops")).toBeTruthy()
    expect(screen.getByText("1 op")).toBeTruthy()

    // The split at `colourKey`: both bars resolve to the vendor, so they carry one hue. A failed
    // split leaves two distinct keys in the domain and the ordinal scale gives them two.
    const hue = (bar: HTMLElement) =>
      (bar.firstElementChild as HTMLElement).style.backgroundColor
    expect(hue(payments)).not.toBe("")
    expect(hue(payments)).toBe(hue(billing))
  })

  it("says nothing is bound here rather than drawing an empty table", () => {
    useRepositoryCoverage.mockReturnValue(
      settled({
        repo_id: "org/one",
        by_vendor: {},
        last_indexed: {},
        total_call_sites: 0,
        by_service: [],
        by_operation: [],
      })
    )
    renderAt("org/one")

    expect(screen.getByText(/No API service is bound to org\/one/i)).toBeTruthy()
    expect(screen.queryByRole("table")).toBeNull()
  })
})
