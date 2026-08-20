/**
 * The API products one repository calls: `Payments` under `stripe`, not `stripe` again.
 *
 * **A vendor is the provider; a service is one of the APIs it sells.** Until 2026-08-19 the graph
 * carried only the provider, so this screen listed `vendor_id` and so did the Vendors screen --
 * one question answered twice under two headings, which is the duplication the owner named. The
 * layer is `call_site.service_id` now and this screen is the only one that renders it.
 *
 * **Findings are not here, and their absence is the point.** What is open against a provider and
 * whether Sync can watch it at all are the Vendors screen's questions; repeating them here is what
 * made the two screens look alike. This one reads `/api/repositories/{repo}/coverage` alone -- one
 * route, one grain, no second answer to disagree with it.
 *
 * **A row with no service is work not done rather than a call outside every service.** Only a
 * vendor adapter can map an operation onto a product and none supplies that mapping yet, so most
 * real rows group under NULL and the table says so in the absence vocabulary rather than inventing
 * a product name or dropping the rows.
 *
 * **The coverage address does not route for a real repository identifier (B147).** Every identifier
 * is `host/owner/name`, the route declares the default path converter, and the console percent-
 * encodes the slashes -- so the request 404s before any reader runs. The generic 404 explanation,
 * *"The API does not hold that identifier"*, is false in that case: the repository exists and
 * `/api/repositories` lists it. This screen intercepts that 404 and says what actually happened,
 * which it can do unambiguously because `sync.dashboard.graph_views.index_coverage` has no 404 of
 * its own -- it returns a well-formed empty payload for a repository it holds nothing for.
 */

import { useState } from "react"
import { ChevronRight } from "lucide-react"
import { Link, useParams } from "react-router"

import { NotFoundError } from "@/api/errors"
import { useRepositoryCoverage } from "@/api/queries"
import type { OperationCoverageRow, ServiceCoverageRow, Tally } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { InfoHint } from "@/components/info-hint"
import { KpiStrip } from "@/components/kpi-strip"
import { LastIndexed } from "@/components/last-indexed"
import { RankedBars } from "@/components/ranked-bars"
import { Absent, Formatted } from "@/components/status"
import { EmptyState, ErrorState, LoadingState, NotFoundState } from "@/components/states"
import { formatTimestamp } from "@/lib/format"


import { bindingSurfaceHref, vendorHref } from "@/lib/hrefs"
/** What the index-coverage answer turned out to be, once its scope and its 404 are accounted for. */
type CoverageState =
  | {
      kind: "ready"
      byVendor: Tally
      lastIndexed: Record<string, string>
      byService: readonly ServiceCoverageRow[]
      byOperation: readonly OperationCoverageRow[]
    }
  | { kind: "unrouted" }
  | { kind: "failed"; error: unknown }
  | { kind: "otherScope"; scope: string }

/**
 * One API product, with the operations behind it a press away.
 *
 * The shape `change-unit-groups.tsx` uses on the findings screen, and for the same reason: a
 * product is a decision a reader scans, its operations are the detail they open. They were
 * rendered as a wall of inline chips in the row itself, which made a vendor with fifteen
 * ungrouped operations a paragraph inside a table cell.
 */
function ServiceRow({
  repoId,
  row,
  operations,
}: {
  repoId: string
  row: ServiceCoverageRow
  operations: readonly OperationCoverageRow[]
}) {
  const [open, setOpen] = useState(false)
  const noun = row.operations === 1 ? "operation" : "operations"

  return (
    <>
      <TableRow>
        <TableCell>
          <button
            type="button"
            onClick={() => setOpen((was) => !was)}
            aria-expanded={open}
            className="flex items-center gap-field rounded-control px-field py-field text-meta text-ink transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <ChevronRight
              aria-hidden="true"
              className={`size-3.5 shrink-0 transition-transform ${open ? "rotate-90" : ""}`}
            />
            <span className="tabular-nums">
              {row.operations.toLocaleString()} {noun}
            </span>
          </button>
        </TableCell>
        <TableCell className="font-mono text-meta">
          <Link
            to={vendorHref(repoId, row.vendor_id)}
            className="text-ink underline underline-offset-2"
          >
            {row.vendor_id}
          </Link>
          {row.service_id === null ? (
            // Not a service named nothing: no adapter has mapped these operations onto a product.
            // The absence marker says which nothing it is.
            <span className="ml-field">
              <Absent>not grouped into a product yet</Absent>
            </span>
          ) : (
            <span className="text-ink-muted"> / {row.service_id}</span>
          )}
        </TableCell>
        <TableCell className="font-mono text-meta text-ink-muted">
          <Formatted value={formatTimestamp(row.last_indexed)} />
        </TableCell>
        <TableCell className="text-right tabular-nums text-meta text-ink-muted">
          {row.call_sites.toLocaleString()}
        </TableCell>
      </TableRow>
      {open && (
        <TableRow>
          <TableCell colSpan={4} className="bg-surface-subtle p-section">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Operation</TableHead>
                  <TableHead className="text-right">Call sites</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {operations.map((operation) => (
                  <TableRow key={operation.operation_id}>
                    <TableCell>
                      <Link
                        to={bindingSurfaceHref(repoId, operation.vendor_id, operation.operation_id)}
                        className="font-mono text-meta text-ink underline underline-offset-2"
                      >
                        {operation.operation_id}
                      </Link>
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-meta text-ink-muted">
                      {operation.call_sites.toLocaleString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

export interface RepositoryServicesPageProps {
  readonly question?: string
}

export function RepositoryServicesPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const coverage = useRepositoryCoverage(repoId ?? "")



  if (coverage.isPending) {
    return (
      <section className="flex flex-col gap-8">
        <LoadingState what="the connections this repository has" />
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
          byService: coverage.data.by_service,
          byOperation: coverage.data.by_operation,
        }
      : { kind: "otherScope", scope: coverage.data?.repo_id ?? "another repository" }

  // The answer names the scope it was computed for. Rendering rows from a fleet-wide answer under
  // this repository's heading would be a false claim about this repository, so it is refused rather
  // than shown with a caveat.
  // The rows are API products, not providers. This page used to list `vendor_id` -- the same
  // identifier the Vendors screen lists -- so the two screens answered one question twice under
  // two headings, which is the duplication the owner named on 2026-08-19. A service is one of the
  // APIs a vendor sells, and the graph carries it per call site now.
  const byService = coverageState.kind === "ready" ? coverageState.byService : []
  const grouped = byService.filter((row) => row.service_id !== null)
  const ungrouped = byService.filter((row) => row.service_id === null)
  const ungroupedOperations = ungrouped.reduce((sum, row) => sum + row.operations, 0)
  // Which operations sit under each product. Keyed on the pair because an operation id is unique
  // only within its vendor, and two providers naming one alike would merge their rows.
  const operationsOf = (vendorId: string, serviceId: string | null) =>
    (coverageState.kind === "ready" ? coverageState.byOperation : []).filter(
      (row) => row.vendor_id === vendorId && row.service_id === serviceId,
    )

  return (
    <section className="flex flex-col gap-8">

      {/* The page's own facts, ahead of the table (owner ruling 2026-08-19). None restates the
          table's footer: the counts split the list by *which answer* names each service, which
          is the distinction the table draws per column and never totals. */}
      {(
        <KpiStrip
          items={[
            {
              label: "Services called",
              value: grouped.length.toLocaleString(),
              note: "distinct API products this codebase reaches",
            },
            {
              // Freshness as one figure, replacing the per-vendor `IndexFreshness` card that sat
              // above the table until 2026-08-19. That card listed one row per vendor to say what
              // the whole page is scoped to anyway -- a panel's worth of height for a fact that is
              // the same for every row on the screen. Staleness, never liveness.
              label: "Last indexed",
              value: <LastIndexed repoId={repoId ?? ""} />,
              note: "when this codebase's call sites were last read",
              figure: false,
            },
            {
              label: "Call sites in a service",
              value: grouped.reduce((sum, row) => sum + row.call_sites, 0).toLocaleString(),
              note: `of ${(coverage.data?.total_call_sites ?? 0).toLocaleString()} indexed here`,
            },
            {
              label: "Operations not grouped",
              value: ungroupedOperations.toLocaleString(),
              // Work not done, and it must not read as a service named nothing: only a vendor
              // adapter can map an operation onto a product, and none supplies that mapping yet.
              note: "no adapter maps them to a product yet",
            },
          ]}
        />
      )}

      <div className="flex flex-wrap items-center gap-row">
        <h2 className="text-section">API products this workspace calls</h2>
        {/* A claim, not an argument, so it stays visible -- caught by
            `repository-services-page.test.tsx` when the sweep moved it into the hover. What a
            screen does not show is exactly the kind of absence a non-hovering reader must be able
            to see; the *why* is in the â“˜. */}
        <span className="text-meta text-ink-muted">findings are on Findings</span>
        <InfoHint label="About the services list">
          A <em>vendor</em> is the provider Sync watches; a <em>service</em> is one of the APIs it
          sells &mdash; <span className="font-mono">Payments</span> under{" "}
          <span className="font-mono">stripe</span>. This screen answers what your code calls,
          counted over indexed call sites. What is open against a provider, and whether Sync can
          watch it at all, is the Vendors screen&rsquo;s question and is deliberately not repeated
          here. An operation with no service is one no adapter has mapped onto a product yet
          &mdash; that is work not done, never a call outside every service. Each row lists the
          operations behind it, which this screen could not do until the index reported them.
        </InfoHint>
      </div>

      {/* Where the exposure is, as bars rather than as a column a reader sorts by eye. The
          chart draws the index's answer only -- open findings are the other question, and a
          bar mixing the two would be the merge this screen's docstring refuses. */}
      {coverageState.kind === "ready" && grouped.length > 0 && (
        <RankedBars
          label="Call sites per service"
          caption="What the index bound in this codebase, per API product. Colour is the vendor that sells it, which is the one thing the bar lengths do not carry."
          rows={grouped
            .map((row) => ({
              key: `${row.vendor_id} Â· ${row.service_id ?? ""}`,
              value: row.call_sites,
            }))
            .sort((a, b) => b.value - a.value || a.key.localeCompare(b.key))}
          unit="call sites"
          colourKey={(key) => key.split(" Â· ")[0]}
          detail={(key) => {
            const row = grouped.find(
              (candidate) => `${candidate.vendor_id} Â· ${candidate.service_id ?? ""}` === key,
            )
            if (row === undefined) return ""
            return `${row.operations} op${row.operations === 1 ? "" : "s"}`
          }}
        />
      )}

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

      {byService.length === 0 ? (
        <EmptyState
          headline={`No API service is bound to ${repoId}.`}
          detail="This repository was never indexed, or it was indexed and nothing bound to a vendor was found. Those are the same answer here: the index has no configuration table, so a repository it has never seen a call site from is indistinguishable from one nobody ever configured."
          command={`uv run sync index --repo ${repoId}`}
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Operations</TableHead>
              <TableHead>Vendor / service</TableHead>
              <TableHead>Last indexed</TableHead>
              <TableHead className="text-right">Call sites</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {/* Grouped first, then whatever is not grouped -- the ungrouped rows are the honest
                bottom of the list rather than a state hidden behind a filter. */}
            {[...grouped, ...ungrouped].map((row) => (
              <ServiceRow
                key={`${row.vendor_id}:${row.service_id ?? ""}`}
                repoId={repoId ?? ""}
                row={row}
                operations={operationsOf(row.vendor_id, row.service_id)}
              />
            ))}
          </TableBody>
        </Table>
      )}

    </section>
  )
}
