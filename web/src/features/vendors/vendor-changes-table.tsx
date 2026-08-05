/**
 * What the vendor changed, whether or not this codebase is affected.
 *
 * The same graph level as the findings table and a second view of it, rather than a fourth
 * navigation level the hierarchy does not have.
 *
 * This route's envelope carries a null `indexed_at` and a null `binding_source`, and both
 * are correct rather than missing: the answer is built from vendor changes alone and holds
 * no binding, so naming a rung would claim a mapping that does not appear in the payload.
 */

import { DEFAULT_LIMIT } from "@/api/client"
import { useVendorChanges } from "@/api/queries"
import { PageControls } from "@/components/page-controls"
import { ProvenanceStrip } from "@/components/provenance"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Formatted } from "@/components/status"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { ABSENT, formatTimestamp, orAbsent } from "@/lib/format"
import { useOffsetParam } from "@/lib/use-offset-param"

export function VendorChangesTable({ vendorId }: { vendorId: string }) {
  const [offset, setOffset] = useOffsetParam("changes_offset")
  const query = useVendorChanges(vendorId, { limit: DEFAULT_LIMIT, offset })

  if (query.isPending) return <LoadingState what={`vendor changes for ${vendorId}`} />
  if (query.isError) {
    return <ErrorState error={query.error} what={`vendor changes for ${vendorId}`} />
  }

  const page = query.data

  return (
    <div className="flex flex-col gap-4">
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
                  key={`${change.published_at}-${change.operation ?? ABSENT}-${change.change_kind}-${index}`}
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
                    <Formatted value={orAbsent(change.operation)} />
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
          <PageControls
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
    </div>
  )
}
