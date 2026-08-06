/**
 * The fifth kind of nothing: a role with no integration attached at all.
 *
 * `components/states.tsx` already draws four — "no findings", "that finding is not open", "the
 * API is not running" and "still asking" — and each of those is an answer *to a query*: a
 * request went out and came back empty, forbidden, or unresolved. This state is not that. It
 * renders before any query runs, because there is no table, no adapter and no configuration
 * row to ask about this role for this repository — the graph has never been given anything to
 * report on this axis, and could not answer "quiet" or "noisy" if asked.
 *
 * That distinction is the reason this is its own component rather than `EmptyState` with a
 * different sentence. `EmptyState` documents its own headline as "the API answered, and the
 * answer was nothing — a true answer, not a failure." Reusing it here would put a role with no
 * integration on the same axis as a role that was checked and found idle, which is exactly the
 * conflation the M5 role split exists to keep apart: *attached and quiet* is a fact about
 * traffic, *nothing is attached* is a fact about configuration, and this console does not let
 * one stand in for the other.
 */

export function NotAttachedState({ detail }: { detail: string }) {
  return (
    <div className="max-w-prose rounded border border-border p-section text-muted-foreground">
      <p className="text-emphasis text-foreground">No integration of this role is attached.</p>
      <p className="mt-field text-body">{detail}</p>
    </div>
  )
}
