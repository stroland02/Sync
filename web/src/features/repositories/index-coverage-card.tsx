/**
 * Index coverage, for one repository: which vendors the static index found call sites for.
 *
 * Extracted out of `codebase-page.tsx` so the Signals level could render the same query under its
 * vendor role without a second implementation. **M7-W175 ended that arrangement**: Signals now
 * draws a card per vendor rather than a table of them, and
 * `features/signals/subject-catalogue.tsx` is where that lives. Ruling 6 of
 * `docs/superpowers/briefs/2026-08-07-substrate-signals.md` carries what it cost and why it was
 * still the right trade — chiefly that neither rendering computes anything, so there is no
 * derivation duplicated between them, only a sort.
 *
 * This component therefore has one caller again. The two protected sentences it carries — a vendor
 * absent from the table is a question rather than a zero, and "last indexed" is staleness rather
 * than a promise — are reproduced in full over there rather than paraphrased, which is the part
 * that had to survive the split.
 *
 * **The call-site figure is this panel's own metric rather than a tile in a rail**, and that is
 * unchanged: M7-W173 ported the Codebase level onto the substrate and did not give it a fact rail.
 * `docs/superpowers/briefs/2026-08-07-substrate-codebase.md` carries the mapping and that ruling.
 */

import { Link } from "react-router"

import { useRepositoryCoverage } from "@/api/queries"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { MetricPanel } from "@/components/metric-panel"
import { Formatted } from "@/components/status"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { formatTimestamp } from "@/lib/format"

export function IndexCoverageCard({ repoId }: { repoId: string }) {
  const query = useRepositoryCoverage(repoId)

  return (
    <div className="flex min-w-0 flex-col gap-section">
      {query.isPending && <LoadingState what={`index coverage for ${repoId}`} />}
      {query.isError && (
        <ErrorState error={query.error} what={`index coverage for ${repoId}`} />
      )}

      {query.isSuccess && (
        <MetricPanel
          label="Index coverage"
          metric={
            query.data.total_call_sites === 0
              ? undefined
              : {
                  value: query.data.total_call_sites.toLocaleString(),
                  unit: `call site${query.data.total_call_sites === 1 ? "" : "s"} indexed`,
                }
          }
          caption={
            <p className="max-w-prose">
              Call sites the index holds for this repository, per vendor. A vendor absent from the
              table is not zero — it is a question this view cannot answer: whether the indexer
              looked and found nothing, or nothing declares which package to look for. A vendor
              name below opens that vendor's own page with this repository's scope carried into
              it, so the findings there are this codebase's; what the vendor published is not
              scoped, and that page says which of its two halves is which.
            </p>
          }
        >
          {query.data.total_call_sites === 0 ? (
            <EmptyState
              headline={`The index holds no call site for ${repoId}.`}
              detail="This repository was never indexed, or it was indexed and nothing bound to a vendor was found. Those are the same answer here: the index has no configuration table, so a repository it has never seen a call site from is indistinguishable from one nobody ever configured."
            />
          ) : (
            <>
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
                        <TableCell>
                          <Link
                            to={`/vendors/${encodeURIComponent(vendorId)}?repo_id=${encodeURIComponent(repoId)}`}
                            className="font-mono underline underline-offset-2"
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
            </>
          )}
        </MetricPanel>
      )}
    </div>
  )
}
