/**
 * Index coverage, for one repository: which vendors the static index found call sites for.
 *
 * Extracted out of `codebase-page.tsx` so `signals-page.tsx` can render the same query under
 * the Signals level's vendor role without a second implementation. The two callers ask
 * different questions of one answer — Codebase asks "how much of this codebase has Sync
 * read", Signals asks "which vendor subjects are attached to this repository's graph" — and
 * both are honest readings of `by_vendor`, which is why this stays one component rather than
 * one query duplicated into two renderings that could drift.
 */

import { Link } from "react-router"

import { useRepositoryCoverage } from "@/api/queries"
import { Formatted } from "@/components/status"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatTimestamp } from "@/lib/format"

export function IndexCoverageCard({ repoId }: { repoId: string }) {
  const query = useRepositoryCoverage(repoId)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Index coverage</CardTitle>
        <CardDescription className="max-w-prose">
          Call sites the index holds for this repository, per vendor. A vendor absent from the
          table is not zero — it is a question this view cannot answer: whether the indexer
          looked and found nothing, or nothing declares which package to look for. A vendor
          name below opens that vendor's own page with this repository's scope carried into
          it, so the findings there are this codebase's; what the vendor published is not
          scoped, and that page says which of its two halves is which.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {query.isPending && <LoadingState what={`index coverage for ${repoId}`} />}
        {query.isError && (
          <ErrorState error={query.error} what={`index coverage for ${repoId}`} />
        )}
        {query.isSuccess &&
          (query.data.total_call_sites === 0 ? (
            <EmptyState
              headline={`The index holds no call site for ${repoId}.`}
              detail="This repository was never indexed, or it was indexed and nothing bound to a vendor was found. Those are the same answer here: the index has no configuration table, so a repository it has never seen a call site from is indistinguishable from one nobody ever configured."
            />
          ) : (
            <div className="flex flex-col gap-section">
              <p className="flex flex-wrap items-baseline gap-field text-body">
                <span className="text-figure">{query.data.total_call_sites}</span>
                <span>call site{query.data.total_call_sites === 1 ? "" : "s"} indexed.</span>
              </p>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Vendor</TableHead>
                    <TableHead>Call sites</TableHead>
                    <TableHead>Last indexed</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Object.entries(query.data.by_vendor)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([vendorId, count]) => (
                      <TableRow key={vendorId}>
                        <TableCell className="font-mono">
                          <Link
                            to={`/vendors/${encodeURIComponent(vendorId)}?repo_id=${encodeURIComponent(repoId)}`}
                            className="underline underline-offset-2"
                          >
                            {vendorId}
                          </Link>
                        </TableCell>
                        <TableCell className="font-mono">{count}</TableCell>
                        <TableCell className="font-mono text-meta">
                          {/* Optional access, not the type contract: `last_indexed` shares
                              `by_vendor`'s key set by construction on every current build of
                              `index_coverage`. The guard is here only because the console's own
                              dev API process can be older than the code it is serving while a
                              deploy is mid-flight, and a stale response must not crash the page
                              that reads it. */}
                          <Formatted
                            value={formatTimestamp(query.data.last_indexed?.[vendorId])}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                </TableBody>
              </Table>
              <p className="max-w-prose text-body text-muted-foreground">
                "Last indexed" is the newest indexing timestamp among that vendor's call sites —
                staleness, not a promise the index is current. A repository re-scanned weeks ago
                reports the same value every day after, until another re-index moves it.
              </p>
            </div>
          ))}
      </CardContent>
    </Card>
  )
}
