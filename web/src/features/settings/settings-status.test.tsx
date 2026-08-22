/**
 * Settings on the frame: the two controls hoisted out of the rail, and a band published by
 * whichever panel is open.
 *
 * The band is the part worth pinning. `ScreenFrame` and a panel publish through one channel and
 * a parent's effect commits after its children's, so a panel that publishes once at mount was
 * overwritten by the page's fallback and never seen — which is exactly what About and Pages do.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import * as queries from "@/api/queries"
import * as settingsApi from "@/features/settings/api"
import type { AdapterInventoryResponse, RepositoriesResponse } from "@/api/types"
import { SettingsPage } from "@/features/settings/settings-page"
import { StatusTargetProvider, useStatusTarget } from "@/layouts/screen-frame"

afterEach(cleanup)

function Harness({ entry }: { entry: string }) {
  const { target, footerRef } = useStatusTarget()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <StatusTargetProvider target={target}>
          <SettingsPage />
          <div ref={footerRef} />
        </StatusTargetProvider>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

function renderSettings(entry = "/settings") {
  const adapterData: AdapterInventoryResponse = {
    adapters: [
      {
        vendor_id: "stripe",
        kind: "coded",
        source: null,
        changes: 4,
        operations: 12,
        last_change_at: "2026-08-16T10:04:00+00:00",
        sources: ["oasdiff"],
        last_attempt_at: null,
        last_attempt_outcome: null,
        last_attempt_reason: null,
        last_attempt_changes: null,
        attempts: {},
      },
    ],
  }
  const reposData: RepositoriesResponse = { repo_ids: ["stroland02/Sync"] }

  vi.spyOn(queries, "useAdapters").mockReturnValue({
    data: adapterData,
    isPending: false,
    isError: false,
    isSuccess: true,
    error: null,
    refetch: vi.fn(),
  } as never)

  vi.spyOn(queries, "useRepositories").mockReturnValue({
    data: reposData,
    isPending: false,
    isError: false,
    isSuccess: true,
    error: null,
    refetch: vi.fn(),
  } as never)

  vi.spyOn(settingsApi, "fetchRepoSettings").mockResolvedValue({
    repo_id: "stroland02/Sync",
    merge_policy: "never",
    merge_method: "squash",
    base_branch: "main",
    remote_url: null,
  })

  return render(<Harness entry={entry} />)
}

function band(name: string): HTMLElement | null {
  return document.querySelector(`[data-band="${name}"]`)
}

describe("Settings on ScreenFrame", () => {
  it("hoists the target codebase select and the group control into the controls band", () => {
    renderSettings()

    const controls = band("controls")
    expect(controls).toBeTruthy()
    expect(controls?.querySelector('[aria-label="Target codebase"]')).toBeTruthy()
    expect(controls?.contains(screen.getByRole("button", { name: /Adapters/i }))).toBe(true)
  })

  it("publishes the open group's own count rather than the page's fallback", async () => {
    renderSettings()

    expect(await screen.findByText("This is all 1 codebase.")).toBeTruthy()
    expect(band("status")?.textContent).toContain("Codebases")
  })

  it("names the narrowing rather than claiming the whole set under a filtered table", async () => {
    renderSettings()
    fireEvent.click(screen.getByRole("button", { name: /With active remediations/i }))

    const text = band("status")?.textContent ?? ""
    expect(text).not.toContain("This is all")
    expect(text.toLowerCase()).toContain("narrowed")
  })

  it("says a reference group holds no records rather than leaving the band blank", async () => {
    renderSettings()
    fireEvent.click(screen.getByRole("button", { name: /^About/i }))

    expect(await screen.findByText(/reference/i)).toBeTruthy()
    expect(band("status")?.textContent).not.toBe("")
  })

  it("says the same for the page guides, which also hold no records", async () => {
    renderSettings()
    fireEvent.click(screen.getByRole("button", { name: /^Pages/i }))

    expect(await screen.findByText(/reference/i)).toBeTruthy()
  })

  it("counts the adapters the inventory holds", async () => {
    renderSettings()
    fireEvent.click(screen.getByRole("button", { name: /^Adapters/i }))

    expect(await screen.findByText("This is all 1 adapter.")).toBeTruthy()
  })
})
