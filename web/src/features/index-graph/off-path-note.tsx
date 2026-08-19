/**
 * What the graph holds that the canvas cannot draw as an edge.
 *
 * **Off-path is a place on this screen, not an omission.** An uncorrelated span named no
 * operation, so there is no node to draw a line to; folding it into `observed` would claim a
 * correlation nothing made, and leaving it out would understate what reached the vendor. A
 * finding carrying `unattributed` holds a value no binder emits and which `BindingRung`
 * deliberately excludes, so it cannot be drawn as a rung either.
 *
 * Rendered in every state including the empty ones, because a repository whose call sites were
 * all retracted still holds both, and "nothing here" would drop them.
 *
 * Nought is printed rather than hidden. The tables were read and held none, which is a
 * measurement, and a panel that vanishes at nought makes a reader guess whether it was checked.
 */

import type { RepositoryGraphResponse } from "@/api/types"
import { Tag } from "@/components/tag"

export function OffPathNote({
  graph,
  total,
}: {
  graph: RepositoryGraphResponse
  total: number
}) {
  return (
    <p className="text-meta text-ink-muted leading-relaxed">
      <Tag>off path</Tag>{" "}
      {total === 0 ? (
        <>
          Nothing is off the path here: no uncorrelated span and no unattributed finding. Both
          tables were read, so this is nought rather than unchecked.
        </>
      ) : (
        <>
          <span className="font-mono">{graph.off_path.unresolved}</span> uncorrelated{" "}
          {graph.off_path.unresolved === 1 ? "span" : "spans"} and{" "}
          <span className="font-mono">{graph.off_path.unattributed}</span> unattributed{" "}
          {graph.off_path.unattributed === 1 ? "finding" : "findings"} are held by the graph and
          drawn by no edge above. An uncorrelated span named no operation, so there is no node to
          reach; an unattributed finding predates the column that would have recorded its rung.
          Neither is folded into a rung and neither is dropped.
        </>
      )}
    </p>
  )
}
