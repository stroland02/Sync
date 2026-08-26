/**
 * The operations this page's changes name, ranked by how heavily this codebase calls them.
 *
 * The feed answers *did anything change*; this answers *where the changes are landing*. One entry
 * per integration and operation, heaviest binding first, so the concentration is visible without
 * reading fifty rows — and the tail of the ranking is the half nothing here calls, which is a real
 * answer rather than noise to filter away.
 *
 * **Scoped to the page, and the pane says so.** The feed is paged, so this is a ranking over the
 * changes in hand — never over the record, which the screen never held.
 */

import { ListTree } from "lucide-react"
import { Link } from "react-router"

import { InfoHint } from "@/components/info-hint"
import { PanelPane } from "@/components/pane"
import type { NamedOperation } from "@/features/vendors/change-binding"
import { BindingMark } from "@/features/vendors/changes-feed"
import { bindingSurfaceHref } from "@/lib/hrefs"

export function ChangesOperationsPane({
  repoId,
  operations,
  changesOnPage,
  className,
}: {
  repoId: string
  operations: readonly NamedOperation[]
  changesOnPage: number
  className?: string
}) {
  return (
    <PanelPane
      className={className}
      icon={ListTree}
      label="Operations named"
      hint={
        <InfoHint label="About the operations ranking">
          One entry per integration and operation named by the changes on this page, ordered by the
          call sites this codebase holds for it. The call-site figure is static evidence from the
          last index pass — places the code calls the operation, not calls observed. An entry with
          no figure carries the reason instead, because a census that was never taken and one that
          answered nothing are different facts.
        </InfoHint>
      }
      footer={
        <span className="min-w-0 truncate">
          {operations.length.toLocaleString()} operation
          {operations.length === 1 ? "" : "s"} across the {changesOnPage.toLocaleString()} change
          {changesOnPage === 1 ? "" : "s"} on this page
        </span>
      }
    >
      <ul className="flex min-w-0 flex-col">
        {operations.map((row) => (
          <li
            key={`${row.vendorId} ${row.operationId}`}
            className="flex min-w-0 flex-col gap-field border-b border-line px-row py-row last:border-b-0"
          >
            <Link
              to={bindingSurfaceHref(repoId, row.vendorId, row.operationId)}
              className="min-w-0 break-all font-mono text-meta text-ink underline underline-offset-2"
            >
              {row.vendorId} / {row.operationId}
            </Link>
            <div className="flex min-w-0 flex-wrap items-center gap-row text-meta text-ink-muted">
              <BindingMark binding={row.binding} />
              <span className="shrink-0">
                {row.changes.toLocaleString()} change{row.changes === 1 ? "" : "s"} here
              </span>
            </div>
          </li>
        ))}
      </ul>
    </PanelPane>
  )
}
