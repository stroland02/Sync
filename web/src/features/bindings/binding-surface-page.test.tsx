/**
 * What the rebuilt binding surface must keep being, stated as invariants rather than as pixels.
 *
 * Five claims, none covered elsewhere, and every one of them is a thing the 2026-08-26 rebuild
 * could have quietly lost while looking better.
 *
 * **The screen is bounded.** The defect the owner reported was 1397px of page in a 720px viewport.
 * `layout="locked"` is what stamps `data-screen="locked"`, which is the single attribute the
 * chassis reads to hand its scrollbar to the screen — a rebuild that reverts to `flow` reads as a
 * cosmetic change and is the whole regression.
 *
 * **Each nothing still says which nothing it is.** Four of them, and each is a different fact: the
 * index holds none, the filter excluded them, the window is past the end, the vendor never changed
 * the operation. This is the rule `web/CLAUDE.md` says is lost most easily in a tidy-up, and a
 * rebuild that cuts prose is exactly a tidy-up.
 *
 * **No column was dropped, only relocated.** Nine became five; the four that left are rendered for
 * the selected row. A test that only counted headers would pass while the four vanished.
 *
 * **The right pane does not collapse.** It is mounted with nothing selected, because a pane that
 * appears and disappears reflows the table under the reader's cursor.
 *
 * **The repository facet is a destination.** It used to write a `repo_id` search parameter nothing
 * read, so pressing it moved the URL and no rows. Anything that is not a link here is that bug
 * again.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, waitFor, within } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { BindingSurfacePage } from "@/features/bindings/binding-surface-page"

const ROUTE = "/repositories/:repoId/bindings/vendors/:vendorId/operations/:operationId"
const ADDRESS = "/repositories/synthetic%2Fevery-state/bindings/vendors/stripe/operations/PostPaymentIntents"

function callSite(overrides: Record<string, unknown> = {}) {
  return {
    repo_id: "synthetic/every-state",
    path: "app/api/checkout/route.ts",
    line: 12,
    col: 2,
    symbol: "stripe.paymentIntents.create",
    sdk_version: "18.4.0",
    args_keys: ["amount", "currency"],
    response_fields_read: ["id", "client_secret"],
    loop_depth: 0,
    binding_rung: "static",
    indexed_at: "2026-08-26T11:19:43Z",
    snippet: "const intent = await stripe.paymentIntents.create({\n  amount,\n})",
    snippet_start_line: 10,
    ...overrides,
  }
}

function change() {
  return {
    change_id: "b46da60a",
    kind: "response-body-property-removed",
    severity: "breaking",
    from_version: "2026-06-30.basil",
    to_version: "2026-08-27.acacia",
    path_ptr: "/paths/~1v1~1payment_intents/post",
    detected_at: "2026-08-26T11:19:43Z",
  }
}

/** The live payload's own shape: 58 call sites across three repositories, one of them in scope. */
function payload({
  callSites = [callSite()],
  callSitesTotal = 1,
  changes = [change()],
  changesTotal = 1,
  commonDirectory = "app/api/checkout/",
  sourceServed = true,
}: {
  callSites?: unknown[]
  callSitesTotal?: number
  changes?: unknown[]
  changesTotal?: number
  commonDirectory?: string
  sourceServed?: boolean
} = {}) {
  return {
    vendor_id: "stripe",
    operation_id: "PostPaymentIntents",
    repo_id: "synthetic/every-state",
    path_prefix: null,
    call_sites: { items: callSites, total: callSitesTotal, next_offset: null },
    call_sites_common_directory: commonDirectory,
    changes: { items: changes, total: changesTotal, next_offset: null },
    repositories: [
      { repo_id: "github.com/stroland02/Sync", call_site_count: 56 },
      { repo_id: "synthetic/every-state", call_site_count: 1 },
      { repo_id: "synthetic/never-indexed", call_site_count: 1 },
    ],
    source_served: sourceServed,
  }
}

function stubFetch(body: unknown) {
  vi.stubGlobal("fetch", () =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response),
  )
}

function renderSurface(search = "") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`${ADDRESS}${search}`]}>
        <Routes>
          <Route path={ROUTE} element={<BindingSurfacePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  stubFetch(payload())
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("the screen is bounded rather than a scrolling column", () => {
  it("stamps the locked layout the chassis reads to take the page's scrollbar away", async () => {
    renderSurface()

    await screen.findByText("Call sites")
    // `data-screen` is the whole contract between a screen and the chassis: `app-frame.tsx` flips
    // `main` to `overflow-hidden` through `:has([data-screen=locked])` and nothing else.
    const band = document.querySelector('[data-band="content"]')
    expect(band?.getAttribute("data-screen")).toBe("locked")
  })

  it("draws no controls band, because both narrowings sit in the pane they narrow", async () => {
    renderSurface()

    await screen.findByText("Call sites")
    // A band rendered to hold nothing spends the locked column's height on chrome.
    expect(document.querySelector('[data-band="controls"]')).toBeNull()
  })
})

describe("each nothing says which nothing it is", () => {
  it("distinguishes an index that holds no binding at all", async () => {
    stubFetch(payload({ callSites: [], callSitesTotal: 0, commonDirectory: "" }))
    renderSurface()

    expect(
      await screen.findByText(/No call site in the index is bound to this operation\./),
    ).toBeTruthy()
    // Never indexed and nothing here are the same empty list on the wire.
    expect(screen.getByText(/the index cannot tell the two apart/)).toBeTruthy()
  })

  it("distinguishes a filter that excluded them from an index that holds none", async () => {
    stubFetch(payload({ callSites: [], callSitesTotal: 0, commonDirectory: "" }))
    renderSurface("?path_prefix=src/billing/")

    expect(await screen.findByText(/No call site matches this filter\./)).toBeTruthy()
    // The repositories are counted without the filter, which is what proves the operation is
    // called from somewhere.
    expect(screen.getByText(/58 call sites on this operation/)).toBeTruthy()
  })

  it("distinguishes a page past the end from a set that is empty", async () => {
    stubFetch(payload({ callSites: [], callSitesTotal: 120 }))
    renderSurface("?call_sites_offset=200")

    expect(await screen.findByText(/past the end of the 120 call sites/)).toBeTruthy()
  })

  it("distinguishes a vendor that never changed the operation from a read that failed", async () => {
    stubFetch(payload({ changes: [], changesTotal: 0 }))
    renderSurface()

    expect(
      await screen.findByText(/The vendor has never changed this operation\./),
    ).toBeTruthy()
    expect(screen.getByText(/that is an answer, not a failure/)).toBeTruthy()
  })
})

describe("nine columns became five and nothing was dropped", () => {
  it("draws the five, with the rung first", async () => {
    renderSurface()

    await screen.findByRole("button", { name: /Sort by Call site/ })
    const heads = [...document.querySelectorAll("th")]
      .map((th) => th.textContent?.replace(/\s+/g, " ").trim())
      // The vendor-changes table below shares the document; its head starts at `Detected`.
      .slice(0, 5)
    // The rung is the widest cell's neighbour and the layout does not protect a column further
    // right, which is why its position is an invariant rather than a preference.
    expect(heads[0]).toContain("Rung")
    expect(heads.filter((h) => h?.includes("Repository"))).toEqual([])
  })

  it("renders the four that left the table for the selected call site", async () => {
    renderSurface(
      "?binding=synthetic%2Fevery-state%3Aapp%2Fapi%2Fcheckout%2Froute.ts%3A12%3A2",
    )

    // The pane is whatever holds the banded header, which is what `PanelPane` composes: the
    // heading's `<header>` and the body are siblings inside it.
    const heading = await screen.findByText(/Selected call site/)
    const pane = heading.closest("header")?.parentElement
    expect(pane).toBeTruthy()
    await within(pane as HTMLElement).findByRole("figure")
    for (const label of [
      "Repository",
      "SDK version",
      "Argument keys",
      "Response fields read",
    ]) {
      expect(within(pane as HTMLElement).getByText(label)).toBeTruthy()
    }
    // The captured window, not a path the console would go and fetch.
    expect(within(pane as HTMLElement).getByRole("figure")).toBeTruthy()
  })
})

describe("the selected-call-site pane", () => {
  it("stays mounted with nothing selected, and names what it would hold", async () => {
    renderSurface()

    expect(await screen.findByText(/No call site is selected\./)).toBeTruthy()
    expect(screen.getByText("Selected call site")).toBeTruthy()
  })

  it("says the address names a call site this page does not hold", async () => {
    renderSurface("?binding=other%2Frepo%3Asrc%2Fa.ts%3A1%3A1")

    // Neither an empty pane (the call site is gone) nor no pane (the link was wrong): both are
    // claims this payload cannot support.
    expect(await screen.findByText(/none of them is that one/)).toBeTruthy()
  })
})

describe("the repository facet", () => {
  it("is a link per repository rather than a control writing a parameter nothing reads", async () => {
    renderSurface()

    const link = await screen.findByRole("link", { name: /github\.com\/stroland02\/Sync/ })
    expect(link.getAttribute("href")).toBe(
      "/repositories/github.com%2Fstroland02%2FSync/bindings/vendors/stripe/operations/PostPaymentIntents",
    )
  })

  it("marks the repository the route is scoped to without relying on colour", async () => {
    renderSurface()

    const current = await screen.findByRole("link", { name: /synthetic\/every-state/ })
    expect(current.getAttribute("aria-current")).toBe("page")
  })
})

describe("the figures arrive with their scope", () => {
  it("says the pane's counts are the workspace's and the chassis band says the window is not", async () => {
    renderSurface()

    await screen.findByRole("button", { name: /Sort by Call site/ })
    expect(screen.getByText(/Counted across every repository, before the narrowings below\./)).toBeTruthy()
    const status = document.querySelector('[data-band="status"]')?.textContent ?? ""
    expect(status).toContain("Call sites")
    expect(status).toContain("synthetic/every-state")
  })

  it("says which silence it is while the read is in flight rather than counting zero", async () => {
    vi.stubGlobal("fetch", () => new Promise<Response>(() => {}))
    renderSurface()

    await waitFor(() => {
      const status = document.querySelector('[data-band="status"]')?.textContent ?? ""
      expect(status).toContain("asking for the bindings on stripe/PostPaymentIntents")
    })
    expect(document.querySelector('[data-band="status"]')?.textContent).not.toContain("No call")
  })
})
