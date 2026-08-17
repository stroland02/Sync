/**
 * What the vendor changed, whether or not this codebase is affected.
 *
 * The same graph level as the findings table and a second view of it, rather than a fourth
 * navigation level the hierarchy does not have.
 *
 * This route's envelope carries a null `indexed_at` and a null `binding_source`, and both
 * are correct rather than missing: the answer is built from vendor changes alone and holds
 * no binding, so naming a rung would claim a mapping that does not appear in the payload.
 *
 * The operation column links into the Binding surface level — reached from the operation a
 * user is already looking at, rather than from a lookup form on a hub page that no longer
 * exists. `repoId`, when the caller has one, rides along in the query string so the surface
 * that opens is scoped to it; `binding_surface` already accepts that parameter.
 *
 * **This panel has no headline figure, and that is the ruling M7-W174 exists to make.**
 * `src/sync/graph/schema.sql` declares `vendor_change` as the one source in the pipeline that
 * does not converge: the rows are at-least-once, and a count of them is not a measurement. A
 * figure at the panel's largest register would have been the console asserting one anyway. The
 * range under the table stays, because it is how a reader knows which rows they are looking at,
 * and the caption is what stops it being read as a total.
 *
 * `docs/superpowers/briefs/2026-08-07-substrate-api-services.md` carries the mapping this port was
 * gated on, and it is what to read before porting a level, not this docstring.
 */

import { Link } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { useVendorChanges } from "@/api/queries"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { MetricPanel } from "@/components/metric-panel"
import { ProvenanceStrip } from "@/components/provenance"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Formatted } from "@/components/status"
import { FooterBar } from "@/layouts/footer-bar"
import { formatTimestamp, orAbsent } from "@/lib/format"
import { useOffsetParam } from "@/lib/use-offset-param"

function bindingSurfaceHref(vendorId: string, operation: string, repoId: string | null): string {
  const path = `/bindings/vendors/${encodeURIComponent(vendorId)}/operations/${encodeURIComponent(operation)}`
  return repoId === null ? path : `${path}?repo_id=${encodeURIComponent(repoId)}`
}

export function VendorChangesCard({
  vendorId,
  repoId = null,
}: {
  vendorId: string
  repoId?: string | null
}) {
  const [offset, setOffset] = useOffsetParam("changes_offset")
  const query = useVendorChanges(vendorId, { limit: DEFAULT_LIMIT, offset })

  if (query.isPending) return <LoadingState what={`vendor changes for ${vendorId}`} />
  if (query.isError) {
    return <ErrorState error={query.error} what={`vendor changes for ${vendorId}`} onRetry={() => void query.refetch()} />
  }

  const page = query.data

  return (
    <MetricPanel
      label="Vendor changes"
      caption={
        <>
          <p className="max-w-prose">
            What {vendorId} published, whether or not this codebase is affected. Every change
            the feed has recorded, and{" "}
            {repoId === null ? "not narrowed to any repository" : (
              <>
                <span className="font-mono">not</span> narrowed to{" "}
                <span className="font-mono">{repoId}</span>
              </>
            )}
            : a vendor publishes a change once, to everyone, so this list is the same whichever
            repository you reached it from. To see what it hits here, open an operation's
            binding surface from the table above.
          </p>
          <p className="max-w-prose">
            There is no count above this sentence on purpose. These rows are recorded at least
            once rather than exactly once — comparing the same two published specifications twice
            can return a different set — so a count of them is not a measurement. The range under
            the table says which rows this page holds, which is a fact about the page and not
            about the vendor.
          </p>
        </>
      }
    >
      {page.items.length === 0 ? (
        <EmptyState
          headline={`Nothing recorded for ${vendorId}.`}
          detail="The API answered with an empty page. Either no feed has been ingested for this vendor, or it has published nothing Sync tracks."
        />
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Published</TableHead>
                <TableHead>Kind</TableHead>
                <TableHead>Severity</TableHead>
                <TableHead>Operation</TableHead>
                <TableHead>Path</TableHead>
                <TableHead>Versions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {page.items.map((change, index) => (
                <TableRow
                  key={`${change.published_at}-${change.operation ?? ""}-${change.change_kind}-${index}`}
                >
                  <TableCell className="text-meta">
                    <time dateTime={change.published_at}>
                      <Formatted value={formatTimestamp(change.published_at)} />
                    </time>
                  </TableCell>
                  <TableCell>
                    <Formatted value={orAbsent(change.change_kind)} />
                  </TableCell>
                  <TableCell>
                    <Formatted value={orAbsent(change.severity)} />
                  </TableCell>
                  <TableCell className="font-mono">
                    {change.operation ? (
                      <Link
                        to={bindingSurfaceHref(vendorId, change.operation, repoId)}
                        className="underline underline-offset-2"
                      >
                        {change.operation}
                      </Link>
                    ) : (
                      <Formatted value={orAbsent(change.operation)} />
                    )}
                  </TableCell>
                  <TableCell className="font-mono">
                    <Formatted value={orAbsent(change.path_ptr)} />
                  </TableCell>
                  <TableCell className="font-mono">
                    <Formatted value={orAbsent(change.from_version)} /> →{" "}
                    <Formatted value={orAbsent(change.to_version)} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <FooterBar
            offset={offset}
            limit={DEFAULT_LIMIT}
            shown={page.items.length}
            total={page.total}
            nextOffset={page.next_offset}
            busy={query.isFetching}
            onOffsetChange={setOffset}
          />
        </>
      )}
      <ProvenanceStrip
        provenance={page}
        bindingNullLabel="none: this answer is built from vendor changes and holds no binding"
        indexedNullLabel="not applicable: nothing here was read out of the codebase"
      />
    </MetricPanel>
  )
}
