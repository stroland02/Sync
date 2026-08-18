/**
 * The API services one repository calls.
 *
 * The owner asked for *"an api services page that list all the different services"*. Two answers
 * carry part of that list and neither carries all of it: `/api/repositories/{repo_id}/coverage`
 * names a service the static index bound a call site to, and `/api/overview?repo_id=` names a
 * service with at least one open finding. A service can be in either without being in the other, so
 * this screen renders the union and keeps the two grains apart per column rather than merging them
 * into one figure — the merge is the defect, not the extra column.
 *
 * **Both answers echo the scope they were computed for, and both are checked.** `/api/overview`
 * has been rendered fleet-wide under one repository's name here before (`codebases-panel.tsx`,
 * fixed in `M14-W265`), so the list is refused outright when the overview's scope does not match the
 * address, and the index columns alone are dropped when the coverage answer's does not.
 *
 * **The coverage address does not route for a real repository identifier (B147).** Every identifier
 * is `host/owner/name`, the route declares the default path converter, and the console percent-
 * encodes the slashes — so the request 404s before any reader runs. The generic 404 explanation,
 * *"The API does not hold that identifier"*, is false in that case: the repository exists and
 * `/api/repositories` lists it. This screen intercepts that 404 and says what actually happened,
 * which it can do unambiguously because `sync.dashboard.graph_views.index_coverage` has no 404 of
 * its own — it returns a well-formed empty payload for a repository it holds nothing for.
 *
 * **What this screen does not show, and says so on screen.** The operations each service exposes are
 * not listed, because no route returns the operations one repository calls: `/api/change-units` and
 * `/api/vendors/{id}` are the only answers carrying an operation identifier, both are scoped to open
 * findings — a different question — and the first does not echo its own scope, so it could not be
 * checked against this address at all. That is stated as absent work rather than drawn as an empty
 * panel carrying the never-measured marker.
 */

import { Link, useParams } from "react-router"

import { NotFoundError } from "@/api/errors"
import { useOverview, useRepositoryCoverage } from "@/api/queries"
import type { Tally } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { Absent, Formatted } from "@/components/status"
import { EmptyState, ErrorState, LoadingState, NotFoundState } from "@/components/states"
import { Badge } from "@/vendor/supabase/ui/badge"
import { formatTimestamp } from "@/lib/format"


/** What the index-coverage answer turned out to be, once its scope and its 404 are accounted for. */
type CoverageState =
  | { kind: "ready"; byVendor: Tally; lastIndexed: Record<string, string> }
  | { kind: "unrouted" }
  | { kind: "failed"; error: unknown }
  | { kind: "otherScope"; scope: string }

export interface RepositoryServicesPageProps {
  readonly question?: string
}

export function RepositoryServicesPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const overview = useOverview(repoId)
  const coverage = useRepositoryCoverage(repoId ?? "")



  if (overview.isPending || coverage.isPending) {
    return (
      <section className="flex flex-col gap-section">
        <LoadingState what="the API services this repository calls" />
      </section>
    )
  }

  if (overview.isError) {
    return (
      <section className="flex flex-col gap-section">
        <ErrorState
          error={overview.error}
          what="the API services this repository calls"
          onRetry={() => void overview.refetch()}
        />
      </section>
    )
  }

  const coverageState: CoverageState = coverage.isError
    ? coverage.error instanceof NotFoundError
      ? { kind: "unrouted" }
      : { kind: "failed", error: coverage.error }
    : coverage.data?.repo_id === repoId
      ? {
          kind: "ready",
          byVendor: coverage.data.by_vendor,
          lastIndexed: coverage.data.last_indexed,
        }
      : { kind: "otherScope", scope: coverage.data?.repo_id ?? "another repository" }

  const indexed = coverageState.kind === "ready" ? coverageState.byVendor : {}
  const lastIndexed = coverageState.kind === "ready" ? coverageState.lastIndexed : {}

  // The answer names the scope it was computed for. Rendering rows from a fleet-wide answer under
  // this repository's heading would be a false claim about this repository, so it is refused rather
  // than shown with a caveat.
  const scopeMatches = overview.data?.repo_id === repoId
  const openFindings = new Map(
    (overview.data?.vendors ?? []).map((vendor) => [vendor.vendor_id, vendor.open_finding_count])
  )
  const services = scopeMatches
    ? [...new Set([...openFindings.keys(), ...Object.keys(indexed)])].sort((a, b) =>
        a.localeCompare(b)
      )
    : []

  return (
    <section className="flex flex-col gap-section">

      <p className="max-w-prose text-body text-muted-foreground">
        A service is listed here when the index bound a call site in this repository to it, or when
        an open finding names it. Those are two answers to two different questions, and each column
        below reports only its own — a blank in one is not a zero in the other.
      </p>

      {coverageState.kind === "unrouted" && (
        <NotFoundState
          headline="The index could not be asked about this repository."
          detail={
            "The address holding call sites and index times answered 404 before any reader ran: " +
            "its route cannot match a repository identifier containing a slash, and every " +
            "identifier is host/owner/name. This repository exists and /api/repositories lists " +
            "it, so this is the transport failing to route the question rather than an index with " +
            "nothing in it. Call sites and last indexed are not shown below."
          }
          identifier={`/api/repositories/${encodeURIComponent(repoId ?? "")}/coverage`}
        />
      )}

      {coverageState.kind === "failed" && (
        <ErrorState
          error={coverageState.error}
          what={`index coverage for ${repoId}`}
          onRetry={() => void coverage.refetch()}
        />
      )}

      {coverageState.kind === "otherScope" && (
        <EmptyState
          headline="The index answered about a different repository."
          detail={
            `The index coverage that arrived names its scope as ${coverageState.scope}, not ` +
            `${repoId}. Its call-site counts and index times are not shown here, because another ` +
            `repository's counts under this repository's name is a claim nothing computed.`
          }
        />
      )}

      {!scopeMatches ? (
        <EmptyState
          headline="This answer was computed for a different scope."
          detail={
            `The overview that arrived names its scope as ` +
            `${overview.data?.repo_id ?? "the whole fleet"}, not ${repoId}. Its services are not ` +
            `shown here, because a fleet-wide list under one repository's name is a claim about ` +
            `that repository which nothing computed.`
          }
        />
      ) : services.length === 0 ? (
        <EmptyState
          headline={`No API service is bound to ${repoId}.`}
          detail="This repository was never indexed, or it was indexed and nothing bound to a vendor was found. Those are the same answer here: the index has no configuration table, so a repository it has never seen a call site from is indistinguishable from one nobody ever configured."
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Service</TableHead>
              <TableHead>Open findings</TableHead>
              {coverageState.kind === "ready" && (
                <>
                  <TableHead>Call sites</TableHead>
                  <TableHead>Last indexed</TableHead>
                </>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {services.map((service) => {
              const open = openFindings.get(service)
              const sites = indexed[service]
              return (
                <TableRow key={service}>
                  <TableCell>
                    <Link
                      to={`/vendors/${encodeURIComponent(service)}?repo_id=${encodeURIComponent(repoId ?? "")}`}
                      className="font-mono underline underline-offset-2"
                    >
                      {service}
                    </Link>
                  </TableCell>
                  <TableCell>
                    {/* A confirmed zero is an answer about this service and renders as words. A
                        service the vendor breakdown never named has no figure at all — that
                        breakdown counts open findings and emits no row where there are none — so it
                        takes the absence marker. The two are different claims and this console
                        exists to keep them apart. */}
                    {open === undefined ? (
                      <Absent />
                    ) : (
                      <Badge>{open === 0 ? "No open findings" : `${open} open findings`}</Badge>
                    )}
                  </TableCell>
                  {coverageState.kind === "ready" && (
                    <>
                      <TableCell className="font-mono">
                        {sites === undefined ? <Absent /> : sites}
                      </TableCell>
                      <TableCell className="font-mono text-meta">
                        <Formatted value={formatTimestamp(lastIndexed[service])} />
                      </TableCell>
                    </>
                  )}
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      )}

      {coverageState.kind === "ready" && (
        <>
          <p className="max-w-prose text-body text-muted-foreground">
            A vendor absent from the table is not zero — it is a question this view cannot answer:
            whether the indexer looked and found nothing, or nothing declares which package to look
            for.
          </p>
          <p className="max-w-prose text-body text-muted-foreground">
            "Last indexed" is the newest indexing timestamp among that vendor's call sites —
            staleness, not a promise the index is current. A repository re-scanned weeks ago reports
            the same value every day after, until another re-index moves it.
          </p>
        </>
      )}

      <p className="max-w-prose text-body text-muted-foreground">
        The operations each service exposes are not listed, because no answer holds the operations
        one repository calls: the two that carry an operation identifier are scoped to open findings,
        which is a narrower question than this list, and one of them does not echo the scope it was
        computed for, so it could not be checked against this address. That is work not done rather
        than a service with no operations.
      </p>
    </section>
  )
}
