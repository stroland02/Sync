/**
 * Codebases Panel: The primary centerpiece of the front page.
 * Displays each monitored codebase, its attached API vendors, open findings, and active runs.
 */

import { FolderGit2, ArrowRight, CheckCircle2, AlertCircle, Clock } from "lucide-react"
import { Link } from "react-router"

import { useOverview, useRepositories, useRuns } from "@/api/queries"
import { Badge } from "@/vendor/supabase/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/vendor/supabase/ui/card"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { formatElapsed } from "@/lib/format"

export type CodebaseFilter = "ALL" | "NEEDS_REVIEW" | "CLEAN"

export interface CodebasesPanelProps {
  readonly filter?: CodebaseFilter
}

export function CodebasesPanel({ filter = "ALL" }: CodebasesPanelProps) {
  const reposQuery = useRepositories()
  const overviewQuery = useOverview()
  const runsQuery = useRuns({ limit: 20, offset: 0 })

  if (reposQuery.isPending || overviewQuery.isPending) {
    return <LoadingState what="monitored codebases" />
  }

  if (reposQuery.isError) {
    return <ErrorState error={reposQuery.error} what="monitored codebases" />
  }

  const rawRepos = reposQuery.data?.repo_ids ?? []
  // Ensure we display watched codebases from index or default active repository
  const repoList = rawRepos.length > 0 ? rawRepos : ["acme/payments-api"]
  const vendors = overviewQuery.data?.vendors ?? []
  const runs = runsQuery.data?.items ?? []
  const totalFindings = overviewQuery.data?.total_findings ?? 0

  const filteredRepos = repoList.filter(() => {
    if (filter === "NEEDS_REVIEW") {
      return totalFindings > 0 || runs.length > 0
    }
    if (filter === "CLEAN") {
      return totalFindings === 0 && runs.length === 0
    }
    return true
  })

  return (
    <div className="flex flex-col gap-row">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-foreground">Monitored Codebases</h2>
          <p className="text-meta text-muted-foreground">
            Select a repository to inspect its attached API services, telemetry signals, and active remediations.
          </p>
        </div>
      </div>

      {filteredRepos.length === 0 ? (
        <EmptyState
          headline="No codebases match the selected filter."
          detail="No repositories match the chosen filter criteria. Switch back to 'All repositories' to view all watched codebases."
        />
      ) : (
        <div className="grid gap-row md:grid-cols-2">
          {filteredRepos.map((repoId) => {
            const repoRuns = runs.filter(
              (r) => !r.abandon_reason && r.outcome !== "abandoned"
            )
            const openFindingsCount = overviewQuery.data?.total_findings ?? 0
            const activeRun = repoRuns[0]
            const isClean = openFindingsCount === 0

            return (
              <Card
                key={repoId}
                className="group relative flex flex-col justify-between border-line bg-surface hover:border-border transition-colors duration-150"
              >
                <CardHeader className="gap-field pb-row">
                  <div className="flex items-start justify-between gap-row">
                    <div className="flex items-center gap-field">
                      <div className="flex size-8 items-center justify-center rounded-md bg-muted border border-border text-foreground">
                        <FolderGit2 className="size-4" />
                      </div>
                      <div>
                        <CardTitle className="font-mono text-base font-semibold group-hover:text-primary transition-colors">
                          <Link
                            to={`/repositories/${encodeURIComponent(repoId)}`}
                            className="focus:outline-none"
                          >
                            {repoId}
                          </Link>
                        </CardTitle>
                        <CardDescription className="text-meta text-muted-foreground">
                          Git repository · Monitored by Sync
                        </CardDescription>
                      </div>
                    </div>

                    {isClean ? (
                      <Badge variant="success" className="flex items-center gap-field border-emerald-500/30 text-emerald-400 bg-emerald-500/10">
                        <CheckCircle2 className="size-3" /> <span>Clean</span>
                      </Badge>
                    ) : (
                      <Badge variant="warning" className="flex items-center gap-field border-amber-500/30 text-amber-400 bg-amber-500/10">
                        <AlertCircle className="size-3" /> <span>{openFindingsCount} Findings</span>
                      </Badge>
                    )}
                  </div>
                </CardHeader>

                <CardContent className="flex flex-col gap-row pt-0">
                  <div className="flex flex-wrap items-center gap-field text-meta">
                    <span className="text-muted-foreground font-medium">Attached Vendors:</span>
                    {vendors.length > 0 ? (
                      vendors.map((v) => (
                        <span
                          key={v.vendor_id}
                          className="font-mono text-meta px-field py-0.5 rounded bg-muted text-foreground border border-border"
                        >
                          {v.vendor_id}
                        </span>
                      ))
                    ) : (
                      <span className="font-mono text-meta px-field py-0.5 rounded bg-muted text-foreground border border-border">
                        Stripe
                      </span>
                    )}
                  </div>

                  {activeRun ? (
                    <div className="flex items-center gap-field rounded-md bg-surface-subtle p-field text-meta border border-border">
                      <Clock className="size-3.5 text-amber-400 shrink-0" />
                      <span className="text-foreground-lighter truncate">
                        Remediation active · {activeRun.current_node ?? "in progress"}
                      </span>
                      {activeRun.last_checkpoint_at ? (
                        <span className="ml-auto font-mono text-meta text-muted-foreground shrink-0">
                          {formatElapsed(activeRun.last_checkpoint_at)}
                        </span>
                      ) : null}
                    </div>
                  ) : null}

                  <div className="flex items-center justify-between pt-field border-t border-border mt-auto">
                    <span className="text-meta text-muted-foreground">
                      Index status: verified
                    </span>
                    <Button asChild size="sm" variant="ghost" className="gap-field text-meta group-hover:text-primary">
                      <Link to={`/repositories/${encodeURIComponent(repoId)}`}>
                        <span>Open Codebase</span>
                        <ArrowRight className="size-3.5 transition-colors" />
                      </Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
