/**
 * Settings: what this deployment watches, and what it lets you configure.
 *
 * One group at a time, per owner decision 17, which also fixes the order:
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
import { SETTING_GROUPS, type SettingsGroup } from "@/features/settings/groups"
import { SetupPanel } from "@/features/settings/setup-panel"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/vendor/supabase/ui/select"



export interface SettingsPageProps {
  readonly question?: string
}

/**
 * The page's own band, deliberately the same array on every render.
 *
 * `ScreenFrame` republishes whenever this changes and a parent's effect commits after its
 * children's, so a group-aware version would land on top of the open panel's own count.
 */
const OPENING: StatusSegment[] = [
  { kind: "none", why: "the open settings group states what it holds" },
]

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

  const controls = (
    <>
      {/* Both controls narrow every group below them, so both belong in the frame's controls
          band rather than in the 16rem rail they were stacked in. */}
      <div className="flex min-w-0 items-center gap-field">
        <span className="shrink-0 text-meta text-ink-muted">Target codebase</span>
        <Select value={activeRepo} onValueChange={setSelectedRepoId}>
          <SelectTrigger
            aria-label="Target codebase"
            className="w-64 text-meta font-mono bg-surface border-line"
          >
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

      <div role="group" aria-label="Settings groups" className="flex flex-wrap items-center gap-field">
        {SETTING_GROUPS.map((group) => {
          const isSelected = selectedGroup === group.id
          return (
            <button
              key={group.id}
              type="button"
              aria-pressed={isSelected}
              title={group.description}
              onClick={() => handleSelectGroup(group.id)}
              className={`rounded-control border px-field py-field text-meta transition-colors ${
                isSelected
                  ? "border-line bg-surface-subtle text-ink"
                  : "border-transparent text-ink-muted hover:text-ink"
              }`}
            >
              {group.label}
            </button>
          )
        })}
      </div>
    </>
  )

  return (
    <ScreenFrame controls={controls} status={OPENING}>
      {/* Each panel publishes its own band: nine groups count nine different sets, and this page
          cannot re-derive what the open one already fetched. */}
      <section className="flex min-w-0 flex-col gap-section">
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
      </section>
    </ScreenFrame>
  )
}
