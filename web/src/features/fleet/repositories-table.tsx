/**
 * `repo_id` roll-up from the index, with its limit stated.
 *
 * These are repositories the index has seen, not repositories that were ever configured:
 * a repository configured but never indexed writes no `call_site` row and does not appear
 * here — indistinguishable from one that was never configured at all.
 */

import { Link } from "react-router"

import { useRepositories } from "@/api/queries"
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
import { CardinalityStatement, describeCardinality, sliceForDisplay } from "@/features/fleet/cardinality"

export function RepositoriesCard() {
  const query = useRepositories()

  return (
    <div className="flex flex-col gap-4">
      {query.isPending && <LoadingState what="the indexed repositories" />}
      {query.isError && <ErrorState error={query.error} what="the indexed repositories" />}

      {query.isSuccess && (
        <Card>
          <CardHeader>
            <CardTitle className="text-emphasis">
              {query.data.repo_ids.length}{" "}
              {query.data.repo_ids.length === 1 ? "repository" : "repositories"} indexed
            </CardTitle>
            <CardDescription className="text-body">
              Every repository the API Dependency Graph holds at least one call site from.
              A repository that was configured but never indexed has no row here — the same
              absence as one that was never configured at all, because the index cannot
              tell the two apart.
            </CardDescription>
          </CardHeader>
          <CardContent>
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
                      <TableHead className="text-meta">Repository</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sliceForDisplay(query.data.repo_ids).map((repoId) => (
                      <TableRow key={repoId}>
                        <TableCell className="font-mono text-body">
                          <Link
                            to={`/bindings/repositories/${encodeURIComponent(repoId)}`}
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
          </CardContent>
        </Card>
      )}
    </div>
  )
}
