/**
 * Settings test suite for sub-navigation, card-scoped settings, refusal contracts, and about platform panel.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import * as queries from "@/api/queries"
import * as settingsApi from "@/features/settings/api"
import type { AdapterInventoryResponse, RepositoriesResponse } from "@/api/types"
import { SettingsPage } from "@/features/settings/settings-page"

afterEach(cleanup)

function renderSettings(initialEntry = "/settings") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
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
      },
    ],
  }
  const reposData: RepositoriesResponse = {
    repositories: [
      { repo_id: "stroland02/Sync", call_sites: 42, vendors: 3 },
    ],
  }

  vi.spyOn(queries, "useAdapters").mockReturnValue({
    data: adapterData,
    isPending: false,
    isError: false,
    isSuccess: true,
    error: null,
    refetch: vi.fn(),
  } as any)

  vi.spyOn(queries, "useRepositories").mockReturnValue({
    data: reposData,
    isPending: false,
    isError: false,
    isSuccess: true,
    error: null,
    refetch: vi.fn(),
  } as any)

  vi.spyOn(settingsApi, "fetchRepoSettings").mockResolvedValue({
    repo_id: "stroland02/Sync",
    merge_policy: "never",
    merge_method: "squash",
    base_branch: "main",
  })

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <SettingsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("SettingsPage sub-navigation and setting cards", () => {
  it("renders the left sub-navigation with all five setting groups", () => {
    renderSettings()
    expect(screen.getByRole("button", { name: /Pull requests/i })).toBeTruthy()
    expect(screen.getByRole("button", { name: /Codebases/i })).toBeTruthy()
    expect(screen.getByRole("button", { name: /Adapters/i })).toBeTruthy()
    expect(screen.getByRole("button", { name: /GitHub Connection/i })).toBeTruthy()
    expect(screen.getByRole("button", { name: /About Sync/i })).toBeTruthy()
  })

  it("renders Pull requests settings with merge policy, method, branch cards and refusal notice", async () => {
    renderSettings()
    expect(await screen.findByText("Merge Policy")).toBeTruthy()
    expect(screen.getByText("Merge Method")).toBeTruthy()
    expect(screen.getByText("Base Branch")).toBeTruthy()
    // Refusal notice must state why immediate is refused
    expect(screen.getByText(/Refused Option: Immediate/i)).toBeTruthy()
    expect(screen.getByText(/nothing reaches a pull request unverified/i)).toBeTruthy()
  })

  it("renders Codebases group with read-only .sync/context.md notice", async () => {
    renderSettings()
    const codebasesBtn = screen.getByRole("button", { name: /Codebases/i })
    fireEvent.click(codebasesBtn)

    expect(await screen.findByText("Project Context (.sync/context.md)")).toBeTruthy()
    expect(screen.getByText(/read-only in the console/i)).toBeTruthy()
    expect(screen.getByText(/Source of Truth: Customer Git Repository/i)).toBeTruthy()
  })

  it("renders GitHub Connection group with local gh CLI status and OAuth absence note", async () => {
    renderSettings()
    const githubBtn = screen.getByRole("button", { name: /GitHub Connection/i })
    fireEvent.click(githubBtn)

    expect(await screen.findByText("Forge Authentication (Local CLI)")).toBeTruthy()
    expect(screen.getByText(/Authenticated via gh CLI/i)).toBeTruthy()
    expect(screen.getByText(/Hosted GitHub App OAuth \(Absent by Design\)/i)).toBeTruthy()
    expect(screen.getByText(/Local-Only Architecture/i)).toBeTruthy()
  })

  it("renders Adapters group with the adapter inventory table", async () => {
    renderSettings()
    const adaptersBtn = screen.getByRole("button", { name: /Adapters/i })
    fireEvent.click(adaptersBtn)

    expect(await screen.findByText("Registered Adapters & Vendor Feeds")).toBeTruthy()
    expect(screen.getByText("stripe")).toBeTruthy()
  })

  it("renders About Sync group with platform documentation and explanations", async () => {
    renderSettings()
    const aboutBtn = screen.getByRole("button", { name: /About Sync/i })
    fireEvent.click(aboutBtn)

    expect(await screen.findByText("About Sync & Platform Concepts")).toBeTruthy()
    expect(screen.getByText("Provenance Rungs")).toBeTruthy()
    expect(screen.getByText("Adapter Tiers")).toBeTruthy()
    expect(screen.getByText("Abandoned Runs as Data")).toBeTruthy()
    expect(screen.getByText("Verification Gates")).toBeTruthy()
  })
})
