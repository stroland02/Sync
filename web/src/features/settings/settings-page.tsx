/**
 * Settings: what this deployment watches, and what it lets you configure.
 *
 * Organized into four primary setting groups matching the system's operational architecture:
 * 1. Codebases — Repository scope, project context (.sync/context.md), and static analysis configuration.
 * 2. Pull requests — Automated merge policies (with refusal notice for immediate/always), merge methods, base branches.
 * 3. Adapters — Inventory of registered signal feeds and vendor adapters.
 * 4. GitHub Connection — Local gh CLI authentication status, monitored repository permissions, and local-only forge notes.
 */

import { useState } from "react"
import { useSearchParams } from "react-router"

import { useRepositories } from "@/api/queries"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { PageHeader } from "@/layouts/page-header"
import { PullRequestsSettingsPanel } from "@/features/settings/pull-requests-settings-panel"
import { CodebasesSettingsPanel } from "@/features/settings/codebases-settings-panel"
import { GithubConnectionSettingsPanel } from "@/features/settings/github-connection-settings-panel"
import { AdaptersSettingsPanel } from "@/features/settings/adapters-settings-panel"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/vendor/supabase/ui/select"

export type SettingsGroup = "pull-requests" | "codebases" | "adapters" | "github-connection"

interface GroupDef {
  id: SettingsGroup
  label: string
  description: string
}

const SETTING_GROUPS: readonly GroupDef[] = [
  {
    id: "pull-requests",
    label: "Pull requests",
    description: "Merge policy, merge methods, and base branch automation",
  },
  {
    id: "codebases",
    label: "Codebases",
    description: "Repository context (.sync/context.md) and analysis rules",
  },
  {
    id: "adapters",
    label: "Adapters",
    description: "Registered signal feeds, adapter inventory, and intake metrics",
  },
  {
    id: "github-connection",
    label: "GitHub Connection",
    description: "Forge authentication, local CLI status, and permissions",
  },
] as const

const DEFAULT_QUESTION =
  "What does this deployment watch, what policy is in force when a patch is ready, and how is the forge connected?"

export interface SettingsPageProps {
  readonly question?: string
}

export function SettingsPage({ question = DEFAULT_QUESTION }: SettingsPageProps) {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialGroup = (searchParams.get("group") as SettingsGroup) || "pull-requests"
  const [selectedGroup, setSelectedGroup] = useState<SettingsGroup>(
    SETTING_GROUPS.some((g) => g.id === initialGroup) ? initialGroup : "pull-requests"
  )

  const reposQuery = useRepositories()
  const repos = reposQuery.data?.repositories ?? []
  const [selectedRepoId, setSelectedRepoId] = useState<string>(
    repos[0]?.repo_id ?? "stroland02/Sync"
  )

  // Keep selectedRepoId in sync with loaded repositories if unset
  if (repos.length > 0 && selectedRepoId === "stroland02/Sync" && !repos.some((r) => r.repo_id === selectedRepoId)) {
    setSelectedRepoId(repos[0].repo_id)
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
      <PageHeader
        title="Settings"
        question={question}
        trail={<Breadcrumbs trail={[{ label: "Settings" }]} />}
      />

      <div className="flex flex-col md:flex-row gap-section items-start">
        {/* Left Sub-Navigation */}
        <aside className="w-full md:w-64 shrink-0 flex flex-col gap-field">
          {/* Target Codebase Selector */}
          <div className="flex flex-col gap-1 p-3 rounded-surface border border-line bg-surface">
            <span className="text-meta font-medium text-ink">Target Codebase</span>
            <Select value={activeRepo} onValueChange={setSelectedRepoId}>
              <SelectTrigger className="w-full text-meta font-mono bg-surface border-line">
                <SelectValue placeholder="Select repository" />
              </SelectTrigger>
              <SelectContent>
                {repos.length === 0 ? (
                  <SelectItem value={activeRepo}>{activeRepo}</SelectItem>
                ) : (
                  repos.map((r) => (
                    <SelectItem key={r.repo_id} value={r.repo_id} className="font-mono text-meta">
                      {r.repo_id}
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>

          {/* Group Nav Items */}
          <nav className="flex flex-col gap-1 rounded-surface border border-line bg-surface p-1">
            {SETTING_GROUPS.map((group) => {
              const isSelected = selectedGroup === group.id
              return (
                <button
                  key={group.id}
                  type="button"
                  onClick={() => handleSelectGroup(group.id)}
                  className={`flex flex-col items-start px-3 py-2 rounded-surface text-left transition-colors ${
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
        </main>
      </div>
    </div>
  )
}
