/**
 * Pick a repository to see its observed telemetry.
 *
 * The list is the index's `repo_id` roll-up — every repository with at least one indexed call
 * site — not a list of repositories with telemetry. A repository can appear here and still
 * show three empty tables on the next screen; that is a true answer about it, not a dead link.
 */

import { Link } from "react-router"

import { useRepositories } from "@/api/queries"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Breadcrumbs } from "@/layouts/breadcrumbs"

export function ObservedTelemetryHubPage() {
  const query = useRepositories()

  return (
    <section className="flex flex-col gap-4">
      <Breadcrumbs trail={[{ label: "Fleet", to: "/" }, { label: "Observed telemetry" }]} />
      <h1 className="text-page">Observed telemetry</h1>
      <p className="text-body text-muted-foreground">
        What traffic Sync has seen for a repository, what response shapes it recorded, and
        where error rates moved — the telemetry rung of the API Dependency Graph, read
        directly rather than through a finding.
      </p>

      {query.isPending && <LoadingState what="the indexed repositories" />}
      {query.isError && <ErrorState error={query.error} what="the indexed repositories" />}

      {query.isSuccess && (
        <Card>
          <CardHeader>
            <CardTitle>
              {query.data.repo_ids.length}{" "}
              {query.data.repo_ids.length === 1 ? "repository" : "repositories"} indexed
            </CardTitle>
            <CardDescription>
              Every repository with at least one indexed call site. Being listed here says
              nothing about whether telemetry has recorded any traffic for it — that is the
              question the next screen answers, and it may answer with three empty tables.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {query.data.repo_ids.length === 0 ? (
              <EmptyState
                headline="The index has seen no repository."
                detail="The API answered, and no call site in the graph names a repository. That is an answer, not a failure — either nothing has been indexed yet, or nothing indexed carries a repository identifier."
              />
            ) : (
              <ul className="flex flex-col gap-2">
                {query.data.repo_ids.map((repoId) => (
                  <li key={repoId}>
                    <Link
                      to={`/repositories/${encodeURIComponent(repoId)}/observed`}
                      className="font-mono underline underline-offset-2"
                    >
                      {repoId}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}
    </section>
  )
}
