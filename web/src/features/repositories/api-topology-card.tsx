/**
 * API topology: the shape of this codebase's API surface, measured from its own call sites.
 *
 * The owner's ask of 2026-08-18 — topology, complexity, composition — answered from what the
 * index already read rather than from a scanner bolted on beside it
 * (`references/notes/code-metrics-tooling.md` carries the survey and the verdicts).
 *
 * **Four questions, four counts, and nothing averaging them.** How wide the surface is
 * (operations, files, integrations), where it concentrates (the busiest operations), where a
 * change would cost most (files touching more than one integration), and how much of it sits
 * inside loops. A maintainability index or a health grade would be a composite, and this
 * console refuses those on the record.
 *
 * **Loop depth is the complexity signal this product actually holds**, and it is labelled as
 * static evidence: a loop that never runs still counts, because the number says what the code
 * says rather than what ran.
 */

import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router"

import {
  ApiStatusError,
  MalformedResponseError,
  UnreachableApiError,
} from "@/api/errors"
import { InfoHint } from "@/components/info-hint"
import { MetricPanel } from "@/components/metric-panel"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"

interface VendorRow {
  vendor_id: string
  call_sites: number
  operations: number
  files: number
}

interface OperationRow {
  vendor_id: string
  operation_id: string
  call_sites: number
  files: number
}

interface Topology {
  repo_id: string
  totals: { call_sites: number; vendors: number; operations: number; files: number }
  by_vendor: VendorRow[]
  busiest_operations: OperationRow[]
  multi_vendor_files: { path: string; vendors: number; call_sites: number }[]
  by_loop_depth: Record<string, number>
}

async function fetchTopology(repoId: string, signal?: AbortSignal): Promise<Topology> {
  const path = `/api/repositories/${encodeURIComponent(repoId)}/topology`
  let response: Response
  try {
    response = await fetch(path, { headers: { Accept: "application/json" }, signal })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new UnreachableApiError(path, { cause })
  }
  if (!response.ok) throw new ApiStatusError(response.status, path)
  try {
    return (await response.json()) as Topology
  } catch (cause) {
    throw new MalformedResponseError(path, { cause })
  }
}

function Figure({ label, value, unit }: { label: string; value: number; unit: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-field">
      <span className="furniture text-meta text-ink-muted">{label}</span>
      <span className="flex items-baseline gap-row">
        <span className="text-figure text-foreground tabular-nums">{value.toLocaleString()}</span>
        <span className="text-meta text-ink-muted">{unit}</span>
      </span>
    </div>
  )
}

export function ApiTopologyCard({ repoId }: { repoId: string }) {
  const query = useQuery({
    queryKey: ["api-topology", repoId],
    queryFn: ({ signal }) => fetchTopology(repoId, signal),
  })

  if (query.isPending) return <LoadingState what={`the API topology of ${repoId}`} />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what={`the API topology of ${repoId}`}
        onRetry={() => void query.refetch()}
      />
    )
  }

  const { totals, by_vendor, busiest_operations, multi_vendor_files, by_loop_depth } = query.data
  if (totals.call_sites === 0) {
    return (
      <EmptyState
        headline="No API surface to describe yet."
        detail="These figures are counted over indexed call sites, and this codebase has none. That is the absence of an index pass rather than a codebase that calls nothing."
      />
    )
  }

  const looped = Object.entries(by_loop_depth)
    .filter(([depth]) => depth !== "0")
    .reduce((sum, [, count]) => sum + count, 0)
  const deepest = Object.keys(by_loop_depth)
    .map(Number)
    .reduce((max, depth) => Math.max(max, depth), 0)

  return (
    <MetricPanel
      label="API topology"
      hint={
        <InfoHint label="About API topology">
          The shape of this codebase&rsquo;s API surface, counted over the call sites the index
          holds — how wide it is, where it concentrates, where a change would cost most, and how
          much of it sits inside loops. Every figure is a count of rows the index wrote; there is
          no score over them, because a number averaging four different questions answers none of
          them.
        </InfoHint>
      }
    >
      <div className="grid gap-section sm:grid-cols-2 xl:grid-cols-4">
        <Figure label="Integrations" value={totals.vendors} unit="called" />
        <Figure label="Operations" value={totals.operations} unit="reached" />
        <Figure label="Files" value={totals.files} unit="calling out" />
        <Figure label="Call sites" value={totals.call_sites} unit="indexed" />
      </div>

      <div className="grid gap-section border-t border-line pt-section lg:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-row">
          <h3 className="furniture text-meta text-ink-muted">
            Most-called operations
          </h3>
          <div className="grid grid-cols-[minmax(0,1fr)_auto_auto] gap-x-section gap-y-field">
            <span className="furniture text-meta text-ink-muted">operation</span>
            <span className="furniture text-right text-meta text-ink-muted">sites</span>
            <span className="furniture text-right text-meta text-ink-muted">files</span>
            {busiest_operations.map((row) => (
              <FanIn key={`${row.vendor_id}:${row.operation_id}`} row={row} repoId={repoId} />
            ))}
          </div>
          <p className="max-w-prose text-meta text-ink-muted">
            Concentration is what makes a vendor change cheap or expensive: one operation reached
            from many files is one change to review and many places to patch.
          </p>
        </div>

        <div className="flex min-w-0 flex-col gap-section">
          <div className="flex flex-col gap-row">
            <h3 className="furniture text-meta text-ink-muted">Calls inside loops</h3>
            <span className="flex items-baseline gap-row">
              <span className="text-figure text-foreground tabular-nums">{looped}</span>
              <span className="text-meta text-ink-muted">
                of {totals.call_sites.toLocaleString()} call sites, deepest nesting {deepest}
              </span>
            </span>
            <p className="max-w-prose text-meta text-ink-muted">
              Static evidence, not runtime: a loop that never runs still counts. Depth one is a
              page of results becoming one call each; depth two is quadratic.
            </p>
          </div>

          <div className="flex flex-col gap-row">
            <h3 className="furniture text-meta text-ink-muted">
              Files calling more than one integration
            </h3>
            {multi_vendor_files.length === 0 ? (
              <p className="max-w-prose text-meta text-ink-muted">
                None — every file that calls out reaches exactly one integration. A measured
                zero: the query ran over {totals.files.toLocaleString()} files.
              </p>
            ) : (
              <ul className="flex flex-col gap-field">
                {multi_vendor_files.map((file) => (
                  <li key={file.path} className="min-w-0 truncate font-mono text-meta text-ink">
                    {file.path}{" "}
                    <span className="text-ink-muted">
                      — {file.vendors} integrations, {file.call_sites} sites
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="flex flex-col gap-row">
            <h3 className="furniture text-meta text-ink-muted">Per integration</h3>
            <ul className="flex flex-col gap-field">
              {by_vendor.map((vendor) => (
                <li key={vendor.vendor_id} className="text-meta">
                  <span className="font-mono text-ink">{vendor.vendor_id}</span>
                  <span className="text-ink-muted">
                    {" "}
                    — {vendor.call_sites} sites across {vendor.files} files, {vendor.operations}{" "}
                    operations
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </MetricPanel>
  )
}

function FanIn({ row, repoId }: { row: OperationRow; repoId: string }) {
  return (
    <>
      <span className="min-w-0 truncate font-mono text-meta text-ink">
        <Link
          to={`/repositories/${encodeURIComponent(repoId)}/bindings/vendors/${encodeURIComponent(row.vendor_id)}/operations/${encodeURIComponent(row.operation_id)}`}
          className="underline underline-offset-2"
        >
          {row.operation_id}
        </Link>
        <span className="text-ink-muted"> · {row.vendor_id}</span>
      </span>
      <span className="text-right font-mono text-meta tabular-nums text-ink">{row.call_sites}</span>
      <span className="text-right font-mono text-meta tabular-nums text-ink-muted">{row.files}</span>
    </>
  )
}
