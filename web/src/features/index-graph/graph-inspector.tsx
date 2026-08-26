/**
 * What one mark on the codebase map actually is, read beside the map rather than over it.
 *
 * Four branches, one per thing a mark can be — nothing selected, a file, an operation, an
 * integration — each its own component so no hook is conditional. Only the operation branch
 * fetches; every other figure here comes off the graph read the page already holds.
 *
 * The three derivations are exported because each has a wrong answer: a file addressed by its
 * basename opens the wrong file, an integration whose observed rows are missing must not read as
 * nought calls, and a vendor's operation list is a distinct-count nothing else on screen repeats.
 */

import { useMemo } from "react"
import { Link } from "react-router"

import { useBindingSurface } from "@/api/queries"
import type {
  RepositoryGraphBinding,
  RepositoryGraphObservedBinding,
  RepositoryGraphResponse,
} from "@/api/types"
import { InfoHint } from "@/components/info-hint"
import { RelativeTime } from "@/components/relative-time"
import { ErrorState, LoadingState } from "@/components/states"
import { Absent } from "@/components/status"
import { ChangeKindTag, CountTag, SeverityTag, Tag } from "@/components/tag"
import { Button } from "@/components/ui/button"
import { CallSiteDetail } from "@/features/bindings/call-site-drawer"
import type { ForceNode } from "@/features/index-graph/force-map"
import { OffPathNote } from "@/features/index-graph/off-path-note"
import { vendorName } from "@/features/vendors/vendor-name"
import { formatTimestamp } from "@/lib/format"
import { seriesScale } from "@/lib/palette"

/** Every drawn call site in one file, addressed by the recorded path and never by a basename. */
export function callSitesInFile(
  graph: RepositoryGraphResponse,
  path: string,
): RepositoryGraphBinding[] {
  return graph.bindings.filter((row) => row.path === path)
}

/** The distinct operations this integration is called at, in the drawn subset. */
export function operationsOfVendor(graph: RepositoryGraphResponse, vendorId: string): string[] {
  const seen = new Set<string>()
  for (const row of graph.bindings) {
    if (row.vendor_id === vendorId) seen.add(row.operation_id)
  }
  return [...seen].sort()
}

/** The observed edges correlated to an integration, or to one of its operations. */
export function observedFor(
  graph: RepositoryGraphResponse,
  vendorId: string,
  operationId?: string,
): RepositoryGraphObservedBinding[] {
  return graph.observed_bindings.filter(
    (row) =>
      row.vendor_id === vendorId &&
      (operationId === undefined || row.operation_id === operationId),
  )
}

function Section({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="flex min-w-0 flex-col gap-row">
      <div className="flex items-center gap-row">
        <h3 className="furniture text-meta text-ink-muted">{label}</h3>
        {hint !== undefined && <InfoHint label={`About ${label.toLowerCase()}`}>{hint}</InfoHint>}
      </div>
      {children}
    </section>
  )
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-field">
      <span className="furniture text-meta text-ink-muted">{label}</span>
      <span className="min-w-0 break-words font-mono text-body text-ink">{value}</span>
    </div>
  )
}

/** What the marks mean. The canvas has never carried this anywhere, and it is not derivable. */
function MapLegend({
  graph,
  nodeCount,
  offPathTotal,
}: {
  graph: RepositoryGraphResponse
  nodeCount: number
  offPathTotal: number
}) {
  const vendorIds = useMemo(
    () => [...new Set(graph.bindings.map((row) => row.vendor_id))].sort(),
    [graph.bindings],
  )
  const ink = useMemo(() => seriesScale(vendorIds), [vendorIds])

  return (
    <div className="flex min-w-0 flex-col gap-section">
      <div className="flex flex-col gap-field">
        <h3 className="text-emphasis font-medium text-ink">Nothing selected</h3>
        <p className="text-body text-ink-muted">
          No mark is selected. This panel describes one file, one operation or one integration —
          pick a mark on the map. This is the panel having nothing to show, not the map having
          nothing in it: {nodeCount.toLocaleString()} {nodeCount === 1 ? "node is" : "nodes are"}{" "}
          drawn.
        </p>
      </div>

      <Section label="What the marks mean">
        <ul className="flex flex-col gap-row text-meta text-ink-muted">
          <li className="flex items-center gap-row">
            <svg aria-hidden="true" viewBox="0 0 16 16" className="size-4 shrink-0">
              <circle cx={8} cy={8} r={5} className="fill-line-strong" />
            </svg>
            <span>
              <span className="text-ink">disc</span> — a file that calls out
            </span>
          </li>
          <li className="flex items-center gap-row">
            <svg aria-hidden="true" viewBox="0 0 16 16" className="size-4 shrink-0">
              <circle cx={8} cy={8} r={5} fill="none" strokeWidth={2} className="stroke-line-strong" />
            </svg>
            <span>
              <span className="text-ink">ring</span> — an operation the file reaches
            </span>
          </li>
          <li className="flex items-center gap-row">
            <svg aria-hidden="true" viewBox="0 0 16 16" className="size-4 shrink-0">
              <rect x={3} y={3} width={10} height={10} rx={2} className="fill-line-strong" />
            </svg>
            <span>
              <span className="text-ink">square</span> — the integration behind it
            </span>
          </li>
        </ul>
        <p className="text-meta text-ink-muted">
          Radius is the call sites counted at that mark. Colour carries integration identity and
          nothing else — never a rung, a severity or a health.
        </p>
      </Section>

      {vendorIds.length > 0 && (
        <Section label="Integrations drawn">
          <ul className="flex flex-wrap gap-field">
            {vendorIds.map((id) => (
              <li key={id} className="flex items-center gap-field text-meta text-ink">
                <span
                  aria-hidden="true"
                  className="size-3 shrink-0 rounded-control"
                  style={{ backgroundColor: ink(id) }}
                />
                {vendorName(id)}
              </li>
            ))}
          </ul>
        </Section>
      )}

      <OffPathNote graph={graph} total={offPathTotal} />
    </div>
  )
}

function FileDetail({
  repoId,
  graph,
  node,
}: {
  repoId: string
  graph: RepositoryGraphResponse
  node: ForceNode
}) {
  const path = node.path ?? node.label
  const sites = callSitesInFile(graph, path)

  return (
    <div className="flex min-w-0 flex-col gap-section">
      <div className="flex flex-col gap-field">
        <Tag>file</Tag>
        <code className="min-w-0 break-all font-mono text-body text-ink select-all">{path}</code>
      </div>

      {sites.length === 0 ? (
        <p className="text-body text-ink-muted">
          <Absent>this file&rsquo;s call sites are not in the drawn subset</Absent> — the map holds
          a mark for it, and the drawn bindings hold no row at this path. The picture is capped, so
          the two reads disagree about which rows they cover.
        </p>
      ) : (
        <Section
          label={`Call sites in this file (${sites.length})`}
          hint="Every drawn call site whose recorded path is exactly this one. The map labels a file by its basename, which two files can share; this list is matched on the full path."
        >
          <ul className="flex flex-col gap-row">
            {sites.map((row) => (
              <li
                key={`${row.path}:${row.line}:${row.operation_id}`}
                className="flex min-w-0 flex-col gap-field rounded-surface border border-line bg-surface-subtle p-row"
              >
                <span className="font-mono text-meta text-ink">
                  {row.symbol}
                  <span className="text-ink-muted"> · line {row.line}</span>
                </span>
                <span className="min-w-0 truncate text-meta text-ink-muted">
                  {vendorName(row.vendor_id)} → {row.operation_id}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Button asChild variant="outline" size="sm">
        <Link
          to={`/repositories/${encodeURIComponent(repoId)}/call-sites?call_sites_path=${encodeURIComponent(path)}`}
        >
          Open this file in call sites
        </Link>
      </Button>
    </div>
  )
}

function OperationDetail({
  repoId,
  graph,
  node,
}: {
  repoId: string
  graph: RepositoryGraphResponse
  node: ForceNode
}) {
  const vendorId = node.vendorId ?? ""
  const operationId = node.operationId ?? node.label
  const query = useBindingSurface(vendorId, operationId, { repoId })
  const what = `the call sites for ${vendorName(vendorId)} ${operationId}`
  const observed = observedFor(graph, vendorId, operationId)
  const sites = query.data?.call_sites
  const first = sites?.items[0]

  return (
    <div className="flex min-w-0 flex-col gap-section">
      <div className="flex flex-col gap-field">
        <Tag>operation</Tag>
        <code className="min-w-0 break-all font-mono text-body text-ink">{operationId}</code>
        <span className="text-meta text-ink-muted">{vendorName(vendorId)}</span>
      </div>

      {query.isPending && <LoadingState what={what} />}
      {query.isError && (
        <ErrorState error={query.error} what={what} onRetry={() => void query.refetch()} />
      )}

      {query.data !== undefined && (
        <>
          {query.data.changes.total === 0 ? (
            <p className="text-meta text-ink-muted">
              No vendor change is recorded against this operation.
            </p>
          ) : (
            <Section
              label="Recorded vendor changes"
              hint="What the vendor published against this operation, with the kind and severity they recorded. Neither value is a judgement of ours about the node."
            >
              <ul className="flex flex-col gap-row">
                {query.data.changes.items.map((change) => (
                  <li key={change.change_id} className="flex min-w-0 flex-col gap-field">
                    <span className="flex flex-wrap items-center gap-field">
                      <ChangeKindTag kind={change.kind} />
                      <SeverityTag severity={change.severity} />
                    </span>
                    <span className="text-meta text-ink-muted">
                      {change.from_version ?? "an unrecorded version"} →{" "}
                      {change.to_version ?? "an unrecorded version"} ·{" "}
                      <RelativeTime iso={change.detected_at} />
                    </span>
                  </li>
                ))}
              </ul>
              {query.data.changes.items.length < query.data.changes.total && (
                <p className="text-meta text-ink-muted">
                  Showing {query.data.changes.items.length} of {query.data.changes.total} recorded
                  changes.
                </p>
              )}
            </Section>
          )}

          {sites !== undefined && sites.total === 0 && (
            <p className="text-body text-ink-muted">
              The binding surface holds no call site for this operation in{" "}
              <span className="font-mono">{repoId}</span>. The map drew this node from the graph
              read, so the two reads disagree — most likely the index moved between them.
            </p>
          )}

          {sites !== undefined && first !== undefined && (
            <>
              {sites.items.length < sites.total && (
                <p className="text-meta text-ink-muted">
                  Showing {sites.items.length} of {sites.total} call sites.
                </p>
              )}
              <CallSiteDetail
                site={{
                  id: `${first.path}:${first.line}`,
                  path: first.path,
                  line: first.line,
                  col: first.col,
                  vendor_id: vendorId,
                  operation_id: operationId,
                  symbol: first.symbol ?? "",
                  args_keys: first.args_keys,
                  response_fields_read: first.response_fields_read,
                  sdk_version: first.sdk_version,
                  loop_depth: first.loop_depth,
                  indexed_at: first.indexed_at,
                  snippet: first.snippet,
                  snippet_start_line: first.snippet_start_line,
                }}
                sourceServed={query.data.source_served}
              />
              <Fact label="Indexed" value={<RelativeTime iso={first.indexed_at} />} />
            </>
          )}
        </>
      )}

      <Section
        label="Observed traffic"
        hint="Calls telemetry correlated to this operation. The graph payload carries no attachment timestamp, so an integration with no row here is uncorrelated rather than measured at nought."
      >
        {observed.length === 0 ? (
          <p className="text-meta text-ink-muted">
            <Absent>no observed call has been correlated to this operation</Absent>
          </p>
        ) : (
          <ul className="flex flex-col gap-field">
            {observed.map((row) => (
              <li key={row.binding_rung} className="flex items-center gap-field text-meta">
                <Tag>{row.binding_rung}</Tag>
                <CountTag count={row.calls} unit={row.calls === 1 ? "call" : "calls"} />
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Button asChild variant="outline" size="sm">
        <Link
          to={`/repositories/${encodeURIComponent(repoId)}/bindings/vendors/${encodeURIComponent(vendorId)}/operations/${encodeURIComponent(operationId)}`}
        >
          Open the binding surface
        </Link>
      </Button>
      <p className="text-meta text-ink-muted">
        Remediation is queued against a finding, never against a node on this map.
      </p>
    </div>
  )
}

function VendorDetail({
  repoId,
  graph,
  node,
}: {
  repoId: string
  graph: RepositoryGraphResponse
  node: ForceNode
}) {
  const vendorId = node.vendorId ?? node.label
  const rollUp = graph.vendors.find((row) => row.vendor_id === vendorId) ?? null
  const operations = operationsOfVendor(graph, vendorId)
  const observed = observedFor(graph, vendorId)

  return (
    <div className="flex min-w-0 flex-col gap-section">
      <div className="flex flex-col gap-field">
        <Tag>integration</Tag>
        <span className="text-emphasis font-medium text-ink">{vendorName(vendorId)}</span>
        <code className="font-mono text-meta text-ink-muted">{vendorId}</code>
      </div>

      {rollUp === null ? (
        <p className="text-body text-ink-muted">
          The per-integration roll-up carries no row for {vendorName(vendorId)}; the counts below
          are over the call sites drawn.
        </p>
      ) : (
        <div className="grid gap-section sm:grid-cols-2">
          <Fact label="Indexed call sites" value={rollUp.indexed_call_sites.toLocaleString()} />
          <Fact
            label="Last indexed"
            value={
              rollUp.last_indexed === null ? (
                <Absent>never recorded</Absent>
              ) : (
                (formatTimestamp(rollUp.last_indexed) ?? <Absent>never recorded</Absent>)
              )
            }
          />
        </div>
      )}

      <Section
        label={`Operations reached (${operations.length})`}
        hint="Distinct operations this integration is called at, over the call sites this map drew. A capped picture holds fewer than the graph does."
      >
        <ul className="flex flex-wrap gap-field">
          {operations.map((id) => (
            <li key={id} className="rounded-control border border-line px-field py-field font-mono text-meta">
              {id}
            </li>
          ))}
        </ul>
      </Section>

      <Section
        label="Observed traffic"
        hint="Calls telemetry correlated to this integration, by the rung the edge was established at. The graph payload holds no attachment timestamp, so this screen cannot tell an unattached repository from a measured nought and does not claim either."
      >
        {observed.length === 0 ? (
          <>
            <p className="text-meta text-ink-muted">
              <Absent>no observed call has been correlated to this integration</Absent>
            </p>
            <OffPathNote graph={graph} total={graph.off_path.unresolved + graph.off_path.unattributed} />
          </>
        ) : (
          <ul className="flex flex-col gap-field">
            {observed.map((row) => (
              <li key={`${row.operation_id}:${row.binding_rung}`} className="flex min-w-0 items-center gap-field text-meta">
                <span className="min-w-0 truncate font-mono text-ink">{row.operation_id}</span>
                <Tag>{row.binding_rung}</Tag>
                <CountTag count={row.calls} unit={row.calls === 1 ? "call" : "calls"} />
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Button asChild variant="outline" size="sm">
        <Link to={`/repositories/${encodeURIComponent(repoId)}/vendors/${encodeURIComponent(vendorId)}`}>
          Open the integration
        </Link>
      </Button>
    </div>
  )
}

export function GraphInspector({
  repoId,
  graph,
  node,
  nodeCount,
  offPathTotal,
}: {
  repoId: string
  graph: RepositoryGraphResponse
  /** The selected mark, or `null` when nothing is. */
  node: ForceNode | null
  /** How many marks the map settled, so the empty panel can say which nothing it is. */
  nodeCount: number
  offPathTotal: number
}) {
  if (node === null) {
    return <MapLegend graph={graph} nodeCount={nodeCount} offPathTotal={offPathTotal} />
  }
  if (node.kind === "file") return <FileDetail repoId={repoId} graph={graph} node={node} />
  if (node.kind === "operation") return <OperationDetail repoId={repoId} graph={graph} node={node} />
  return <VendorDetail repoId={repoId} graph={graph} node={node} />
}

/** The heading the pane wears for the selected mark. */
export function inspectorTitle(node: ForceNode | null): string {
  if (node === null) return "Inspector"
  if (node.kind === "file") return node.path ?? node.label
  if (node.kind === "operation") return node.operationId ?? node.label
  return vendorName(node.vendorId ?? node.label)
}
