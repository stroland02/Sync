/**
 * The published-change feed: one dense row per change, newest first.
 *
 * Seven columns, and each is a fact a reader needs *per row* rather than on opening one. Detected
 * is the ordering key. Severity is the vendor's own as published. Integration and operation are
 * the subject. Kind is what changed, which severity does not say. **Binds here is the join this
 * screen exists for** — a breaking change against an operation nothing in this codebase calls is a
 * different object from one against an operation with forty call sites, and the two are
 * indistinguishable without it. Source is what separates a converged count from an at-least-once
 * one, so it cannot move behind a disclosure.
 *
 * The version pair moved to the drawer: it identifies the comparison, and a reader scanning the
 * feed is not choosing between releases.
 */

import { Link } from "react-router"

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { RelativeTime } from "@/components/relative-time"
import { Absent } from "@/components/status"
import { ChangeKindTag, SeverityTag, Tag } from "@/components/tag"
import type { ChangeBinding } from "@/features/vendors/change-binding"
import { bindingSurfaceHref } from "@/lib/hrefs"

export interface ChangeRow {
  id: string
  vendor_id: string
  from_version: string
  to_version: string
  kind: string
  operation_id: string
  path_ptr: string
  severity: string
  source: string
  detected_at: string
}

/**
 * The binding answer as a mark, in the fewest honest words.
 *
 * Four values, three of which are absences that mean different things — and the difference is
 * carried by the words, never by a colour. The argument for each sits in the `title`; the claim is
 * on screen for a reader who never hovers.
 */
export function BindingMark({ binding }: { binding: ChangeBinding }) {
  if (binding.kind === "bound") {
    return (
      <Tag
        title={`${binding.callSites.toLocaleString()} current call site${binding.callSites === 1 ? "" : "s"} in this repository name this operation. Static evidence from the last index pass.`}
      >
        {binding.callSites.toLocaleString()} here
      </Tag>
    )
  }
  if (binding.kind === "not-bound") {
    return (
      <span title="The call-site census answered and holds no current site naming this operation. A measured zero, not an unasked question.">
        <Absent>nothing here calls it</Absent>
      </span>
    )
  }
  if (binding.kind === "never-indexed") {
    return (
      <span title="No index pass has ever run over this repository, so no call site was looked for. This is not a zero.">
        <Absent>never indexed</Absent>
      </span>
    )
  }
  return (
    <span title={binding.why}>
      <Absent>not counted</Absent>
    </span>
  )
}

export function ChangesFeed({
  repoId,
  rows,
  bindingOfRow,
  selectedId,
  onSelect,
}: {
  repoId: string
  rows: readonly ChangeRow[]
  bindingOfRow: (row: ChangeRow) => ChangeBinding
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  return (
    <Table>
      <TableHeader sticky>
        <TableRow>
          <TableHead>Detected</TableHead>
          <TableHead>Severity</TableHead>
          <TableHead>Integration</TableHead>
          <TableHead>Operation</TableHead>
          <TableHead>Kind</TableHead>
          <TableHead>Binds here</TableHead>
          <TableHead>Source</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((change) => (
          <TableRow
            key={change.id}
            onClick={() => onSelect(change.id)}
            data-state={change.id === selectedId ? "selected" : undefined}
            className="cursor-pointer"
          >
            <TableCell className="whitespace-nowrap font-mono text-meta text-ink-muted">
              <RelativeTime iso={change.detected_at} />
            </TableCell>
            <TableCell>
              <SeverityTag severity={change.severity} />
            </TableCell>
            <TableCell className="font-mono text-meta">{change.vendor_id}</TableCell>
            <TableCell className="font-mono text-meta">
              <Link
                to={bindingSurfaceHref(repoId, change.vendor_id, change.operation_id)}
                onClick={(event) => event.stopPropagation()}
                className="break-all underline underline-offset-2"
              >
                {change.operation_id}
              </Link>
            </TableCell>
            <TableCell>
              <ChangeKindTag kind={change.kind} />
            </TableCell>
            <TableCell className="text-meta">
              <BindingMark binding={bindingOfRow(change)} />
            </TableCell>
            <TableCell className="whitespace-nowrap font-mono text-meta text-ink-muted">
              {change.source}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
