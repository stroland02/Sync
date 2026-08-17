/**
 * Codebases Panel: one card per repository the index holds, claiming only what an answer
 * scoped to that repository has actually said.
 *
 * `/api/overview` echoes the scope it was computed for (`repo_id`) precisely so a caller
 * cannot render one repository's figures under another's name by accident. The panel this
 * file replaced fetched the fleet-wide overview once and printed its `total_findings` under
 * every card — a false claim about every repository except (by coincidence) the one the
 * fleet-wide figure happened to match. `useRepoOverviews` below issues one scoped query per
 * `repo_id`, at the same key `useOverview` would use for that repository, so the cache holds
 * one answer per scope rather than one answer mistaken for many.
 *
 * A run is deliberately never attributed to a card. `RunRow` carries no `repo_id` — nothing
 * in the transport says which repository a checkpoint thread belongs to — so a card showing
 * "Remediation active" was inventing an attribution the payload cannot support. The runs table
 * elsewhere on this screen is where a run is shown, against the only scope it actually carries.
 * The same reasoning retires the old "Index status: verified" line: nothing in any payload this
 * panel reads asserts that, so nothing on the card does either.
 *
 * `openFindings` is `number | null`, never defaulted to zero. `null` means the scoped answer for
 * this repository has not arrived yet — pending, or not yet requested — and renders the console's
 * one absence marker (`Absent`). A confirmed zero renders "No open findings". Collapsing "not yet
 * answered" onto "zero" is exactly the kind of claim this rewrite exists to stop making; see
 * `codebase-cards.ts` for where the distinction is computed and tested.
 *
 * The same distinction has to hold at the filter, not only at the card. `NEEDS_REVIEW` and
 * `CLEAN` both read `openFindings`, and `matchesFilter` treats `null` as matching neither — but a
 * filtered list built from cards that are still `null` would still read as "zero matches" to
 * whoever is looking at the empty state, which is the conflation this file exists to refuse. So
 * while any scoped query behind a non-`ALL` filter is still pending, the panel renders
 * `LoadingState` rather than let the filter claim a confirmed absence of matches it cannot back.
 * `ALL` never reads `openFindings` to decide membership, so it is never held back by this.
 */

import { useQueries } from "@tanstack/react-query"
import { FolderGit2, ArrowRight } from "lucide-react"
import { Link } from "react-router"

import { fetchOverview } from "@/api/client"
import { useRepositories } from "@/api/queries"
import type { OverviewResponse } from "@/api/types"
import { Badge } from "@/vendor/supabase/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/vendor/supabase/ui/card"
import { Absent } from "@/components/status"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { cardFacts, matchesFilter, type CodebaseCardFacts, type CodebaseFilter } from "@/features/fleet/codebase-cards"

export type { CodebaseFilter } from "@/features/fleet/codebase-cards"

export interface CodebasesPanelProps {
  readonly filter?: CodebaseFilter
}

/**
 * One `/api/overview` query per repository, keyed exactly as `useOverview(repoId)` would key it
 * so the two share a cache entry rather than issuing the answer twice.
 */
function useRepoOverviews(repoIds: string[]) {
  return useQueries({
    queries: repoIds.map((repoId) => ({
      queryKey: ["overview", repoId],
      queryFn: ({ signal }: { signal: AbortSignal }): Promise<OverviewResponse> =>
        fetchOverview({ repoId }, signal),
    })),
  })
}

function VendorBadge({ vendorId }: { vendorId: string }) {
  return (
    <span className="font-mono text-meta px-field py-field rounded-control bg-muted text-foreground border border-border">
      {vendorId}
    </span>
  )
}

function FindingsBadge({ facts }: { facts: CodebaseCardFacts }) {
  if (facts.openFindings === null) {
    return (
      <Badge>
        <Absent>open findings not yet answered</Absent>
      </Badge>
    )
  }
  return <Badge>{facts.openFindings === 0 ? "No open findings" : `${facts.openFindings} open findings`}</Badge>
}

function CodebaseCard({ facts }: { facts: CodebaseCardFacts }) {
  return (
    <Card className="group relative flex flex-col justify-between border-line bg-surface hover:border-border transition-colors duration-150">
      <CardHeader className="gap-field pb-row">
        <div className="flex items-start justify-between gap-row">
          <div className="flex items-center gap-field">
            <div className="flex size-8 items-center justify-center rounded-control bg-muted border border-border text-foreground">
              <FolderGit2 className="size-4" />
            </div>
            <div>
              <CardTitle className="font-mono text-emphasis font-semibold group-hover:text-primary transition-colors">
                <Link to={`/repositories/${encodeURIComponent(facts.repoId)}`} className="focus:outline-none">
                  {facts.repoId}
                </Link>
              </CardTitle>
              {/* No description. It read "Git repository · Monitored by Sync" on every card, and a
                  reader looking at the Sync console's own repository list already knows both
                  halves. Measured as 170 of Fleet's 450 discretionary characters against the drawn
                  console's 340 — the largest prose on the screen carrying none of the four
                  protected distinctions, and the only piece whose deletion removes no fact. */}
            </div>
          </div>

          <FindingsBadge facts={facts} />
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-row pt-0">
        {facts.vendors.length > 0 ? (
          <div className="flex flex-wrap items-center gap-field text-meta">
            <span className="text-muted-foreground font-medium">Attached Vendors:</span>
            {facts.vendors.map((vendorId) => (
              <VendorBadge key={vendorId} vendorId={vendorId} />
            ))}
          </div>
        ) : null}

        <div className="flex items-center justify-end pt-field border-t border-border mt-auto">
          <Button asChild size="sm" variant="ghost" className="gap-field text-meta group-hover:text-primary">
            <Link to={`/repositories/${encodeURIComponent(facts.repoId)}`}>
              <span>Open Codebase</span>
              <ArrowRight className="size-3.5 transition-colors" />
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function CodebasesPanel({ filter = "ALL" }: CodebasesPanelProps) {
  const reposQuery = useRepositories()
  const repoIds = reposQuery.data?.repo_ids ?? []
  const overviewQueries = useRepoOverviews(repoIds)

  if (reposQuery.isPending) {
    return <LoadingState what="monitored codebases" />
  }

  if (reposQuery.isError) {
    return <ErrorState error={reposQuery.error} what="monitored codebases" onRetry={() => void reposQuery.refetch()} />
  }

  // NEEDS_REVIEW and CLEAN both read `openFindings`, so filtering against a scope whose answer
  // has not arrived yet would count a pending query as a non-match — the same null-vs-zero
  // conflation `codebase-cards.ts` refuses at the derivation layer, reached instead through the
  // filter. ALL never reads the count, so it is exempt: nothing here needs the scoped answer to
  // decide whether a card belongs on screen.
  const overviewsPending = overviewQueries.some((query) => query.isPending)
  if (filter !== "ALL" && overviewsPending) {
    return <LoadingState what="monitored codebases" />
  }

  const cards = repoIds.map((repoId, index) => cardFacts(repoId, overviewQueries[index]?.data))
  const filteredCards = cards.filter((facts) => matchesFilter(facts, filter))

  return (
    <div className="flex flex-col gap-row">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-page font-semibold tracking-tight text-foreground">Monitored Codebases</h2>
          <p className="text-meta text-muted-foreground">
            Select a repository to inspect its attached API services, telemetry signals, and active remediations.
          </p>
        </div>
      </div>

      {repoIds.length === 0 ? (
        <EmptyState
          headline="No repositories are monitored."
          detail="The index has not recorded any repositories. A repository appears here once INDEX has run against it."
        />
      ) : filteredCards.length === 0 ? (
        <EmptyState
          headline="No codebases match the selected filter."
          detail="No repositories match the chosen filter criteria. Switch back to 'All repositories' to view all watched codebases."
        />
      ) : (
        <div className="grid gap-row md:grid-cols-2">
          {filteredCards.map((facts) => (
            <CodebaseCard key={facts.repoId} facts={facts} />
          ))}
        </div>
      )}
    </div>
  )
}
