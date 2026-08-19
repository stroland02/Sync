/**
 * Settings: what this deployment watches, and what it lets you configure.
 *
 * A left sub-nav showing one group at a time, per owner decision 17, which also fixes the order:
 * 1. Codebases — Repository scope, project context (.sync/context.md), and static analysis configuration.
 * 2. Pull requests — Automated merge policies (with refusal notice for immediate/always), merge methods, base branches.
 * 3. Adapters — Inventory of registered signal feeds and vendor adapters.
 * 4. Connection — Local gh CLI authentication status, monitored repository permissions, and local-only forge notes.
 * 5. About — Foundational platform explanations (provenance rungs, adapter tiers, abandon reasons, verification gates).
 *
 * The selected group rides in the `group` query parameter so a chosen group survives a reload and
 * can be linked to.
 */

import { useState } from "react"
import { useSearchParams } from "react-router"

import { useRepositories } from "@/api/queries"
import { PullRequestsSettingsPanel } from "@/features/settings/pull-requests-settings-panel"
import { CodebasesSettingsPanel } from "@/features/settings/codebases-settings-panel"
import { GithubConnectionSettingsPanel } from "@/features/settings/github-connection-settings-panel"
import { AdaptersSettingsPanel } from "@/features/settings/adapters-settings-panel"
import { ModelSettingsPanel } from "@/features/settings/model-settings-panel"
import { activeWorkspace, rememberedWorkspace } from "@/layouts/active-workspace"
import { AboutPlatformPanel } from "@/features/settings/about-platform-panel"
import { IntegrationsCataloguePanel } from "@/features/settings/integrations-catalogue-panel"
import { PagesGuidePanel } from "@/features/settings/pages-guide-panel"
import { SetupPanel } from "@/features/settings/setup-panel"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/vendor/supabase/ui/select"

export type SettingsGroup =
  | "setup"
  | "model"
  | "pull-requests"
  | "codebases"
  | "adapters"
  | "integrations"
  | "github-connection"
  | "pages"
  | "about"

interface GroupDef {
  id: SettingsGroup
  label: string
  description: string
}

/**
 * Decision 17's five groups, in decision 17's order.
 *
 * The order is part of the decision rather than a rendering detail: Codebases leads because
 * what this deployment watches precedes what it does when it finds something.
 */
const SETTING_GROUPS: readonly GroupDef[] = [
  // Setup leads, amending decision 17's order on the owner's 2026-08-18 direction: the
  // checklist is what makes every group below it configurable, and a fresh install reads
  // this screen top-down.
  {
    id: "setup",
    label: "Setup",
    description: "The full loop's prerequisites, probed — and the git remote it addresses",
  },
  // Second, immediately after Setup: it is the one prerequisite the checklist cannot probe its
  // way past, because a deployment with no model connected writes no patch and the owner's
  // ruling is that Sync never inherits the installer's credential to hide that.
  {
    id: "model",
    label: "Model",
    description: "Which model writes the patches, and whose credential pays — yours, never ours",
  },
  {
    id: "codebases",
    label: "Codebases",
    description: "Repository context (.sync/context.md) and analysis rules",
  },
  {
    id: "pull-requests",
    label: "Pull requests",
    description: "Merge policy, merge methods, and base branch automation",
  },
  {
    id: "adapters",
    label: "Adapters",
    description: "Registered signal feeds, adapter inventory, and intake metrics",
  },
  {
    id: "github-connection",
    label: "Connection",
    description: "Forge authentication, local CLI status, and permissions",
  },
  {
    id: "pages",
    label: "Pages",
    description: "How each screen works — the long form behind every ⓘ",
  },
  {
    id: "about",
    label: "About",
    description: "Platform architecture, provenance rungs, adapter tiers, and gates",
  },
] as const


export interface SettingsPageProps {
  readonly question?: string
}

export function SettingsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialGroup = (searchParams.get("group") as SettingsGroup) || "codebases"
  const [selectedGroup, setSelectedGroup] = useState<SettingsGroup>(
    SETTING_GROUPS.some((g) => g.id === initialGroup) ? initialGroup : "codebases"
  )

  const reposQuery = useRepositories()
  const repos = reposQuery.data?.repo_ids ?? []
  const [selectedRepoId, setSelectedRepoId] = useState<string>(repos[0] ?? "stroland02/Sync")

  // Keep selectedRepoId in sync with loaded repositories if unset
  if (repos.length > 0 && selectedRepoId === "stroland02/Sync" && !repos.includes(selectedRepoId)) {
    setSelectedRepoId(repos[0])
  }

  function handleSelectGroup(group: SettingsGroup) {
    setSelectedGroup(group)
    const nextParams = new URLSearchParams(searchParams)
    nextParams.set("group", group)
    setSearchParams(nextParams, { replace: true })
  }

  // **Was `selectedRepoId || "stroland02/Sync"`.** That literal is not a repository this
  // deployment holds -- the real identity is `github.com/stroland02/Sync`, derived from the git
  // remote -- so Settings opened on a workspace that does not exist, every panel below it asked
  // the API about nothing, and the reader's own codebase was dropped. That is the owner's report
  // of 2026-08-19 in full: a hardcoded fallback, stale by one identity change.
  //
  // The chassis knows which workspace is attached and keeps it across unscoped screens
  // (`active-workspace.ts`), so this reads that rather than guessing, and falls back to the first
  // repository the graph actually holds.
  const activeRepo =
    selectedRepoId || activeWorkspace(undefined, rememberedWorkspace(), repos) || repos[0] || ""

  return (
    <div className="flex flex-col gap-section min-w-0">

      <div className="flex flex-col md:flex-row gap-section items-start">
        {/* Left Sub-Navigation */}
        <aside className="w-full md:w-64 shrink-0 flex flex-col gap-field">
          {/* Target Codebase Selector */}
          <div className="flex flex-col gap-field p-row rounded-surface border border-line bg-surface">
            <span className="text-meta font-medium text-ink">Target Codebase</span>
            <Select value={activeRepo} onValueChange={setSelectedRepoId}>
              <SelectTrigger className="w-full text-meta font-mono bg-surface border-line">
                <SelectValue placeholder="Select repository" />
              </SelectTrigger>
              <SelectContent>
                {repos.length === 0 ? (
                  // No invented value: an id nobody can select is a control that looks broken.
                  <SelectItem value="none" disabled>
                    No codebase indexed yet
                  </SelectItem>
                ) : (
                  repos.map((repoId) => (
                    <SelectItem key={repoId} value={repoId} className="font-mono text-meta">
                      {repoId}
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>

          {/* Group Nav Items */}
          <nav className="flex flex-col gap-field rounded-surface border border-line bg-surface p-field">
            {SETTING_GROUPS.map((group) => {
              const isSelected = selectedGroup === group.id
              return (
                <button
                  key={group.id}
                  type="button"
                  onClick={() => handleSelectGroup(group.id)}
                  className={`flex flex-col items-start px-row py-row rounded-surface text-left transition-colors ${
                    isSelected
                      ? "bg-surface-muted text-ink font-medium shadow-sm"
                      : "text-ink-muted hover:text-ink hover:bg-surface-muted/50"
                  }`}
                >
                  <span className="text-body font-medium">{group.label}</span>
                  <span className="text-meta text-ink-muted line-clamp-1">{group.description}</span>
                </button>
              )
            })}
          </nav>
        </aside>

        {/* Main Setting Panel */}
        <main className="flex-1 min-w-0 flex flex-col gap-section">
          {selectedGroup === "setup" && (
            <SetupPanel repoId={activeRepo} />
          )}
          {selectedGroup === "model" && <ModelSettingsPanel />}
          {selectedGroup === "pull-requests" && (
            <PullRequestsSettingsPanel repoId={activeRepo} />
          )}
          {selectedGroup === "codebases" && (
            <CodebasesSettingsPanel repoId={activeRepo} />
          )}
          {selectedGroup === "integrations" && (
            <IntegrationsCataloguePanel repoId={activeRepo} />
          )}
          {selectedGroup === "adapters" && (
            <AdaptersSettingsPanel />
          )}
          {selectedGroup === "github-connection" && (
            <GithubConnectionSettingsPanel repoId={activeRepo} />
          )}
          {selectedGroup === "pages" && (
            <PagesGuidePanel />
          )}
          {selectedGroup === "about" && (
            <AboutPlatformPanel />
          )}
        </main>
      </div>
    </div>
  )
}
