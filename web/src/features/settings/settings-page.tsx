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
import { AboutPlatformPanel } from "@/features/settings/about-platform-panel"
import { PagesGuidePanel } from "@/features/settings/pages-guide-panel"
import { SetupPanel } from "@/features/settings/setup-panel"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/vendor/supabase/ui/select"

export type SettingsGroup =
  | "setup"
  | "pull-requests"
  | "codebases"
  | "adapters"
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

  const activeRepo = selectedRepoId || "stroland02/Sync"

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
                  <SelectItem value={activeRepo}>{activeRepo}</SelectItem>
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
          {selectedGroup === "pull-requests" && (
            <PullRequestsSettingsPanel repoId={activeRepo} />
          )}
          {selectedGroup === "codebases" && (
            <CodebasesSettingsPanel repoId={activeRepo} />
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
