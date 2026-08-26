/**
 * Two claims about the rebuilt Integration changes screen, and both are ones a token swap cannot
 * satisfy.
 *
 * **It is locked.** `ScreenFrame layout="locked"` stamps `data-screen="locked"`, which is the whole
 * contract between a screen and the chassis — `app-frame.tsx` flips `main` to `overflow-hidden`
 * through `:has([data-screen=locked])` and nothing else. A screen that loses the stamp goes back to
 * one long scrolling column while looking identical in a diff.
 *
 * **The binding column says which nothing it is.** A repository nobody has indexed and one whose
 * census answered and holds no matching call site are different facts, and rendering the first as
 * the second is the refusal `web/CLAUDE.md` names first. The derivation has its own unit tests;
 * this is the seam — that the page hands the census the index history rather than assuming.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { IntegrationChangesPage } from "@/features/vendors/integration-changes-page"

const CHANGE = {
  id: "c-1",
  vendor_id: "stripe",
  from_version: "v1",
  to_version: "v2",
  kind: "response-property-removed",
  operation_id: "PostCharges",
  path_ptr: "/p",
  severity: "breaking",
  source: "oasdiff",
  detected_at: "2026-08-18T00:00:00Z",
}

function changesPage() {
  return {
    items: [CHANGE],
    total: 1,
    next_offset: null,
    by_vendor: { stripe: 1 },
    by_severity: { breaking: 1 },
    by_vendor_severity: { stripe: { breaking: 1 } },
    unfiltered_total: 1,
    vendor_ids: [],
    severities: [],
  }
}

function overview(indexed: boolean) {
  return {
    repo_id: "demo",
    vendors: [],
    total_findings: 0,
    total_findings_bound: 0,
    total_findings_bound_reached: false,
    severity_counts: {},
    bindings_by_rung: {},
    last_index_run: indexed
      ? { started_at: "2026-08-17T00:00:00Z", finished_at: "2026-08-17T01:00:00Z" }
      : null,
  }
}

function stub({
  indexed,
  sites,
}: {
  indexed: boolean
  sites: { vendor_id: string; operation_id: string }[]
}) {
  vi.stubGlobal("fetch", (input: string) => {
    const url = new URL(String(input), "http://localhost")
    const body = url.pathname.endsWith("/call-sites")
      ? { repo_id: "demo", items: sites, total: sites.length, next_offset: null }
      : url.pathname.startsWith("/api/overview")
        ? overview(indexed)
        : changesPage()
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
  })
}

function renderChanges() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/repositories/demo/integration-changes"]}>
        <Routes>
          <Route
            path="/repositories/:repoId/integration-changes"
            element={<IntegrationChangesPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("the changes screen is locked", () => {
  it("stamps the content band so the chassis stops scrolling the page", async () => {
    stub({ indexed: true, sites: [] })
    const { container } = renderChanges()
    await screen.findAllByText(/PostCharges/)

    const band = container.querySelector('[data-band="content"]')
    expect(band?.getAttribute("data-screen")).toBe("locked")
  })
})

describe("which nothing the binding column reports", () => {
  it("says never indexed when no pass has run, rather than nothing-here", async () => {
    stub({ indexed: false, sites: [] })
    renderChanges()

    expect(await screen.findAllByText(/never indexed/)).not.toHaveLength(0)
    expect(screen.queryByText(/nothing here calls it/)).toBeNull()
  })

  it("says nothing-here when a pass has run and the census holds no matching site", async () => {
    stub({ indexed: true, sites: [{ vendor_id: "openai", operation_id: "createChatCompletion" }] })
    renderChanges()

    expect(await screen.findAllByText(/nothing here calls it/)).not.toHaveLength(0)
    expect(screen.queryByText(/never indexed/)).toBeNull()
  })

  it("counts the call sites that do name the operation", async () => {
    stub({
      indexed: true,
      sites: [
        { vendor_id: "stripe", operation_id: "PostCharges" },
        { vendor_id: "stripe", operation_id: "PostCharges" },
      ],
    })
    renderChanges()

    expect(await screen.findAllByText("2 here")).not.toHaveLength(0)
  })
})
