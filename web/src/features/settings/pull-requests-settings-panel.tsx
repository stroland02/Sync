import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"

import { SettingCard } from "@/features/settings/setting-card"
import { fetchRepoSettings, updateRepoSettings, type RepoSettingsPayload } from "@/features/settings/api"
import { useRepositories } from "@/api/queries"
import { Badge } from "@/vendor/supabase/ui/badge"
import { Button } from "@/vendor/supabase/ui/button"
import { Input } from "@/vendor/supabase/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/vendor/supabase/ui/select"
import { LoadingState, ErrorState } from "@/components/states"
import { Formatted } from "@/components/status"

export interface PullRequestsSettingsPanelProps {
  repoId: string
}

export function PullRequestsSettingsPanel({ repoId }: PullRequestsSettingsPanelProps) {
  const queryClient = useQueryClient()
  const settingsQuery = useQuery({
    queryKey: ["repo-settings", repoId],
    queryFn: ({ signal }) => fetchRepoSettings(repoId, signal),
  })

  const reposQuery = useRepositories()
  const repos = reposQuery.data?.repo_ids ?? []

  const [mergePolicy, setMergePolicy] = useState<"never" | "when_checks_pass">("never")
  const [mergeMethod, setMergeMethod] = useState<"squash" | "merge" | "rebase">("squash")
  const [baseBranch, setBaseBranch] = useState<string>("main")
  const [syncedData, setSyncedData] = useState<RepoSettingsPayload | null>(null)

  // Sync state when data loads
  if (settingsQuery.data && settingsQuery.data !== syncedData) {
    setSyncedData(settingsQuery.data)
    setMergePolicy(settingsQuery.data.merge_policy)
    setMergeMethod(settingsQuery.data.merge_method)
    setBaseBranch(settingsQuery.data.base_branch)
  }

  const mutation = useMutation({
    mutationFn: (params: Parameters<typeof updateRepoSettings>[1]) =>
      updateRepoSettings(repoId, params),
    onSuccess: (data) => {
      setSyncedData(data)
      queryClient.setQueryData(["repo-settings", repoId], data)
    },
  })

  if (settingsQuery.isPending) {
    return <LoadingState what={`settings for ${repoId}`} />
  }

  if (settingsQuery.isError) {
    return (
      <ErrorState
        error={settingsQuery.error}
        what={`settings for ${repoId}`}
        onRetry={() => void settingsQuery.refetch()}
      />
    )
  }

  const hasPolicyChanged = mergePolicy !== syncedData?.merge_policy
  const hasMethodChanged = mergeMethod !== syncedData?.merge_method
  const hasBranchChanged = baseBranch !== syncedData?.base_branch

  return (
    <div className="flex flex-col gap-section">
      <div className="flex flex-col gap-field pb-field border-b border-line">
        <h2 className="text-emphasis font-medium text-ink">Pull Request Automation Settings</h2>
        <p className="text-body text-ink-muted">
          Configure how Sync opens, tests, and merges pull requests for repository{" "}
          <span className="font-mono text-ink font-medium">{repoId}</span>.
        </p>
      </div>

      {/* Setting 1: Merge Policy — styled matching 10-settings mock */}
      <SettingCard
        title="Merge Policy"
        description={
          <>
            <p>
              Controls when Sync is permitted to automatically merge verified remediation pull
              requests after verification.
            </p>
            <p className="text-meta text-ink-muted">
              Select <code className="font-mono text-ink">when_checks_pass</code> to allow merging
              once customer CI gates turn green, or{" "}
              <code className="font-mono text-ink">never</code> to require manual human review.
            </p>
          </>
        }
        refusalNotice={
<<<<<<< HEAD
          <div className="rounded-surface border border-line bg-surface-muted/40 p-3 text-meta text-ink-muted space-y-field">
=======
          <div className="rounded-surface border border-line bg-surface-muted/40 p-row text-meta text-ink-muted space-y-field">
>>>>>>> origin/main
            <div className="flex items-center gap-row">
              <Badge>Refused Option: Immediate</Badge>
            </div>
            <p>
              Sync strictly refuses <code className="font-mono text-ink">immediate</code> /{" "}
              <code className="font-mono text-ink">always</code> merge policies. Unverified patches
              will never merge automatically because doing so directly violates the invariant{" "}
              <em>&ldquo;nothing reaches a pull request unverified&rdquo;</em>.
            </p>
          </div>
        }
        control={
          <div className="flex flex-col gap-row w-full max-w-md">
            {/* Option 1: when_checks_pass */}
            <button
              type="button"
              onClick={() => setMergePolicy("when_checks_pass")}
<<<<<<< HEAD
              className={`flex items-start gap-3 p-3 rounded-surface border text-left transition-colors ${
=======
              className={`flex items-start gap-row p-row rounded-surface border text-left transition-colors ${
>>>>>>> origin/main
                mergePolicy === "when_checks_pass"
                  ? "border-foreground/30 bg-surface-muted/80 shadow-sm"
                  : "border-border hover:bg-surface-muted/40"
              }`}
            >
              <div className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-primary">
                {mergePolicy === "when_checks_pass" && (
                  <div className="h-2 w-2 rounded-full bg-primary" />
                )}
              </div>
              <div className="flex flex-col">
                <span className="text-body font-medium text-ink">Merge when CI is green</span>
                <span className="text-meta text-ink-muted">
                  Approval is a standing instruction: the merge happens automatically once customer
                  CI checks pass.
                </span>
              </div>
            </button>

            {/* Option 2: never */}
            <button
              type="button"
              onClick={() => setMergePolicy("never")}
<<<<<<< HEAD
              className={`flex items-start gap-3 p-3 rounded-surface border text-left transition-colors ${
=======
              className={`flex items-start gap-row p-row rounded-surface border text-left transition-colors ${
>>>>>>> origin/main
                mergePolicy === "never"
                  ? "border-foreground/30 bg-surface-muted/80 shadow-sm"
                  : "border-border hover:bg-surface-muted/40"
              }`}
            >
              <div className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-primary">
                {mergePolicy === "never" && (
                  <div className="h-2 w-2 rounded-full bg-primary" />
                )}
              </div>
              <div className="flex flex-col">
                <span className="text-body font-medium text-ink">Open the pull request only</span>
                <span className="text-meta text-ink-muted">
                  Sync stops at the door. Pull requests are opened for manual human review and merge
                  on the forge.
                </span>
              </div>
            </button>
          </div>
        }
        footer={
          <>
            <span>Current policy: <strong className="text-ink font-mono">{syncedData?.merge_policy}</strong></span>
            <div className="flex items-center gap-row">
              {hasPolicyChanged && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setMergePolicy(syncedData?.merge_policy ?? "never")}
                >
                  Reset
                </Button>
              )}
              <Button
                size="sm"
                disabled={!hasPolicyChanged || mutation.isPending}
                onClick={() => mutation.mutate({ merge_policy: mergePolicy })}
              >
                {mutation.isPending ? "Saving..." : "Save Policy"}
              </Button>
            </div>
          </>
        }
      />

      {/* Setting 2: Merge Method */}
      <SettingCard
        title="Merge Method"
        description={
          <p>
            The git merge strategy used when merging approved pull requests into the base branch.
            Squash is recommended to maintain clean, bisectable commit history.
          </p>
        }
        control={
          <Select
            value={mergeMethod}
            onValueChange={(val) => setMergeMethod(val as "squash" | "merge" | "rebase")}
          >
            <SelectTrigger className="w-64 bg-surface border-line">
              <SelectValue placeholder="Select merge method" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="squash">Squash and merge (recommended)</SelectItem>
              <SelectItem value="merge">Merge commit</SelectItem>
              <SelectItem value="rebase">Rebase and merge</SelectItem>
            </SelectContent>
          </Select>
        }
        footer={
          <>
            <span>Current method: <strong className="text-ink font-mono">{syncedData?.merge_method}</strong></span>
            <div className="flex items-center gap-row">
              {hasMethodChanged && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setMergeMethod(syncedData?.merge_method ?? "squash")}
                >
                  Reset
                </Button>
              )}
              <Button
                size="sm"
                disabled={!hasMethodChanged || mutation.isPending}
                onClick={() => mutation.mutate({ merge_method: mergeMethod })}
              >
                {mutation.isPending ? "Saving..." : "Save Method"}
              </Button>
            </div>
          </>
        }
      />

      {/* Setting 3: Base Branch Override */}
      <SettingCard
        title="Base Branch"
        description={
          <p>
            The default repository branch Sync targets when proposing remediation pull requests.
            Defaults to <code className="font-mono text-ink">main</code>.
          </p>
        }
        control={
          <Input
            value={baseBranch}
            onChange={(e) => setBaseBranch(e.target.value)}
            className="w-64 font-mono bg-surface border-line"
            placeholder="main"
          />
        }
        footer={
          <>
            <span>Target branch: <strong className="text-ink font-mono">{syncedData?.base_branch}</strong></span>
            <div className="flex items-center gap-row">
              {hasBranchChanged && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setBaseBranch(syncedData?.base_branch ?? "main")}
                >
                  Reset
                </Button>
              )}
              <Button
                size="sm"
                disabled={!hasBranchChanged || !baseBranch.trim() || mutation.isPending}
                onClick={() => mutation.mutate({ base_branch: baseBranch.trim() })}
              >
                {mutation.isPending ? "Saving..." : "Save Branch"}
              </Button>
            </div>
          </>
        }
      />

      {/* Repository Overrides Card — from console-mock 10-settings */}
      {repos.length > 0 && (
<<<<<<< HEAD
        <div className="rounded-surface border border-line bg-surface p-section flex flex-col gap-3">
=======
        <div className="rounded-surface border border-line bg-surface p-section flex flex-col gap-row">
>>>>>>> origin/main
          <div className="flex flex-col gap-field">
            <h3 className="text-meta font-semibold uppercase tracking-wider text-ink-muted">
              Repository Overrides
            </h3>
            <p className="text-meta text-ink-muted">
              The policy in force for the repository selected above. Every other repository is
              shown without one because this screen has not read its settings, which is different
              from having read them and found no override.
            </p>
          </div>
          <div className="flex flex-col divide-y divide-border">
            {repos.map((otherRepoId) => (
              <div
                key={otherRepoId}
                className="flex items-center justify-between py-row text-meta first:pt-0"
              >
                <span className="font-mono text-ink">{otherRepoId}</span>
                <span className="text-ink-muted">
                  {otherRepoId === repoId ? (
                    mergePolicy === "when_checks_pass" ? (
                      "merge when green"
                    ) : (
                      "open only"
                    )
                  ) : (
                    <Formatted value={null} />
                  )}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
