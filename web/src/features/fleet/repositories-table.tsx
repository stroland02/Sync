/**
 * `repo_id` roll-up from the index, with its limit stated.
 *
 * These are repositories the index has seen, not repositories that were ever configured:
 * a repository configured but never indexed writes no `call_site` row and does not appear
 * here — indistinguishable from one that was never configured at all.
 *
 * No metric figure, and the count stays in the panel's own name. The fact rail at the top of this
 * screen already renders it, and M7-W163's ruling stands: two renderings of one count is a fact
 * written twice. `docs/superpowers/briefs/2026-08-07-substrate-fleet.md` carries the mapping.
 */

import { Link } from "react-router"

import { useRepositories } from "@/api/queries"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { MetricPanel } from "@/components/metric-panel"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { CardinalityStatement, describeCardinality, sliceForDisplay } from "@/features/fleet/cardinality"

export function RepositoriesCard() {
  const query = useRepositories()

  return (
    <div className="flex flex-col gap-section">
      {query.isPending && <LoadingState what="the indexed repositories" />}
      {query.isError && <ErrorState error={query.error} what="the indexed repositories" />}

      {query.isSuccess && (
        <MetricPanel
          label={`${query.data.repo_ids.length} ${
            query.data.repo_ids.length === 1 ? "repository" : "repositories"
          } indexed`}
          caption={
            <p className="max-w-prose">
              Every repository the API Dependency Graph holds at least one call site from.
              A repository that was configured but never indexed has no row here — the same
              absence as one that was never configured at all, because the index cannot
              tell the two apart.
            </p>
          }
        >
          {query.data.repo_ids.length === 0 ? (
            <EmptyState
              headline="The index has seen no repository."
              detail="The API answered, and no call site in the graph names a repository. That is an answer, not a failure — either nothing has been indexed yet, or nothing indexed carries a repository identifier."
            />
          ) : (
            <>
              <CardinalityStatement
                text={describeCardinality(
                  query.data.repo_ids.length,
                  "repository",
                  "repositories",
                  "repository id, alphabetically",
                )}
              />
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Repository</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sliceForDisplay(query.data.repo_ids).map((repoId) => (
                    <TableRow key={repoId}>
                      <TableCell className="font-mono">
                        <Link
                          to={`/repositories/${encodeURIComponent(repoId)}`}
                          className="underline underline-offset-2"
                        >
                          {repoId}
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </>
          )}
        </MetricPanel>
      )}
    </div>
  )
}
