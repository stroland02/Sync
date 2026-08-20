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
 *
 * **It is drawn on the vendored `Card`, at the same depth and radius as every attached
 * integration's card, and that placement is the argument.** A role with nothing attached rendered as
 * loose prose beneath three carded roles reads as an afterthought — something the screen ran out of
 * room for. Rendered as a card in the catalogue, it reads as what it is: an answer, sitting where
 * an answer goes. `docs/superpowers/briefs/2026-08-07-substrate-signals.md` ruling 7.
 */

import { Card, CardContent, CardHeader } from "@/vendor/supabase/ui/card"

export function NotAttachedState({
  detail,
  command,
}: {
  detail: string
  /**
   * The invocation that attaches a source of this role, where one exists.
   *
   * **Owner direction, 2026-08-19: nothing on screen that just sits there.** This card explained
   * an absence and stopped, which left a reader knowing a role was empty and not how to fill it.
   * The console cannot run the command itself -- no route mutates the graph or triggers a run --
   * so what it honestly offers is the exact invocation rather than a button that would have to
   * pretend it did something.
   */
  command?: string
}) {
  return (
    <Card className="max-w-prose">
      <CardHeader>
        <p className="text-emphasis text-foreground">No integration of this role is attached.</p>
      </CardHeader>
      <CardContent className="flex flex-col gap-row">
        <p className="text-body text-muted-foreground">{detail}</p>
        {command !== undefined && (
          <div className="flex flex-col gap-field">
            <span className="furniture text-meta text-ink-muted">Attach one</span>
            <code className="block overflow-x-auto rounded-control border border-line bg-surface-subtle px-field py-field font-mono text-meta text-ink select-all">
              {command}
            </code>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
