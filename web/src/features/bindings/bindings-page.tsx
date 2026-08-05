/**
 * The API Dependency Graph, made visible.
 *
 * Sync's whole claim is the binding — this call site depends on this vendor operation, and
 * here is the class of evidence that says so — and until this screen an operator could not
 * see one. Two questions, two sections: which call sites bind to a vendor operation and what
 * changed about it (a lookup, since nothing in the graph enumerates every operation a vendor
 * has); and what the index actually holds per repository, joined against what traffic Sync has
 * watched for it.
 *
 * This reads `sync.dashboard.graph_views` exclusively, never `GraphSurface` — the same
 * amendment `sync.dashboard.fleet` already made for "every run" and "every attempt": a
 * question whose grain is the graph itself, not one finding an agent is already pointed at.
 *
 * Which detector is raising findings at which rungs, across the whole graph, is a related but
 * separate question — answered on its own screen at `/detectors` rather than restated here.
 */

import { Link } from "react-router"

import { useRepositories } from "@/api/queries"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { BindingLookupForm } from "@/features/bindings/binding-lookup-form"
import { Breadcrumbs } from "@/layouts/breadcrumbs"

function RepositoryList() {
  const query = useRepositories()

  if (query.isPending) return <LoadingState what="the indexed repositories" />
  if (query.isError) return <ErrorState error={query.error} what="the indexed repositories" />

  if (query.data.repo_ids.length === 0) {
    return (
      <EmptyState
        headline="The index has seen no repository."
        detail="The API answered, and no call site in the graph names a repository. Either nothing has been indexed yet, or nothing indexed carries a repository identifier."
      />
    )
  }

  return (
    <ul className="flex flex-col gap-1">
      {query.data.repo_ids.map((repoId) => (
        <li key={repoId}>
          <Link
            to={`/bindings/repositories/${encodeURIComponent(repoId)}`}
            className="font-mono text-body underline underline-offset-2"
          >
            {repoId}
          </Link>
        </li>
      ))}
    </ul>
  )
}

export function BindingsPage() {
  return (
    <section className="flex flex-col gap-4">
      <Breadcrumbs trail={[{ label: "Fleet", to: "/" }, { label: "Bindings" }]} />
      <h1 className="text-page">Bindings</h1>
      <p className="text-body text-muted-foreground">
        What does my code depend on, and how does Sync know? A binding is a call site joined
        against a vendor operation, and every binding here carries the rung of evidence that
        produced it — read out of the source, resolved past it, or correlated from watched
        traffic.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>Look up a binding</CardTitle>
          <CardDescription>
            The graph has no list of "every operation a vendor has" to pick from — enter a
            vendor id and an operation id from a finding, a vendor's changes, or a vendor's own
            documentation. Repository is optional; leave it blank to see every repository the
            index has bound to this operation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <BindingLookupForm />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Index coverage and observed telemetry</CardTitle>
          <CardDescription>
            Every repository the index has seen at least one call site from. A repository that
            was configured but never indexed has no row here — indistinguishable from one that
            was never configured at all, because the index cannot tell the two apart.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <RepositoryList />
        </CardContent>
      </Card>

      <p className="text-body text-muted-foreground">
        Which detector raised which finding, at which rung, is answered on its own screen:{" "}
        <Link to="/detectors" className="underline underline-offset-2">
          detector accountability
        </Link>
        .
      </p>
    </section>
  )
}
